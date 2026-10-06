"""Record and replay (AD-5a). Modes:
  replay  answer only from recordings; a miss is an explicit error (the default)
  record  call live, store the answer, return it
  live    call live, store nothing
Refusals and errors are never recorded."""

from __future__ import annotations

from typing import Any, Protocol

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
        if self.mode == "replay":
            rec = self.store.get_llm_call(key)
            if rec is None:
                raise ModelError("replay_miss", f"no recording for {self.provider.name} {req.task} call {key[:12]}")
            return call.parse(rec["response"])
        response = call.send(call.body)
        self.calls += 1
        answer = call.parse(response)  # raises on refusal or garbage: nothing is stored then
        if self.mode == "record":
            self.store.put_llm_call(key, {"provider": self.provider.name, "model": self.provider.model, "task": req.task,
                                          "origin": getattr(self.provider, "origin", "live"), "request": call.body, "response": response})
        return answer
