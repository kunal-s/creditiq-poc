"""F-02: the processing job queue. A killed job resumes and processes
nothing twice; stage timings are recorded and exportable; every run records
the configuration version it used; statuses follow the state diagram."""

import io
import json
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cli, db, jobs, pipeline
from engine.ingest_client import StubIngestClient
from tests.conftest import RM, fixture_file, make_case, run_jobs, sign_in, upload


class RecordingClient(StubIngestClient):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[list[str]] = []

    def process(self, request, payloads):
        self.requests.append([f.original_name for f in request.files])
        return super().process(request, payloads)


def _case_with_upload(client: TestClient, root: Path, names: list[str]) -> tuple[str, dict]:
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, root, borrower="Heronbay Polymers Pvt Ltd")
    result = upload(client, rm, case_id, [(n, fixture_file(n)) for n in names])
    assert result.status_code == 202
    return case_id, result.json()


def test_f02_killed_job_resumes_without_reprocessing(client, published_data_root, monkeypatch):
    names = ["bank statement apr-mar.pdf", "Tarun Velankar PAN.pdf", "Sunil Karve PAN.pdf"]
    case_id, result = _case_with_upload(client, published_data_root, names)
    real_store = pipeline._store_file_result
    calls = {"n": 0}

    def crash_on_second_file(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("worker killed")
        return real_store(*args, **kwargs)

    monkeypatch.setattr(pipeline, "_store_file_result", crash_on_second_file)
    recorder = RecordingClient()
    assert jobs.run_pending(published_data_root, client=recorder, limit=1) == 1
    conn = db.connect(published_data_root)
    try:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (result["job_id"],)).fetchone()
        assert job["status"] == "queued" and "worker killed" in job["error"]
        processed = conn.execute("SELECT COUNT(*) FROM files WHERE processed_at IS NOT NULL AND case_id = ?",
                                 (case_id,)).fetchone()[0]
        assert processed == 1
    finally:
        conn.close()

    monkeypatch.setattr(pipeline, "_store_file_result", real_store)
    assert jobs.run_pending(published_data_root, client=recorder) == 1
    # The resumed run sends only the two files not yet stored.
    assert recorder.requests == [names, names[1:]]
    conn = db.connect(published_data_root)
    try:
        assert conn.execute("SELECT status FROM jobs WHERE id = ?", (result["job_id"],)).fetchone()[0] == "done"
        per_file = conn.execute(
            "SELECT file_id, COUNT(*) AS n FROM documents WHERE case_id = ? GROUP BY file_id", (case_id,)
        ).fetchall()
    finally:
        conn.close()
    assert sorted(r["n"] for r in per_file) == [1, 1, 1]


def test_f02_a_job_whose_worker_died_is_taken_over_after_its_lease(client, published_data_root):
    _case_with_upload(client, published_data_root, ["Sunil Karve PAN.pdf"])
    conn = db.connect(published_data_root)
    try:
        job = jobs.claim(conn)  # a worker takes the job, then dies
        assert job is not None and job["status"] == "running"
        assert jobs.claim(conn) is None  # still leased
        later = datetime.now(timezone.utc) + timedelta(seconds=jobs.LEASE_SECONDS + 1)
        again = jobs.claim(conn, now=later)
        assert again is not None and again["id"] == job["id"] and again["attempts"] == 2
        jobs.run_job(conn, published_data_root, again, StubIngestClient())
        assert conn.execute("SELECT status FROM jobs WHERE id = ?", (job["id"],)).fetchone()[0] == "done"
    finally:
        conn.close()


def test_f02_a_failing_job_stops_after_its_attempts(client, published_data_root, tmp_path):
    _case_with_upload(client, published_data_root, ["Sunil Karve PAN.pdf"])
    empty = StubIngestClient(fixtures=tmp_path)  # no fixture: an explicit error, never a guess
    for _ in range(jobs.MAX_ATTEMPTS):
        jobs.run_pending(published_data_root, client=empty, limit=1)
    conn = db.connect(published_data_root)
    try:
        row = conn.execute("SELECT status, attempts, error FROM jobs").fetchone()
    finally:
        conn.close()
    assert row["status"] == "failed" and row["attempts"] == jobs.MAX_ATTEMPTS
    assert "no stub fixture" in row["error"]


def test_f02_statuses_timings_and_run_record(client, published_data_root):
    names = ["partial_bundle.pdf", "scan_0412.pdf", "gst_sep_photo.pdf", "itr_blurred.pdf"]
    case_id, _ = _case_with_upload(client, published_data_root, names)
    run_jobs(published_data_root)
    rm = sign_in(client, RM)
    docs = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    statuses = {d["status"] for d in docs}
    # FRD section 7: accepted, in review (key value below threshold),
    # unclassified (to review), in exception (grade U).
    assert statuses == {"accepted", "in_review", "unclassified", "in_exception"}
    for d in docs:
        assert d["config_version"]

    fields = client.get(f"/api/cases/{case_id}/fields", headers=sign_in(client, "ananya.krishnan@rblbank.com")).json()
    assert all(f["confidence"] is not None and f["evidence"]["page"] >= 1 for f in fields if f["value"] is not None)
    low = next(f for f in fields if f["field"] == "outward_taxable_supplies" and f["status"] == "in_review")
    assert low["confidence"] < 0.8
    assert low["confidence_components"]["cap.grade_c_page"] == 0.6

    conn = db.connect(published_data_root)
    try:
        stages = {r["stage"] for r in conn.execute("SELECT stage FROM stage_timings WHERE case_id = ?", (case_id,))}
        run = conn.execute(
            "SELECT detail FROM decision_log WHERE case_id = ? AND action = 'processing.run'", (case_id,)
        ).fetchone()
    finally:
        conn.close()
    assert {"ingest", "read", "grade", "classify", "extract", "store"} <= stages
    assert json.loads(run["detail"])["config_version"]

    out = io.StringIO()
    with redirect_stdout(out):
        assert cli.main(["case", "timings", case_id, "--data-root", str(published_data_root)]) == 0
    lines = out.getvalue().strip().splitlines()
    assert lines[0] == "case_id,subject,stage,started_at,ms" and len(lines) > 5


def test_f02_cli_runs_the_queue_once(client, published_data_root, monkeypatch):
    case_id, _ = _case_with_upload(client, published_data_root, ["Sunil Karve PAN.pdf"])
    out = io.StringIO()
    with redirect_stdout(out):
        assert cli.main(["jobs", "run", "--once", "--data-root", str(published_data_root)]) == 0
    assert "ran 1 job(s)" in out.getvalue()
    conn = db.connect(published_data_root)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents WHERE case_id = ?", (case_id,)).fetchone()[0] == 1
    finally:
        conn.close()


def test_f02_the_api_worker_processes_uploads(published_data_root, monkeypatch):
    """With the lifespan worker on, an upload is processed without a CLI run."""
    import time

    monkeypatch.setenv("CREDITIQ_DATA_ROOT", str(published_data_root))
    monkeypatch.setenv("CREDITIQ_INGEST", "stub")
    monkeypatch.setenv("CREDITIQ_WORKER", "1")
    from engine.api import app

    with TestClient(app) as client:
        rm = sign_in(client, RM)
        case_id = make_case(client, rm, published_data_root)
        upload(client, rm, case_id, [("Sunil Karve PAN.pdf", fixture_file("Sunil Karve PAN.pdf"))])
        for _ in range(100):
            if client.get(f"/api/cases/{case_id}/documents", headers=rm).json():
                break
            time.sleep(0.05)
        else:
            pytest.fail("the worker did not process the upload")
