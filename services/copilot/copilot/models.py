"""Build the configured models, always behind the recording wrapper."""

from __future__ import annotations

import os
from collections.abc import Callable

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import LlmConfig
from .recording import Mode, RecordingModel
from .store import Store


def build_model(llm: LlmConfig, role: str, *, store: Store, mode: Mode, now: Callable[[], str]) -> Model:
    """`role` is "router" or "runner". The key comes from the environment; replay mode never needs one."""
    name = {"router": llm.router_model, "runner": llm.runner_model}[role]
    key = os.environ.get(llm.api_key_env)
    if not key and mode != "replay":
        raise RuntimeError(f"{llm.api_key_env} is not set; it is required to {mode} model calls")
    provider = OpenAIProvider(base_url=llm.base_url, api_key=key or "replay-only")
    return RecordingModel(OpenAIChatModel(name, provider=provider), llm=llm, store=store, mode=mode, now=now)
