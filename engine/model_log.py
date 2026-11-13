"""The engine's model call log: one row per HTTP attempt and per recorded answer of the CAM copilot
(engine/cam_copilot.py), in the append-only `model_log` table and as one JSON line on the
`creditiq.model` logger. The same columns as the document-processing service's and the case
assistant's logs.

Never the prompt, the answer, the key or the Authorization header: the request is named by its
recording hash, and an error message is cut to 300 characters with key-like values redacted.
Writing the log never fails a call or slows it: any error is caught, warned about once, and the call
goes on."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

LOGGER = "creditiq.model"
COLUMNS = ("id", "at", "service", "task", "provider", "model", "mode", "source", "case_ref", "run_id", "request_key",
           "attempt", "status", "error_code", "http_status", "latency_ms", "input_tokens", "output_tokens",
           "total_tokens", "cached_tokens", "ratelimit_remaining_tokens", "ratelimit_remaining_requests",
           "retry_after_s", "message")

log = logging.getLogger(LOGGER)
_warned = False

_SECRETS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{6,}"), "sk-[redacted]"),
    (re.compile(r"(?i)(api[-_ ]?key[\"'\s:=]+)([^\s\"',;}]+)"), r"\1[redacted]"),
    (re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]+)"), r"\1[redacted]"),
]


def console() -> None:
    """Make the JSON lines show in the engine's console: uvicorn configures only its own loggers."""
    if not log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False


console()


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
    try:
        h = {str(k).lower(): v for k, v in dict(headers or {}).items()}
    except (TypeError, ValueError):
        h = {}
    retry = None
    for name, scale in (("retry-after-ms", 1000), ("retry-after", 1)):
        if retry is None and h.get(name) not in (None, ""):
            try:
                retry = float(h[name]) / scale
            except ValueError:
                retry = None
    return {"ratelimit_remaining_tokens": _int(h.get("x-ratelimit-remaining-tokens")),
            "ratelimit_remaining_requests": _int(h.get("x-ratelimit-remaining-requests")),
            "retry_after_s": retry}


def usage_fields(answer: Any) -> dict:
    """Tokens from an OpenAI chat-completions answer (`usage`); nothing when it has none."""
    usage = answer.get("usage") if isinstance(answer, dict) else None
    if not isinstance(usage, dict):
        return {}
    details = usage.get("prompt_tokens_details") or {}
    return {"input_tokens": _int(usage.get("prompt_tokens")), "output_tokens": _int(usage.get("completion_tokens")),
            "total_tokens": _int(usage.get("total_tokens")),
            "cached_tokens": _int(details.get("cached_tokens")) if isinstance(details, dict) else None}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(conn: sqlite3.Connection | None, row: dict) -> None:
    """Store the row and print its JSON line; never raises."""
    global _warned
    full = {c: row.get(c) for c in COLUMNS}
    try:
        if conn is not None:
            conn.execute(f"INSERT INTO model_log ({','.join(COLUMNS)}) VALUES ({','.join('?' * len(COLUMNS))})",
                         tuple(full[c] for c in COLUMNS))
        log.info(json.dumps(full, default=str))
    except Exception as e:  # noqa: BLE001 - the log must never fail a model call
        if not _warned:
            _warned = True
            log.warning("model call log could not be written: %s", type(e).__name__)


class Stopwatch:
    def __init__(self) -> None:
        self.at = now_iso()
        self._t = time.monotonic()

    def ms(self) -> float:
        return (time.monotonic() - self._t) * 1000


class CallLog:
    """The rows of one model call, written as they happen. A successful HTTP attempt is held until the
    answer is read, so an unusable answer is that row's outcome rather than a second row."""

    def __init__(self, conn: sqlite3.Connection | None, *, service: str, task: str, provider: str, model: str,
                 mode: str, request_key: str, case_ref: str | None = None, run_id: str | None = None):
        self.conn = conn
        self.base = {"service": service, "task": task, "provider": provider, "model": model, "mode": mode,
                     "case_ref": case_ref, "run_id": run_id, "request_key": request_key}
        self.attempts = 0
        self._held: dict | None = None

    def _row(self, **fields) -> dict:
        return {"id": uuid.uuid4().hex, **self.base, **fields}

    def replay(self, *, hit: bool) -> None:
        write(self.conn, self._row(at=now_iso(), source="replay_hit" if hit else "replay_miss", attempt=1,
                                   status="ok" if hit else "error", error_code=None if hit else "replay_miss",
                                   latency_ms=0))

    def attempt(self, *, at: str, latency_ms: float, ok: bool, http_status: int | None = None, headers: Any = None,
                answer: Any = None, error_code: str | None = None, message: str | None = None) -> None:
        self.attempts += 1
        row = self._row(at=at, source="live", attempt=self.attempts, status="ok" if ok else "error",
                        error_code=None if ok else error_code, http_status=http_status,
                        latency_ms=round(latency_ms, 1), message=None if ok else redact(message),
                        **header_fields(headers), **(usage_fields(answer) if ok else {}))
        if ok:
            self._flush()
            self._held = row
        else:
            write(self.conn, row)

    def done(self, error_code: str | None = None, message: str | None = None) -> None:
        if self._held is not None and error_code:
            self._held.update(status="error", error_code=error_code, message=redact(message))
        self._flush()

    def _flush(self) -> None:
        if self._held is not None:
            write(self.conn, self._held)
            self._held = None
