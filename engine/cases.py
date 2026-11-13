"""Case store: create, list and read cases (docs/functional-requirements.md F-01).

A case exists only after a person confirms it (F-04.7); this module creates
exactly what it is given. The proposal flow (F-04) and the duplicate-case
check (F-04.5) sit in front of `create_case`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import (branch_for_label, feature_enabled, find_user_by_id, load_app_config, option_default,
                     option_ids)
from .contracts import CaseCreate, CaseDetail, CaseSummary, HeaderField
from .db import log_decision, transaction
from .names import normalise_name, similarity
from .store import MESSAGE_FILE_NAME, case_files_dir, data_root
from .util import stable_id


class CaseError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_case_id(conn: sqlite3.Connection, year: int) -> str:
    row = conn.execute("SELECT last FROM case_seq WHERE year = ?", (year,)).fetchone()
    seq = (row["last"] if row else 0) + 1
    conn.execute(
        "INSERT INTO case_seq (year, last) VALUES (?, ?) ON CONFLICT(year) DO UPDATE SET last = excluded.last",
        (year, seq),
    )
    return load_app_config()["case_id"]["format"].format(year=year, seq=seq)


def _validate(data: CaseCreate) -> None:
    if data.channel not in option_ids("channels"):
        raise CaseError(f"unknown channel {data.channel!r}")
    if data.constitution not in option_ids("constitutions"):
        raise CaseError(f"unknown constitution {data.constitution!r}")
    unknown = set(data.facilities) - option_ids("facilities")
    if unknown:
        raise CaseError(f"unknown facilities {sorted(unknown)}")
    if data.case_type not in option_ids("case_types"):
        raise CaseError(f"unknown case type {data.case_type!r}")
    for value, key, label in (
        (data.product, "products", "product"),
        (data.branch, "branches", "branch"),
        (data.bank_stage, "bank_stages", "bank stage"),
    ):
        if value is not None and value not in option_ids(key):
            raise CaseError(f"unknown {label} {value!r}")


def _clean_id(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _with_defaults(data: CaseCreate, created_by: str) -> CaseCreate:
    """T2.1: fill product and bank stage from their configured defaults and the
    branch from the RM's own, recording each in the header with where it came
    from, so a default is never mistaken for a confirmed value (F-01.2)."""
    header = dict(data.header)
    filled: dict[str, str | None] = {}
    rm_branch = branch_for_label((find_user_by_id(created_by) or {}).get("branch"))
    for name, current, default, source in (
        ("product", data.product, option_default("products"), "default:config"),
        ("bank_stage", data.bank_stage, option_default("bank_stages"), "default:config"),
        ("branch", data.branch, rm_branch, "default:rm"),
    ):
        if current is not None or default is None:
            continue
        filled[name] = default
        if name not in header:
            header[name] = HeaderField(value=default, proposed=default, source=source)
    return data.model_copy(update={
        **filled,
        "application_id": _clean_id(data.application_id),
        "customer_id": _clean_id(data.customer_id),
        "header": header,
    })


class DuplicateCase(CaseError):
    """F-04.5: the duplicate-case check matched and no override reason was given."""

    def __init__(self, duplicates: list[CaseSummary]) -> None:
        self.duplicates = duplicates
        ids = ", ".join(d.id for d in duplicates)
        super().__init__(f"a case for this borrower exists ({ids}); give duplicate_override_reason to create anyway")


def find_duplicates(
    conn: sqlite3.Connection,
    *,
    pan: str | None,
    gstin: str | None,
    borrower: str | None,
    name_threshold: float,
    application_id: str | None = None,
) -> list[CaseSummary]:
    """F-04.5: existing cases matching on PAN, GSTIN, application ID (T2.1) or normalised name."""
    pan = (pan or "").strip().upper() or None
    gstin = (gstin or "").strip().upper() or None
    application_id = (application_id or "").strip().upper() or None
    target = normalise_name(borrower)
    out = []
    for row in conn.execute("SELECT * FROM cases ORDER BY created_at"):
        same = (
            (pan and (row["pan"] or "").upper() == pan)
            or (gstin and (row["gstin"] or "").upper() == gstin)
            or (application_id and (row["application_id"] or "").upper() == application_id)
        )
        if not same and target:
            same = normalise_name(row["borrower"]) == target or similarity(row["borrower"], borrower) >= name_threshold
        if same:
            out.append(CaseSummary(**_summary_fields(conn, row)))
    return out


def _check_message_sources(data: CaseCreate) -> None:
    for name, h in data.header.items():
        m = re.fullmatch(r"message:(\d+)-(\d+)", h.source or "")
        if not m:
            continue
        start, end = int(m[1]), int(m[2])
        if data.message_text is None or not (0 <= start < end <= len(data.message_text)):
            raise CaseError(f"header field {name!r}: source {h.source!r} does not point into the message")


def _store_message(conn: sqlite3.Connection, root: Path, case_id: str, data: CaseCreate, created_by: str, at: str,
                   config_version: str | None) -> None:
    """F-04.8: the pasted message, unchanged, as the case's first document."""
    raw = data.message_text.encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    files_dir = case_files_dir(case_id, root)
    for d in (files_dir.parent.parent, files_dir.parent, files_dir):
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(d, 0o700)
    target = files_dir / sha
    if not target.exists():
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
    file_id = stable_id("F", case_id, "message")
    conn.execute(
        """INSERT INTO files (id, case_id, sha256, original_name, archive_path, content_type, size_bytes, channel,
               uploaded_by, uploaded_at, status, stored_name, processed_at)
           VALUES (?, ?, ?, ?, NULL, 'text/plain', ?, ?, ?, ?, 'registered', ?, ?)""",
        (file_id, case_id, sha, MESSAGE_FILE_NAME, len(raw), data.channel, created_by, at, sha, at),
    )
    classification = {"types": ["application_message"], "confidence": 1.0, "exit_tier": "person", "signals": [],
                      "candidates": []}
    conn.execute(
        """INSERT INTO documents (id, case_id, file_id, page_from, page_to, pages, grade, classification, status,
               config_version, doc_key, created_at)
           VALUES (?, ?, ?, 1, 1, ?, 'A', ?, 'accepted', ?, 'message', ?)""",
        (
            stable_id("DOC", case_id, file_id, "message"),
            case_id,
            file_id,
            json.dumps([{"n": 1, "route": "text", "grade": "A", "reasons": [], "ocr_confidence": None}]),
            json.dumps(classification),
            config_version,
            at,
        ),
    )


# Header fields that are the RM's declaration, kept for triangulation (F-04.8, F-19).
DECLARED_FIELDS = ("declared_turnover_inr", "amount_inr", "existing_banking")


def _store_declared(conn: sqlite3.Connection, case_id: str, data: CaseCreate) -> None:
    for name in DECLARED_FIELDS:
        h = data.header.get(name)
        value = h.value if h else None
        if name == "amount_inr" and value is None:
            value = str(data.amount_inr)
        if value is None:
            continue
        conn.execute(
            """INSERT INTO declared_figures (case_id, field, value, proposed, source, basis)
               VALUES (?, ?, ?, ?, ?, 'RM declaration, unverified')""",
            (case_id, name, value, h.proposed if h else None, (h.source if h else None) or "person"),
        )


def create_case(
    conn: sqlite3.Connection,
    data: CaseCreate,
    *,
    created_by: str,
    config_version: str | None,
    root: Path | None = None,
    name_threshold: float = 0.85,
) -> CaseDetail:
    _validate(data)
    _check_message_sources(data)
    data = _with_defaults(data, created_by)
    duplicates = find_duplicates(
        conn, pan=data.pan, gstin=data.gstin, borrower=data.borrower, name_threshold=name_threshold,
        application_id=data.application_id,
    )
    if duplicates and not (data.duplicate_override_reason or "").strip():
        raise DuplicateCase(duplicates)
    root = Path(root or data_root())
    now = _now()
    with transaction(conn):
        case_id = _next_case_id(conn, now.year)
        conn.execute(
            """INSERT INTO cases (id, borrower, constitution, facilities, amount_inr, pan, gstin, cin, udyam,
                   collateral_present, channel, stage, as_of, created_by, created_at, config_version, header,
                   product, case_type, application_id, customer_id, branch, bank_stage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Intake', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                case_id,
                data.borrower.strip(),
                data.constitution,
                json.dumps(data.facilities),
                data.amount_inr,
                data.pan,
                data.gstin,
                data.cin,
                data.udyam,
                int(data.collateral_present),
                data.channel,
                now.date().isoformat(),
                created_by,
                now.isoformat(timespec="seconds"),
                config_version,
                json.dumps({k: v.model_dump() for k, v in data.header.items()}),
                data.product,
                data.case_type,
                data.application_id,
                data.customer_id,
                data.branch,
                data.bank_stage,
            ),
        )
        log_decision(
            conn,
            at=now.isoformat(timespec="seconds"),
            actor=created_by,
            case_id=case_id,
            action="case.created",
            detail=json.dumps(
                {
                    "channel": data.channel,
                    "product": data.product,
                    "case_type": data.case_type,
                    "application_id": data.application_id,
                    "customer_id": data.customer_id,
                    "branch": data.branch,
                    "bank_stage": data.bank_stage,
                    "config_version": config_version,
                    "duplicate_override_reason": data.duplicate_override_reason,
                    "duplicates": [d.id for d in duplicates],
                    "message_sha256": hashlib.sha256(data.message_text.encode("utf-8")).hexdigest()
                    if data.message_text is not None
                    else None,
                }
            ),
        )
        at = now.isoformat(timespec="seconds")
        if data.message_text is not None:
            _store_message(conn, root, case_id, data, created_by, at, config_version)
        _store_declared(conn, case_id, data)
    detail = get_case(conn, case_id)
    assert detail is not None
    return detail


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
           FROM files f WHERE f.case_id = ?""", (1 if integrity else 0, case_id)).fetchall()
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
        assessment_opened_at=row["assessment_opened_at"],
        assessment_opened_by=row["assessment_opened_by"],
    )


class GateNotMet(RuntimeError):
    """The assessment gate is shut: completeness is not satisfied yet (F-13)."""

    def __init__(self, blockers: list[str]) -> None:
        super().__init__("assessment gate not met")
        self.blockers = blockers


def open_assessment(conn: sqlite3.Connection, root: Path, case: CaseDetail, actor: str) -> CaseDetail:
    """Create the case: open cross-verification, policy checks and the outputs (F-13).

    Refuses while the review gate is unmet, a blocking checklist item is open or a file is
    still an exception. Writing is idempotent: a case already created is returned unchanged,
    so a second press neither moves the timestamp nor logs again.
    """
    from . import progress as progress_module

    if case.assessment_opened_at:
        return case
    gate = progress_module.compute(conn, root, case).gate
    if gate is None or not gate.can_open:
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
