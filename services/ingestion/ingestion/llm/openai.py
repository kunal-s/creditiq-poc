"""OpenAI-compatible chat completions with strict JSON-schema output. `base_url` makes this work
for any compatible endpoint, which is how the model stays a configuration choice."""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable

import httpx

from ..config.models import LlmConfig
from . import errors
from .calllog import CallLog, Stopwatch
from .provider import ModelError, ModelRequest, NativeCall


class OpenAIProvider:
    name = "openai"

    def __init__(self, cfg: LlmConfig, api_key: str | None, *, sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic, rand: Callable[[float, float], float] = random.uniform):
        """`sleep`, `monotonic` and `rand` are injected so a test waits for nothing."""
        self.cfg = cfg
        self.model = cfg.model
        self.sampling = {k: v for k, v in (("temperature", cfg.temperature), ("seed", cfg.seed)) if v is not None}
        self.api_key = api_key
        self._sleep, self._monotonic, self._rand = sleep, monotonic, rand

    def build(self, req: ModelRequest) -> NativeCall:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": req.system}, {"role": "user", "content": req.user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": req.task, "strict": True, "schema": req.schema}},
            **self.sampling,
        }
        return NativeCall(body, self._send, self._parse)

    def _send(self, body: dict, report: CallLog | None = None) -> dict:
        """Send the body under the configured retry policy (llm/errors.py): a server that is down or slow
        is tried again after a backoff, a per-minute limit after the wait it asks for (up to max_wait_s),
        anything else not at all; the breaker fails a call at once while the server is known to be down.
        Every attempt is reported to the call log with its kind and the wait chosen."""
        if not self.api_key:
            raise ModelError("not_configured", f"{self.cfg.api_key_env} is not set", kind="not_configured")
        policy = self.cfg.retry
        br = errors.breaker(self.cfg.base_url, self.model, policy.breaker_failures, policy.breaker_cooldown_s)
        server_tries = rate_tries = 0
        while True:
            if not br.allow(self._monotonic()):
                message = (f"the model server failed {policy.breaker_failures} times in a row; calls are paused "
                           f"for {policy.breaker_cooldown_s:.0f} s")
                if report:
                    report.failed_before_sending("http", message, "server_unavailable")
                raise ModelError("http", message, kind="server_unavailable")
            watch = Stopwatch()
            status, headers, answer = None, None, None
            try:
                r = httpx.post(self.cfg.base_url.rstrip("/") + "/chat/completions", json=body, timeout=self.cfg.timeout_s,
                               headers={"Authorization": f"Bearer {self.api_key}"})
            except httpx.TimeoutException as e:
                kind, code, last = "timeout", type(e).__name__, str(e) or type(e).__name__
            except httpx.HTTPError as e:
                kind, code, last = "server_unavailable", type(e).__name__, str(e) or type(e).__name__
            else:
                status, headers = r.status_code, r.headers
                if r.status_code < 400:
                    answer = r.json()
                    br.success()
                    if report:
                        report.attempt(at=watch.at, latency_ms=watch.ms(), ok=True, http_status=status, headers=headers,
                                       response=answer)
                    return answer
                kind, code, last = errors.http_kind(r.status_code, r.text), "http", f"{r.status_code}: {r.text[:300]}"
            wait = None
            if kind in errors.SERVER:
                br.failure(self._monotonic())
                server_tries += 1
                if server_tries < policy.server_attempts:
                    base = policy.server_backoff_s[min(server_tries - 1, len(policy.server_backoff_s) - 1)]
                    j = policy.backoff_jitter
                    wait = base * self._rand(1 - j, 1 + j)
            else:
                if status is not None:
                    br.answered()
                if kind == "rate_limit_minute":
                    rate_tries += 1
                    asked = errors.wait_asked_s(headers)
                    want = asked if asked is not None else policy.rate_limit_wait_s
                    if want > policy.max_wait_s:
                        last = f"{last} (the provider asks to wait {want:.0f} s, more than the {policy.max_wait_s:.0f} s allowed)"
                    elif rate_tries < policy.rate_limit_attempts:
                        wait = want
            if report:
                report.attempt(at=watch.at, latency_ms=watch.ms(), ok=False, http_status=status, headers=headers,
                               error_code=code if status is None else "http", message=last, kind=kind,
                               retry_after_s=wait)
            if wait is None:
                raise ModelError("http", last, kind=kind)
            self._sleep(wait)

    @staticmethod
    def _parse(resp: dict):
        try:
            msg = resp["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError("bad_response", "no choices in the response") from e
        if msg.get("refusal"):
            raise ModelError("refusal", str(msg["refusal"])[:300])
        try:
            return json.loads(msg.get("content") or "")
        except json.JSONDecodeError as e:
            raise ModelError("bad_response", "the answer was not valid JSON") from e


class FixtureProvider(OpenAIProvider):
    """Answers from a function instead of the network. Used to author test recordings; what it
    records is marked origin='fixture' so it is never mistaken for a real model answer."""

    origin = "fixture"

    def __init__(self, cfg: LlmConfig, answerer):
        super().__init__(cfg, "fixture")
        self.answerer = answerer

    def build(self, req: ModelRequest) -> NativeCall:
        call = super().build(req)

        def send(body: dict, report: CallLog | None = None) -> dict:
            watch = Stopwatch()
            answer = {"choices": [{"message": {"content": json.dumps(self.answerer(req))}}]}
            if report:
                report.attempt(at=watch.at, latency_ms=watch.ms(), ok=True, response=answer)
            return answer

        call.send = send
        return call
