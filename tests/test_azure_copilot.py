"""Azure OpenAI as the memo copilot's provider (config/cam.yaml `copilot.provider: azure`): the v1 API at
<endpoint>/openai/v1 with the key in an `api-key` header (no bearer token, no api-version), the deployment
named in the request and the model id in the call log. OpenAI's request and its recording hash are exactly
what they were before Azure was added. A rate limit whose message links to a "quotaincrease" page is still a
per-minute limit; a filtered answer is a content_filter failure, never retried or kept. Nothing leaves the
test: urlopen is a fake and so are the clock and the sleep."""

import hashlib
import io
import json
import urllib.error
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from engine import cam_copilot, db, model_retry
from engine.configstore import reader as configstore_reader
from engine.configstore.schema import CamCopilotConfig
from tests.test_cam_review import _case

ANSWER = {"choices": [{"message": {"content": json.dumps({"paragraphs": ["Redrafted."]})}, "finish_reason": "stop"}],
          "usage": {"prompt_tokens": 300, "completion_tokens": 40, "total_tokens": 340}}
FIXED_BODY = {"model": "gpt-5.4-nano", "messages": [{"role": "user", "content": "Redraft."}], "temperature": 0, "seed": 1}
# The recording hash of FIXED_BODY as the copilot computed it before the azure provider existed (commit c8d4bf0:
# the sha256 of the body's sorted JSON). It must not change for OpenAI.
OPENAI_HASH = hashlib.sha256(json.dumps(FIXED_BODY, sort_keys=True).encode()).hexdigest()
AZURE = {"provider": "azure", "base_url": "https://resource.openai.azure.com/openai/v1",
         "api_key_env": "AZURE_OPENAI_API_KEY", "deployment": "creditiq-memo", "model": "gpt-4.1-mini"}


class _Resp(io.BytesIO):
    status = 200
    headers: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(code, body, headers=None):
    return urllib.error.HTTPError("https://x/chat/completions", code, "err", headers or {}, io.BytesIO(json.dumps(body).encode()))


@pytest.fixture
def analyst(client: TestClient) -> dict:
    from tests.conftest import ANALYST, sign_in

    return sign_in(client, ANALYST)


@pytest.fixture
def clock(monkeypatch):
    state = {"t": 1000.0, "slept": []}

    def sleep(s):
        state["slept"].append(s)
        state["t"] += s

    monkeypatch.setattr(cam_copilot, "_sleep", sleep)
    monkeypatch.setattr(cam_copilot, "_monotonic", lambda: state["t"])
    return state


@pytest.fixture
def answers(monkeypatch):
    queue: list = []
    sent: list = []

    def urlopen(req, timeout=None):
        sent.append(req)
        a = queue.pop(0)
        if isinstance(a, Exception):
            raise a
        return _Resp(json.dumps(a).encode())

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-0123456789abcdef")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")
    monkeypatch.setattr(cam_copilot.urllib.request, "urlopen", urlopen)
    return queue, sent


@pytest.fixture
def on_azure(monkeypatch):
    """The published cam section with its copilot switched to the Azure deployment."""
    real = configstore_reader.load_cam

    def load(root):
        cam = real(root)
        return cam.model_copy(update={"copilot": CamCopilotConfig.model_validate({**cam.copilot.model_dump(), **AZURE})})

    monkeypatch.setattr(configstore_reader, "load_cam", load)


def _regen(client, h, case_id, instruction="Shorter."):
    return client.post(f"/api/cases/{case_id}/cam/sections/analysis/regenerate", json={"instruction": instruction}, headers=h)


def _query(root: Path, sql: str) -> list[dict]:
    conn = db.connect(root)
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def test_azure_sends_the_key_as_api_key_to_the_v1_url_and_names_the_deployment(
        client, analyst, published_data_root, clock, answers, on_azure):
    queue, sent = answers
    queue.append(ANSWER)
    case_id = _case(client, analyst, published_data_root)
    assert _regen(client, analyst, case_id).status_code == 200
    [req] = sent
    assert req.full_url == "https://resource.openai.azure.com/openai/v1/chat/completions" and "api-version" not in req.full_url
    assert req.get_header("Api-key") == "azure-test-key" and req.get_header("Authorization") is None
    body = json.loads(req.data)
    assert body["model"] == "creditiq-memo"
    assert not {"top_p", "frequency_penalty", "presence_penalty", "n", "logit_bias"} & set(body)
    [log] = _query(published_data_root, "SELECT * FROM model_log")
    assert (log["provider"], log["model"], log["status"], log["input_tokens"]) == ("azure", "gpt-4.1-mini", "ok", 300)
    [kept] = _query(published_data_root, "SELECT request_hash FROM cam_model_calls")
    # Azure's recording names the provider: never the hash OpenAI would give the same body.
    assert kept["request_hash"] == log["request_key"] != hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def test_openai_requests_and_recording_hashes_are_as_before(client, analyst, published_data_root, clock, answers):
    queue, sent = answers
    queue.append(ANSWER)
    case_id = _case(client, analyst, published_data_root)
    assert _regen(client, analyst, case_id).status_code == 200
    [req] = sent
    assert req.full_url == "https://api.openai.com/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer sk-test-0123456789abcdef" and req.get_header("Api-key") is None
    body = json.loads(req.data)
    assert body["model"] == "gpt-5.4-nano"
    [kept] = _query(published_data_root, "SELECT request_hash FROM cam_model_calls")
    assert kept["request_hash"] == hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    openai_cfg = CamCopilotConfig(enabled=True, model="gpt-5.4-nano")
    assert cam_copilot._request_hash(openai_cfg, FIXED_BODY) == OPENAI_HASH


@pytest.mark.parametrize("limit,header", [("token", {"retry-after": "7"}), ("call", {"retry-after-ms": "7000"})])
def test_an_azure_rate_limit_is_a_per_minute_limit_waited_as_its_header_asks(
        client, analyst, published_data_root, clock, answers, on_azure, limit, header):
    message = (f"Requests to the ChatCompletions_Create Operation under Azure OpenAI API version 2025-04-01 have exceeded "
               f"{limit} rate limit of your current AIServices S0 pricing tier. Please retry after 7 seconds. Please go "
               "here: https://aka.ms/oai/quotaincrease if you would like to further increase the default rate limit.")
    body = {"error": {"code": "429", "message": message}}
    assert model_retry.http_kind(429, json.dumps(body)) == "rate_limit_minute"
    queue, sent = answers
    queue.extend([_http(429, body, header), ANSWER])
    case_id = _case(client, analyst, published_data_root)
    assert _regen(client, analyst, case_id).status_code == 200
    assert clock["slept"] == [7.0] and len(sent) == 2


def test_a_prompt_azure_filters_is_not_retried(client, analyst, published_data_root, clock, answers, on_azure):
    body = {"error": {"message": "The response was filtered due to the prompt triggering Azure OpenAI's content "
                                 "management policy.", "type": None, "param": "prompt", "code": "content_filter",
                      "status": 400, "innererror": {"code": "ResponsibleAIPolicyViolation"}}}
    queue, sent = answers
    queue.append(_http(400, body))
    case_id = _case(client, analyst, published_data_root)
    r = _regen(client, analyst, case_id)
    assert r.status_code == 502 and r.json()["detail"]["kind"] == "content_filter" and len(sent) == 1


def test_an_answer_azure_filtered_is_neither_retried_nor_kept(client, analyst, published_data_root, clock, answers, on_azure):
    queue, sent = answers
    queue.append({"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]})
    case_id = _case(client, analyst, published_data_root)
    r = _regen(client, analyst, case_id)
    assert r.status_code == 502 and r.json()["detail"]["kind"] == "content_filter" and len(sent) == 1
    assert _query(published_data_root, "SELECT * FROM cam_model_calls") == []
    [log] = _query(published_data_root, "SELECT status, kind FROM model_log")
    assert log == {"status": "error", "kind": "content_filter"}


def test_a_cam_section_published_before_azure_still_loads_and_azure_needs_a_deployment():
    cam = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "cam.yaml").read_text())["copilot"]
    for key in ("provider", "deployment"):    # neither existed before
        cam.pop(key, None)
    copilot = CamCopilotConfig.model_validate(cam)
    assert (copilot.provider, copilot.deployment) == ("openai", None)
    with pytest.raises(ValueError, match="deployment"):
        CamCopilotConfig.model_validate({**cam, "provider": "azure"})
