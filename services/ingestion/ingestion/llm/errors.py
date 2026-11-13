"""What went wrong with a model call, sorted into a kind each retry policy can act on, and how long the
provider asks to be left alone. The kinds:

  rate_limit_minute   429 for a per-minute limit (or an unnamed 429)       retried after the wait asked
  quota               429 for a daily limit or an exhausted quota          not retried
  server_unavailable  500, 502, 503, 504, 409, or no connection            retried with backoff
  timeout             408, or a connect or read timeout                    retried with backoff
  content_filter      400 with error.code content_filter (Azure)           not retried
  bad_request         any other 400, 422 (and other 4xx)                  not retried
  auth                401, 403                                             not retried
  not_configured      404 (wrong model or deployment), key not set         not retried
  refusal, bad_response, replay_miss: as before, never retried

The breaker stops a server that is down from stalling every document: after `breaker_failures`
server_unavailable or timeout attempts in a row (across calls), calls fail at once for
`breaker_cooldown_s`, then one trial call is let through. It is kept per (base_url, model), at module
level, because a provider is built for each request."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from typing import Any

SERVER = {"server_unavailable", "timeout"}
_DAILY = re.compile(r"per\s*day|\bTPD\b|\bRPD\b|daily|\bquota\b", re.I)
_DURATION = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def _error(body: Any) -> tuple[str | None, str]:
    """The provider's error code and message from an error body (OpenAI and Azure shapes)."""
    if isinstance(body, (str, bytes)):
        try:
            body = json.loads(body)
        except (ValueError, TypeError):
            return None, body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        code = err.get("code") if isinstance(err, dict) else None
        message = err.get("message") if isinstance(err, dict) else None
        return (str(code) if code is not None else None), str(message or "")
    return None, ""


def http_kind(status: int, body: Any = None, provider_code: str | None = None) -> str:
    """The kind of an HTTP error answer."""
    code, message = _error(body)
    code = provider_code or code
    if status == 429:
        # A daily limit or an exhausted quota will not clear in a minute: not worth a retry.
        if code == "insufficient_quota" or _DAILY.search(message):
            return "quota"
        return "rate_limit_minute"   # rate_limit_exceeded, a per-minute limit named, or none named
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


def duration_s(text: str | None) -> float | None:
    """An OpenAI duration ("6m0s", "1.5s", "20ms") in seconds."""
    if not text:
        return None
    parts = _DURATION.findall(str(text).strip())
    if not parts:
        return None
    scale = {"h": 3600, "m": 60, "s": 1, "ms": 0.001}
    return sum(float(n) * scale[u] for n, u in parts)


def wait_asked_s(headers: Any) -> float | None:
    """How long the provider asks to wait: retry-after-ms, else retry-after (seconds), else the
    x-ratelimit-reset-tokens / -requests durations (the longer)."""
    try:
        h = {str(k).lower(): v for k, v in dict(headers or {}).items()}
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
        """Whether a call may go out now: always when closed; once the cooldown is over, one trial."""
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
        """The server answered (an error that is not its being down): a trial is over, and the run of
        server failures is broken."""
        with self.lock:
            self.failures, self.trial = 0, False
            self.opened_at = None


_breakers: dict[tuple[str, str], Breaker] = {}
_breakers_lock = threading.Lock()


def breaker(base_url: str, model: str, failures_to_open: int, cooldown_s: float) -> Breaker:
    key = (base_url.rstrip("/"), model)
    with _breakers_lock:
        b = _breakers.get(key)
        if b is None or (b.failures_to_open, b.cooldown_s) != (failures_to_open, cooldown_s):
            b = _breakers[key] = Breaker(failures_to_open, cooldown_s)
        return b


def reset_breakers() -> None:
    """Forget every breaker (tests)."""
    with _breakers_lock:
        _breakers.clear()
