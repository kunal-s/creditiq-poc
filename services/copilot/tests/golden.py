"""The golden set harness: shared by tests/test_golden.py (replay) and scripts/record_golden.py (record)."""

from __future__ import annotations

from pathlib import Path

import httpx
import yaml

from copilot.config import CopilotConfig
from copilot.identity import Principal
from copilot.models import build_model
from copilot.runner import TurnResult, handle_turn
from copilot.store import Store
from copilot.tools import ToolCaller

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
# (cases, recorded model answers): the golden set, and the end-to-end spec's questions
SETS = [(FIXTURES / "golden.yaml", FIXTURES / "golden_recordings.json"), (FIXTURES / "e2e.yaml", FIXTURES / "e2e_recordings.json")]
NOW = lambda: "2026-10-28T10:00:00"  # noqa: E731
USER = Principal("u1", "analyst", frozenset({"case.read", "message.send"}), "token")


def load(path: Path = SETS[0][0]) -> dict:
    return yaml.safe_load(path.read_text())


def _host(cfg: CopilotConfig, golden: dict, spec: dict) -> ToolCaller:
    rows = golden["hosts"][spec["rows"]] if "rows" in spec else {}
    status = spec.get("status", 200)
    client = httpx.AsyncClient(base_url=cfg.host.base_url, transport=httpx.MockTransport(lambda r: httpx.Response(status, json=rows)))
    return ToolCaller(cfg, client, now=NOW)


async def run_case(cfg: CopilotConfig, golden: dict, case: dict, store: Store, mode: str) -> tuple[TurnResult, list[dict]]:
    router, runner = (build_model(cfg.llm, r, store=store, mode=mode, now=NOW) for r in ("router", "runner"))
    session = store.create_session(USER.user_id, NOW(), dict(case["context"]))
    if case.get("pending_draft"):  # a draft the user has just been shown, waiting to be sent
        act = next(u for u in cfg.registry.use_cases if u.act)
        session.pending_action = {"id": "p_golden", "use_case": act.id, "slots": dict(case["context"]), "context": dict(case["context"]),
                                  "fields": {"to": "", "subject": "Please resend corrected documents", "body": "Hello [Name],\n\nPlease resend the bank statement."},
                                  "expires_at": "2099-01-01T00:00:00"}
    say = case["say"] if isinstance(case["say"], list) else [case["say"]]  # several messages are one conversation; the last is judged
    caller = _host(cfg, golden, case["host"])
    for message in say:
        res = await handle_turn(cfg, router_model=router, runner_model=runner, caller=caller, store=store,
                                principal=USER, session=session, message=message, now=NOW)
    return res, store.read_trace(session.session_id)


def problems(cfg: CopilotConfig, case: dict, res: TurnResult, trace: list[dict]) -> list[str]:
    """What differs from the case's expectation, as sentences; empty when it behaved as expected."""
    want, out = case["expect"], []
    calls = [t["detail"] for t in trace if t["event"] == "tool_call"]
    if res.terminal != want["terminal"]:
        out.append(f"terminal {res.terminal!r}, expected {want['terminal']!r}")
    if "use_case" in want and res.use_case != want["use_case"]:
        out.append(f"use case {res.use_case!r}, expected {want['use_case']!r}")
    if [c["tool"] for c in calls] != want["tools"]:
        out.append(f"tools {[c['tool'] for c in calls]}, expected {want['tools']}")
    if "rows" in want and len(res.rows) != want["rows"]:
        out.append(f"{len(res.rows)} rows, expected {want['rows']}")
    for bad in want.get("text_excludes", []):
        if bad.lower() in res.text.lower():  # the sentence, not the table: a file name is shown as it is
            out.append(f"the reply contains {bad!r}")
    for need in want.get("text_includes", []):
        if need.lower() not in res.text.lower():
            out.append(f"the reply lacks {need!r}")
    if want.get("text_equals_message") and res.text != getattr(cfg.runtime.messages, want["text_equals_message"]):
        out.append("the reply is not the configured message")
    if res.use_case and len([c for c in calls if c["error"] != "BLOCKED"]) > cfg.use_case(res.use_case).max_steps:
        out.append("more tool calls than the step budget")
    if any(c["error"] == "BLOCKED" for c in calls):
        out.append("a call was blocked: the model looped or repeated itself")
    return out
