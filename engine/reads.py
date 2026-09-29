"""Read models for the case screens, straight from the store (AD-3).

Writers land with their features (Wave 1 onward); these reads are the
contract the screens build against, so they return real, possibly empty,
data from the first day.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .checklist import CaseAttributes, applies
from .config import load_app_config
from .configstore.reader import load_checklist_taxonomy, load_policy
from .contracts import (
    CaseDetail,
    ChecklistItemState,
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

ALL_CONSTITUTIONS = ("private_limited", "proprietorship", "partnership")


def _json(text: str | None):
    return None if text is None else json.loads(text)


def files(conn: sqlite3.Connection, case_id: str) -> list[FileRecord]:
    rows = conn.execute("SELECT * FROM files WHERE case_id = ? ORDER BY uploaded_at, original_name", (case_id,))
    return [FileRecord(**dict(row)) for row in rows]


def documents(conn: sqlite3.Connection, case_id: str) -> list[LogicalDocument]:
    rows = conn.execute("SELECT * FROM documents WHERE case_id = ? ORDER BY file_id, page_from", (case_id,))
    out = []
    for row in rows:
        d = dict(row)
        d["pages"] = [PageInfo(**p) for p in json.loads(d["pages"])]
        d["classification"] = Classification(**json.loads(d["classification"])) if d["classification"] else None
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
    rows = conn.execute("SELECT * FROM findings WHERE case_id = ? ORDER BY blocking DESC, severity, rule_id", (case_id,))
    out = []
    for row in rows:
        d = dict(row)
        d["blocking"] = bool(d["blocking"])
        d["sides"] = [FindingSide(**s) for s in json.loads(d["sides"])]
        out.append(Finding(**d))
    return out


def query_items(conn: sqlite3.Connection, case_id: str) -> list[QueryItem]:
    rows = conn.execute("SELECT * FROM query_items WHERE case_id = ? ORDER BY grp, id", (case_id,))
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
    """F-12 and F-13.4. Item status comes from the checklist state the
    completeness feature (F-13) writes; until it has run, every item is
    missing. While the constitution is unknown the checklist is provisional
    and holds only the items every constitution needs (F-12.3)."""
    taxonomy = load_checklist_taxonomy(data_root)
    policy = load_policy(data_root)
    facility_sets = {f["id"]: f.get("sets") for f in load_app_config()["facilities"]}
    attrs = CaseAttributes.from_case(
        facilities=case.facilities,
        amount_inr=case.amount_inr,
        collateral_present=case.collateral_present,
        facility_sets=facility_sets,
        mpbf_above_limit_inr=policy.working_capital.mpbf_above_limit_inr,
    )
    provisional = case.constitution not in ALL_CONSTITUTIONS
    if provisional:
        items = [
            item
            for item in taxonomy.items
            if set(ALL_CONSTITUTIONS) <= set(item.constitutions) and all(attrs.has(a) for a in item.requires_attributes)
        ]
    else:
        items = [item for item in taxonomy.items if applies(item, case.constitution, attrs)]

    states = [
        ChecklistItemState(
            item_id=item.id,
            name=item.name,
            section=item.category,
            blocking=item.blocking,
            weight=item.weight,
            status="missing",
            deficiency="Not yet received",
            why=item.why,
            basis=item.basis,
        )
        for item in items
    ]
    total = sum(s.weight for s in states) or 1
    satisfied = sum(s.weight for s in states if s.status in ("satisfied", "waived"))
    blocking_open = sum(1 for s in states if s.blocking and s.status not in ("satisfied", "waived"))
    score = round(100 * satisfied / total, 1)
    return Readiness(
        score_pct=score,
        gate_pct=taxonomy.review_gate_threshold,
        gate_met=score >= taxonomy.review_gate_threshold and blocking_open == 0,
        blocking_open=blocking_open,
        provisional=provisional,
        items=states,
    )
