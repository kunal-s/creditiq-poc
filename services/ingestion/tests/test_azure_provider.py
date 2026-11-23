"""Azure OpenAI as the document-processing service's provider (config/ingestion/llm.yaml `provider: azure`):
the v1 API at <endpoint>/openai/v1 with the key in an `api-key` header (no bearer token, no api-version), the
deployment named in the request and the model id in the call log and the recordings. OpenAI's requests and
recording keys are exactly what they were before Azure was added. Azure's own answers: a rate limit whose
message links to a "quotaincrease" page is still a per-minute limit; a filtered prompt (400) or a filtered
answer (200, finish_reason content_filter) is a content_filter failure, never retried or recorded."""

import json
from pathlib import Path

import httpx
import pytest
import yaml

from ingestion.config.loader import load_dir
from ingestion.config.models import LlmConfig
from ingestion.llm import openai as openai_mod
from ingestion.llm.errors import http_kind
from ingestion.llm.openai import OpenAIProvider
from ingestion.llm.provider import ModelError, ModelRequest
from ingestion.llm.recorder import ModelClient
from ingestion.store import Store

CONFIG = Path(__file__).resolve().parents[3] / "config" / "ingestion"
REQ = ModelRequest("classify", "s", "u", {"type": "object", "properties": {"type": {"type": "string"}},
                                          "required": ["type"], "additionalProperties": False})
# The OpenAI request for REQ and its recording key, computed by the code as it was before the azure
# provider existed (commit c8d4bf0): they must not change.
OPENAI_KEY = "03d4c9cc951ae95615de61f5b8f4e7e93fe839642f382c3267980e1f3faba655"
OPENAI_BODY_SHA = "c542e459c15f4ecc97312966414e63a90c896b3133a0d83e2e77cd82b17f6dd1"


def ok(finish_reason="stop", content=None):
    return {"choices": [{"message": {"content": json.dumps({"type": "company_pan"}) if content is None else content},
                         "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 6, "total_tokens": 56}}


@pytest.fixture(scope="module")
def cfg():
    return load_dir(CONFIG, version="test")


@pytest.fixture()
def azure(cfg):
    llm = cfg.llm.model_copy(update={"provider": "azure", "base_url": "https://resource.openai.azure.com/openai/v1",
                                     "api_key_env": "AZURE_OPENAI_API_KEY", "deployment": "creditiq-docs",
                                     "model": "gpt-4.1-mini"})
    return llm


class Clock:
    def __init__(self):
        self.t, self.slept = 1000.0, []

    def monotonic(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


@pytest.fixture()
def http(monkeypatch):
    queue: list = []
    sent: list = []

    def post(url, json=None, timeout=None, headers=None):
        sent.append({"url": url, "body": json, "headers": headers})
        status, body, hdrs = queue.pop(0)
        return httpx.Response(status, json=body, headers=hdrs or {}, request=httpx.Request("POST", url))

    monkeypatch.setattr(openai_mod.httpx, "post", post)
    return queue, sent


def client(llm, store, mode="record", clock=None, key="azure-test-key"):
    clock = clock or Clock()
    return ModelClient(OpenAIProvider(llm, key, sleep=clock.sleep, monotonic=clock.monotonic), mode, store)


def test_azure_sends_the_key_as_api_key_to_the_v1_url_and_names_the_deployment(azure, http):
    queue, sent = http
    queue.append((200, ok(), None))
    store = Store()
    assert client(azure, store).call(REQ) == {"type": "company_pan"}
    [s] = sent
    assert s["url"] == "https://resource.openai.azure.com/openai/v1/chat/completions" and "api-version" not in s["url"]
    assert s["headers"] == {"api-key": "azure-test-key"}
    assert s["body"]["model"] == "creditiq-docs"
    # Nothing else in the request differs from OpenAI's: only the model the body names.
    openai_body = OpenAIProvider(azure.model_copy(update={"provider": "openai"}), "k").build(REQ).body
    assert {**s["body"], "model": openai_body["model"]} == openai_body
    [log] = store.model_log()
    assert (log["provider"], log["model"], log["status"], log["input_tokens"]) == ("azure", "gpt-4.1-mini", "ok", 50)
    rec = store.get_llm_call(log["request_key"])
    assert rec["provider"] == "azure" and rec["model"] == "gpt-4.1-mini" and log["request_key"] != OPENAI_KEY


def test_openai_requests_and_recording_keys_are_as_before(cfg, http):
    queue, sent = http
    queue.append((200, ok(), None))
    store = Store()
    c = client(cfg.llm, store, key="sk-test")
    assert c.key_for(REQ) == OPENAI_KEY
    c.call(REQ)
    [s] = sent
    assert s["url"] == "https://api.openai.com/v1/chat/completions"
    assert s["headers"] == {"Authorization": "Bearer sk-test"}
    import hashlib

    assert hashlib.sha256(json.dumps(s["body"], sort_keys=True).encode()).hexdigest() == OPENAI_BODY_SHA
    assert store.model_log()[0]["provider"] == "openai"


def test_an_openai_recording_is_never_replayed_for_azure(cfg, azure, http):
    queue, _ = http
    queue.append((200, ok(), None))
    store = Store()
    client(cfg.llm.model_copy(update={"model": "gpt-4.1-mini"}), store, key="sk-test").call(REQ)
    with pytest.raises(ModelError) as e:
        client(azure, store, mode="replay").call(REQ)
    assert e.value.code == "replay_miss"


@pytest.mark.parametrize("limit,header", [("token", {"retry-after": "7"}), ("call", {"retry-after-ms": "7000"})])
def test_an_azure_rate_limit_is_a_per_minute_limit_waited_as_its_header_asks(azure, http, limit, header):
    message = (f"Requests to the ChatCompletions_Create Operation under Azure OpenAI API version 2025-04-01 have exceeded "
               f"{limit} rate limit of your current AIServices S0 pricing tier. Please retry after 7 seconds. Please go "
               "here: https://aka.ms/oai/quotaincrease if you would like to further increase the default rate limit.")
    body = {"error": {"code": "429", "message": message}}
    assert http_kind(429, json.dumps(body)) == "rate_limit_minute"   # not quota, though the link says "quotaincrease"
    queue, sent = http
    queue.extend([(429, body, header), (200, ok(), None)])
    store, clock = Store(), Clock()
    client(azure, store, clock=clock).call(REQ)
    assert clock.slept == [7.0] and len(sent) == 2
    assert [r["kind"] for r in store.model_log()] == ["rate_limit_minute", None]


def test_a_prompt_azure_filters_is_not_retried(azure, http):
    body = {"error": {"message": "The response was filtered due to the prompt triggering Azure OpenAI's content "
                                 "management policy.", "type": None, "param": "prompt", "code": "content_filter",
                      "status": 400, "innererror": {"code": "ResponsibleAIPolicyViolation",
                                                    "content_filter_result": {"hate": {"filtered": True, "severity": "high"}}}}}
    queue, sent = http
    queue.append((400, body, None))
    with pytest.raises(ModelError) as e:
        client(azure, Store()).call(REQ)
    assert (e.value.code, e.value.kind, len(sent)) == ("http", "content_filter", 1)


def test_an_answer_azure_filtered_is_neither_retried_nor_recorded(azure, http):
    queue, sent = http
    queue.append((200, ok(finish_reason="content_filter", content=""), None))
    store = Store()
    c = client(azure, store)
    with pytest.raises(ModelError) as e:
        c.call(REQ)
    assert (e.value.code, e.value.kind, len(sent)) == ("refusal", "content_filter", 1)
    [log] = store.model_log()
    assert (log["status"], log["kind"]) == ("error", "content_filter")
    assert store.get_llm_call(log["request_key"]) is None


def test_a_version_published_before_azure_still_loads_and_azure_needs_a_deployment():
    old = yaml.safe_load((CONFIG / "llm.yaml").read_text())
    for key in ("provider", "deployment"):    # neither existed before
        old.pop(key, None)
    llm = LlmConfig.model_validate(old)
    assert (llm.provider, llm.deployment) == ("openai", None)
    with pytest.raises(ValueError, match="deployment"):
        LlmConfig.model_validate({**old, "provider": "azure"})


def test_the_service_reads_with_the_model_on_an_azure_configuration(tmp_path, monkeypatch):
    """Through the service's own API: a version naming Azure gets a model (it is not read by rules alone), and
    the transactions endpoint asks the deployment. A version naming no provider gets none."""
    import re
    import shutil

    from fastapi.testclient import TestClient

    from ingestion.api import create_app, model_client
    from ingestion.config import loader
    from ingestion.settings import Settings
    from tests.test_transactions import CATEGORIES, ROWS

    monkeypatch.setattr(loader, "_build", loader._build.unpinned)    # this test is of another provider
    cfgdir = tmp_path / "config"
    shutil.copytree(CONFIG, cfgdir)
    llm = yaml.safe_load((cfgdir / "llm.yaml").read_text())
    llm.update(provider="azure", base_url="https://resource.openai.azure.com/openai/v1", api_key_env="AZURE_OPENAI_API_KEY",
               deployment="creditiq-docs", model="gpt-4.1-mini")
    (cfgdir / "llm.yaml").write_text(yaml.safe_dump(llm, sort_keys=False))
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")
    sent: list = []

    def post(url, json=None, timeout=None, headers=None):
        sent.append({"url": url, "body": json, "headers": headers})
        keys = re.findall(r'"key": ?"([^"]+)"', json["messages"][1]["content"])
        answer = {"results": [{"key": k, "category": "unknown", "confidence": "low", "reason": "not stated"} for k in keys]}
        return httpx.Response(200, json={"choices": [{"message": {"content": __import__("json").dumps(answer)},
                                                      "finish_reason": "stop"}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(openai_mod.httpx, "post", post)
    store = Store()
    app = TestClient(create_app(Settings(tmp_path, cfgdir, "127.0.0.1", 0, "", "record"), store))
    r = app.post("/v1/classify-transactions", json={"config_version": "dev", "categories": [c.model_dump() for c in CATEGORIES],
                                                    "items": [i.model_dump() for i in ROWS]})
    assert r.status_code == 200, r.text
    assert sent and all(s["url"] == "https://resource.openai.azure.com/openai/v1/chat/completions" for s in sent)
    assert all(s["headers"] == {"api-key": "azure-test-key"} and s["body"]["model"] == "creditiq-docs" for s in sent)
    assert {(x["provider"], x["model"], x["task"]) for x in store.model_log()} == {("azure", "gpt-4.1-mini", "transactions")}

    azure = load_dir(cfgdir, version="dev")
    assert model_client(azure, "replay", store).name == "azure:gpt-4.1-mini"
    stub = azure.model_copy(update={"llm": azure.llm.model_copy(update={"provider": "stub"})})
    assert model_client(stub, "replay", store) is None
