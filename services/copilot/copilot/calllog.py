"""The case assistant's model call log: one row per model request (each attempt the wrapped model makes)
and per replay, in the store's append-only `model_log` table and as one JSON line on the
`creditiq.model` logger. The same columns as the document-processing service's and the engine's logs.

Never the prompt, the answer, the key or the Authorization header: the request is named by its
recording key, and an error message is cut to 300 characters with key-like values redacted. Writing
the log never fails a turn: any error is caught, warned about once, and the turn goes on. The turn and
the case a call belongs to are carried in a ContextVar, set around one turn (runner.py)."""

from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from .store import MODEL_LOG_COLUMNS

SERVICE = "copilot"
LOGGER = "creditiq.model"
log = logging.getLogger(LOGGER)
_context: ContextVar[dict] = ContextVar("copilot_model_call_context", default={})
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
    """The case and turn every model call inside belongs to."""
    token = _context.set({"case_ref": case_ref, "run_id": run_id})
    try:
        yield
    finally:
        _context.reset(token)


def context() -> dict:
    return dict(_context.get())


def redact(message: Any) -> str | None:
    if message is None:
        return None
    text = message if isinstance(message, str) else json.dumps(message, default=str)
    for rx, sub in _SECRETS:
        text = rx.sub(sub, text)
    return text[:300]


def _int(v: Any) -> int | None:
    try:
        return int(float(v)) if v is not None and str(v).strip() != "" else None
    except (TypeError, ValueError):
        return None


def header_fields(headers: Any, retry_after: float | None = None) -> dict:
    try:
        h = {str(k).lower(): v for k, v in dict(headers or {}).items()}
    except (TypeError, ValueError):
        h = {}
    retry = retry_after
    for name, scale in (("retry-after-ms", 1000), ("retry-after", 1)):
        if retry is None and h.get(name) not in (None, ""):
            try:
                retry = float(h[name]) / scale
            except ValueError:
                retry = None
    return {"ratelimit_remaining_tokens": _int(h.get("x-ratelimit-remaining-tokens")),
            "ratelimit_remaining_requests": _int(h.get("x-ratelimit-remaining-requests")),
            "retry_after_s": retry}


def usage_fields(usage: Any) -> dict:
    """Tokens from a Pydantic AI response's `usage` (input, output, cache read)."""
    if usage is None:
        return {}
    inp, out = _int(getattr(usage, "input_tokens", None)), _int(getattr(usage, "output_tokens", None))
    total = (inp or 0) + (out or 0) if inp is not None or out is not None else None
    return {"input_tokens": inp, "output_tokens": out, "total_tokens": total,
            "cached_tokens": _int(getattr(usage, "cache_read_tokens", None))}


def write(store: Any, row: dict) -> None:
    """Store the row and print its JSON line; never raises."""
    global _warned
    full = {c: row.get(c) for c in MODEL_LOG_COLUMNS}
    full["id"] = full["id"] or uuid.uuid4().hex
    try:
        put = getattr(store, "put_model_log", None)
        if put is not None:
            put(full)
        log.info(json.dumps(full, default=str))
    except Exception as e:  # noqa: BLE001 - the log must never fail a turn
        if not _warned:
            _warned = True
            log.warning("model call log could not be written: %s", type(e).__name__)
