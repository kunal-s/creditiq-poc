"""What went wrong with a model request, sorted into the kinds the retry policy acts on (the same kinds as
the document-processing service's llm/errors.py and the engine's model_retry.py), how long the provider
asks to be left alone, and the circuit breaker, kept per (base_url, model) for the process.

  rate_limit_minute   429 for a per-minute limit (or an unnamed 429)    retried after the wait asked
  quota               429 for a daily limit or an exhausted quota       not retried
  server_unavailable  500, 502, 503, 504, 409, or no connection         retried with backoff
  timeout             408, or a connect or read timeout                 retried with backoff
  content_filter      400 with error.code content_filter                not retried
  bad_request         any other 400, 422 (and other 4xx)               not retried
  auth                401, 403                                          not retried
  not_configured      404 (wrong model or deployment)                   not retried
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.exceptions import ModelConnectionError, ModelHTTPError, ModelTimeoutError

SERVER = {"server_unavailable", "timeout"}
_DAILY = re.compile(r"per\s*day|\bTPD\b|\bRPD\b|daily|\bquota\b", re.I)
_DURATION = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def _error(body: Any) -> tuple[str | None, str]:
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return None, body
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        code = err.get("code") if isinstance(err, dict) else None
        return (str(code) if code is not None else None), str((err or {}).get("message") or "")
    return None, ""


def http_kind(status: int, body: Any = None, provider_code: str | None = None) -> str:
    code, message = _error(body)
    code = provider_code or code
    if status == 429:
        if code == "insufficient_quota" or _DAILY.search(message):
            return "quota"
        return "rate_limit_minute"
    if status in (500, 502, 503, 504, 409):
        return "server_unavailable"
    if status == 408:
        return "timeout"
    if status in (401, 403):
        return "auth"
    if status == 404:
        return "not_configured"
    if status == 400 and code == "content_filter":
        return "content_filter"
    return "bad_request"


def kind_of(e: BaseException) -> str | None:
    """The kind of a model error, or None for an error that is not the model's (never retried)."""
    if isinstance(e, ModelHTTPError):
        return http_kind(e.status_code, e.body, e.provider_error_code)
    if isinstance(e, ModelTimeoutError):
        return "timeout"
    if isinstance(e, ModelConnectionError):
        return "server_unavailable"
    return None


def duration_s(text: str | None) -> float | None:
    if not text:
        return None
    parts = _DURATION.findall(str(text).strip())
    if not parts:
        return None
    scale = {"h": 3600, "m": 60, "s": 1, "ms": 0.001}
    return sum(float(n) * scale[u] for n, u in parts)


def wait_asked_s(e: BaseException) -> float | None:
    """How long the provider asks to wait: the error's retry_after, else its headers (retry-after-ms,
    retry-after, then the x-ratelimit-reset durations)."""
    asked = getattr(e, "retry_after", None)
    if asked is not None:
        return float(asked)
    try:
        h = {str(k).lower(): v for k, v in dict(getattr(e, "headers", None) or {}).items()}
    except (TypeError, ValueError):
        return None
    for name, scale in (("retry-after-ms", 1000), ("retry-after", 1)):
        if h.get(name) not in (None, ""):
            try:
                return float(h[name]) / scale
            except ValueError:
                pass
    resets = [d for d in (duration_s(h.get("x-ratelimit-reset-tokens")), duration_s(h.get("x-ratelimit-reset-requests")))
              if d is not None]
    return max(resets) if resets else None


@dataclass
class Breaker:
    failures_to_open: int
    cooldown_s: float
    failures: int = 0
    opened_at: float | None = None
    trial: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self, now: float) -> bool:
        with self.lock:
            if self.opened_at is None:
                return True
            if now - self.opened_at < self.cooldown_s or self.trial:
                return False
            self.trial = True
            return True

    def success(self) -> None:
        with self.lock:
            self.failures, self.opened_at, self.trial = 0, None, False

    def failure(self, now: float) -> None:
        with self.lock:
            self.failures += 1
            if self.trial or self.failures >= self.failures_to_open:
                self.opened_at, self.trial = now, False

    def answered(self) -> None:
        with self.lock:
            self.failures, self.opened_at, self.trial = 0, None, False


_breakers: dict[tuple[str, str], Breaker] = {}
_lock = threading.Lock()


def breaker(base_url: str, model: str, failures_to_open: int, cooldown_s: float) -> Breaker:
    key = (base_url.rstrip("/"), model)
    with _lock:
        b = _breakers.get(key)
        if b is None or (b.failures_to_open, b.cooldown_s) != (failures_to_open, cooldown_s):
            b = _breakers[key] = Breaker(failures_to_open, cooldown_s)
        return b


def reset_breakers() -> None:
    with _lock:
        _breakers.clear()


class ModelUnavailable(RuntimeError):
    """A model request that failed after the retry policy (or at once, with the breaker open), with its kind."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
