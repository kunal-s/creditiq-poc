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
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import find_user_by_id, load_app_config, option_ids
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
) -> list[CaseSummary]:
    """F-04.5: existing cases matching on PAN, GSTIN or normalised name."""
    pan = (pan or "").strip().upper() or None
    gstin = (gstin or "").strip().upper() or None
    target = normalise_name(borrower)
    out = []
    for row in conn.execute("SELECT * FROM cases ORDER BY created_at"):
        same = (pan and (row["pan"] or "").upper() == pan) or (gstin and (row["gstin"] or "").upper() == gstin)
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
    duplicates = find_duplicates(
        conn, pan=data.pan, gstin=data.gstin, borrower=data.borrower, name_threshold=name_threshold
    )
    if duplicates and not (data.duplicate_override_reason or "").strip():
        raise DuplicateCase(duplicates)
    root = Path(root or data_root())
    now = _now()
    with transaction(conn):
        case_id = _next_case_id(conn, now.year)
        conn.execute(
            """INSERT INTO cases (id, borrower, constitution, facilities, amount_inr, pan, gstin, cin, udyam,
                   collateral_present, channel, stage, as_of, created_by, created_at, config_version, header)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Intake', ?, ?, ?, ?, ?)""",
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


def _open_reviews(conn: sqlite3.Connection, case_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM review_items WHERE case_id = ? AND status = 'open'", (case_id,)
    ).fetchone()[0]


def _summary_fields(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "borrower": row["borrower"],
        "constitution": row["constitution"],
        "facilities": json.loads(row["facilities"]),
        "amount_inr": row["amount_inr"],
        "stage": row["stage"],
        "rm": (find_user_by_id(row["created_by"]) or {}).get("name", row["created_by"]),
        "created_at": row["created_at"],
        "open_review_items": _open_reviews(conn, row["id"]),
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
        as_of=row["as_of"],
        created_by=row["created_by"],
        config_version=row["config_version"],
        header={k: HeaderField(**v) for k, v in json.loads(row["header"]).items()},
    )
