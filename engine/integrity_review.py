"""A person's conclusion on a file's integrity (F-07A).

The checks say what they found; only a person says what it means. A reviewer
records one of genuine, altered, unclear or not completed, with the reason, and
every decision is kept (the latest is the one shown). Nothing here is set by the
checks, and a file needing review is not therefore altered.

A decision on a file that raised a file-integrity item in the review queue
settles that item: altered confirms what stood out, genuine waives it with the
reason. Unclear and not completed leave it open.
"""

from __future__ import annotations

import sqlite3
import uuid

from .contracts import IntegrityReview
from .db import log_decision, transaction
from .review_items import close_item
from .util import dumps, now_iso, stable_id

__all__ = ["DECISIONS", "IntegrityReviewError", "record", "latest"]

DECISIONS = ("genuine", "altered", "unclear", "not_completed")

#: The shortest reason accepted for a conclusion: a word or two, not a keystroke.
MIN_REASON = 3

_QUEUE = {"altered": "confirm", "genuine": "waive"}


class IntegrityReviewError(ValueError):
    pass


def record(conn: sqlite3.Connection, *, case_id: str, file_id: str, decision: str, reason: str,
           user_id: str) -> IntegrityReview:
    row = conn.execute("SELECT id, integrity FROM files WHERE id = ? AND case_id = ?", (file_id, case_id)).fetchone()
    if row is None:
        raise LookupError(f"no file {file_id!r} in case {case_id!r}")
    if decision not in DECISIONS:
        raise IntegrityReviewError(f"a decision is one of {', '.join(DECISIONS)}")
    reason = (reason or "").strip()
    if decision != "not_completed" and len(reason) < MIN_REASON:
        raise IntegrityReviewError("a conclusion needs the reason for it")
    at = now_iso()
    with transaction(conn):
        conn.execute(
            "INSERT INTO integrity_reviews (id, case_id, file_id, decision, reason, decided_by, decided_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("IR-" + uuid.uuid4().hex[:12].upper(), case_id, file_id, decision, reason, user_id, at),
        )
        if decision in _QUEUE:
            close_item(conn, item_id=stable_id("RV", case_id, "integrity", f"file:{file_id}"),
                       decision=_QUEUE[decision], reason=reason, decided_by=user_id)
        log_decision(conn, at=at, actor=user_id, case_id=case_id, action="integrity.reviewed",
                     detail=dumps({"file_id": file_id, "decision": decision, "reason": reason}))
    return IntegrityReview(decision=decision, reason=reason, decided_by=user_id, decided_at=at)


def latest(conn: sqlite3.Connection, case_id: str) -> dict[str, IntegrityReview]:
    """Each file's latest decision in a case."""
    out: dict[str, IntegrityReview] = {}
    for r in conn.execute(
        "SELECT file_id, decision, reason, decided_by, decided_at FROM integrity_reviews WHERE case_id = ? "
        "ORDER BY decided_at, rowid", (case_id,)):
        out[r["file_id"]] = IntegrityReview(decision=r["decision"], reason=r["reason"],
                                            decided_by=r["decided_by"], decided_at=r["decided_at"])
    return out
