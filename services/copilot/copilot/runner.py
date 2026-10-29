"""Use-case runner: one turn from message to a terminal state.

The model decides which allowed tool to call next; this code decides whether a call is allowed and when the turn must
end. Every turn ends in exactly one of:
  answer    grounded in tool results, with a source for each fact
  ask_user  one specific question (a missing slot, or a low-confidence route)
  cannot_do what was found and what is missing (step limit, repeated call, no access, ungrounded, declined)
  confirm   an act use case with a draft to act on: the values to check, and the id to confirm them under. The act
            itself runs in actions.py, after the user presses the button; no model is involved in it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from .config import CopilotConfig, UseCase
from .identity import Principal
from .recording import sampling_settings
from .router import Route, route
from .store import Session, Store
from .tools import ToolBlocked, ToolCaller, ToolDeps, build_tools

Terminal = Literal["answer", "ask_user", "cannot_do", "confirm"]
_TERMINAL = {"use_case": "answer", "ask": "ask_user", "clarify": "ask_user"}


class RunnerAnswer(BaseModel):
    text: str = Field(description="The reply, using only the tool results")
    rows: list[dict[str, str]] = Field(default_factory=list, description="Table rows when the output is a table")
    sources: list[str] = Field(default_factory=list, description="Names of the tools whose results support the reply")


@dataclass
class TurnResult:
    session_id: str
    turn_id: str
    terminal: Terminal
    text: str
    use_case: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)  # {tool, fetched_at}
    action: dict | None = None  # {id, use_case, fields, expires_at} for a "confirm" terminal
    format: str = "text"  # how to show the text: text, table or draft
    follow_ups: list[str] = field(default_factory=list)  # offered under an answer that found something


def _instructions(cfg: CopilotConfig, uc: UseCase, slots: dict) -> str:
    text = cfg.prompts[uc.prompt].strip()
    if uc.output.format == "table":
        text += f"\n\nPut the findings in rows with exactly these columns: {', '.join(uc.output.columns)}. Keep the text to one short sentence."
    # Slots the open screen supplies (the case) are filled into the tool calls; the model does not need them, and a
    # prompt that names them could never be replayed on another case.
    stated = {k: v for k, v in slots.items() if k not in uc.context_slots}
    if stated:
        text += "\n\nResolved: " + ", ".join(f"{k}={v}" for k, v in sorted(stated.items()))
    return text


def _cannot(cfg: CopilotConfig, found: list[str], reason: str) -> str:
    return cfg.runtime.messages.cannot_do.format(found=", ".join(found) or "nothing", missing=getattr(cfg.runtime.messages.reasons, reason))


def _ungrounded_cells(rows: list[dict], columns: list[str], evidence: str) -> bool:
    for r in rows:
        if set(r) - set(columns):
            return True
        for v in r.values():
            v = _plain(v)
            if v and v not in ("-", "none", "n/a") and v not in evidence:
                return True
    return False


async def handle_turn(
    cfg: CopilotConfig, *, router_model: Model, runner_model: Model, caller: ToolCaller, store: Store,
    principal: Principal, session: Session, message: str, now: Callable[[], str],
) -> TurnResult:
    turn_id = f"t_{uuid.uuid4().hex[:10]}"
    sid, uid = session.session_id, principal.user_id

    def trace(event: str, **detail) -> None:
        store.trace(at=now(), session_id=sid, turn_id=turn_id, user_id=uid, event=event, detail=detail)

    store.add_message(sid, now(), "user", message)
    r: Route = await route(cfg, router_model, principal, session, message)
    trace("route", kind=r.kind, use_case=r.use_case, confidence=r.confidence, slots=sorted(r.slots))

    res = TurnResult(sid, turn_id, _TERMINAL.get(r.kind, "cannot_do"), r.message, r.use_case)
    session.pending_slot = None
    if r.kind == "ask":
        session.active_use_case, session.resolved_slots, session.pending_slot = r.use_case, r.slots, r.pending_slot
    elif r.kind == "use_case":
        uc = cfg.use_case(r.use_case)
        session.active_use_case, session.resolved_slots = uc.id, r.slots
        if uc.kind == "act":
            _propose(cfg, uc, session, res, now, trace)
        else:
            await _run(cfg, uc, runner_model, caller, principal, session, message, res, trace)
            _offer(cfg, uc, session, res, now, trace)
    _finish(store, session, res, now, trace)
    return res


async def _run(cfg, uc, model, caller, principal, session, message, res, trace) -> None:
    g = cfg.runtime.guards
    deps = ToolDeps(principal, dict(session.resolved_slots), caller, max_steps=uc.max_steps, block_repeat=g.block_repeat_calls)
    agent = Agent(model, output_type=RunnerAnswer, instructions=_instructions(cfg, uc, session.resolved_slots),
                  tools=build_tools(cfg, uc.tools), deps_type=ToolDeps, model_settings=sampling_settings(cfg.llm))
    out, stop = None, None
    try:
        out = (await agent.run(message, deps=deps, usage_limits=UsageLimits(request_limit=uc.max_steps + 2))).output
    except ToolBlocked as e:
        stop = e.reason
    except UsageLimitExceeded:
        stop = "step_limit"
    for c in deps.calls:
        trace("tool_call", **c)
    ok = [c for c in deps.calls if c["ok"]]
    found = sorted({c["tool"] for c in ok})

    res.terminal = "cannot_do"
    if any(c["error"] == "FORBIDDEN" for c in deps.calls):
        res.text = cfg.runtime.messages.forbidden
    elif stop and ok:
        res.text = _cannot(cfg, found, stop)
    elif not ok:  # a retry after a failed lookup is blocked too, but the true reason is that nothing came back
        res.text = _cannot(cfg, found, "no_data")
    elif g.ground_table_cells and uc.output.format == "table" and _ungrounded_cells(out.rows, uc.output.columns, _evidence(deps)):
        res.text = _cannot(cfg, found, "ungrounded")
    elif uc.empty_message and all(not data for data in deps.results):
        # Nothing came back: say so in the configured words. A model asked to draft from nothing will invent.
        res.terminal, res.text = "answer", uc.empty_message
        res.sources = [{"tool": c["tool"], "fetched_at": c["at"]} for c in ok]
    else:
        res.terminal, res.text = "answer", out.text
        res.format = uc.output.format
        res.follow_ups = list(uc.follow_ups) if any(deps.results) else []
        res.columns = uc.output.columns if uc.output.format == "table" else []
        res.rows = out.rows if uc.output.format == "table" else []
        res.sources = [{"tool": c["tool"], "fetched_at": c["at"]} for c in ok]
        session.last_results = [{"tool": c["tool"], "ref": f"r_{i}", "fetched_at": c["at"]} for i, c in enumerate(ok, 1)]


def _later(at: str, seconds: int) -> str:
    return (datetime.fromisoformat(at) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def parse_draft(text: str, act) -> dict | None:
    """The subject and body of a draft written in the configured shape, or None when it does not have that shape."""
    lines = text.splitlines()
    at = next((i for i, ln in enumerate(lines) if ln.strip().startswith(act.subject_marker)), None)
    if at is None:
        return None
    subject = lines[at].strip()[len(act.subject_marker):].strip()
    body = "\n".join(lines[at + 1:]).strip()
    return {"subject": subject, "body": body} if subject and body else None


def _offer(cfg, uc, session, res: TurnResult, now, trace) -> None:
    """A finished draft that an act use case can send becomes the session's pending action, bound to this case."""
    act_uc = cfg.act_for(uc.id)
    if act_uc is None or res.terminal != "answer" or not res.sources:
        return
    parsed = parse_draft(res.text, act_uc.act)
    if parsed is None:
        return
    tool = cfg.tool(act_uc.act.tool)
    fields = {n: parsed.get(n, "") for n, p in tool.params.items() if not p.from_slot}
    session.pending_action = {
        "id": f"p_{uuid.uuid4().hex[:12]}", "use_case": act_uc.id, "fields": fields,
        "slots": dict(session.resolved_slots), "context": dict(session.context),
        "expires_at": _later(now(), cfg.runtime.session.pending_action_ttl_s),
    }
    trace("offer", use_case=act_uc.id, pending_id=session.pending_action["id"])


def _propose(cfg, uc, session, res: TurnResult, now, trace) -> None:
    """Show the confirmation card for the live draft, or say there is none. Nothing is called here."""
    p = session.pending_action
    if not p or p.get("use_case") != uc.id or p.get("expires_at", "") <= now() or p.get("context") != session.context:
        res.terminal, res.text = "cannot_do", uc.act.needs_draft
        return
    p["proposed"] = True  # the card has been shown; a reloaded panel shows it again until the action lapses
    res.terminal, res.text = "confirm", uc.act.confirm_text
    res.action = {"id": p["id"], "use_case": uc.id, "fields": p["fields"], "expires_at": p["expires_at"]}
    trace("propose", use_case=uc.id, pending_id=p["id"])


def _leaves(data) -> list[str]:
    if isinstance(data, dict):
        return [t for v in data.values() for t in _leaves(v)]
    if isinstance(data, list):
        return [t for v in data for t in _leaves(v)]
    return [] if data is None else [str(data)]


def _plain(text: str) -> str:
    return " ".join(text.lower().split())


def _evidence(deps: ToolDeps) -> str:
    """The tool results as the raw text of their values, not as JSON: a quote in a reason must match a quote in a cell."""
    return _plain("\n".join(t for data in deps.results for t in _leaves(data)))


def _finish(store, session, res: TurnResult, now, trace) -> None:
    store.add_message(session.session_id, now(), "assistant", res.text, res.terminal,
                      {"columns": res.columns, "rows": res.rows, "sources": res.sources, "format": res.format, "follow_ups": res.follow_ups,
                       **({"action": res.action} if res.action else {})}
                      if res.rows or res.sources or res.action or res.follow_ups else None)
    store.save(session, now())
    trace("terminal", terminal=res.terminal, use_case=res.use_case)
