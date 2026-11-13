"""The model call log (llm/calllog.py): one row per HTTP attempt and per replay, with tokens, latency and
outcome, in `model_log` and as one JSON line on `creditiq.model`. Recordings are unchanged by it, it
never logs a prompt, an answer or a key, and it never fails a call."""

import json
import logging
from pathlib import Path

import httpx
import pytest

from ingestion.config.loader import load_dir
from ingestion.llm import calllog
from ingestion.llm import openai as openai_mod
from ingestion.llm.openai import FixtureProvider, OpenAIProvider
from ingestion.llm.provider import ModelError, ModelRequest, recording_key
from ingestion.llm.recorder import ModelClient
from ingestion.store import Store

CONFIG = Path(__file__).resolve().parents[3] / "config" / "ingestion"
REQ = ModelRequest("classify", "Say which type.", "PAN: AAACK1234K", {"type": "object", "properties": {"type": {"type": "string"}},
                                                                    "required": ["type"], "additionalProperties": False})
ANSWER = {"choices": [{"message": {"content": json.dumps({"type": "company_pan"})}}],
          "usage": {"prompt_tokens": 120, "completion_tokens": 8, "total_tokens": 128,
                    "prompt_tokens_details": {"cached_tokens": 64}}}
HEADERS = {"x-ratelimit-remaining-tokens": "199872", "x-ratelimit-remaining-requests": "499"}


@pytest.fixture(scope="module")
def cfg():
    return load_dir(CONFIG, version="test")


@pytest.fixture()
def http(monkeypatch):
    """httpx.post answers from a queue of (status, json, headers); sleeping between attempts is skipped."""
    queue: list = []
    sent: list = []

    def post(url, json=None, timeout=None, headers=None):
        sent.append({"url": url, "json": json, "headers": headers})
        status, body, hdrs = queue.pop(0)
        if isinstance(status, Exception):
            raise status
        return httpx.Response(status, json=body, headers=hdrs, request=httpx.Request("POST", url))

    monkeypatch.setattr(openai_mod.httpx, "post", post)
    monkeypatch.setattr(openai_mod.time, "sleep", lambda s: None)
    return queue, sent


@pytest.fixture()
def lines():
    """The JSON lines written on the creditiq.model logger."""
    got: list[dict] = []

    class Grab(logging.Handler):
        def emit(self, record):
            got.append(json.loads(record.getMessage()))

    h = Grab()
    logging.getLogger("creditiq.model").addHandler(h)
    yield got
    logging.getLogger("creditiq.model").removeHandler(h)


def _client(cfg, mode, store, key="sk-test-0123456789abcdef"):
    return ModelClient(OpenAIProvider(cfg.llm, key, sleep=lambda s: None), mode, store)


def test_an_answer_with_usage_gives_one_ok_row_with_tokens_and_latency(cfg, http, lines):
    queue, sent = http
    queue.append((200, ANSWER, HEADERS))
    store = Store()
    with calllog.call_context(case_ref="BBG-2026-000021", run_id="run-1"):
        assert _client(cfg, "live", store).call(REQ) == {"type": "company_pan"}
    [row] = store.model_log()
    assert row["service"] == "ingestion" and row["task"] == "classify" and row["mode"] == "live" and row["source"] == "live"
    assert row["status"] == "ok" and row["attempt"] == 1 and row["http_status"] == 200 and row["error_code"] is None
    assert (row["input_tokens"], row["output_tokens"], row["total_tokens"], row["cached_tokens"]) == (120, 8, 128, 64)
    assert row["ratelimit_remaining_tokens"] == 199872 and row["ratelimit_remaining_requests"] == 499
    assert row["latency_ms"] is not None and row["latency_ms"] >= 0
    assert row["case_ref"] == "BBG-2026-000021" and row["run_id"] == "run-1"
    assert row["provider"] == "openai" and row["model"] == cfg.llm.model
    assert row["request_key"] == recording_key("openai", cfg.llm.model, sent[0]["json"])
    # The same row as one JSON line; never the prompt, the answer or the key.
    assert lines == [row]
    text = json.dumps(lines)
    assert "Say which type" not in text and "company_pan" not in text and "sk-test" not in text


def test_a_retry_shows_as_two_rows(cfg, http):
    queue, _ = http
    queue.extend([(503, {"error": {"message": "overloaded"}}, {"retry-after": "2"}), (200, ANSWER, HEADERS)])
    store = Store()
    _client(cfg, "live", store).call(REQ)
    first, second = store.model_log()
    assert (first["attempt"], first["status"], first["http_status"], first["error_code"]) == (1, "error", 503, "http")
    # The wait chosen before the retry: the first backoff, within its jitter.
    lo, hi = (cfg.llm.retry.server_backoff_s[0] * (1 + s * cfg.llm.retry.backoff_jitter) for s in (-1, 1))
    assert lo <= first["retry_after_s"] <= hi and first["kind"] == "server_unavailable"
    assert first["input_tokens"] is None and "overloaded" in first["message"]
    assert (second["attempt"], second["status"], second["http_status"]) == (2, "ok", 200)


def test_a_connection_error_is_logged_by_its_class(cfg, http):
    queue, _ = http
    queue.extend([(httpx.ConnectError("refused"), None, None)] * cfg.llm.retry.server_attempts)
    store = Store()
    with pytest.raises(ModelError):
        _client(cfg, "live", store).call(REQ)
    rows = store.model_log()
    assert len(rows) == cfg.llm.retry.server_attempts
    assert all(r["status"] == "error" and r["error_code"] == "ConnectError" and r["http_status"] is None for r in rows)


def test_replay_hits_and_misses_each_give_a_row_with_no_tokens(cfg, http):
    store = Store()
    client = _client(cfg, "replay", store)
    with pytest.raises(ModelError) as e:
        client.call(REQ)
    assert e.value.code == "replay_miss"
    key = client.key_for(REQ)
    store.put_llm_call(key, {"provider": "openai", "model": cfg.llm.model, "task": "classify", "origin": "live",
                             "request": {}, "response": ANSWER})
    assert client.call(REQ) == {"type": "company_pan"}
    miss, hit = store.model_log()
    assert (miss["source"], miss["status"], miss["error_code"]) == ("replay_miss", "error", "replay_miss")
    assert (hit["source"], hit["status"]) == ("replay_hit", "ok")
    assert all(r["input_tokens"] is None and r["mode"] == "replay" and r["request_key"] == key for r in (miss, hit))
    assert http[1] == []  # nothing was sent


def test_record_mode_stores_the_same_recording_as_before(cfg, http):
    queue, sent = http
    queue.append((200, ANSWER, HEADERS))
    store = Store()
    _client(cfg, "record", store).call(REQ)
    body = sent[0]["json"]
    key = recording_key("openai", cfg.llm.model, body)
    rec = store.get_llm_call(key)
    assert rec == {"provider": "openai", "model": cfg.llm.model, "task": "classify", "origin": "live", "request": body,
                   "response": ANSWER}
    # The body sent is the one the provider has always built: nothing was added for the log.
    assert body == OpenAIProvider(cfg.llm, "x").build(REQ).body


def test_a_fixture_provider_still_works_and_is_logged(cfg):
    store = Store()
    client = ModelClient(FixtureProvider(cfg.llm, lambda req: {"type": "director_kyc"}), "record", store)
    assert client.call(REQ) == {"type": "director_kyc"}
    [row] = store.model_log()
    assert row["status"] == "ok" and row["source"] == "live" and row["input_tokens"] is None
    assert store.get_llm_call(client.key_for(REQ))["origin"] == "fixture"


def test_a_refusal_marks_its_attempt_failed_and_is_not_recorded(cfg, http):
    queue, _ = http
    queue.append((200, {"choices": [{"message": {"refusal": "cannot help"}}], "usage": {"prompt_tokens": 5}}, {}))
    store = Store()
    with pytest.raises(ModelError):
        _client(cfg, "record", store).call(REQ)
    [row] = store.model_log()
    assert row["status"] == "error" and row["error_code"] == "refusal" and row["input_tokens"] == 5
    assert store.get_llm_call(recording_key("openai", cfg.llm.model, OpenAIProvider(cfg.llm, "x").build(REQ).body)) is None


def test_no_key_is_one_error_row_and_nothing_sent(cfg, http):
    store = Store()
    with pytest.raises(ModelError) as e:
        _client(cfg, "live", store, key=None).call(REQ)
    assert e.value.code == "not_configured"
    [row] = store.model_log()
    assert row["error_code"] == "not_configured" and http[1] == []


def test_keys_are_redacted_from_messages():
    assert calllog.redact("bad key sk-proj-abcdef0123456789 given") == "bad key sk-[redacted] given"
    assert calllog.redact('{"api-key": "abc123secret"}') == '{"api-key": "[redacted]"}'
    assert calllog.redact("Authorization: Bearer abc.def-ghi") == "Authorization: Bearer [redacted]"
    assert len(calllog.redact("x" * 500)) == 300


def test_a_log_that_cannot_be_written_never_fails_the_call(cfg, http):
    queue, _ = http
    queue.append((200, ANSWER, HEADERS))

    class Broken(Store):
        def put_model_log(self, row):
            raise RuntimeError("disk full")

    assert _client(cfg, "live", Broken()).call(REQ) == {"type": "company_pan"}


def test_the_log_is_append_only():
    import sqlite3

    store = Store()
    calllog.write(store, {"id": "x", "at": "2026-11-13T00:00:00+00:00", "service": "ingestion", "source": "live",
                          "status": "ok"})
    with pytest.raises(sqlite3.DatabaseError):
        store._conn.execute("DELETE FROM model_log")
