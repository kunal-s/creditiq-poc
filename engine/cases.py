"""Case store: create, list and read cases (docs/functional-requirements.md F-01).

A case exists only after a person confirms it (F-04.7); this module creates
exactly what it is given. The proposal flow (F-04) and the duplicate-case
check (F-04.5) sit in front of `create_case`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .config import find_user_by_id, load_app_config, option_ids
from .contracts import CaseCreate, CaseDetail, CaseSummary, HeaderField
from .db import log_decision, transaction


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


def create_case(
    conn: sqlite3.Connection, data: CaseCreate, *, created_by: str, config_version: str | None
) -> CaseDetail:
    _validate(data)
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
                }
            ),
        )
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
