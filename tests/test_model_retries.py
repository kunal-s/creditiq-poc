"""The CAM copilot's model call under the retry policy (config/cam.yaml `copilot.retry`, engine/model_retry.py):
a per-minute limit waits what it asks, a server that is down is tried again with backoff, an auth failure is
not retried, the breaker fails a call at once, and the screen is told the kind of failure. Nothing really
waits: the clock and the sleep are fakes."""

import io
import json
import urllib.error
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from engine import cam_copilot, db
from engine.configstore.schema import CamCopilotConfig
from tests.test_cam_review import _case

ANSWER = {"choices": [{"message": {"content": json.dumps({"paragraphs": ["Redrafted."]})}}], "usage": {"prompt_tokens": 9}}


class _Resp(io.BytesIO):
    status = 200
    headers: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(code, body=None, headers=None):
    return urllib.error.HTTPError("https://x/chat/completions", code, "err", headers or {},
                                  io.BytesIO(json.dumps(body or {"error": {"code": "x"}}).encode()))


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
    monkeypatch.setattr(cam_copilot.urllib.request, "urlopen", urlopen)
    return queue, sent


def _regen(client, h, case_id, instruction):
    return client.post(f"/api/cases/{case_id}/cam/sections/analysis/regenerate", json={"instruction": instruction}, headers=h)


def _kinds(root: Path) -> list:
    conn = db.connect(root)
    try:
        return [r["kind"] for r in conn.execute("SELECT kind FROM model_log ORDER BY at, rowid")]
    finally:
        conn.close()


def test_a_per_minute_limit_waits_then_answers(client, analyst, published_data_root, clock, answers):
    queue, sent = answers
    queue.extend([_http(429, {"error": {"code": "rate_limit_exceeded"}}, {"retry-after": "7"}), ANSWER])
    case_id = _case(client, analyst, published_data_root)
    assert _regen(client, analyst, case_id, "Shorter.").status_code == 200
    assert clock["slept"] == [7.0] and len(sent) == 2
    assert _kinds(published_data_root) == ["rate_limit_minute", None]


def test_a_server_that_is_down_is_retried_then_reported_by_kind(client, analyst, published_data_root, clock, answers):
    queue, sent = answers
    queue.extend([_http(503)] * 3)
    case_id = _case(client, analyst, published_data_root)
    r = _regen(client, analyst, case_id, "Shorter.")
    assert r.status_code == 502 and r.json()["detail"]["kind"] == "server_unavailable"
    assert len(sent) == 3 and len(clock["slept"]) == 2
    assert 2 * 0.8 <= clock["slept"][0] <= 2 * 1.2 and 4 * 0.8 <= clock["slept"][1] <= 4 * 1.2


def test_an_auth_failure_is_not_retried(client, analyst, published_data_root, clock, answers):
    queue, sent = answers
    queue.append(_http(401, {"error": {"code": "invalid_api_key"}}))
    case_id = _case(client, analyst, published_data_root)
    r = _regen(client, analyst, case_id, "Shorter.")
    assert r.json()["detail"]["kind"] == "auth" and len(sent) == 1 and clock["slept"] == []


def test_the_breaker_fails_at_once_after_repeated_failures(client, analyst, published_data_root, clock, answers):
    queue, sent = answers
    queue.extend([_http(503)] * 6)
    case_id = _case(client, analyst, published_data_root)
    _regen(client, analyst, case_id, "One.")          # 3 failures
    _regen(client, analyst, case_id, "Two.")          # 2 more: the breaker opens
    n = len(sent)
    r = _regen(client, analyst, case_id, "Three.")
    assert r.json()["detail"]["kind"] == "server_unavailable" and len(sent) == n


def test_a_cam_section_published_before_the_retry_block_still_loads():
    cam = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "cam.yaml").read_text())["copilot"]
    cam.pop("retry")
    assert CamCopilotConfig.model_validate(cam).retry.server_attempts == 3
    assert CamCopilotConfig.model_validate({**cam, "max_retries": 1}).retry.server_attempts == 2
