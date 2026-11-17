"""The case assistant's model call log, read for the Administration's Model usage section: only a signed-in
user with model_usage.read may read it, summarised by day in the zone asked for, and listed newest first."""

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from copilot import calllog
from copilot.api import create_app
from copilot.config import load_dir
from copilot.identity import HostIdentity
from copilot.settings import Settings
from copilot.store import Store

CFG = load_dir(Path(__file__).resolve().parent.parent / "config")
USERS = {"tok-admin": {"id": "admin", "role": "administrator", "permissions": ["model_usage.read"]},
         "tok-a": {"id": "u1", "role": "analyst", "permissions": ["case.read"]}}


def host(req):
    u = USERS.get(req.headers.get("authorization", "").removeprefix("Bearer "))
    return httpx.Response(200, json=u) if u else httpx.Response(401)


def app(tmp_path):
    a = create_app(Settings(Path("."), tmp_path), cfg=CFG,
                   identity=HostIdentity(CFG.host, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(host))))
    return a, TestClient(a)


def _row(i, at, **kw):
    return {"id": f"r{i}", "at": at, "service": "copilot", "task": "router", "provider": "openai", "model": "gpt-5.4-nano",
            "mode": "replay", "source": "live", "status": "ok", "attempt": 1, "latency_ms": 100.0 * i, **kw}


def test_only_a_reader_of_model_usage_reads_the_log(tmp_path):
    _, c = app(tmp_path)
    q = {"from": "2026-11-12", "to": "2026-11-12"}
    assert c.get("/v1/model-log/summary", params=q).status_code == 401
    assert c.get("/v1/model-log/summary", params=q, headers={"Authorization": "Bearer tok-a"}).status_code == 403
    assert c.get("/v1/model-log/summary", params=q, headers={"Authorization": "Bearer tok-admin"}).status_code == 200


def test_it_is_summarised_by_day_in_the_zone_and_listed_newest_first(tmp_path):
    _, c = app(tmp_path)
    store = Store(tmp_path / "copilot.sqlite3")     # the app's own store (settings.data_dir)
    # 20:00 UTC on the 11th is the 12th in Kolkata (+05:30).
    calllog.write(store, _row(1, "2026-11-11T20:00:00", input_tokens=50, output_tokens=5))
    calllog.write(store, _row(2, "2026-11-12T03:00:00", status="error", error_code="replay_miss", kind="replay_miss",
                               source="replay_miss"))
    h = {"Authorization": "Bearer tok-admin"}
    s = c.get("/v1/model-log/summary", params={"from": "2026-11-12", "to": "2026-11-12", "tz": "Asia/Kolkata"}, headers=h).json()
    [row] = s["rows"]
    assert s["service"] == "copilot" and row["day"] == "2026-11-12" and row["calls"] == 2
    assert row["errors"] == {"replay_miss": 1} and row["replay_misses"] == 1 and row["input_tokens"] == 50
    utc = c.get("/v1/model-log/summary", params={"from": "2026-11-12", "to": "2026-11-12", "tz": "UTC"}, headers=h).json()
    assert [r["calls"] for r in utc["rows"]] == [1]
    calls = c.get("/v1/model-log/calls", params={"from": "2026-11-11", "to": "2026-11-12", "tz": "UTC"}, headers=h).json()
    assert calls["total"] == 2 and [r["id"] for r in calls["rows"]] == ["r2", "r1"]
