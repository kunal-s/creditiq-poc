"""Retries by the kind of failure (llm/errors.py, `retry:` in config/ingestion/llm.yaml): a per-minute limit
waits what it is asked, up to max_wait_s; a server that is down is tried again with a jittered backoff and
never waited after the last attempt; a quota, auth, missing model or filtered content is not retried; the
breaker fails calls at once while the server is down, then lets one trial through. Nothing really waits:
the clock and the sleep are fakes."""

import json
from pathlib import Path

import httpx
import pytest
import yaml

from ingestion.config.loader import load_dir
from ingestion.config.models import LlmConfig
from ingestion.llm import openai as openai_mod
from ingestion.llm.openai import OpenAIProvider
from ingestion.llm.provider import ModelError, ModelRequest
from ingestion.llm.recorder import ModelClient
from ingestion.stages import transactions as T
from ingestion.store import Store

CONFIG = Path(__file__).resolve().parents[3] / "config" / "ingestion"
REQ = ModelRequest("classify", "s", "u", {"type": "object", "properties": {"type": {"type": "string"}},
                                          "required": ["type"], "additionalProperties": False})
OK = {"choices": [{"message": {"content": json.dumps({"type": "company_pan"})}}], "usage": {"prompt_tokens": 10}}


@pytest.fixture(scope="module")
def cfg():
    return load_dir(CONFIG, version="test")


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


@pytest.fixture()
def http(monkeypatch):
    queue: list = []
    sent: list = []

    def post(url, json=None, timeout=None, headers=None):
        sent.append(json)
        status, body, hdrs = queue.pop(0)
        if isinstance(status, Exception):
            raise status
        return httpx.Response(status, json=body, headers=hdrs or {}, request=httpx.Request("POST", url))

    monkeypatch.setattr(openai_mod.httpx, "post", post)
    return queue, sent


def client(cfg, store, clock, rand=None):
    p = OpenAIProvider(cfg.llm, "sk-test", sleep=clock.sleep, monotonic=clock.monotonic,
                       **({"rand": rand} if rand else {}))
    return ModelClient(p, "live", store)


def err(code, message=""):
    return {"error": {"code": code, "message": message}}


def test_a_per_minute_limit_waits_what_it_asks_then_answers(cfg, http):
    queue, _ = http
    queue.extend([(429, err("rate_limit_exceeded", "Rate limit reached on tokens per min (TPM)"), {"retry-after": "7"}),
                  (200, OK, None)])
    store, clock = Store(), Clock()
    assert client(cfg, store, clock).call(REQ) == {"type": "company_pan"}
    assert clock.slept == [7.0]
    first, second = store.model_log()
    assert (first["kind"], first["retry_after_s"], second["status"]) == ("rate_limit_minute", 7.0, "ok")


def test_a_per_minute_limit_naming_no_wait_waits_the_configured_time(cfg, http):
    queue, _ = http
    queue.extend([(429, err("rate_limit_exceeded"), None), (200, OK, None)])
    clock = Clock()
    client(cfg, Store(), clock).call(REQ)
    assert clock.slept == [cfg.llm.retry.rate_limit_wait_s]


def test_a_wait_longer_than_allowed_is_not_waited(cfg, http):
    queue, sent = http
    queue.append((429, err("rate_limit_exceeded"), {"retry-after": "300"}))
    store, clock = Store(), Clock()
    with pytest.raises(ModelError) as e:
        client(cfg, store, clock).call(REQ)
    assert e.value.kind == "rate_limit_minute" and e.value.code == "http" and "300 s" in str(e.value)
    assert clock.slept == [] and len(sent) == 1


def test_an_exhausted_quota_is_not_retried(cfg, http):
    queue, sent = http
    queue.append((429, err("insufficient_quota", "You exceeded your current quota"), None))
    store, clock = Store(), Clock()
    with pytest.raises(ModelError) as e:
        client(cfg, store, clock).call(REQ)
    assert e.value.kind == "quota" and len(sent) == 1 and clock.slept == []
    assert store.model_log()[0]["kind"] == "quota"


def test_a_server_that_is_down_is_tried_with_backoff_and_never_waited_after_the_last(cfg, http):
    queue, sent = http
    policy = cfg.llm.retry
    queue.extend([(503, err("server_error"), None)] * policy.server_attempts)
    store, clock = Store(), Clock()
    with pytest.raises(ModelError) as e:
        client(cfg, store, clock).call(REQ)
    assert e.value.kind == "server_unavailable" and len(sent) == policy.server_attempts
    assert len(clock.slept) == policy.server_attempts - 1           # no wait after the last attempt
    for wait, base in zip(clock.slept, policy.server_backoff_s):
        assert base * (1 - policy.backoff_jitter) <= wait <= base * (1 + policy.backoff_jitter)
    assert [r["kind"] for r in store.model_log()] == ["server_unavailable"] * policy.server_attempts


@pytest.mark.parametrize("answer,kind", [
    ((httpx.ReadTimeout("read timed out"), None, None), "timeout"),
    ((401, err("invalid_api_key"), None), "auth"),
    ((404, err("model_not_found"), None), "not_configured"),
    ((400, err("content_filter", "The response was filtered"), None), "content_filter"),
    ((422, err("invalid"), None), "bad_request"),
])
def test_each_failure_has_its_kind(cfg, http, answer, kind):
    queue, sent = http
    queue.extend([answer] * cfg.llm.retry.server_attempts)
    with pytest.raises(ModelError) as e:
        client(cfg, Store(), Clock()).call(REQ)
    assert e.value.kind == kind
    assert len(sent) == (cfg.llm.retry.server_attempts if kind == "timeout" else 1)


def test_the_breaker_fails_calls_at_once_then_lets_one_trial_through(cfg, http):
    queue, sent = http
    policy = cfg.llm.retry
    store, clock = Store(), Clock()
    c = client(cfg, store, clock)
    queue.extend([(503, err("server_error"), None)] * policy.breaker_failures)
    while len(sent) < policy.breaker_failures:
        with pytest.raises(ModelError):
            c.call(REQ)
    # Open: the next call fails at once, with no request sent.
    with pytest.raises(ModelError) as e:
        c.call(REQ)
    assert e.value.kind == "server_unavailable" and len(sent) == policy.breaker_failures
    assert store.model_log()[-1]["http_status"] is None
    # After the cooldown one trial goes through; answered, the breaker closes.
    clock.t += policy.breaker_cooldown_s
    queue.append((200, OK, None))
    assert c.call(REQ) == {"type": "company_pan"} and len(sent) == policy.breaker_failures + 1


def test_a_failed_trial_opens_the_breaker_again(cfg, http):
    queue, sent = http
    policy = cfg.llm.retry
    clock = Clock()
    c = client(cfg, Store(), clock)
    queue.extend([(503, err("server_error"), None)] * (policy.breaker_failures + 1))
    while len(sent) < policy.breaker_failures:
        with pytest.raises(ModelError):
            c.call(REQ)
    clock.t += policy.breaker_cooldown_s
    with pytest.raises(ModelError):
        c.call(REQ)                     # the trial fails
    n = len(sent)
    with pytest.raises(ModelError):
        c.call(REQ)                     # open again: nothing sent
    assert len(sent) == n


def test_a_version_published_before_the_retry_block_still_loads():
    llm = yaml.safe_load((CONFIG / "llm.yaml").read_text())
    llm.pop("retry")
    llm["max_retries"] = 4
    old = LlmConfig.model_validate(llm)
    assert old.retry.server_attempts == 5 and old.retry.rate_limit_wait_s == 60
    llm.pop("max_retries")
    assert LlmConfig.model_validate(llm).retry.server_attempts == 3


def test_a_failed_transactions_batch_leaves_the_others_kept(cfg, http):
    queue, _ = http
    narrow = cfg.model_copy(deep=True)
    narrow.llm.transactions.batch_size = 1

    def answer(key, cat):
        return (200, {"choices": [{"message": {"content": json.dumps(
            {"results": [{"key": key, "category": cat, "confidence": "high", "reason": "named"}]})}}]}, None)

    queue.extend([answer("a", "customer_receipt"), *[(503, err("server_error"), None)] * narrow.llm.retry.server_attempts,
                  answer("c", "customer_receipt")])
    req = T.ClassifyRequest(categories=[T.Category(id="customer_receipt", direction="credit", label="Customer receipt")],
                            items=[T.Item(key=k, direction="credit", narration=f"by transfer {k}", amount=100) for k in "abc"])
    out = T.classify(narrow, client(narrow, Store(), Clock()), req)
    by = {r.key: r for r in out.results}
    assert out.failed_batches == 1
    assert by["a"].category == by["c"].category == "customer_receipt"
    assert by["b"].category == "unknown" and by["b"].reason == "model_unavailable:server_unavailable"
