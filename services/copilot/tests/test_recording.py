from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from copilot.config import load_dir
from copilot.recording import RecordingModel, ReplayMiss, SamplingRefused, request_key, sampling_settings
from copilot.store import Store

LLM = load_dir(Path(__file__).resolve().parent.parent / "config").llm
NOW = lambda: "2026-10-28T10:00:00"  # noqa: E731


def make(store, mode, calls):
    def fn(messages, info):
        calls.append(1)
        return ModelResponse(parts=[TextPart("rejected: blurred scan")])

    return RecordingModel(FunctionModel(fn), llm=LLM, store=store, mode=mode, now=NOW)


def agent(model):
    return Agent(model, instructions="explain", model_settings=sampling_settings(LLM))


async def test_record_then_replay_without_provider():
    store, calls = Store(":memory:"), []
    r1 = await agent(make(store, "record", calls)).run("why?")
    assert len(calls) == 1
    again = []
    r2 = await agent(make(store, "replay", again)).run("why?")  # a new run: new timestamps and run id
    assert again == [] and r2.output == r1.output == "rejected: blurred scan"


async def test_replay_miss_raises_and_never_calls():
    calls = []
    with pytest.raises(ReplayMiss):
        await agent(make(Store(":memory:"), "replay", calls)).run("why?")
    assert calls == []


async def test_different_prompt_is_a_miss():
    store, calls = Store(":memory:"), []
    await agent(make(store, "record", calls)).run("why?")
    with pytest.raises(ReplayMiss):
        await agent(make(store, "replay", calls)).run("something else")


async def test_live_calls_every_time_and_stores_nothing():
    store, calls = Store(":memory:"), []
    m = make(store, "live", calls)
    await agent(m).run("why?")
    await agent(m).run("why?")
    assert len(calls) == 2
    with pytest.raises(ReplayMiss):
        await agent(make(store, "replay", [])).run("why?")


async def test_sampling_outside_configuration_refused_before_any_call():
    calls = []
    m = make(Store(":memory:"), "live", calls)
    for bad in ({"top_p": 0.5}, {"temperature": 0.7}, {"seed": 99}, {"max_tokens": 10}):
        with pytest.raises(SamplingRefused):
            await Agent(m, model_settings={**sampling_settings(LLM), **bad}).run("x")
    assert calls == []


async def test_errors_are_not_recorded():
    store = Store(":memory:")

    def boom(messages, info):
        raise RuntimeError("provider down")

    with pytest.raises(Exception):
        await agent(RecordingModel(FunctionModel(boom), llm=LLM, store=store, mode="record", now=NOW)).run("why?")
    with pytest.raises(ReplayMiss):
        await agent(make(store, "replay", [])).run("why?")


def test_key_ignores_volatile_fields_and_changes_with_settings():
    from pydantic_ai.messages import ModelRequest, UserPromptPart
    from pydantic_ai.models import ModelRequestParameters

    p = ModelRequestParameters()
    a = [ModelRequest(parts=[UserPromptPart("hi")])]
    b = [ModelRequest(parts=[UserPromptPart("hi")])]
    assert request_key("m", a, {"temperature": 0}, p)[0] == request_key("m", b, {"temperature": 0}, p)[0]
    assert request_key("m", a, {"temperature": 0}, p)[0] != request_key("m", a, {"temperature": 0, "seed": 1}, p)[0]
