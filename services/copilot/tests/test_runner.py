from pathlib import Path

import httpx
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from copilot.config import load_dir
from copilot.identity import Principal
from copilot.runner import handle_turn
from copilot.store import Store
from copilot.tools import ToolCaller

CFG = load_dir(Path(__file__).resolve().parent.parent / "config")
ANALYST = Principal("u1", "analyst", frozenset({"case.read", "data.read"}), "t")
UC = "explain_rejections"
ROWS = [{"document": "Bank statement", "status": "Rejected", "reason": "Pages are blurred", "rule": "QUAL-02"}]
ANSWER = {"text": "One document was rejected.", "rows": [{"document": "bank statement", "status": "rejected", "reason": "pages are blurred", "rule": "qual-02"}]}
NOW = lambda: "2026-10-28T10:00:00"  # noqa: E731


def router(answer=None):
    ans = answer or {"use_case": UC, "confidence": 0.9}
    return FunctionModel(lambda m, i: ModelResponse(parts=[ToolCallPart("final_result", ans)]))


def runner(script):
    """script(n_tool_returns) -> list of parts"""
    def fn(messages, info):
        n = sum(isinstance(p, ToolReturnPart) for m in messages for p in m.parts)
        return ModelResponse(parts=script(n))
    return FunctionModel(fn)


def host(status=200, body=ROWS, hits=None):
    def h(req):
        if hits is not None:
            hits.append(req.url.path)
        return httpx.Response(status, json=body)
    return ToolCaller(CFG, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(h)), now=NOW)


def with_steps(n):
    """The use case gets a second tool (a clone) so a turn can make two different calls."""
    clone = CFG.tool("get_rejection_reasons").model_copy(update={"name": "get_rejection_reasons_again"})
    uc = CFG.use_case(UC).model_copy(update={"max_steps": n, "tools": ["get_rejection_reasons", clone.name]})
    return CFG.model_copy(update={"registry": CFG.registry.model_copy(update={"use_cases": [uc]}),
                                  "tools": CFG.tools.model_copy(update={"tools": [*CFG.tools.tools, clone]})})


async def turn(runner_model, caller, *, cfg=CFG, router_model=None, store=None, session=None, msg="why rejected?", ctx=None):
    store = store or Store(":memory:")
    session = session or store.create_session("u1", NOW(), ctx if ctx is not None else {"case_id": "1042"})
    res = await handle_turn(cfg, router_model=router_model or router(), runner_model=runner_model, caller=caller,
                            store=store, principal=ANALYST, session=session, message=msg, now=NOW)
    return res, store, session


GOOD = runner(lambda n: [ToolCallPart("get_rejection_reasons", {})] if n == 0 else [ToolCallPart("final_result", ANSWER)])


async def test_grounded_answer_with_sources_trace_and_state():
    hits = []
    res, store, s = await turn(GOOD, host(hits=hits))
    assert res.terminal == "answer" and res.rows == ANSWER["rows"] and res.columns == ["document", "status", "reason", "rule"]
    assert res.sources == [{"tool": "get_rejection_reasons", "fetched_at": NOW()}]
    assert hits == ["/api/cases/1042/rejections"]
    events = [t["event"] for t in store.read_trace(s.session_id)]
    assert events == ["route", "tool_call", "terminal"]
    msgs = store.messages(s.session_id, "u1")
    assert [(m.role, m.terminal) for m in msgs] == [("user", None), ("assistant", "answer")] and msgs[1].payload["rows"]
    got = store.load(s.session_id, "u1")
    assert got.active_use_case == UC and got.resolved_slots == {"case_id": "1042"} and got.last_results[0]["tool"] == "get_rejection_reasons"


async def test_repeated_call_is_blocked_and_host_called_once():
    hits = []
    again = runner(lambda n: [ToolCallPart("get_rejection_reasons", {})] if n < 3 else [ToolCallPart("final_result", ANSWER)])
    res, store, s = await turn(again, host(hits=hits))
    assert res.terminal == "cannot_do" and CFG.runtime.messages.reasons.repeat_call in res.text and "get_rejection_reasons" in res.text
    assert len(hits) == 1
    assert any(t["detail"].get("reason") == "repeat_call" for t in store.read_trace(s.session_id))


async def test_step_limit_ends_the_turn():
    hits = []
    two = runner(lambda n: [ToolCallPart("get_rejection_reasons_again", {})] if n == 0 else [ToolCallPart("get_rejection_reasons", {})])
    res, *_ = await turn(two, host(hits=hits), cfg=with_steps(1))
    assert res.terminal == "cannot_do" and CFG.runtime.messages.reasons.step_limit in res.text and len(hits) == 1


async def test_forbidden_from_host_is_cannot_do_with_forbidden_message():
    res, *_ = await turn(GOOD, host(403, {}))
    assert (res.terminal, res.text) == ("cannot_do", CFG.runtime.messages.forbidden)


async def test_answer_without_any_lookup_is_refused():
    direct = runner(lambda n: [ToolCallPart("final_result", ANSWER)])
    res, *_ = await turn(direct, host())
    assert res.terminal == "cannot_do" and CFG.runtime.messages.reasons.no_data in res.text


async def test_table_cell_not_in_tool_results_is_refused_unless_switched_off():
    bad = {"text": "x", "rows": [{"document": "bank statement", "status": "rejected", "reason": "forged signature", "rule": "qual-02"}]}
    liar = runner(lambda n: [ToolCallPart("get_rejection_reasons", {})] if n == 0 else [ToolCallPart("final_result", bad)])
    res, *_ = await turn(liar, host())
    assert res.terminal == "cannot_do" and CFG.runtime.messages.reasons.ungrounded in res.text and res.rows == []
    off = CFG.model_copy(update={"runtime": CFG.runtime.model_copy(update={"guards": CFG.runtime.guards.model_copy(update={"ground_table_cells": False})})})
    assert (await turn(liar, host(), cfg=off))[0].terminal == "answer"


async def test_no_open_case_asks_then_next_message_completes():
    store = Store(":memory:")
    res1, _, s = await turn(GOOD, host(), store=store, ctx={})
    assert (res1.terminal, res1.text) == ("ask_user", "Which case do you mean?")
    s = store.load(s.session_id, "u1")
    assert s.pending_slot == "case_id"
    hits = []
    res2, *_ = await turn(GOOD, host(hits=hits), store=store, session=s, msg="1042")
    assert res2.terminal == "answer" and hits == ["/api/cases/1042/rejections"]
    assert store.load(s.session_id, "u1").pending_slot is None


async def test_decline_low_confidence_and_other_case_are_terminal_without_tools():
    def never(messages, info):
        raise AssertionError("runner called")

    hits = []
    for answer, terminal, text in [
        ({"use_case": None, "confidence": 0.9}, "cannot_do", CFG.runtime.messages.decline),
        ({"use_case": UC, "confidence": 0.2}, "ask_user", CFG.runtime.messages.clarify),
    ]:
        res, *_ = await turn(FunctionModel(never), host(hits=hits), router_model=router(answer))
        assert (res.terminal, res.text) == (terminal, text)
    res, *_ = await turn(FunctionModel(never), host(hits=hits), router_model=router({"use_case": UC, "confidence": 0.9, "slots": {"case_id": "2000"}}))
    assert res.terminal == "cannot_do" and "2000" in res.text and hits == []


async def test_the_runner_prompt_does_not_name_the_open_case():
    seen = []

    def fn(messages, info):
        seen.append(messages[0].instructions)
        n = sum(isinstance(p, ToolReturnPart) for m in messages for p in m.parts)
        return ModelResponse(parts=[ToolCallPart("get_rejection_reasons", {})] if n == 0 else [ToolCallPart("final_result", ANSWER)])

    await turn(FunctionModel(fn), host(), ctx={"case_id": "BBG-2026-000321"})
    assert "BBG-2026-000321" not in seen[0]


async def test_empty_result_gets_the_configured_message_not_the_models_draft():
    uc = CFG.use_case(UC).model_copy(update={"empty_message": "Nothing to ask for."})
    cfg = CFG.model_copy(update={"registry": CFG.registry.model_copy(update={"use_cases": [uc]})})
    invented = {"text": "Subject: please send your documents", "rows": []}
    model = runner(lambda n: [ToolCallPart("get_rejection_reasons", {})] if n == 0 else [ToolCallPart("final_result", invented)])
    res, *_ = await turn(model, host(body=[]), cfg=cfg)
    assert (res.terminal, res.text) == ("answer", "Nothing to ask for.")
    # With rows the model's text stands
    res, *_ = await turn(GOOD, host(), cfg=cfg)
    assert res.text == ANSWER["text"]


async def test_a_cell_copied_exactly_is_grounded_even_when_json_would_escape_it():
    quoted = 'The file type "application/pdf" could not be recognised.\nPath C:\\scans'
    rows = [{**ROWS[0], "reason": quoted}]
    copy = {"text": "One.", "rows": [{"document": "bank statement", "status": "rejected", "reason": quoted, "rule": "qual-02"}]}
    model = runner(lambda n: [ToolCallPart("get_rejection_reasons", {})] if n == 0 else [ToolCallPart("final_result", copy)])
    res, *_ = await turn(model, host(body=rows))
    assert res.terminal == "answer" and res.rows[0]["reason"] == quoted
