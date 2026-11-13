"""Record and replay (AD-5a). Modes:
  replay  answer only from recordings; a miss is an explicit error (the default)
  record  call live, store the answer, return it
  live    call live, store nothing
Refusals and errors are never recorded."""

from __future__ import annotations

import inspect
from typing import Any, Protocol

from .calllog import CallLog, Stopwatch
from .provider import ModelError, ModelRequest, Provider, assert_sampling, recording_key


class RecordingStore(Protocol):
    def get_llm_call(self, key: str) -> dict | None: ...
    def put_llm_call(self, key: str, row: dict) -> None: ...


class ModelClient:
    def __init__(self, provider: Provider, mode: str, store: RecordingStore):
        if mode not in ("replay", "record", "live"):
            raise ValueError(f"unknown model mode {mode}")
        self.provider, self.mode, self.store = provider, mode, store
        self.calls = 0  # live calls made by this client (a replay run must leave this at 0)

    @property
    def name(self) -> str:
        return f"{self.provider.name}:{self.provider.model}"

    def key_for(self, req: ModelRequest) -> str:
        return recording_key(self.provider.name, self.provider.model, self.provider.build(req).body)

    def call(self, req: ModelRequest) -> Any:
        call = self.provider.build(req)
        assert_sampling(call.body, getattr(self.provider, "sampling", {}))
        key = recording_key(self.provider.name, self.provider.model, call.body)
        log = CallLog(self.store, task=req.task, provider=self.provider.name, model=self.provider.model, mode=self.mode,
                      request_key=key)
        if self.mode == "replay":
            rec = self.store.get_llm_call(key)
            log.replay(hit=rec is not None)
            if rec is None:
                raise ModelError("replay_miss", f"no recording for {self.provider.name} {req.task} call {key[:12]}")
            return call.parse(rec["response"])
        response = self._send(call, log)
        self.calls += 1
        try:
            answer = call.parse(response)  # raises on refusal or garbage: nothing is stored then
        except ModelError as e:
            log.done(e.code, str(e))
            raise
        log.done()
        if self.mode == "record":
            self.store.put_llm_call(key, {"provider": self.provider.name, "model": self.provider.model, "task": req.task,
                                          "origin": getattr(self.provider, "origin", "live"), "request": call.body, "response": response})
        return answer

    @staticmethod
    def _send(call, log: CallLog) -> Any:
        """Send the call, its attempts reported to the call log. A provider whose `send` takes no reporter
        is timed here, as one attempt."""
        if "report" in inspect.signature(call.send).parameters:
            try:
                return call.send(call.body, report=log)
            except ModelError as e:
                if log.attempts == 0:
                    log.failed_before_sending(e.code, str(e))
                raise
        watch = Stopwatch()
        try:
            response = call.send(call.body)
        except ModelError as e:
            log.attempt(at=watch.at, latency_ms=watch.ms(), ok=False, error_code=e.code, message=str(e))
            raise
        log.attempt(at=watch.at, latency_ms=watch.ms(), ok=True, response=response)
        return response
