"""Record and replay of model responses (CLAUDE.md rule 6).

`RecordingModel` wraps any Pydantic AI model. Determinism is replay of a recorded answer, not a sampling setting:
  replay  (default) answer from the store; a miss raises ReplayMiss and nothing is sent to the provider.
  record  answer from the store when present, else call the provider and store the answer.
  live    always call the provider, store nothing.
The only sampling parameters that may reach a provider are those named in the published configuration
(`temperature` and `seed`), with the configured values; anything else is refused before any call.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

from . import calllog, model_errors
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
    def __init__(self, wrapped: Model, *, llm: LlmConfig, store: Store, mode: Mode = "replay", now: Callable[[], str],
                 role: str = "runner", sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 monotonic: Callable[[], float] = time.monotonic, rand: Callable[[float, float], float] = random.uniform):
        """`role` ("router" or "runner") is the task the model call log names; `sleep`, `monotonic` and
        `rand` are injected so a test waits for nothing."""
        super().__init__(wrapped)
        self._llm, self._store, self._mode, self._now, self._role = llm, store, mode, now, role
        self._sleep, self._monotonic, self._rand = sleep, monotonic, rand

    def _log(self, key: str, **fields) -> None:
        """One row of the model call log (copilot/calllog.py); never fails the request."""
        calllog.write(self._store, {"id": None, "service": calllog.SERVICE, "task": self._role,
                                    "provider": self._llm.provider, "model": self.model_name, "mode": self._mode,
                                    "request_key": key, "attempt": 1, **calllog.context(), **fields})

    async def request(self, messages, model_settings, model_request_parameters) -> ModelResponse:
        assert_sampling(model_settings, self._llm)
        key, canon = request_key(self.model_name, messages, model_settings, model_request_parameters)
        if self._mode != "live":
            hit = self._store.get_llm_call(key)
            if hit is not None:
                self._log(key, at=self._now(), source="replay_hit", status="ok", latency_ms=0)
                return ModelMessagesTypeAdapter.validate_json(hit)[0]
            if self._mode == "replay":
                self._log(key, at=self._now(), source="replay_miss", status="error", error_code="replay_miss",
                          kind="replay_miss", latency_ms=0)
                raise ReplayMiss(f"no recording for request {key[:12]} (model {self.model_name})")
        response = await self._live(key, messages, model_settings, model_request_parameters)
        if self._mode == "record":
            self._store.put_llm_call(key, self.model_name, self._now(), canon, ModelMessagesTypeAdapter.dump_json([response]).decode())
        return response

    async def _live(self, key, messages, model_settings, model_request_parameters) -> ModelResponse:
        """Ask the provider under the published retry policy (llm.retry, copilot/model_errors.py): a server
        that is down or slow is asked again after a backoff, a per-minute limit after the wait it asks
        for (up to max_wait_s), anything else not at all; while the breaker is open the request fails at
        once. Every attempt is one row of the model call log. A request that still fails raises
        ModelUnavailable with its kind; an error that is not the model's is raised as it came."""
        policy = self._llm.retry
        br = model_errors.breaker(self._llm.base_url, self.model_name, policy.breaker_failures, policy.breaker_cooldown_s)
        attempt = server_tries = rate_tries = 0
        while True:
            attempt += 1
            if not br.allow(self._monotonic()):
                message = f"the model server failed {policy.breaker_failures} times in a row; requests are paused"
                self._log(key, at=self._now(), source="live", attempt=attempt, status="error", error_code="ModelUnavailable",
                          kind="server_unavailable", latency_ms=0, message=message)
                raise model_errors.ModelUnavailable("server_unavailable", message)
            at, t0 = self._now(), self._monotonic()
            try:
                response = await super().request(messages, model_settings, model_request_parameters)
            except Exception as e:
                kind = model_errors.kind_of(e)
                wait = None
                if kind in model_errors.SERVER:
                    br.failure(self._monotonic())
                    server_tries += 1
                    if server_tries < policy.server_attempts:
                        base = policy.server_backoff_s[min(server_tries - 1, len(policy.server_backoff_s) - 1)]
                        wait = base * self._rand(1 - policy.backoff_jitter, 1 + policy.backoff_jitter)
                elif kind is not None:
                    br.answered()
                    if kind == "rate_limit_minute":
                        rate_tries += 1
                        asked = model_errors.wait_asked_s(e)
                        want = asked if asked is not None else policy.rate_limit_wait_s
                        if want <= policy.max_wait_s and rate_tries < policy.rate_limit_attempts:
                            wait = want
                http = isinstance(e, ModelHTTPError)
                fields = calllog.header_fields(getattr(e, "headers", None), getattr(e, "retry_after", None))
                if wait is not None:
                    fields["retry_after_s"] = round(wait, 3)
                self._log(key, at=at, source="live", attempt=attempt, status="error",
                          error_code=(e.provider_error_code if http else None) or type(e).__name__, kind=kind,
                          http_status=e.status_code if http else None, latency_ms=round((self._monotonic() - t0) * 1000, 1),
                          message=calllog.redact(e.body if http and e.body is not None else str(e)), **fields)
                if kind is None:
                    raise
                if wait is None:
                    raise model_errors.ModelUnavailable(kind, str(e)) from e
                await self._sleep(wait)
                continue
            br.success()
            self._log(key, at=at, source="live", attempt=attempt, status="ok",
                      latency_ms=round((self._monotonic() - t0) * 1000, 1), **calllog.usage_fields(response.usage))
            return response

    def request_stream(self, *a, **k):  # an unrecorded path must not exist
        raise NotImplementedError("streaming model calls are not recorded; use request()")
