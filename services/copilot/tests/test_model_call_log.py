"""The case assistant's model call log (copilot/calllog.py): every model request writes a row with its
tokens and latency; a ModelHTTPError writes an error row and is raised as before; replays are logged
with no tokens; a turn's calls carry the turn id and the open case. Recordings are unchanged by it."""

import json
import logging
from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from copilot import calllog
from copilot.config import load_dir
from copilot.model_errors import ModelUnavailable
from copilot.recording import RecordingModel, ReplayMiss, sampling_settings
from copilot.store import Store

LLM = load_dir(Path(__file__).resolve().parent.parent / "config").llm
NOW = lambda: "2026-11-13T10:00:00+00:00"  # noqa: E731


def _model(store, mode, fn, role="runner"):
    return RecordingModel(FunctionModel(fn), llm=LLM, store=store, mode=mode, now=NOW, role=role)


def _agent(model):
    return Agent(model, instructions="explain", model_settings=sampling_settings(LLM))


def answer(messages, info):
    return ModelResponse(parts=[TextPart("rejected: blurred scan")],
                         usage=RequestUsage(input_tokens=210, output_tokens=12, cache_read_tokens=64))


async def test_a_live_request_gives_one_ok_row_with_tokens():
    store = Store(":memory:")
    with calllog.call_context(case_ref="BBG-2026-000021", run_id="t_abc"):
        await _agent(_model(store, "live", answer, role="router")).run("why?")
    [row] = store.model_log()
    assert (row["service"], row["task"], row["mode"], row["source"], row["status"]) == ("copilot", "router", "live", "live", "ok")
    assert row["input_tokens"] is not None and row["output_tokens"] is not None
    assert row["total_tokens"] == row["input_tokens"] + row["output_tokens"]
    assert row["at"] == NOW() and row["latency_ms"] >= 0
    assert (row["case_ref"], row["run_id"]) == ("BBG-2026-000021", "t_abc")
    text = json.dumps(row)
    assert "blurred" not in text and "why?" not in text


async def test_a_model_http_error_is_logged_and_raised():
    def boom(messages, info):
        raise ModelHTTPError(400, "gpt-test", body={"error": {"message": "Bad input, key sk-live-0123456789abc"}},
                             headers={"retry-after": "7", "x-ratelimit-remaining-requests": "0"},
                             provider_error_code="invalid_request_error")

    store = Store(":memory:")
    with pytest.raises(ModelUnavailable) as e:
        await _agent(_model(store, "live", boom)).run("why?")
    assert isinstance(e.value.__cause__, ModelHTTPError) and e.value.kind == "bad_request"
    [row] = store.model_log()
    assert (row["status"], row["error_code"], row["http_status"], row["kind"]) == ("error", "invalid_request_error", 400, "bad_request")
    assert row["retry_after_s"] == 7.0 and row["ratelimit_remaining_requests"] == 0
    assert "Bad input" in row["message"] and "sk-live" not in row["message"]


async def test_replay_hits_and_misses_are_logged_with_no_tokens_and_recordings_are_unchanged():
    store = Store(":memory:")
    await _agent(_model(store, "record", answer)).run("why?")
    [(key, recorded)] = store._conn().__enter__().execute("SELECT request_key, response FROM llm_calls").fetchall()
    await _agent(_model(store, "replay", answer)).run("why?")  # replay never calls the model
    with pytest.raises(ReplayMiss):
        await _agent(_model(Store(":memory:"), "replay", answer)).run("another question")
    live, hit = store.model_log()
    assert live["source"] == "live" and hit["source"] == "replay_hit" and hit["input_tokens"] is None
    assert live["request_key"] == hit["request_key"] == key
    # The recorded answer is the response itself, not the log.
    assert "blurred scan" in recorded


async def test_a_log_that_cannot_be_written_never_fails_the_turn():
    class Broken(Store):
        def put_model_log(self, row):
            raise RuntimeError("disk full")

    out = await _agent(_model(Broken(":memory:"), "live", answer)).run("why?")
    assert out.output == "rejected: blurred scan"


def test_the_json_line_shows_on_the_console_logger():
    logger = logging.getLogger("creditiq.model")
    assert logger.handlers and logger.level == logging.INFO
