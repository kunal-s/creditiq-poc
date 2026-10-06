"""The model layer (FRD AD-5a, principle 6).

One provider-neutral request goes in, parsed JSON comes out. A provider turns the request into
its native body; the recorder keys every call by sha256 of the canonical JSON of
{provider, model, body}. The only sampling parameters sent are the ones the configuration names (temperature and seed),
and they are part of the body, so a recording is keyed by them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from ..util import canonical_json, sha256_hex

SAMPLING_PARAMS = {"temperature", "top_p", "top_k", "topP", "topK", "seed", "presence_penalty", "frequency_penalty"}


class ModelError(Exception):
    """code: replay_miss | refusal | bad_response | http | not_configured"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class ModelRequest:
    task: str      # "classify" | "extract": part of the key and useful when reading recordings
    system: str
    user: str
    schema: dict   # JSON schema of the answer (strict: every property required, no extras)


@dataclass
class NativeCall:
    body: dict
    send: Callable[[dict], dict]     # sends the body live, returns the provider's raw JSON
    parse: Callable[[dict], Any]     # pulls the answer out; raises ModelError on refusal/garbage


class Provider(Protocol):
    name: str
    model: str
    sampling: dict[str, Any]
    """Sampling parameters this provider is configured to send (may be empty)."""

    def build(self, req: ModelRequest) -> NativeCall: ...


def assert_sampling(body: Any, allowed: dict[str, Any] | None = None) -> None:
    """A body may carry a sampling parameter only if it is configured, with the configured value."""
    allowed = allowed or {}
    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if k in SAMPLING_PARAMS and (k not in allowed or allowed[k] != v):
                    raise ValueError(f'sampling parameter "{k}" is not configured and must not be sent (principle 6)')
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(body)


def recording_key(provider: str, model: str, body: dict) -> str:
    return sha256_hex(canonical_json({"provider": provider, "model": model, "body": body}))
