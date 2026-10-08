"""Read models for the case screens, straight from the store (AD-3).

Writers land with their features (Wave 1 onward); these reads are the
contract the screens build against, so they return real, possibly empty,
data from the first day.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import completeness
from .contracts import (
    CaseDetail,
    Classification,
    Evidence,
    FieldValue,
    FileRecord,
    Finding,
    FindingSide,
    LogicalDocument,
    PageInfo,
    QueryItem,
    Readiness,
    ReviewItem,
)

def _json(text: str | None):
    return None if text is None else json.loads(text)


def files(conn: sqlite3.Connection, case_id: str) -> list[FileRecord]:
    rows = conn.execute("SELECT * FROM files WHERE case_id = ? ORDER BY uploaded_at, rowid", (case_id,))
    return [FileRecord(**dict(row)) for row in rows]


def documents(conn: sqlite3.Connection, case_id: str) -> list[LogicalDocument]:
    """A person's type assignment (F-09.5) is shown as the classification at
    exit tier "person"; the machine's signals and candidates are kept."""
    rows = conn.execute("SELECT * FROM documents WHERE case_id = ? ORDER BY file_id, page_from", (case_id,))
    out = []
    for row in rows:
        d = dict(row)
        d["pages"] = [PageInfo(**p) for p in json.loads(d["pages"])]
        classification = json.loads(d["classification"]) if d["classification"] else None
        if d.get("assigned_types"):
            classification = {
                **(classification or {"signals": [], "candidates": []}),
                "types": json.loads(d["assigned_types"]),
                "exit_tier": "person",
                "confidence": 1.0,
            }
        d["classification"] = Classification(**classification) if classification else None
        d["label_mismatch"] = bool(d["label_mismatch"])
        out.append(LogicalDocument(**d))
    return out


def field_values(conn: sqlite3.Connection, case_id: str, document_id: str | None = None) -> list[FieldValue]:
    if document_id:
        rows = conn.execute(
            "SELECT * FROM field_values WHERE case_id = ? AND document_id = ? ORDER BY field", (case_id, document_id)
        )
    else:
        rows = conn.execute("SELECT * FROM field_values WHERE case_id = ? ORDER BY document_id, field", (case_id,))
    out = []
    for row in rows:
        d = dict(row)
        d["value"] = _json(d["value"])
        d["corrected_value"] = _json(d["corrected_value"])
        d["evidence"] = Evidence(**json.loads(d["evidence"])) if d["evidence"] else None
        d["confidence_components"] = json.loads(d["confidence_components"])
        out.append(FieldValue(**d))
    return out


def findings(conn: sqlite3.Connection, case_id: str) -> list[Finding]:
    rows = conn.execute(
        """SELECT * FROM findings WHERE case_id = ? ORDER BY
           CASE outcome WHEN 'fail' THEN 0 WHEN 'incomplete' THEN 1 WHEN 'pass' THEN 2 ELSE 3 END,
           CASE severity WHEN 'serious' THEN 0 WHEN 'moderate' THEN 1 ELSE 2 END, blocking DESC, rule_id, title""",
        (case_id,),
    )
    out = []
    for row in rows:
        d = dict(row)
        d["blocking"] = bool(d["blocking"])
        d["sides"] = [FindingSide(**s) for s in json.loads(d["sides"])]
        d["detail"] = json.loads(d["detail"]) if d.get("detail") else None
        d["missing"] = json.loads(d.get("missing") or "[]")
        out.append(Finding(**d))
    return out


def query_items(conn: sqlite3.Connection, case_id: str) -> list[QueryItem]:
    rows = conn.execute(
        """SELECT * FROM query_items WHERE case_id = ?
           ORDER BY CASE grp WHEN 'documents_needed' THEN 0 WHEN 'documents_to_redo' THEN 1 ELSE 2 END,
                    resolved, rowid""",
        (case_id,),
    )
    out = []
    for row in rows:
        d = dict(row)
        d["group"] = d.pop("grp")
        d["evidence"] = [Evidence(**e) for e in json.loads(d["evidence"])]
        d["resolved"] = bool(d["resolved"])
        out.append(QueryItem(**d))
    return out


def review_items(conn: sqlite3.Connection, *, case_id: str | None = None, open_only: bool = True) -> list[ReviewItem]:
    sql = "SELECT * FROM review_items WHERE 1 = 1"
    args: list = []
    if case_id:
        sql += " AND case_id = ?"
        args.append(case_id)
    if open_only:
        sql += " AND status = 'open'"
    sql += " ORDER BY created_at"
    return [ReviewItem(**dict(row)) for row in conn.execute(sql, args)]


def readiness(conn: sqlite3.Connection, data_root: Path, case: CaseDetail) -> Readiness:
    """F-12 and F-13: the checklist for the case's constitution and
    attributes, each item with its status and specific deficiency, and the
    weighted readiness against the configured gate (engine/completeness.py).
    While the constitution is unknown the checklist is provisional and holds
    only the items every constitution needs (F-12.3)."""
    result, _ = completeness.evaluate(conn, data_root, case)
    return result
