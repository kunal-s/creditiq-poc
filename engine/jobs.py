"""The processing job queue (F-02.3): SQLite, shared by the API worker and
the command line (`creditiq jobs run --once`).

A job is claimed with a lease. A worker that dies leaves its job "running"
with a lease that expires; the next claim takes it over and the pipeline
resumes where it stopped, because each file's result is committed on its
own and a processed file is never sent again.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import db
from .db import transaction
from .util import dumps, now_iso

log = logging.getLogger("creditiq.jobs")

LEASE_SECONDS = 900
MAX_ATTEMPTS = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(conn: sqlite3.Connection, *, case_id: str, kind: str, payload: dict) -> str:
    """Queue a job. Call inside the caller's transaction."""
    job_id = "JOB-" + uuid.uuid4().hex[:12].upper()
    conn.execute(
        "INSERT INTO jobs (id, case_id, kind, payload, status, created_at) VALUES (?, ?, ?, ?, 'queued', ?)",
        (job_id, case_id, kind, dumps(payload), now_iso()),
    )
    wake()
    return job_id


def claim(conn: sqlite3.Connection, *, now: datetime | None = None) -> sqlite3.Row | None:
    """Take the oldest queued job, or a running job whose lease expired."""
    now = now or _now()
    with transaction(conn):
        row = conn.execute(
            """SELECT * FROM jobs
               WHERE (status = 'queued') OR (status = 'running' AND (lease_until IS NULL OR lease_until < ?))
               ORDER BY created_at LIMIT 1""",
            (now.isoformat(),),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """UPDATE jobs SET status = 'running', attempts = attempts + 1, started_at = ?, lease_until = ?
               WHERE id = ?""",
            (now.isoformat(), (now + timedelta(seconds=LEASE_SECONDS)).isoformat(), row["id"]),
        )
        return conn.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()


def _finish(conn: sqlite3.Connection, job_id: str, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE jobs SET status = ?, error = ?, finished_at = ?, lease_until = NULL WHERE id = ?",
        (status, error, now_iso(), job_id),
    )


def run_job(conn: sqlite3.Connection, root: Path, job: sqlite3.Row, client=None) -> None:
    from . import pipeline
    from .ingest_client import get_client

    client = client or get_client()
    payload = json.loads(job["payload"])
    try:
        if job["kind"] == "process":
            pipeline.process_files(conn, root, job["id"], job["case_id"], payload["file_ids"], client)
        elif job["kind"] == "reextract":
            pipeline.reextract_document(conn, root, job["id"], job["case_id"], payload["document_id"], client)
        else:
            raise ValueError(f"unknown job kind {job['kind']!r}")
    except Exception as e:  # recorded on the job; retried until MAX_ATTEMPTS
        log.exception("job %s failed", job["id"])
        status = "failed" if job["attempts"] >= MAX_ATTEMPTS else "queued"
        _finish(conn, job["id"], status, f"{type(e).__name__}: {e}")
        return
    _finish(conn, job["id"], "done")


def run_pending(root: Path, *, client=None, limit: int | None = None) -> int:
    """Run jobs until none is claimable (or `limit` have run). Returns how many ran."""
    conn = db.connect(root)
    ran = 0
    try:
        while limit is None or ran < limit:
            job = claim(conn)
            if job is None:
                break
            run_job(conn, root, job, client)
            ran += 1
    finally:
        conn.close()
    return ran


def pending_for_case(conn: sqlite3.Connection, case_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE case_id = ? AND status IN ('queued', 'running')", (case_id,)
    ).fetchone()[0]


# --- The API's background worker ---

_wake = threading.Event()


def wake() -> None:
    _wake.set()


class Worker:
    """Runs queued jobs in a background thread while the API is up."""

    def __init__(self, root_fn, poll_seconds: float = 2.0) -> None:
        self.root_fn = root_fn
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="creditiq-jobs", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        _wake.set()
        if self._thread:
            self._thread.join(timeout=30)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                run_pending(Path(self.root_fn()))
            except Exception:  # keep the worker alive; the job row holds the error
                log.exception("job worker iteration failed")
            _wake.wait(self.poll_seconds)
            _wake.clear()
