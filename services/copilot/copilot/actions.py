"""Confirming or cancelling a pending action.

An act is never run by the model. A draft leaves a pending action on the session (runner._offer); the act use case
shows it as a confirmation card (runner._propose); the user presses a button, and the gateway calls here. The call is
made with the user's own token, only with the values the user confirmed, and only while the action is live, belongs to
the user's open case and the user still holds the use case's permissions. It runs once: the action is cleared on
success, and the host treats the action id as an idempotency key, so a repeated press records nothing twice.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .config import CopilotConfig
from .identity import Principal
from .store import Session, Store
from .tools import ToolCaller

MAX_FIELD_CHARS = 6000


class ActionRefused(Exception):
    """The action was not run and the card stays open: `status` is the HTTP status and `message` is for the user."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


@dataclass
class ActionResult:
    session_id: str
    terminal: str
    text: str
    sources: list[dict]
    done: bool = False  # the action ran; the panel shows it as completed


def _end(store: Store, session: Session, now: str, terminal: str, text: str, sources: list[dict] | None = None, done: bool = False) -> ActionResult:
    payload = {**({"sources": sources} if sources else {}), **({"done": True} if done else {})}
    store.add_message(session.session_id, now, "assistant", text, terminal, payload or None)
    store.save(session, now)
    return ActionResult(session.session_id, terminal, text, sources or [], done)


def _live(cfg: CopilotConfig, session: Session, pending_id: str, now: str, context: dict):
    p = session.pending_action
    if not p or p.get("id") != pending_id or p.get("expires_at", "") <= now or p.get("context") != context:
        return None
    return p


async def confirm(
    cfg: CopilotConfig, *, caller: ToolCaller, store: Store, principal: Principal, session: Session,
    pending_id: str, values: dict, context: dict, now: Callable[[], str],
) -> ActionResult:
    at = now()

    def trace(event: str, **detail) -> None:
        store.trace(at=at, session_id=session.session_id, turn_id=pending_id, user_id=principal.user_id, event=event, detail=detail)

    msgs = cfg.runtime.messages
    p = _live(cfg, session, pending_id, at, context)
    if p is None:
        session.pending_action = None
        trace("act", pending_id=pending_id, outcome="expired")
        return _end(store, session, at, "cannot_do", msgs.action_expired)
    uc = cfg.use_case(p["use_case"])
    if not principal.can(uc.permissions):
        trace("act", pending_id=pending_id, tool=uc.act.tool, outcome="forbidden")
        return _end(store, session, at, "cannot_do", msgs.forbidden)

    tool = cfg.tool(uc.act.tool)
    names = [n for n, prm in tool.params.items() if not prm.from_slot]
    if set(values) != set(names) or not all(isinstance(v, str) and len(v) <= MAX_FIELD_CHARS for v in values.values()):
        raise ActionRefused(422, uc.act.blocked)
    if uc.act.blocked_pattern and any(re.search(uc.act.blocked_pattern, v) for n, v in values.items() if n != "to"):
        raise ActionRefused(422, uc.act.blocked)

    res = await caller.call(tool, principal, {**p["slots"], "pending_id": p["id"]}, values)
    trace("act", pending_id=pending_id, tool=tool.name, ok=res.ok, error=res.error)
    if not res.ok:
        if res.error == "NEEDS_INPUT":
            raise ActionRefused(422, res.message or uc.act.blocked)
        if res.error == "UNAVAILABLE":
            raise ActionRefused(503, msgs.reasons.no_data)
        session.pending_action = None
        return _end(store, session, at, "cannot_do", msgs.forbidden if res.error == "FORBIDDEN" else msgs.action_expired)
    session.pending_action = None
    return _end(store, session, at, "answer", uc.act.done.format(to=values.get("to", "").strip()),
                [{"tool": tool.name, "fetched_at": res.fetched_at}], done=True)


def cancel(cfg: CopilotConfig, *, store: Store, principal: Principal, session: Session, pending_id: str, now: Callable[[], str]) -> ActionResult:
    at = now()
    p = session.pending_action
    if p and p.get("id") == pending_id:
        session.pending_action = None
        store.trace(at=at, session_id=session.session_id, turn_id=pending_id, user_id=principal.user_id, event="act",
                    detail={"pending_id": pending_id, "outcome": "cancelled"})
    return _end(store, session, at, "answer", cfg.runtime.messages.action_cancelled)
