"""Writing review items (F-17.4). One item per (case, kind, ref): raising the
same item again is a no-op, so re-runs never duplicate the queue.

A finding's escalation to the Credit Manager (engine/xv.py) is also kept with
the discrepancy's identity (case, rule, scope: the key of its XV reference),
because a run of the checks withdraws the open item of a discrepancy that does
not fail (engine/crosschecks.run). When the discrepancy fails again, the item
raised for it carries the escalation still unresolved, so it stays with the
Credit Manager; accepting or dismissing the discrepancy resolves it."""

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


# --- Escalations of findings ---


def keep_escalation(conn: sqlite3.Connection, *, case_id: str, rule_id: str, scope: str | None,
                    escalation: dict) -> None:
    """Keep a discrepancy's escalation ({by, at, comment}, as the review item's detail holds it)
    with its identity, unresolved."""
    conn.execute(
        """INSERT INTO finding_escalations (case_id, rule_id, scope, escalated_by, escalated_at, comment)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT (case_id, rule_id, scope) DO UPDATE SET escalated_by = excluded.escalated_by,
             escalated_at = excluded.escalated_at, comment = excluded.comment, resolved_by = NULL,
             resolved_at = NULL""",
        (case_id, rule_id, scope or "", escalation["by"], escalation["at"], escalation["comment"]),
    )


def unresolved_escalations(conn: sqlite3.Connection, case_id: str) -> dict[tuple[str, str], dict]:
    """The case's escalations not yet resolved, by (rule, scope), each as a review item's detail
    holds it."""
    return {(r["rule_id"], r["scope"]): {"by": r["escalated_by"], "at": r["escalated_at"], "comment": r["comment"]}
            for r in conn.execute(
                "SELECT * FROM finding_escalations WHERE case_id = ? AND resolved_at IS NULL", (case_id,))}


def resolve_escalation(conn: sqlite3.Connection, *, case_id: str, finding_id: str, resolved_by: str) -> None:
    """Accepting or dismissing a discrepancy resolves its escalation, if it has one."""
    found = conn.execute("SELECT rule_id, scope FROM findings WHERE id = ? AND case_id = ?",
                         (finding_id, case_id)).fetchone()
    if found is None:
        return
    conn.execute(
        """UPDATE finding_escalations SET resolved_by = ?, resolved_at = ?
           WHERE case_id = ? AND rule_id = ? AND scope = ? AND resolved_at IS NULL""",
        (resolved_by, now_iso(), case_id, found["rule_id"], found["scope"] or ""),
    )
