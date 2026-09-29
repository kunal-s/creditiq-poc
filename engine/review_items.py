"""Writing review items (F-17.4). One item per (case, kind, ref): raising the
same item again is a no-op, so re-runs never duplicate the queue."""

from __future__ import annotations

import sqlite3

from .util import dumps, now_iso, stable_id


def raise_item(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    kind: str,
    ref: str,
    summary: str,
    detail: dict | None = None,
    maker: str | None = None,
) -> str:
    item_id = stable_id("RV", case_id, kind, ref)
    conn.execute(
        """INSERT INTO review_items (id, case_id, kind, ref, summary, created_at, status, maker, detail)
           VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
           ON CONFLICT(case_id, kind, ref) DO NOTHING""",
        (item_id, case_id, kind, ref, summary, now_iso(), maker, dumps(detail or {})),
    )
    return item_id


def reopen_item(
    conn: sqlite3.Connection, *, case_id: str, kind: str, ref: str, summary: str, detail: dict | None, maker: str
) -> str:
    """For manual entry: a fresh maker entry replaces an earlier one that was
    never checked."""
    item_id = stable_id("RV", case_id, kind, ref)
    conn.execute(
        """INSERT INTO review_items (id, case_id, kind, ref, summary, created_at, status, maker, detail)
           VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
           ON CONFLICT(case_id, kind, ref) DO UPDATE SET
             summary = excluded.summary, status = 'open', maker = excluded.maker, detail = excluded.detail,
             decision = NULL, reason = NULL, decided_by = NULL, decided_at = NULL""",
        (item_id, case_id, kind, ref, summary, now_iso(), maker, dumps(detail or {})),
    )
    return item_id


def close_item(conn: sqlite3.Connection, *, item_id: str, decision: str, reason: str, decided_by: str) -> None:
    conn.execute(
        """UPDATE review_items SET status = 'decided', decision = ?, reason = ?, decided_by = ?, decided_at = ?
           WHERE id = ? AND status = 'open'""",
        (decision, reason, decided_by, now_iso(), item_id),
    )
