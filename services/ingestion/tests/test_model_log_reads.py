"""The document service's model call log, read for the Administration's Model usage section (behind the
service's own key): summarised by day in the zone asked for, and listed with filters, newest first."""

from pathlib import Path

from fastapi.testclient import TestClient

from ingestion.api import create_app
from ingestion.llm import calllog
from ingestion.settings import Settings
from ingestion.store import Store

CONFIG = Path(__file__).resolve().parents[3] / "config" / "ingestion"


def _row(i, at, **kw):
    return {"id": f"r{i}", "at": at, "service": "ingestion", "task": "extract", "provider": "openai",
            "model": "gpt-5.4-nano", "mode": "replay", "source": "replay_miss", "status": "error",
            "error_code": "replay_miss", "kind": "replay_miss", "attempt": 1, "latency_ms": 0, "case_ref": "BBG-1", **kw}


def test_the_log_is_read_behind_the_key_by_day_and_filtered(tmp_path):
    store = Store()
    calllog.write(store, _row(1, "2026-11-11T20:00:00+00:00"))                      # the 12th in Kolkata
    calllog.write(store, _row(2, "2026-11-12T05:00:00+00:00", task="classify", status="ok", error_code=None,
                              kind=None, source="live", input_tokens=10, output_tokens=2, latency_ms=300.0))
    c = TestClient(create_app(Settings(tmp_path, CONFIG, "127.0.0.1", 0, "secret", "replay"), store))
    q = {"from": "2026-11-12", "to": "2026-11-12", "tz": "Asia/Kolkata"}
    assert c.get("/v1/model-log/summary", params=q).status_code == 401
    h = {"x-api-key": "secret"}
    rows = c.get("/v1/model-log/summary", params=q, headers=h).json()["rows"]
    assert {(r["task"], r["calls"], r["replay_misses"], r["live_calls"]) for r in rows} == {("extract", 1, 1, 0), ("classify", 1, 0, 1)}
    misses = c.get("/v1/model-log/calls", params={**q, "kind": "replay_miss"}, headers=h).json()
    assert misses["total"] == 1 and misses["rows"][0]["id"] == "r1" and misses["rows"][0]["case_ref"] == "BBG-1"
    both = c.get("/v1/model-log/calls", params=q, headers=h).json()
    assert [r["id"] for r in both["rows"]] == ["r2", "r1"]
