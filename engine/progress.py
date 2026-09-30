"""The case's stage progress (FRD §5 to §7).

Each of the six processing stages gets its own status and counts; the
case's stage is the first stage not yet done (§7). Everything is derived
from the document register, the review items and the checklist, so a late
document moves the stage back without special handling.

Cross-verification, policy and outputs report `not_started` until F-18 to
F-24 exist.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import completeness
from .contracts import CaseDetail, CaseProgress, Stage, StageKey, StageProgress
from .store import MESSAGE_FILE_NAME

_IN_FLIGHT = {"received", "graded", "split"}
_CLASSIFIED = {"classified", "extracted", "accepted", "in_review"}
_BLOCKED = {"unclassified", "in_exception"}
_OUT_OF_SCOPE = {"superseded", "duplicate"}

_STAGE_OF: dict[StageKey, Stage] = {
    "documents": "Documents",
    "extraction": "Extraction",
    "completeness": "Completeness",
    "cross_verification": "CrossVerification",
    "policy": "Policy",
    "outputs": "Outputs",
}


def _open_items(conn: sqlite3.Connection, case_id: str, kinds: tuple[str, ...]) -> int:
    marks = ",".join("?" * len(kinds))
    return conn.execute(
        f"SELECT COUNT(*) FROM review_items WHERE case_id = ? AND status = 'open' AND kind IN ({marks})",
        (case_id, *kinds),
    ).fetchone()[0]


def compute(conn: sqlite3.Connection, root: Path, case: CaseDetail, *, running_job: str | None = None) -> CaseProgress:
    case_id = case.id
    submitted = conn.execute(
        "SELECT COUNT(*) FROM files WHERE case_id = ? AND status = 'registered' AND original_name <> ?",
        (case_id, MESSAGE_FILE_NAME),
    ).fetchone()[0]
    pending_files = conn.execute(
        "SELECT COUNT(*) FROM files WHERE case_id = ? AND status = 'registered' AND processed_at IS NULL"
        " AND original_name <> ?",
        (case_id, MESSAGE_FILE_NAME),
    ).fetchone()[0]
    pending_jobs = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE case_id = ? AND status IN ('queued', 'running') AND id <> ?",
        (case_id, running_job or ""),
    ).fetchone()[0]
    statuses = [
        r["status"]
        for r in conn.execute("SELECT status FROM documents WHERE case_id = ?", (case_id,))
        if r["status"] not in _OUT_OF_SCOPE
    ]

    # 1. Quality and classification (F-07 to F-11).
    busy = bool(pending_files or pending_jobs or any(s in _IN_FLIGHT for s in statuses))
    docs = StageProgress(
        key="documents",
        status="not_started",
        done=sum(1 for s in statuses if s in _CLASSIFIED),
        total=len(statuses),
        attention=sum(1 for s in statuses if s in _BLOCKED) + _open_items(conn, case_id, ("split", "party")),
    )
    if submitted:
        docs.status = "in_progress" if busy else "needs_attention" if docs.attention else "done"

    # 2. Extraction (F-15 to F-17).
    classified = [s for s in statuses if s in _CLASSIFIED]
    extraction = StageProgress(
        key="extraction",
        status="not_started",
        done=sum(1 for s in classified if s == "accepted"),
        total=len(classified),
        attention=_open_items(conn, case_id, ("field", "manual_entry")),
    )
    if classified:
        if any(s in ("classified", "extracted") for s in classified):
            extraction.status = "in_progress"
        elif extraction.attention or any(s == "in_review" for s in classified):
            extraction.status = "needs_attention"
        else:
            extraction.status = "done"

    # 3. Validation and completeness (F-12 to F-14). Missing items show as
    # soon as classification has run (§5); the stage is done at the gate.
    readiness, _ = completeness.evaluate(conn, root, case)
    items = readiness.items
    complete = StageProgress(
        key="completeness",
        status="not_started",
        done=sum(1 for i in items if i.status in ("satisfied", "waived")),
        total=len(items),
        attention=sum(1 for i in items if i.status in ("missing", "insufficient")),
    )
    if docs.status != "not_started":
        if extraction.status == "done" and docs.status == "done":
            complete.status = "done" if readiness.gate_met else "needs_attention"
        else:
            complete.status = "in_progress"

    stages = [
        docs,
        extraction,
        complete,
        StageProgress(key="cross_verification", status="not_started"),
        StageProgress(key="policy", status="not_started"),
        StageProgress(key="outputs", status="not_started"),
    ]
    stage: Stage = "Intake"
    if submitted:
        stage = next((_STAGE_OF[s.key] for s in stages if s.status != "done"), "Completed")
    return CaseProgress(case_id=case_id, stage=stage, stages=stages)
