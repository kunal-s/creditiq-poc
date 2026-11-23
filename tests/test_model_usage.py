"""Model usage (Administration): the three model call logs read together, for the administrator only, and
only when the deployment has the section switched on. A source that cannot be read leaves partial data,
cost is tokens times the configured price per million (cached input at its own price), and a model with
no price has none, never 0."""

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, model_usage
from engine.ingest_client import IngestError, StubIngestClient
from engine.model_log import write
from tests.conftest import ANALYST, sign_in

ADMIN = "nikhil.sawant@rblbank.com"
DAY = "2026-11-12"


def _row(**kw) -> dict:
    base = {"id": kw.pop("id"), "at": f"{DAY}T06:00:00+00:00", "service": "cam", "task": "cam_section",
            "provider": "openai", "model": "gpt-5.4-nano", "mode": "record", "source": "live", "status": "ok",
            "attempt": 1, "latency_ms": 800.0}
    return {**base, **kw}


@pytest.fixture
def logged(published_data_root: Path):
    conn = db.connect(published_data_root)
    try:
        write(conn, _row(id="a", input_tokens=1000, cached_tokens=400, output_tokens=200, latency_ms=900.0))
        write(conn, _row(id="b", input_tokens=500, output_tokens=100, latency_ms=1100.0))
        write(conn, _row(id="c", status="error", error_code="http", kind="rate_limit_minute", http_status=429,
                         latency_ms=120.0, message="busy"))
        write(conn, _row(id="d", source="replay_hit", latency_ms=0.0))
    finally:
        conn.close()
    return published_data_root


def _summary(client, headers, **params):
    return client.get("/api/admin/model-usage/summary", params={"from": DAY, "to": DAY, **params}, headers=headers)


def test_an_analyst_may_not_read_it(client: TestClient, logged):
    assert _summary(client, sign_in(client, ANALYST)).status_code == 403


def test_switched_off_the_section_is_not_there(client: TestClient, logged, features_on: dict):
    admin = sign_in(client, ADMIN)
    features_on["model_usage"] = False
    assert _summary(client, admin).status_code == 404
    assert client.get("/api/admin/model-usage/calls", headers=admin).status_code == 404
    assert client.get("/api/meta", headers=admin).json()["features"]["model_usage"] is False


def test_the_engines_own_log_is_summarised_and_a_source_that_is_down_is_named(client: TestClient, logged, monkeypatch):
    def down(self, path, params):
        raise IngestError("ingest service unavailable")

    monkeypatch.setattr(StubIngestClient, "model_log", down)
    monkeypatch.setenv("CREDITIQ_COPILOT_URL", "http://127.0.0.1:9")      # nothing listens there
    r = _summary(client, sign_in(client, ADMIN))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["unavailable"]) == {"ingestion", "copilot"}
    [row] = body["rows"]
    assert (row["day"], row["service"], row["task"], row["model"]) == (DAY, "cam", "cam_section", "gpt-5.4-nano")
    assert (row["calls"], row["ok"], row["errors"]) == (4, 3, {"rate_limit_minute": 1})
    assert (row["live_calls"], row["replay_hits"], row["replay_misses"]) == (3, 1, 0)
    assert (row["input_tokens"], row["cached_tokens"], row["output_tokens"]) == (1500, 400, 300)
    assert row["latency_ms_p50"] == 900.0
    # No price is set for the model: the cost is not known, never 0.
    assert row["cost"] is None and row["price_set"] is False


def test_cost_counts_cached_input_at_its_own_price(client: TestClient, logged, monkeypatch):
    real = model_usage.settings

    def priced():
        cfg = real()
        return {**cfg, "prices": {"gpt-5.4-nano": {"input": 0.20, "cached_input": 0.05, "output": 1.25}}}

    monkeypatch.setattr(model_usage, "settings", priced)
    monkeypatch.setenv("CREDITIQ_COPILOT_URL", "http://127.0.0.1:9")
    [row] = [r for r in _summary(client, sign_in(client, ADMIN)).json()["rows"] if r["service"] == "cam"]
    # (1500 - 400) x 0.20 + 400 x 0.05 + 300 x 1.25, per million tokens
    assert row["cost"] == pytest.approx((1100 * 0.20 + 400 * 0.05 + 300 * 1.25) / 1_000_000)
    assert row["price_set"] is True
    assert model_usage.cost({"m": {"input": 1, "cached_input": 1, "output": 1}}, "m", None, None, None) == (0.0, True)
    assert model_usage.cost({}, "m", 10, 0, 10) == (None, False)


def test_the_call_list_is_filtered_newest_first_and_paged(client: TestClient, logged, monkeypatch):
    monkeypatch.setenv("CREDITIQ_COPILOT_URL", "http://127.0.0.1:9")
    admin = sign_in(client, ADMIN)
    errors = client.get("/api/admin/model-usage/calls", params={"from": DAY, "to": DAY, "status": "error"},
                        headers=admin).json()
    assert errors["total"] == 1 and errors["rows"][0]["kind"] == "rate_limit_minute"
    page = client.get("/api/admin/model-usage/calls", params={"from": DAY, "to": DAY, "service": "cam", "limit": 2,
                                                             "offset": 1}, headers=admin).json()
    assert page["total"] == 4 and len(page["rows"]) == 2 and page["unavailable"] == []


def test_a_call_time_written_without_its_offset_is_given_one_and_sorted_by_the_instant(client: TestClient, logged,
                                                                                      monkeypatch):
    """The case assistant writes UTC times without an offset: the list gives every time its offset, so the
    screen shows each call at its instant, in order with the other services' calls."""
    later = {"id": "c1", "at": f"{DAY}T10:00:00", "service": "copilot", "task": "runner", "model": "gpt-5.4-nano",
             "source": "live", "status": "ok"}
    monkeypatch.setattr(model_usage, "_copilot", lambda path, params, token: {"total": 1, "rows": [later]})
    admin = sign_in(client, ADMIN)
    page = client.get("/api/admin/model-usage/calls", params={"from": DAY, "to": DAY}, headers=admin).json()
    [copilot] = [r for r in page["rows"] if r["service"] == "copilot"]
    assert copilot["at"] == f"{DAY}T10:00:00+00:00"
    instants = [datetime.fromisoformat(r["at"]) for r in page["rows"]]
    assert all(t.tzinfo for t in instants) and instants == sorted(instants, reverse=True)
