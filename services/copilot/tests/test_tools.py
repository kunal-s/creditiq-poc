import json
from pathlib import Path

import httpx
import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from copilot.config import load_dir
from copilot.identity import Principal
from copilot.tools import ToolCaller, ToolDeps, build_tools

CFG = load_dir(Path(__file__).resolve().parent.parent / "config")
P = Principal("u1", "analyst", frozenset({"data.read"}), "tok-123")


def caller(handler):
    return ToolCaller(CFG, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(handler)), now=lambda: "T")


async def call(handler, name="get_rejection_reasons", slots=None, args=None):
    return await caller(handler).call(CFG.tool(name), P, {"case_id": "1042"} if slots is None else slots, args or {})


async def test_ok_call_uses_user_token_and_slot_in_path():
    seen = {}

    def h(req):
        seen.update(auth=req.headers["authorization"], path=req.url.path, q=dict(req.url.params))
        return httpx.Response(200, json=[{"document": "bank statement"}])

    r = await call(h, slots={"case_id": "1042", "document_type": "bank_statement"})
    assert r.ok and r.data == [{"document": "bank statement"}] and r.fetched_at == "T"
    assert seen == {"auth": "Bearer tok-123", "path": "/api/cases/1042/rejections", "q": {"document_type": "bank_statement"}}


async def test_path_value_is_quoted():
    seen = {}
    await call(lambda req: seen.update(raw=req.url.raw_path) or httpx.Response(200, json=[]), slots={"case_id": "../x?y"})
    assert seen["raw"] == b"/api/cases/..%2Fx%3Fy/rejections"


@pytest.mark.parametrize("status,code", [(404, "NOT_FOUND"), (403, "FORBIDDEN"), (401, "FORBIDDEN"), (422, "NEEDS_INPUT"), (500, "UNAVAILABLE")])
async def test_status_maps_to_typed_error(status, code):
    r = await call(lambda req: httpx.Response(status))
    assert not r.ok and r.error == code and "error" in r.for_model()


async def test_timeout_is_unavailable_and_missing_slot_needs_input_without_a_call():
    def boom(req):
        raise httpx.ReadTimeout("slow")

    assert (await call(boom)).error == "UNAVAILABLE"

    def never(req):
        raise AssertionError("host called")

    r = await call(never, slots={})
    assert r.error == "NEEDS_INPUT"


async def test_model_cannot_set_slot_params_or_unknown_args():
    def never(req):
        raise AssertionError("host called")

    assert (await call(never, args={"case_id": "9999"})).error == "NEEDS_INPUT"
    assert (await call(never, args={"bogus": 1})).error == "NEEDS_INPUT"


async def test_rows_are_limited():
    spec_rows = CFG.tool("get_rejection_reasons").row_limit
    r = await call(lambda req: httpx.Response(200, json=[{"i": i} for i in range(spec_rows + 5)]), name="get_rejection_reasons")
    assert len(r.data) == spec_rows and r.truncated and r.for_model()["truncated"]


async def test_model_sees_no_slot_params_and_agent_runs_tool():
    seen = {}

    def fn(messages, info):
        seen["schemas"] = {t.name: t.parameters_json_schema for t in info.function_tools}
        if not any(isinstance(p, ToolReturnPart) for m in messages for p in m.parts):
            return ModelResponse(parts=[ToolCallPart("get_rejection_reasons", {})])
        return ModelResponse(parts=[TextPart("done")])

    deps = ToolDeps(P, {"case_id": "1042"}, caller(lambda req: httpx.Response(200, json=[{"document": "x"}])))
    agent = Agent(FunctionModel(fn), tools=build_tools(CFG, ["get_rejection_reasons"]), deps_type=ToolDeps)
    out = await agent.run("why?", deps=deps)
    assert out.output == "done"
    assert seen["schemas"]["get_rejection_reasons"]["properties"] == {}
    assert "tok-123" not in json.dumps(seen["schemas"])
    assert deps.calls == [{"tool": "get_rejection_reasons", "args": {}, "ok": True, "error": None, "at": "T"}]


async def test_result_fields_drop_everything_else_including_ids():
    rows = [{"id": "f_7b2", "kind": "file", "document": "a.pdf", "status": "rejected", "reason": "x", "rule": None, "extra": 1}]
    r = await call(lambda req: httpx.Response(200, json=rows))
    assert r.data == [{"kind": "file", "document": "a.pdf", "status": "rejected", "reason": "x", "rule": None}]
