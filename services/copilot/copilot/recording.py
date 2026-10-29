"""Record and replay of model responses (CLAUDE.md rule 6).

`RecordingModel` wraps any Pydantic AI model. Determinism is replay of a recorded answer, not a sampling setting:
  replay  (default) answer from the store; a miss raises ReplayMiss and nothing is sent to the provider.
  record  answer from the store when present, else call the provider and store the answer.
  live    always call the provider, store nothing.
The only sampling parameters that may reach a provider are those named in the published configuration
(`temperature` and `seed`), with the configured values; anything else is refused before any call.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, Literal

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

from .config import LlmConfig
from .store import Store

Mode = Literal["replay", "record", "live"]
_VOLATILE = {"timestamp", "run_id", "conversation_id"}  # differ on every run; never part of the key
_OPERATIONAL = {"timeout"}  # not a sampling parameter; not sent in the key either


class ReplayMiss(RuntimeError):
    """Replay mode found no recording for this request."""


class SamplingRefused(ValueError):
    """A sampling parameter that the published configuration does not name, or names with another value."""


def sampling_settings(llm: LlmConfig) -> ModelSettings:
    """The only sampling settings an agent may be given."""
    return ModelSettings(temperature=llm.temperature, seed=llm.seed)


def assert_sampling(settings: ModelSettings | None, llm: LlmConfig) -> None:
    allowed = {"temperature": llm.temperature, "seed": llm.seed}
    for k, v in (settings or {}).items():
        if k in _OPERATIONAL:
            continue
        if k not in allowed:
            raise SamplingRefused(f"sampling parameter {k!r} is not in the published configuration")
        if v != allowed[k]:
            raise SamplingRefused(f"{k}={v!r} differs from the published value {allowed[k]!r}")


def _strip(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in _VOLATILE}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def request_key(model_name: str, messages: list[ModelMessage], settings: ModelSettings | None, params: ModelRequestParameters) -> tuple[str, str]:
    body = {
        "model": model_name,
        "messages": _strip(json.loads(ModelMessagesTypeAdapter.dump_json(messages))),
        "settings": {k: v for k, v in (settings or {}).items() if k not in _OPERATIONAL},
        "tools": sorted(
            ({"name": t.name, "description": t.description, "schema": t.parameters_json_schema} for t in [*params.function_tools, *params.output_tools]),
            key=lambda t: t["name"],
        ),
        "output_mode": params.output_mode,
        "allow_text_output": params.allow_text_output,
    }
    canon = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode()).hexdigest(), canon


class RecordingModel(WrapperModel):
    def __init__(self, wrapped: Model, *, llm: LlmConfig, store: Store, mode: Mode = "replay", now: Callable[[], str]):
        super().__init__(wrapped)
        self._llm, self._store, self._mode, self._now = llm, store, mode, now

    async def request(self, messages, model_settings, model_request_parameters) -> ModelResponse:
        assert_sampling(model_settings, self._llm)
        key, canon = request_key(self.model_name, messages, model_settings, model_request_parameters)
        if self._mode != "live":
            hit = self._store.get_llm_call(key)
            if hit is not None:
                return ModelMessagesTypeAdapter.validate_json(hit)[0]
            if self._mode == "replay":
                raise ReplayMiss(f"no recording for request {key[:12]} (model {self.model_name})")
        response = await super().request(messages, model_settings, model_request_parameters)
        if self._mode == "record":
            self._store.put_llm_call(key, self.model_name, self._now(), canon, ModelMessagesTypeAdapter.dump_json([response]).decode())
        return response

    def request_stream(self, *a, **k):  # an unrecorded path must not exist
        raise NotImplementedError("streaming model calls are not recorded; use request()")
