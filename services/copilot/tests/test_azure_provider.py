"""Azure OpenAI as the case assistant's provider (config/llm.yaml `provider: azure`): the v1 API at
<endpoint>/openai/v1 with the key in an `api-key` header (no bearer token, no api-version), the deployment
named in the request, and the model id in the call log. OpenAI's requests and recording keys are exactly
what they were before Azure was added. The requests go to an httpx MockTransport: nothing leaves the test."""

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models import ModelRequestParameters

from copilot.config import LlmConfig, load_dir
from copilot.model_errors import ModelUnavailable, http_kind
from copilot.models import build_model
from copilot.recording import sampling_settings
from copilot.store import Store

CONFIG = Path(__file__).resolve().parent.parent / "config"
OPENAI = load_dir(CONFIG).llm
AZURE = OPENAI.model_copy(update={"provider": "azure", "base_url": "https://resource.openai.azure.com/openai/v1",
                                  "api_key_env": "AZURE_OPENAI_API_KEY", "deployment": "creditiq-runner",
                                  "router_model": "gpt-4.1-mini", "runner_model": "gpt-4.1-mini"})
NOW = lambda: "2026-11-16T10:00:00+00:00"  # noqa: E731
QUESTION = [ModelRequest(parts=[UserPromptPart("What is the turnover of the borrower?")])]

# The OpenAI request and its recording key for QUESTION, computed by the code as it was before the azure
# provider existed (commit c8d4bf0): they must not change.
OPENAI_KEY = "cf357d1c39331de5a8fa95c62f66a49519338af706a46ecdb901752e44d1dae1"
OPENAI_BODY_SHA = "ecdf0289aeccad09a4b9b563f6100d561f98dec48788b6766d64818f5cf6bcfb"


def completion(finish_reason="stop", content="Rs 4.2 crore."):
    return {"id": "c", "object": "chat.completion", "created": 0, "model": "gpt-4.1-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 8, "total_tokens": 128}}


class Transport:
    """Answers each request with the next queued (status, body, headers); keeps what was sent."""

    def __init__(self, *answers):
        self.queue, self.sent = list(answers), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        status, body, headers = self.queue.pop(0)
        return httpx.Response(status, json=body, headers=headers or {})

    def client(self):
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


class Clock:
    def __init__(self):
        self.t, self.slept = 1000.0, []

    async def sleep(self, s):
        self.slept.append(s)
        self.t += s

    def monotonic(self):
        return self.t


def ask(llm, transport, tmp_path, mode="record", clock=None):
    store = Store(tmp_path / "copilot.sqlite3")
    model = build_model(llm, "runner", store=store, mode=mode, now=NOW, http_client=transport.client())
    if clock:
        model._sleep, model._monotonic = clock.sleep, clock.monotonic
    asyncio.run(model.request(QUESTION, sampling_settings(llm), ModelRequestParameters()))
    return store


def rows(tmp_path, sql):
    db = sqlite3.connect(tmp_path / "copilot.sqlite3")
    db.row_factory = sqlite3.Row
    return [dict(r) for r in db.execute(sql)]


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")


def test_azure_sends_the_key_as_api_key_to_the_v1_url_and_names_the_deployment(tmp_path):
    t = Transport((200, completion(), None))
    ask(AZURE, t, tmp_path)
    [req] = t.sent
    assert str(req.url) == "https://resource.openai.azure.com/openai/v1/chat/completions"
    assert "api-version" not in str(req.url)
    assert req.headers["api-key"] == "azure-test-key" and "authorization" not in req.headers
    body = json.loads(req.content)
    assert body["model"] == "creditiq-runner"
    # Only the published sampling parameters, as for OpenAI.
    assert (body["temperature"], body["seed"]) == (AZURE.temperature, AZURE.seed)
    assert not {"top_p", "frequency_penalty", "presence_penalty", "n", "logit_bias"} & set(body)
    [log] = rows(tmp_path, "SELECT * FROM model_log")
    assert (log["provider"], log["model"], log["status"], log["input_tokens"]) == ("azure", "gpt-4.1-mini", "ok", 120)
    [rec] = rows(tmp_path, "SELECT * FROM llm_calls")
    assert rec["model"] == "gpt-4.1-mini" and rec["request_key"] == log["request_key"] != OPENAI_KEY


def test_openai_requests_and_recording_keys_are_as_before(tmp_path):
    t = Transport((200, completion(), None))
    ask(OPENAI, t, tmp_path)
    [req] = t.sent
    assert str(req.url) == "https://api.openai.com/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer sk-test-openai" and "api-key" not in req.headers
    body = json.loads(req.content)
    assert hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() == OPENAI_BODY_SHA
    [rec] = rows(tmp_path, "SELECT * FROM llm_calls")
    assert rec["request_key"] == OPENAI_KEY
    [log] = rows(tmp_path, "SELECT provider, model FROM model_log")
    assert log == {"provider": "openai", "model": "gpt-5.4-nano"}


def test_an_openai_recording_is_never_replayed_for_azure(tmp_path):
    ask(OPENAI, Transport((200, completion(), None)), tmp_path)
    with pytest.raises(Exception, match="no recording"):
        ask(AZURE, Transport(), tmp_path, mode="replay")


@pytest.mark.parametrize("message,header", [
    ("Requests to the ChatCompletions_Create Operation under Azure OpenAI API version 2025-04-01 have exceeded token rate "
     "limit of your current AIServices S0 pricing tier. Please retry after 7 seconds. Please go here: "
     "https://aka.ms/oai/quotaincrease if you would like to further increase the default rate limit.", {"retry-after": "7"}),
    ("Requests to the ChatCompletions_Create Operation under Azure OpenAI API version 2025-04-01 have exceeded call rate "
     "limit of your current AIServices S0 pricing tier. Please retry after 7 seconds. Please go here: "
     "https://aka.ms/oai/quotaincrease if you would like to further increase the default rate limit.", {"retry-after-ms": "7000"}),
])
def test_an_azure_rate_limit_is_a_per_minute_limit_waited_as_its_header_asks(tmp_path, message, header):
    body = {"error": {"code": "429", "message": message}}
    assert http_kind(429, body) == "rate_limit_minute"         # not quota, though the link says "quotaincrease"
    clock = Clock()
    t = Transport((429, body, header), (200, completion(), None))
    ask(AZURE, t, tmp_path, clock=clock)
    assert clock.slept == [7.0] and len(t.sent) == 2
    assert [r["kind"] for r in rows(tmp_path, "SELECT kind FROM model_log ORDER BY rowid")] == ["rate_limit_minute", None]


def test_a_prompt_azure_filters_is_not_retried(tmp_path):
    body = {"error": {"message": "The response was filtered due to the prompt triggering Azure OpenAI's content "
                                 "management policy.", "type": None, "param": "prompt", "code": "content_filter",
                      "status": 400, "innererror": {"code": "ResponsibleAIPolicyViolation",
                                                    "content_filter_result": {"hate": {"filtered": True, "severity": "high"}}}}}
    t = Transport((400, body, None))
    with pytest.raises(ModelUnavailable) as e:
        ask(AZURE, t, tmp_path, clock=Clock())
    assert e.value.kind == "content_filter" and len(t.sent) == 1


def test_an_answer_azure_filtered_is_neither_retried_nor_recorded(tmp_path):
    t = Transport((200, completion(finish_reason="content_filter", content=""), None))
    with pytest.raises(ModelUnavailable) as e:
        ask(AZURE, t, tmp_path, clock=Clock())
    assert e.value.kind == "content_filter" and len(t.sent) == 1
    assert rows(tmp_path, "SELECT * FROM llm_calls") == []
    [log] = rows(tmp_path, "SELECT status, kind FROM model_log")
    assert log == {"status": "error", "kind": "content_filter"}


def test_a_configuration_written_before_azure_still_loads_and_azure_needs_a_deployment():
    import yaml

    old = yaml.safe_load((CONFIG / "llm.yaml").read_text())
    for key in ("provider", "deployment"):    # neither existed before
        old.pop(key, None)
    llm = LlmConfig.model_validate(old)
    assert (llm.provider, llm.deployment) == ("openai", None)
    with pytest.raises(ValueError, match="deployment"):
        LlmConfig.model_validate({**old, "provider": "azure"})
