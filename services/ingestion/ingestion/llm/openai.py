"""OpenAI-compatible chat completions with strict JSON-schema output. `base_url` makes this work
for any compatible endpoint, which is how the model stays a configuration choice."""

from __future__ import annotations

import json
import time

import httpx

from ..config.models import LlmConfig
from .provider import ModelError, ModelRequest, NativeCall


class OpenAIProvider:
    name = "openai"

    def __init__(self, cfg: LlmConfig, api_key: str | None):
        self.cfg = cfg
        self.model = cfg.model
        self.sampling = {k: v for k, v in (("temperature", cfg.temperature), ("seed", cfg.seed)) if v is not None}
        self.api_key = api_key

    def build(self, req: ModelRequest) -> NativeCall:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": req.system}, {"role": "user", "content": req.user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": req.task, "strict": True, "schema": req.schema}},
            **self.sampling,
        }
        return NativeCall(body, self._send, self._parse)

    def _send(self, body: dict) -> dict:
        if not self.api_key:
            raise ModelError("not_configured", f"{self.cfg.api_key_env} is not set")
        last = ""
        for attempt in range(self.cfg.max_retries + 1):
            try:
                r = httpx.post(self.cfg.base_url.rstrip("/") + "/chat/completions", json=body, timeout=self.cfg.timeout_s,
                               headers={"Authorization": f"Bearer {self.api_key}"})
            except httpx.HTTPError as e:
                last = str(e)
            else:
                if r.status_code < 400:
                    return r.json()
                last = f"{r.status_code}: {r.text[:300]}"
                if r.status_code not in (408, 409, 429, 500, 502, 503, 504):
                    break
            time.sleep(min(2 ** attempt, 8))
        raise ModelError("http", last)

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
        call.send = lambda body: {"choices": [{"message": {"content": json.dumps(self.answerer(req))}}]}
        return call
