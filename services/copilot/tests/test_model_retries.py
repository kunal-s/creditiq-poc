"""Retries of a model request inside RecordingModel, by the kind of failure and the published policy
(config/llm.yaml `retry`, copilot/model_errors.py): the SDK's own retries are off, a per-minute limit waits
what it asks, a server that is down is tried with backoff, a request that still fails is raised with its
kind, and the chat says the configured words for it. Nothing really waits."""

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from copilot.api import create_app
from copilot.config import load_dir
from copilot.identity import HostIdentity
from copilot.model_errors import ModelUnavailable
from copilot.models import build_model
from copilot.recording import RecordingModel, sampling_settings
from copilot.settings import Settings
from copilot.store import Store
from tests.test_api import chat, events, host

CFG = load_dir(Path(__file__).resolve().parent.parent / "config")
LLM = CFG.llm
NOW = lambda: "2026-11-13T10:00:00+00:00"  # noqa: E731


class Clock:
    def __init__(self):
        self.t, self.slept = 1000.0, []

    async def sleep(self, s):
        self.slept.append(s)
        self.t += s

    def monotonic(self):
        return self.t


def failing(*errors):
    queue = list(errors)

    def fn(messages, info):
        e = queue.pop(0)
        if isinstance(e, Exception):
            raise e
        return ModelResponse(parts=[TextPart("ok")])

    return fn


def model(store, fn, clock, role="runner"):
    return RecordingModel(FunctionModel(fn), llm=LLM, store=store, mode="live", now=NOW, role=role,
                          sleep=clock.sleep, monotonic=clock.monotonic)


def agent(m):
    return Agent(m, instructions="explain", model_settings=sampling_settings(LLM))


def http(status, code=None, headers=None):
    return ModelHTTPError(status, "gpt-test", body={"error": {"code": code}}, headers=headers or {}, provider_error_code=code)


async def test_a_per_minute_limit_waits_then_answers():
    store, clock = Store(":memory:"), Clock()
    out = await agent(model(store, failing(http(429, "rate_limit_exceeded", {"retry-after": "7"}), "ok"), clock)).run("why?")
    assert out.output == "ok" and clock.slept == [7.0]
    assert [r["kind"] for r in store.model_log()] == ["rate_limit_minute", None]


async def test_a_server_that_is_down_is_retried_then_raised_with_its_kind():
    store, clock = Store(":memory:"), Clock()
    with pytest.raises(ModelUnavailable) as e:
        await agent(model(store, failing(*[http(503)] * LLM.retry.server_attempts), clock)).run("why?")
    assert e.value.kind == "server_unavailable" and len(clock.slept) == LLM.retry.server_attempts - 1
    assert len(store.model_log()) == LLM.retry.server_attempts


async def test_a_quota_is_not_retried():
    store, clock = Store(":memory:"), Clock()
    with pytest.raises(ModelUnavailable) as e:
        await agent(model(store, failing(http(429, "insufficient_quota")), clock)).run("why?")
    assert e.value.kind == "quota" and clock.slept == []


def test_the_sdk_retries_are_off_and_the_timeout_is_the_configured_one():
    m = build_model(LLM, "runner", store=Store(":memory:"), mode="replay", now=NOW)
    client = m.wrapped.client
    assert client.max_retries == 0 and client.timeout == LLM.timeout_s


def test_the_chat_says_the_configured_words_for_the_kind(tmp_path):
    clock = Clock()
    down = model(Store(":memory:"), failing(*[http(503)] * LLM.retry.server_attempts), clock, role="router")
    app = create_app(Settings(Path("."), tmp_path), cfg=CFG, router_model=down, runner_model=down,
                     identity=HostIdentity(CFG.host, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(host))))
    last = events(chat(TestClient(app), context={"case_id": "1"}))[-1]
    assert last == ("error", {"code": "model_unavailable", "kind": "server_unavailable",
                              "message": CFG.runtime.messages.model_errors["default"]})


def test_an_older_llm_section_with_max_retries_still_loads():
    from copilot.config import LlmConfig

    old = {"base_url": "https://x", "api_key_env": "K", "router_model": "m", "runner_model": "m", "max_retries": 2}
    assert LlmConfig.model_validate(old).retry.server_attempts == 3
