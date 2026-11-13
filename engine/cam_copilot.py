"""Regenerate with copilot (docs/functional-requirements.md F-23): a model redrafts one section of the
draft CAM in other words, on the analyst's instruction, from the section's own paragraphs and facts.

Configuration governs it (config/cam.yaml `copilot`): the model, and the only sampling parameters
sent (temperature, seed). Every answer is recorded by its request (cam_model_calls), so the same
request is answered the same way: determinism is record and replay. An answer that brings in a
figure the section does not hold is refused, never shown. Nothing is kept until a person keeps it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from contextvars import ContextVar

from .configstore.schema import CamCopilotConfig
from .contracts import Cam
from .util import now_iso
from . import cam_review
from .model_log import CallLog, Stopwatch

SCHEMA = {
    "type": "object",
    "properties": {"paragraphs": {"type": "array", "items": {"type": "string"}}},
    "required": ["paragraphs"],
    "additionalProperties": False,
}
FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?")
#: The model call log of the call in progress (engine/model_log.py), for `_call` to report its attempts.
_call_log: ContextVar[CallLog | None] = ContextVar("cam_copilot_call_log", default=None)


class CopilotError(cam_review.ReviewError):
    pass


def available(cfg: CamCopilotConfig) -> bool:
    return bool(cfg.enabled and cfg.model and os.environ.get(cfg.api_key_env))


def _current_words(cam: Cam, section_id: str) -> tuple[str, list[str], list[str]]:
    """The section's title, its paragraphs as they read now, and its other facts, as lines."""
    if section_id == cam_review.SUMMARY:
        words = cam.summary_review.paragraphs or cam_review.drafted_paragraphs(cam, section_id)
        return cam.summary_title, words, [cam.rating_note] if cam.rating_note else []
    if section_id == cam_review.RECOMMENDATION:
        words = cam.recommendation_review.paragraphs or cam_review.drafted_paragraphs(cam, section_id)
        return cam.recommendation_title, words, list(cam.recommendation_prompts)
    s = next((s for s in cam.sections if s.id == section_id), None)
    if s is None:
        raise CopilotError(f"no section {section_id!r} in the memo", 404)
    words = [b.paragraph.text for b in s.blocks if b.kind == "paragraph" and b.paragraph]
    facts = [f"{f.label}: {f.value.text}" for b in s.blocks if b.kind == "facts" for f in b.facts]
    for b in s.blocks:
        if b.kind == "table" and b.table:
            facts += [" | ".join(c.text for c in row) for row in b.table.rows]
    return s.title, words, facts


def _figures(text: str) -> set[str]:
    return {m.replace(",", "") for m in FIGURE.findall(text)}


def regenerate(conn: sqlite3.Connection, cam: Cam, section_id: str, instruction: str,
               cfg: CamCopilotConfig) -> tuple[list[str], bool]:
    """The section redrafted, and whether the answer was a recorded one."""
    if not available(cfg):
        raise CopilotError("The copilot is not configured: its key is not set.", 503)
    title, words, facts = _current_words(cam, section_id)
    if not words:
        raise CopilotError("There are no paragraphs in this section to redraft.")
    fill = {
        "title": title,
        "instruction": instruction.strip() or "None: redraft for clarity and concision.",
        "paragraphs": "\n".join(f"{i}. {w}" for i, w in enumerate(words, start=1)),
        "facts": "\n".join(f"- {f}" for f in facts) or "- none",
    }
    user = cfg.user
    for key, value in fill.items():
        user = user.replace("{{" + key + "}}", value)
    sampling = {k: v for k, v in (("temperature", cfg.temperature), ("seed", cfg.seed)) if v is not None}
    body = {
        "model": cfg.model,
        "messages": [{"role": "system", "content": cfg.system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "cam_section", "strict": True, "schema": SCHEMA}},
        **sampling,
    }
    key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    row = conn.execute("SELECT response FROM cam_model_calls WHERE case_id = ? AND request_hash = ?",
                       (cam.case_id, key)).fetchone()
    log = CallLog(conn, service="cam", task="cam_section", provider=cfg.provider, model=cfg.model, mode="record",
                  request_key=key, case_ref=cam.case_id)
    if row:
        log.replay(hit=True)
        return json.loads(row["response"]), True
    paragraphs = _logged_call(cfg, body, log)
    # Nothing the section does not hold: every figure in the answer must be in what was given.
    given = _figures(" ".join([*words, *facts, fill["instruction"]]))
    new = sorted(_figures(" ".join(paragraphs)) - given)
    if new:
        raise CopilotError(f"The copilot's draft brought in figures the section does not hold ({', '.join(new[:3])}); "
                           "it was not kept.")
    conn.execute("INSERT INTO cam_model_calls (case_id, request_hash, model, response, at) VALUES (?, ?, ?, ?, ?)",
                 (cam.case_id, key, cfg.model, json.dumps(paragraphs), now_iso()))
    conn.commit()
    return paragraphs, False


def _logged_call(cfg: CamCopilotConfig, body: dict, log: CallLog) -> list[str]:
    """`_call` with its attempts written to the model call log. A stand-in `_call` that reports no
    attempt (a test's) is timed here, as one attempt."""
    watch = Stopwatch()
    token = _call_log.set(log)
    try:
        paragraphs = _call(cfg, body)
    except CopilotError as e:
        if log.attempts == 0:
            log.attempt(at=watch.at, latency_ms=watch.ms(), ok=False, error_code=type(e).__name__, message=str(e))
        raise
    finally:
        _call_log.reset(token)
    if log.attempts == 0:
        log.attempt(at=watch.at, latency_ms=watch.ms(), ok=True)
    log.done()
    return paragraphs


def _call(cfg: CamCopilotConfig, body: dict) -> list[str]:
    log = _call_log.get()
    req = urllib.request.Request(
        cfg.base_url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get(cfg.api_key_env, '')}"})
    watch = Stopwatch()
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
            status, headers = getattr(resp, "status", None), getattr(resp, "headers", None)
            answer = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if log:
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:  # noqa: BLE001 - the body is only for the log
                detail = ""
            log.attempt(at=watch.at, latency_ms=watch.ms(), ok=False, http_status=e.code, headers=e.headers,
                        error_code="http", message=f"{e.code}: {detail}")
        raise CopilotError(f"The copilot could not be reached ({e.code}).", 502) from e
    except (OSError, ValueError) as e:
        if log:
            log.attempt(at=watch.at, latency_ms=watch.ms(), ok=False, error_code=type(e).__name__, message=str(e))
        raise CopilotError("The copilot could not be reached.", 502) from e
    if log:
        log.attempt(at=watch.at, latency_ms=watch.ms(), ok=True, http_status=status, headers=headers, answer=answer)
    try:
        msg = answer["choices"][0]["message"]
        if msg.get("refusal"):
            if log:
                log.done("refusal", str(msg.get("refusal")))
            raise CopilotError("The copilot declined to redraft this section.", 502)
        paragraphs = json.loads(msg.get("content") or "")["paragraphs"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        if log:
            log.done("bad_response", "the answer could not be read")
        raise CopilotError("The copilot's answer could not be read.", 502) from e
    out = [p.strip() for p in paragraphs if isinstance(p, str) and p.strip()]
    if not out:
        if log:
            log.done("bad_response", "the answer held no paragraphs")
        raise CopilotError("The copilot returned no paragraphs.", 502)
    return out
