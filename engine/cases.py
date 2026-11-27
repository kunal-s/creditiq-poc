"""Case store: create, list and read cases (docs/functional-requirements.md F-01).

A case exists only after a person confirms it (F-04.7): engine/case_create.py creates
it, after the proposal flow (F-04) and the duplicate-case check here (F-04.5).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from .config import feature_enabled, find_user_by_id
from .contracts import CaseDetail, CaseElsewhere, CaseSummary, HeaderField
from .db import log_decision, transaction
from .names import normalise_name, similarity
from .store import case_files_dir, data_root


class CaseError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DuplicateCase(CaseError):
    """F-04.5: the duplicate-case check matched and no override reason was given (or covers the match).
    `owners` gives who created each matching case, so a response shows another RM's only in part."""

    def __init__(self, duplicates: list[CaseSummary], owners: dict[str, str] | None = None) -> None:
        self.duplicates = duplicates
        self.owners = owners or {}
        ids = ", ".join(d.id for d in duplicates)
        super().__init__(f"a case for this borrower exists ({ids}); give duplicate_override_reason to create anyway")


def _pans_of(row: sqlite3.Row) -> set[str]:
    """Every PAN a stored case holds: its own, and each of its people's (the intake form's rows)."""
    pans = {(row["pan"] or "").strip().upper()} - {""}
    for rows in json.loads(row["intake_groups"] or "{}").values():
        pans |= {str(r["pan"]["value"]).strip().upper() for r in rows if (r.get("pan") or {}).get("value")}
    return pans


def find_duplicates(
    conn: sqlite3.Connection,
    *,
    pan: str | None,
    gstin: str | None,
    borrower: str | None,
    name_threshold: float,
    application_id: str | None = None,
    pans: Iterable[str] = (),
) -> list[CaseSummary]:
    """F-04.5: existing cases matching on PAN (the case's and `pans`, its people's, against each stored
    case's own and its people's), GSTIN, application ID (T2.1) or normalised name."""
    wanted = ({(pan or "").strip().upper()} | {p.strip().upper() for p in pans}) - {""}
    gstin = (gstin or "").strip().upper() or None
    application_id = (application_id or "").strip().upper() or None
    target = normalise_name(borrower)
    out = []
    for row in conn.execute("SELECT * FROM cases ORDER BY created_at"):
        same = (
            bool(wanted & _pans_of(row))
            or (gstin and (row["gstin"] or "").upper() == gstin)
            or (application_id and (row["application_id"] or "").upper() == application_id)
        )
        if not same and target:
            same = normalise_name(row["borrower"]) == target or similarity(row["borrower"], borrower) >= name_threshold
        if same:
            out.append(CaseSummary(**_summary_fields(conn, row)))
    return out


def owners_of(conn: sqlite3.Connection, found: list[CaseSummary]) -> dict[str, str]:
    """Who created each of the cases (their user ids)."""
    ids = [c.id for c in found]
    rows = conn.execute(f"SELECT id, created_by FROM cases WHERE id IN ({','.join('?' * len(ids))})", ids) if ids else []
    return {r["id"]: r["created_by"] for r in rows}


def split_duplicates(found: list[CaseSummary], owners: dict[str, str], user: dict) -> tuple[list[CaseSummary], list[CaseElsewhere]]:
    """The matches a user may read in full (all, with case.read.all; else their own), and of the others only
    the number and the RM (F-03: an RM sees only their own cases)."""
    if "case.read.all" in user["permissions"]:
        return list(found), []
    mine = [c for c in found if owners.get(c.id) == user["id"]]
    others = [CaseElsewhere(id=c.id, rm=c.rm) for c in found if owners.get(c.id) != user["id"]]
    return mine, others


class CaseBusy(CaseError):
    """The case is being processed; deleting it now would race the worker."""


def _case_tables(conn: sqlite3.Connection) -> list[str]:
    """Every table holding per-case rows, found from the schema so tables added
    by later features are covered. The decision log is append-only and keeps
    its history; the case table itself is deleted last."""
    tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return [
        t
        for t in tables
        if t not in ("cases", "decision_log")
        and any(col["name"] == "case_id" for col in conn.execute(f'PRAGMA table_info("{t}")'))
    ]


def delete_case(conn: sqlite3.Connection, case_id: str, *, actor: str, reason: str, root: Path | None = None) -> dict:
    """F-01.5: delete a case and everything it owns: rows in every case table
    and its files and page images on disk. The decision log keeps a
    `case.deleted` entry (counts only, no borrower details). Case IDs are
    never reused. Refused while the case's processing job is running."""
    root = Path(root or data_root())
    now = _now().isoformat(timespec="seconds")
    with transaction(conn):
        if conn.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone() is None:
            raise CaseError(f"no case {case_id!r}")
        if conn.execute(
            "SELECT 1 FROM jobs WHERE case_id = ? AND status = 'running'", (case_id,)
        ).fetchone():
            raise CaseBusy(f"case {case_id} is being processed; try again when processing finishes")
        # Children before parents (foreign keys are enforced).
        order = ["field_values", "documents"]
        tables = order + [t for t in _case_tables(conn) if t not in order]
        counts = {}
        for table in tables:
            counts[table] = conn.execute(f'DELETE FROM "{table}" WHERE case_id = ?', (case_id,)).rowcount
        conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        log_decision(
            conn,
            at=now,
            actor=actor,
            case_id=case_id,
            action="case.deleted",
            detail=json.dumps({"reason": reason, "rows": {k: v for k, v in counts.items() if v}}),
        )
    case_dir = case_files_dir(case_id, root).parent
    if case_dir.exists():
        shutil.rmtree(case_dir)
    return counts


def _open_reviews(conn: sqlite3.Connection, case_id: str) -> int:
    # With the integrity checks switched off (config/app.yaml), their items are not counted.
    skip = "" if feature_enabled("integrity_checks") else " AND kind <> 'integrity'"
    return conn.execute(
        "SELECT COUNT(*) FROM review_items WHERE case_id = ? AND status = 'open'" + skip, (case_id,)
    ).fetchone()[0]


#: What makes a file need a person on the Files page (src/domain/documents.ts `fileGroup`):
#: it could not be read or was refused, its checks found something, or one of its
#: documents waits on a person.
_ALTERED = ("needs_review_priority", "high_risk_indicators")


def _files_attention(conn: sqlite3.Connection, case_id: str) -> tuple[int, int]:
    """Files of the case that need a person, and of those, files whose checks found signs of an edit.
    With the integrity checks switched off (config/app.yaml), what they found counts for neither."""
    integrity = feature_enabled("integrity_checks")
    rows = conn.execute(
        """SELECT f.id, f.integrity_recommendation AS rec,
                  f.status IN ('exception', 'rejected')
                  OR (? AND f.integrity_recommendation IN ('needs_review', 'needs_review_priority', 'high_risk_indicators'))
                  OR EXISTS (SELECT 1 FROM documents d WHERE d.file_id = f.id
                             AND d.status IN ('unclassified', 'in_exception', 'in_review')) AS attention
           FROM files f WHERE f.case_id = ? AND f.status <> 'removed'""", (1 if integrity else 0, case_id)).fetchall()
    altered = sum(1 for r in rows if r["rec"] in _ALTERED) if integrity else 0
    return sum(1 for r in rows if r["attention"]), altered


def _summary_fields(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    attention, altered = _files_attention(conn, row["id"])
    return {
        "id": row["id"],
        "borrower": row["borrower"],
        "constitution": row["constitution"],
        "facilities": json.loads(row["facilities"]),
        "amount_inr": row["amount_inr"],
        "stage": row["stage"],
        "product": row["product"],
        "case_type": row["case_type"],
        "customer_type": row["customer_type"],
        "program": row["program"],
        "bank_stage": row["bank_stage"],
        "rm": (find_user_by_id(row["created_by"]) or {}).get("name", row["created_by"]),
        "created_at": row["created_at"],
        "open_review_items": _open_reviews(conn, row["id"]),
        "files_attention": attention,
        "files_altered": altered,
    }


def list_cases(conn: sqlite3.Connection, *, only_created_by: str | None = None) -> list[CaseSummary]:
    if only_created_by is None:
        rows = conn.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM cases WHERE created_by = ? ORDER BY created_at DESC", (only_created_by,)
        ).fetchall()
    return [CaseSummary(**_summary_fields(conn, row)) for row in rows]


def get_case(conn: sqlite3.Connection, case_id: str) -> CaseDetail | None:
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        return None
    return CaseDetail(
        **_summary_fields(conn, row),
        pan=row["pan"],
        gstin=row["gstin"],
        cin=row["cin"],
        udyam=row["udyam"],
        collateral_present=bool(row["collateral_present"]),
        channel=row["channel"],
        application_id=row["application_id"],
        customer_id=row["customer_id"],
        branch=row["branch"],
        as_of=row["as_of"],
        created_by=row["created_by"],
        config_version=row["config_version"],
        header={k: HeaderField(**v) for k, v in json.loads(row["header"]).items()},
        tenure_months=row["tenure_months"],
        groups={section: [{k: HeaderField(**c) for k, c in r.items()} for r in rows]
                for section, rows in json.loads(row["intake_groups"] or "{}").items()},
        assessment_opened_at=row["assessment_opened_at"],
        assessment_opened_by=row["assessment_opened_by"],
    )


class GateNotMet(RuntimeError):
    """The assessment gate is shut: completeness is not satisfied yet (F-13)."""

    def __init__(self, blockers: list[str]) -> None:
        super().__init__("assessment gate not met")
        self.blockers = blockers


def open_assessment(conn: sqlite3.Connection, root: Path, case: CaseDetail, actor: str,
                    reason: str | None = None) -> CaseDetail:
    """Create the case: open cross-verification, policy checks and the outputs (F-13).

    Refuses while the review gate is unmet, a blocking checklist item is open, a file is still an
    exception or a required field is missing (F-13.6), unless a person gives a reason for creating it
    anyway (F-04.10): who, when, why and what was still open go into the decision log, and the open
    items stay on the query list. Writing is idempotent: a case already created is returned unchanged,
    so a second press neither moves the timestamp nor logs again.
    """
    from . import progress as progress_module

    if case.assessment_opened_at:
        return case
    gate = progress_module.compute(conn, root, case).gate
    reason = (reason or "").strip()
    anyway = gate is not None and not gate.can_open and bool(reason)
    if gate is None or (not gate.can_open and not anyway):
        raise GateNotMet(list(gate.blockers) if gate else ["review_gate"])
    at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "+00:00")
    with transaction(conn):
        conn.execute(
            "UPDATE cases SET assessment_opened_at = ?, assessment_opened_by = ?"
            " WHERE id = ? AND assessment_opened_at IS NULL",
            (at, actor, case.id),
        )
        log_decision(
            conn,
            at=at,
            actor=actor,
            action="case.assessment_opened",
            case_id=case.id,
            detail=json.dumps({"score_pct": gate.score_pct, "gate_pct": gate.gate_pct}),
        )
        if anyway:
            log_decision(
                conn, at=at, actor=actor, action="case.created_anyway", case_id=case.id,
                detail=json.dumps({"reason": reason, "blockers": gate.blockers,
                                   "required_fields": [g.label for g in gate.required_fields],
                                   "blocking_open": gate.blocking_open, "open_exceptions": gate.open_exceptions}),
            )
    return get_case(conn, case.id) or case


# The cross-check that compares each identifier across the documents (config/crosschecks.yaml).
IDENTIFIER_RULES = {"pan": "ID-01", "gstin": "ID-02", "cin": "ID-05"}


class IdentifierError(Exception):
    pass


def record_identifier(conn: sqlite3.Connection, case_id: str, field: str, value: str, *, actor: str) -> None:
    """A borrower identifier taken from the documents onto the case (F-10). Only the value the
    latest cross-check found the same on every document is accepted; the header keeps what was there
    before as the proposed value and names the document it came from, and the decision log keeps who
    recorded it and when."""
    rule = IDENTIFIER_RULES.get(field)
    if rule is None:
        raise IdentifierError(f"{field!r} is not an identifier taken from the documents")
    row = conn.execute(
        "SELECT outcome, sides FROM findings WHERE case_id = ? AND rule_id = ? ORDER BY run_id DESC LIMIT 1",
        (case_id, rule),
    ).fetchone()
    sides = json.loads(row["sides"]) if row and row["outcome"] == "pass" else []
    values = {(s.get("value") or "").strip().upper() for s in sides if s.get("value")}
    agreed = next(iter(values)) if len(values) == 1 else None
    if agreed is None or agreed != value.strip().upper():
        raise IdentifierError(f"the documents do not agree on {value.strip()!r} as the {field.upper()}")
    evidence = next((e for s in sides for e in s.get("evidence") or []), None)
    source = f"document:{evidence['document_id']}:p{evidence['page']}" if evidence else "document"
    case = conn.execute(f"SELECT header, {field} FROM cases WHERE id = ?", (case_id,)).fetchone()
    if case is None:
        raise IdentifierError(f"no case {case_id!r}")
    header = json.loads(case["header"] or "{}")
    before = case[field]
    prior = header.get(field) or {}
    header[field] = HeaderField(value=agreed, proposed=prior.get("proposed") or before, source=source).model_dump()
    with transaction(conn):
        conn.execute(f"UPDATE cases SET {field} = ?, header = ? WHERE id = ?", (agreed, json.dumps(header), case_id))
        log_decision(conn, at=_now().isoformat(timespec="seconds"), actor=actor, case_id=case_id,
                     action="case.identifier_recorded",
                     detail=json.dumps({"field": field, "value": agreed, "before": before, "source": source}))
