"""A person's figure for a statement line (FRD F-22.3, F-17.5).

Once a case exists its figures are changed in one place only: the Extractions tab, where the Credit Analyst
changes the extracted value and the Credit Manager checks it, and every figure worked from it follows
(engine/figure_edits.py, engine/recalculation.py). A statement line is therefore no longer set directly: a
request to do so is refused and says where the figure is changed.

An edit made directly before still stands in place of the printed figure for every reader of the statement lines
(engine/facts.py loads it; the spread and the memo say so), and can be put back; the edit stays in the history.
Nothing here touches configuration.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contracts import CaseDetail, CellEdit, StatementEditRequest
from .db import log_decision, transaction
from .pipeline import refresh_case
from .util import dumps, now_iso

CHANGED_ON_EXTRACTIONS = ("A statement figure is changed on the Extractions tab, where a second person checks the "
                          "change; the financials, the policy norms and the cross-checks then follow it.")


class EditError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _require(cond: bool, message: str, status: int = 422) -> None:
    if not cond:
        raise EditError(status, message)


def edit(conn: sqlite3.Connection, root: Path, case: CaseDetail, body: StatementEditRequest, user: dict) -> CellEdit:
    """Refused: a statement figure is changed on the Extractions tab."""
    raise EditError(409, CHANGED_ON_EXTRACTIONS)


def revert(conn: sqlite3.Connection, root: Path, case: CaseDetail, edit_id: str, reason: str, user: dict) -> None:
    """Put the statement's own figure back. The edit stays in the history."""
    reason = reason.strip()
    _require(len(reason) >= 3, "a reason is required to put the document's figure back")
    with transaction(conn):
        row = conn.execute(
            "SELECT * FROM statement_edits WHERE id = ? AND case_id = ?", (edit_id, case.id)).fetchone()
        _require(row is not None, f"no edit {edit_id!r} on this case", 404)
        _require(row["superseded_at"] is None, "this edit has already been replaced or put back", 409)
        now = now_iso()
        conn.execute("UPDATE statement_edits SET superseded_at = ?, superseded_by = 'reverted' WHERE id = ?",
                     (now, edit_id))
        log_decision(conn, at=now, actor=user["id"], case_id=case.id, action="statement.reverted",
                     detail=dumps({"edit_id": edit_id, "line": row["line"], "column": row["column_name"],
                                   "edited_value": row["value"], "reason": reason}))
    refresh_case(conn, root, case.id)
