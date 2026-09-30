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
from .configstore import reader
from .contracts import CaseDetail, CaseProgress, Stage, StageKey, StageProgress
from .store import MESSAGE_FILE_NAME

_IN_FLIGHT = {"received", "graded", "split"}
_CLASSIFIED = {"classified", "extracted", "accepted", "in_review"}
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
    # A file that could not be read (exception) was still submitted: it holds
    # the stage with its quality item rather than looking like no upload.
    submitted = conn.execute(
        "SELECT COUNT(*) FROM files WHERE case_id = ? AND status IN ('registered', 'exception')"
        " AND original_name <> ?",
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
        # One unit per open decision: an unclassified document (type), an
        # unreadable or poor page or file (quality), a split or a party flag.
        # A grade C document is accepted yet still waits on its quality item.
        attention=_open_items(conn, case_id, ("type", "quality", "split", "party")),
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
        if "in_progress" in (docs.status, extraction.status):
            complete.status = "in_progress"
        elif readiness.gate_met:
            complete.status = "done"
        else:
            complete.status = "needs_attention"

    # 4. Cross-verification (F-18, F-19): done when every failed check has a
    # person's decision.
    outcomes = [r["outcome"] for r in conn.execute("SELECT outcome FROM findings WHERE case_id = ?", (case_id,))]
    applicable = [o for o in outcomes if o != "not_applicable"]
    open_findings = _open_items(conn, case_id, ("finding",))
    cross = StageProgress(
        key="cross_verification",
        status="not_started",
        done=sum(1 for o in applicable if o == "pass"),
        total=len(applicable),
        attention=open_findings,
    )
    if applicable and docs.status != "not_started":
        if "in_progress" in (docs.status, extraction.status):
            cross.status = "in_progress"
        else:
            cross.status = "needs_attention" if open_findings else "done"

    # 5. Policy checks (F-20): needs attention while a norm cannot be
    # evaluated for want of an input; deviations are listed, not blocking.
    policy_stage = StageProgress(key="policy", status="not_started")
    if cross.status != "not_started":
        try:
            from . import policy as policy_module

            norms = [n for n in policy_module.assess(conn, root, case).norms if n.outcome != "not_applicable"]
        except reader.NoPublishedConfig:
            norms = []
        if norms:
            policy_stage.done = sum(1 for n in norms if n.outcome == "pass")
            policy_stage.total = len(norms)
            policy_stage.attention = sum(1 for n in norms if n.outcome == "cannot_evaluate")
            if "in_progress" in (docs.status, extraction.status):
                policy_stage.status = "in_progress"
            else:
                policy_stage.status = "needs_attention" if policy_stage.attention else "done"

    stages = [
        docs,
        extraction,
        complete,
        cross,
        policy_stage,
        StageProgress(key="outputs", status="not_started"),
    ]
    stage: Stage = "Intake"
    if submitted:
        stage = next((_STAGE_OF[s.key] for s in stages if s.status != "done"), "Completed")
    return CaseProgress(case_id=case_id, stage=stage, stages=stages)
