"""A person's figure for a statement line (FRD F-22.3, F-17.5).

The statement's own value stays where it was read; an edit stands in place of it for every reader of
the statement lines (the spread, the policy norms, the cross-checks, the memo), so no screen disagrees
with another. The edit is entered in the unit the statement prints and kept with the figure the document
gives, the reason, who made it and when. An earlier edit of the same figure is superseded, never
overwritten. Nothing here touches configuration.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from . import facts as facts_module
from . import statements
from .configstore import reader
from .contracts import CaseDetail, CellEdit, StatementEditRequest
from .db import log_decision, transaction
from .pipeline import refresh_case
from .util import dumps, now_iso, stable_id

COLUMNS = ("current_period", "previous_period")


class EditError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _require(cond: bool, message: str, status: int = 422) -> None:
    if not cond:
        raise EditError(status, message)


def _doc(conn: sqlite3.Connection, root: Path, case_id: str, document_id: str) -> facts_module.Doc:
    doc = next((d for d in facts_module.load_documents(conn, root, case_id) if d.id == document_id), None)
    _require(doc is not None, f"no document {document_id!r} in this case", 404)
    _require("audited_financial_statements" in doc.types, "only a financial statement's lines are edited here")
    return doc


def _out(row: sqlite3.Row | dict) -> CellEdit:
    from .config import load_roles_config

    by = next((u["name"] for u in load_roles_config()["users"] if u["id"] == row["edited_by"]), row["edited_by"])
    return CellEdit(id=row["id"], original=row["original"], value=row["value"], reason=row["reason"], edited_by=by,
                    edited_at=row["edited_at"])


def edit(conn: sqlite3.Connection, root: Path, case: CaseDetail, body: StatementEditRequest, user: dict) -> CellEdit:
    reason = body.reason.strip()
    _require(len(reason) >= 3, "a reason is required for an edit")
    _require(math.isfinite(body.value), "the figure must be a number")
    cfg = reader.load_statements(root)
    _require(body.line in cfg.lines, f"{body.line!r} is not a line of the statement; derived figures follow from their lines")
    _require(body.column in COLUMNS, "the column is the statement's own year or its comparative")
    doc = _doc(conn, root, case.id, body.document_id)
    # What the document gives for this line, in its own unit: the figure that stays beside the edit.
    for_doc = facts_module.Doc(**{**doc.__dict__, "edits": {}})
    printed = statements.lines(for_doc, cfg, column=body.column).get(body.line)
    original = printed.printed if printed is not None and printed.state in ("printed", "nil") else None

    with transaction(conn):
        now = now_iso()
        edit_id = stable_id("SE", case.id, doc.id, body.line, body.column, now, user["id"])
        conn.execute(
            "UPDATE statement_edits SET superseded_at = ?, superseded_by = ? "
            "WHERE document_id = ? AND line = ? AND column_name = ? AND superseded_at IS NULL",
            (now, edit_id, doc.id, body.line, body.column))
        conn.execute(
            "INSERT INTO statement_edits (id, case_id, document_id, line, column_name, original, value, reason, "
            "edited_by, edited_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (edit_id, case.id, doc.id, body.line, body.column, original, body.value, reason, user["id"], now))
        log_decision(conn, at=now, actor=user["id"], case_id=case.id, action="statement.edited",
                     detail=dumps({"document_id": doc.id, "line": body.line, "column": body.column,
                                   "document_value": original, "value": body.value, "reason": reason}))
    refresh_case(conn, root, case.id)
    return _out(conn.execute("SELECT * FROM statement_edits WHERE id = ?", (edit_id,)).fetchone())


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
