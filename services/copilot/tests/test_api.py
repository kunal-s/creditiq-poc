import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from copilot.api import create_app
from copilot.config import load_dir
from copilot.identity import HostIdentity
from copilot.settings import Settings
from copilot.tools import ToolCaller

CFG = load_dir(Path(__file__).resolve().parent.parent / "config")
ROWS = [{"document": "Bank statement", "status": "Rejected", "reason": "Pages are blurred", "rule": "QUAL-02"}]
ANSWER = {"text": "One rejected.", "rows": [{"document": "bank statement", "status": "rejected", "reason": "pages are blurred", "rule": "qual-02"}]}
USERS = {"tok-a": {"id": "u1", "role": "analyst", "permissions": ["case.read"]},
         "tok-b": {"id": "u2", "role": "analyst", "permissions": ["case.read"]}}


def host(req):
    if req.url.path == CFG.host.identity_path:
        u = USERS.get(req.headers["authorization"].removeprefix("Bearer "))
        return httpx.Response(200, json=u) if u else httpx.Response(401)
    return httpx.Response(200, json=ROWS)


def runner_fn(messages, info):
    n = sum(isinstance(p, ToolReturnPart) for m in messages for p in m.parts)
    return ModelResponse(parts=[ToolCallPart("get_rejection_reasons", {})] if n == 0 else [ToolCallPart("final_result", ANSWER)])


@pytest.fixture
def client(tmp_path):
    mk = lambda: httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(host))  # noqa: E731
    app = create_app(
        Settings(Path("."), tmp_path), cfg=CFG, identity=HostIdentity(CFG.host, mk()), caller=ToolCaller(CFG, mk()),
        router_model=FunctionModel(lambda m, i: ModelResponse(parts=[ToolCallPart("final_result", {"use_case": "explain_rejections", "confidence": 0.9})])),
        runner_model=FunctionModel(runner_fn), now=lambda: "2026-10-28T10:00:00",
    )
    return TestClient(app)


def events(r):
    out = []
    for block in r.text.strip().split("\n\n"):
        ev, data = block.split("\n")
        out.append((ev.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def chat(client, tok="tok-a", **body):
    return client.post("/chat", json={"message": "why rejected?", **body}, headers={"Authorization": f"Bearer {tok}"})


def test_chat_streams_session_then_result_and_history_is_readable(client):
    r = chat(client, context={"case_id": 1042, "ignored": "x"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    (e1, d1), (e2, d2) = events(r)
    assert (e1, e2) == ("session", "result") and d2["terminal"] == "answer" and d2["rows"] == ANSWER["rows"]
    h = client.get(f"/sessions/{d1['session_id']}", headers={"Authorization": "Bearer tok-a"}).json()
    assert h["context"] == {"case_id": "1042"} and [m["role"] for m in h["messages"]] == ["user", "assistant"]
    assert h["messages"][1]["rows"] == ANSWER["rows"]


def test_second_message_reuses_session_and_open_case_follows_the_screen(client):
    sid = events(chat(client, context={"case_id": "1042"}))[0][1]["session_id"]
    d = events(chat(client, session_id=sid, context={"case_id": "2000"}))[1][1]
    assert d["terminal"] == "answer"
    assert client.get(f"/sessions/{sid}", headers={"Authorization": "Bearer tok-a"}).json()["context"] == {"case_id": "2000"}


def test_no_open_case_asks_which_case(client):
    d = events(chat(client))[1][1]
    assert (d["terminal"], d["text"]) == ("ask_user", "Which case do you mean?")


def test_auth_failures_and_session_privacy(client):
    assert client.post("/chat", json={"message": "x"}).status_code == 401
    assert chat(client, tok="nope").status_code == 401
    sid = events(chat(client, context={"case_id": "1"}))[0][1]["session_id"]
    assert client.get(f"/sessions/{sid}", headers={"Authorization": "Bearer tok-b"}).status_code == 404
    assert chat(client, tok="tok-b", session_id=sid).status_code == 404


def test_message_limits(client):
    assert chat(client, message="").status_code == 422
    assert chat(client, message="x" * 2001).status_code == 422


def test_replay_miss_is_a_generic_error_event(tmp_path):
    app = create_app(Settings(Path("."), tmp_path), cfg=CFG,
                     identity=HostIdentity(CFG.host, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(host))))
    r = chat(TestClient(app), context={"case_id": "1"})  # real models in replay mode, empty store
    assert events(r)[-1] == ("error", {"code": "model_unavailable"})


def test_settings_require_a_data_dir_outside_the_repo_and_valid_mode(tmp_path):
    with pytest.raises(RuntimeError, match="DATA"):
        Settings.from_env({})
    s = Settings.from_env({"CREDITIQ_DATA_ROOT": str(tmp_path)})
    assert s.data_dir == tmp_path / "copilot" and s.mode == "replay"
    with pytest.raises(RuntimeError, match="MODE"):
        Settings.from_env({"COPILOT_DATA_DIR": str(tmp_path), "COPILOT_MODEL_MODE": "yolo"})
    assert Settings.from_env({"COPILOT_DATA_DIR": "/x", "COPILOT_HOST_URL": "http://h"}).host_url == "http://h"


def test_unexpected_failure_ends_the_stream_with_an_error_event(tmp_path):
    def boom(messages, info):
        raise KeyError("x")

    app = create_app(Settings(Path("."), tmp_path), cfg=CFG, router_model=FunctionModel(boom), runner_model=FunctionModel(boom),
                     identity=HostIdentity(CFG.host, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(host))))
    assert events(chat(TestClient(app), context={"case_id": "1"}))[-1] == ("error", {"code": "internal"})


def test_cors_origins_can_be_set_from_the_environment(tmp_path):
    s = Settings.from_env({"COPILOT_DATA_DIR": str(tmp_path), "COPILOT_CORS_ORIGINS": "http://a:1, http://b:2"})
    assert s.cors_origins == ("http://a:1", "http://b:2")
    app = create_app(s, cfg=CFG, identity=HostIdentity(CFG.host, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(host))))
    r = TestClient(app).options("/chat", headers={"Origin": "http://b:2", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://b:2"
    r = TestClient(app).options("/chat", headers={"Origin": "http://localhost:4173", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers
