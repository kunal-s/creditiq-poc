"""The model call log: one row per HTTP attempt and per replay (tokens, latency, outcome), written to
the store's append-only `model_log` table and as one JSON line on the `creditiq.model` logger.

Never the prompt, the answer, the key or the Authorization header: the request is named by its
recording key, and an error message is cut to 300 characters with key-like values redacted. Writing
the log never fails a call or slows it: any error is caught, warned about once, and the call goes on.
The case and the run a call belongs to are carried in a ContextVar, set around one file's run
(pipeline.py) and around a transactions request (api.py), so the provider never needs the store."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator

SERVICE = "ingestion"
LOGGER = "creditiq.model"
COLUMNS = ("id", "at", "service", "task", "provider", "model", "mode", "source", "case_ref", "run_id", "request_key",
           "attempt", "status", "error_code", "http_status", "latency_ms", "input_tokens", "output_tokens",
           "total_tokens", "cached_tokens", "ratelimit_remaining_tokens", "ratelimit_remaining_requests",
           "retry_after_s", "message", "kind")

log = logging.getLogger(LOGGER)
_context: ContextVar[dict] = ContextVar("creditiq_model_call_context", default={})
_warned = False

_SECRETS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{6,}"), "sk-[redacted]"),
    (re.compile(r"(?i)(api[-_ ]?key[\"'\s:=]+)([^\s\"',;}]+)"), r"\1[redacted]"),
    (re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]+)"), r"\1[redacted]"),
]


def console() -> None:
    """Make the JSON lines show in the service's console: uvicorn configures only its own loggers."""
    if not log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False


console()


@contextmanager
def call_context(*, case_ref: str | None, run_id: str | None) -> Iterator[None]:
    """The case and run every model call inside belongs to."""
    token = _context.set({"case_ref": case_ref, "run_id": run_id})
    try:
        yield
    finally:
        _context.reset(token)


def redact(message: str | None) -> str | None:
    if message is None:
        return None
    text = str(message)
    for rx, sub in _SECRETS:
        text = rx.sub(sub, text)
    return text[:300]


def _int(v: Any) -> int | None:
    try:
        return int(float(v)) if v is not None and str(v).strip() != "" else None
    except (TypeError, ValueError):
        return None


def header_fields(headers: Any) -> dict:
    """Rate-limit headers, whichever are present (OpenAI and Azure both send them)."""
    h = {str(k).lower(): v for k, v in (dict(headers or {})).items()}
    retry = None
    if h.get("retry-after-ms") not in (None, ""):
        try:
            retry = float(h["retry-after-ms"]) / 1000
        except ValueError:
            retry = None
    if retry is None and h.get("retry-after") not in (None, ""):
        try:
            retry = float(h["retry-after"])
        except ValueError:
            retry = None
    return {"ratelimit_remaining_tokens": _int(h.get("x-ratelimit-remaining-tokens")),
            "ratelimit_remaining_requests": _int(h.get("x-ratelimit-remaining-requests")),
            "retry_after_s": retry}


def usage_fields(response: Any) -> dict:
    """Tokens from an OpenAI chat-completions answer (`usage`); nothing when it has none."""
    usage = response.get("usage") if isinstance(response, dict) else None
    if not isinstance(usage, dict):
        return {}
    details = usage.get("prompt_tokens_details") or {}
    return {"input_tokens": _int(usage.get("prompt_tokens")), "output_tokens": _int(usage.get("completion_tokens")),
            "total_tokens": _int(usage.get("total_tokens")),
            "cached_tokens": _int(details.get("cached_tokens")) if isinstance(details, dict) else None}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(store: Any, row: dict) -> None:
    """Store the row and print its JSON line; never raises."""
    global _warned
    full = {c: row.get(c) for c in COLUMNS}
    try:
        put = getattr(store, "put_model_log", None)
        if put is not None:
            put(full)
        log.info(json.dumps(full, sort_keys=False, default=str))
    except Exception as e:  # noqa: BLE001 - the log must never fail a model call
        if not _warned:
            _warned = True
            logging.getLogger(LOGGER).warning("model call log could not be written: %s", type(e).__name__)


class CallLog:
    """The rows of one model call: its attempts (or its replay), written as they happen. A successful
    HTTP attempt is held until the answer is parsed, so a refusal or an unreadable answer is the row's
    outcome rather than a second row."""

    def __init__(self, store: Any, *, task: str, provider: str, model: str, mode: str, request_key: str):
        ctx = _context.get()
        self.store = store
        self.base = {"service": SERVICE, "task": task, "provider": provider, "model": model, "mode": mode,
                     "case_ref": ctx.get("case_ref"), "run_id": ctx.get("run_id"), "request_key": request_key}
        self.attempts = 0
        self._held: dict | None = None

    def _row(self, **fields) -> dict:
        return {"id": uuid.uuid4().hex, **self.base, **fields}

    def replay(self, *, hit: bool) -> None:
        write(self.store, self._row(at=now_iso(), source="replay_hit" if hit else "replay_miss", attempt=1,
                                    status="ok" if hit else "error", error_code=None if hit else "replay_miss",
                                    kind=None if hit else "replay_miss", latency_ms=0))

    def attempt(self, *, at: str, latency_ms: float, ok: bool, http_status: int | None = None, headers: Any = None,
                response: Any = None, error_code: str | None = None, message: str | None = None,
                kind: str | None = None, retry_after_s: float | None = None) -> None:
        """One HTTP attempt, as the provider saw it: its kind of failure and, when it is retried, the wait."""
        self.attempts += 1
        fields = header_fields(headers)
        if retry_after_s is not None:
            fields["retry_after_s"] = round(retry_after_s, 3)
        row = self._row(at=at, source="live", attempt=self.attempts, status="ok" if ok else "error",
                        error_code=None if ok else error_code, kind=None if ok else (kind or error_code),
                        http_status=http_status, latency_ms=round(latency_ms, 1), message=None if ok else redact(message),
                        **fields, **(usage_fields(response) if ok else {}))
        if ok:
            self._flush()
            self._held = row
        else:
            write(self.store, row)

    def done(self, error_code: str | None = None, message: str | None = None, kind: str | None = None) -> None:
        """The call is over: the held attempt is written, marked failed when its answer could not be used."""
        if self._held is not None and error_code:
            self._held.update(status="error", error_code=error_code, kind=kind or error_code, message=redact(message))
        self._flush()

    def failed_before_sending(self, error_code: str, message: str, kind: str | None = None) -> None:
        """The call could not be sent at all (no key, or the breaker is open)."""
        self.attempts += 1
        write(self.store, self._row(at=now_iso(), source="live", attempt=self.attempts, status="error",
                                    error_code=error_code, kind=kind or error_code, latency_ms=0, message=redact(message)))

    def _flush(self) -> None:
        if self._held is not None:
            write(self.store, self._held)
            self._held = None


class Stopwatch:
    """The start time (UTC ISO) and elapsed milliseconds of one attempt."""

    def __init__(self) -> None:
        self.at = now_iso()
        self._t = time.monotonic()

    def ms(self) -> float:
        return (time.monotonic() - self._t) * 1000
