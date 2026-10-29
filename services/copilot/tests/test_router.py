from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from copilot.config import load_dir
from copilot.identity import Principal
from copilot.models import build_model
from copilot.router import catalogue, route
from copilot.store import Session, Store

CFG = load_dir(Path(__file__).resolve().parent.parent / "config")
ANALYST = Principal("u1", "analyst", frozenset({"case.read", "data.read"}), "t")
RM = Principal("u2", "rm", frozenset({"checklist.read"}), "t")
UC = "explain_rejections"


def model(answer, seen=None):
    def fn(messages, info):
        if seen is not None:
            seen.append(messages[0].instructions)
        return ModelResponse(parts=[ToolCallPart("final_result", answer)])

    return FunctionModel(fn)


def sess(**kw):
    return Session("s1", "u1", **kw)


async def test_routes_and_fills_case_slot_from_open_case():
    seen = []
    r = await route(CFG, model({"use_case": UC, "confidence": 0.9, "slots": {"document_type": "bank_statement"}}, seen), ANALYST, sess(context={"case_id": "1042"}), "why was the bank statement rejected?")
    assert (r.kind, r.use_case, r.slots) == ("use_case", UC, {"document_type": "bank_statement", "case_id": "1042"})
    assert UC in seen[0] and "Examples:" in seen[0]


async def test_no_open_case_asks_which_case_then_continues_without_model():
    r1 = await route(CFG, model({"use_case": UC, "confidence": 0.9}), ANALYST, sess(), "why was it rejected?")
    assert (r1.kind, r1.pending_slot, r1.message) == ("ask", "case_id", "Which case do you mean?")

    def never(messages, info):
        raise AssertionError("model called")

    s = sess(active_use_case=UC, pending_slot="case_id", resolved_slots={})
    r2 = await route(CFG, FunctionModel(never), ANALYST, s, " 1042 ")
    assert (r2.kind, r2.slots) == ("use_case", {"case_id": "1042"})


async def test_open_case_beats_named_case_by_default_and_not_when_configured():
    ans = {"use_case": UC, "confidence": 0.9, "slots": {"case_id": "2000"}}
    r = await route(CFG, model(ans), ANALYST, sess(context={"case_id": "1042"}), "what about case 2000?")
    assert r.kind == "context_differs" and "1042" in r.message and "2000" in r.message
    cfg2 = CFG.model_copy(update={"runtime": CFG.runtime.model_copy(update={"context_wins": False})})
    r = await route(cfg2, model(ans), ANALYST, sess(context={"case_id": "1042"}), "what about case 2000?")
    assert r.kind == "use_case" and r.slots["case_id"] == "2000"


@pytest.mark.parametrize("answer,kind", [
    ({"use_case": None, "confidence": 0.9}, "decline"),
    ({"use_case": "made_up", "confidence": 0.99}, "decline"),
    ({"use_case": UC, "confidence": 0.3}, "clarify"),
])
async def test_decline_and_clarify(answer, kind):
    assert (await route(CFG, model(answer), ANALYST, sess(context={"case_id": "1"}), "hello")).kind == kind


async def test_missing_permission_is_forbidden_before_any_tool():
    r = await route(CFG, model({"use_case": UC, "confidence": 0.9}), RM, sess(context={"case_id": "1"}), "why rejected?")
    assert r.kind == "forbidden" and r.message == CFG.runtime.messages.forbidden


async def test_undeclared_slots_from_the_model_are_dropped():
    r = await route(CFG, model({"use_case": UC, "confidence": 0.9, "slots": {"user_id": "x", "document_type": " "}}), ANALYST, sess(context={"case_id": "1"}), "q")
    assert r.slots == {"case_id": "1"}


def test_catalogue_lists_every_use_case():
    assert all(u.id in catalogue(CFG) for u in CFG.registry.use_cases)


def test_build_model_needs_key_unless_replay(monkeypatch):
    monkeypatch.delenv(CFG.llm.api_key_env, raising=False)
    st = Store(":memory:")
    assert build_model(CFG.llm, "router", store=st, mode="replay", now=lambda: "").model_name == CFG.llm.router_model
    with pytest.raises(RuntimeError, match=CFG.llm.api_key_env):
        build_model(CFG.llm, "router", store=st, mode="record", now=lambda: "")


async def test_carried_over_case_does_not_count_as_named_when_the_open_case_changes():
    s = sess(context={"case_id": "2000"}, active_use_case=UC, resolved_slots={"case_id": "1042", "document_type": "bank_statement"})
    r = await route(CFG, model({"use_case": UC, "confidence": 0.9}), ANALYST, s, "and now?")
    assert r.kind == "use_case" and r.slots == {"case_id": "2000", "document_type": "bank_statement"}
