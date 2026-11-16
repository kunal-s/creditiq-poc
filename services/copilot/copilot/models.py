"""Build the configured models, always behind the recording wrapper."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from openai import AsyncOpenAI
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import LlmConfig
from .recording import Mode, RecordingModel
from .store import Store


class AzureKeyClient(AsyncOpenAI):
    """The OpenAI client for Azure OpenAI's v1 API (<endpoint>/openai/v1): the key goes in an `api-key`
    header and nothing else authenticates, so no bearer token and no api-version are sent (the SDK's
    AsyncAzureOpenAI always adds an api-version, which the v1 API refuses)."""

    def _key(self) -> dict[str, str]:
        return {"api-key": self.api_key} if self.api_key else {}

    @property
    def auth_headers(self) -> dict[str, str]:
        return self._key()

    def _auth_headers(self, security) -> dict[str, str]:  # noqa: ARG002 - the SDK's per-request hook
        return self._key()

    def _validate_headers(self, headers, custom_headers) -> None:  # noqa: ARG002 - the SDK's hook
        if not headers.get("api-key"):
            raise TypeError("the Azure OpenAI key is not set")


def build_model(llm: LlmConfig, role: str, *, store: Store, mode: Mode, now: Callable[[], str],
                http_client: Any = None) -> Model:
    """`role` is "router" or "runner". The key comes from the environment; replay mode never needs one.
    `http_client` replaces the SDK's own (a test's mock transport)."""
    name = {"router": llm.router_model, "runner": llm.runner_model}[role]
    key = os.environ.get(llm.api_key_env)
    if not key and mode != "replay":
        raise RuntimeError(f"{llm.api_key_env} is not set; it is required to {mode} model calls")
    # The SDK's own retries are off and its timeout is the configured one: RecordingModel retries by the
    # published policy (llm.retry), so every attempt is seen and logged.
    client_class = AzureKeyClient if llm.provider == "azure" else AsyncOpenAI
    client = client_class(base_url=llm.base_url, api_key=key or "replay-only", max_retries=0, timeout=llm.timeout_s,
                          **({"http_client": http_client} if http_client is not None else {}))
    provider = OpenAIProvider(openai_client=client)
    # On Azure the request names the deployment; it is shaped by the model id's profile, as on OpenAI.
    sent = llm.deployment if llm.provider == "azure" else name
    chat = OpenAIChatModel(sent, provider=provider, profile=provider.model_profile(name))
    return RecordingModel(chat, llm=llm, store=store, mode=mode, now=now, role=role, model_id=name)
