"""Case stage and stage progress (FRD 3.1 §5 to §7)."""

from pathlib import Path

from fastapi.testclient import TestClient

from engine import db
from tests.conftest import ANALYST, RM, fixture_file, make_case, run_jobs, sign_in, upload

KEYS = ["documents", "extraction", "completeness", "cross_verification", "policy", "outputs"]


def _progress(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/progress", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _status(progress: dict) -> dict[str, str]:
    return {s["key"]: s["status"] for s in progress["stages"]}


def test_new_case_is_intake_with_six_stages_not_started(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    progress = _progress(client, rm, case_id)
    assert progress["stage"] == "Intake"
    assert [s["key"] for s in progress["stages"]] == KEYS
    assert set(_status(progress).values()) == {"not_started"}


def test_stage_follows_processing_and_is_stored_on_the_case(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert upload(client, rm, case_id, [("itr_clear.pdf", fixture_file("itr_clear.pdf"))]).status_code == 202

    progress = _progress(client, rm, case_id)
    assert progress["stage"] == "Documents"
    assert _status(progress)["documents"] == "in_progress"

    assert run_jobs(published_data_root) == 1
    progress = _progress(client, rm, case_id)
    status = _status(progress)
    assert status["documents"] in ("done", "needs_attention")
    assert status["extraction"] != "not_started"
    # Nothing is running, so no stage says it is.
    assert "in_progress" not in status.values()
    # Cross-verification onwards has no feature yet.
    assert [status[k] for k in KEYS[3:]] == ["not_started"] * 3
    assert client.get(f"/api/cases/{case_id}", headers=rm).json()["stage"] == progress["stage"]
    listed = next(c for c in client.get("/api/cases", headers=rm).json() if c["id"] == case_id)
    assert listed["stage"] == progress["stage"]


def test_a_late_document_moves_the_stage_back(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    upload(client, rm, case_id, [("itr_clear.pdf", fixture_file("itr_clear.pdf"))])
    run_jobs(published_data_root)
    conn = db.connect(published_data_root)
    try:
        # Pretend the case had moved on, then a document arrives late.
        conn.execute("UPDATE cases SET stage = 'Completeness' WHERE id = ?", (case_id,))
    finally:
        conn.close()
    upload(client, rm, case_id, [("scan_0412.pdf", fixture_file("scan_0412.pdf"))])
    run_jobs(published_data_root)
    progress = _progress(client, rm, case_id)
    assert progress["stage"] in ("Documents", "Extraction")
    assert client.get(f"/api/cases/{case_id}", headers=rm).json()["stage"] == progress["stage"]


def test_counts_describe_the_checklist(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    completeness = next(s for s in _progress(client, rm, case_id)["stages"] if s["key"] == "completeness")
    checklist = client.get(f"/api/cases/{case_id}/checklist", headers=rm).json()
    assert completeness["total"] == len(checklist["items"])
    assert completeness["attention"] == sum(1 for i in checklist["items"] if i["status"] in ("missing", "insufficient"))


def test_progress_is_gated_like_the_case(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    rm = sign_in(client, RM)
    # An RM sees only their own cases; the case's existence is not disclosed.
    assert client.get(f"/api/cases/{case_id}/progress", headers=rm).status_code == 404
    assert client.get(f"/api/cases/{case_id}/progress").status_code == 401


def test_migration_maps_the_earlier_stages(tmp_path: Path):
    conn = db.connect(tmp_path)
    try:
        insert = (
            "INSERT INTO cases (id, borrower, constitution, facilities, amount_inr, channel, stage, as_of,"
            " created_by, created_at) VALUES (?, 'B', 'unknown', '[]', 1, 'email', ?, '2026-09-29', 'u', 'now')"
        )
        conn.execute(insert, ("C1", "Readiness"))
        conn.execute(insert, ("C2", "Appraisal"))
        conn.executescript(db.MIGRATIONS[2])
        stages = dict(conn.execute("SELECT id, stage FROM cases").fetchall())
    finally:
        conn.close()
    assert stages == {"C1": "Documents", "C2": "CrossVerification"}


def test_an_open_quality_item_holds_the_documents_stage(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    upload(client, rm, case_id, [("itr_clear.pdf", fixture_file("itr_clear.pdf"))])
    run_jobs(published_data_root)
    conn = db.connect(published_data_root)
    try:
        # A grade C page: the document is accepted, its quality item is open.
        conn.execute(
            "INSERT INTO review_items (id, case_id, kind, ref, summary, created_at, status)"
            " VALUES ('RI-q', ?, 'quality', 'document:x', 'grade C', '2026-09-29', 'open')",
            (case_id,),
        )
    finally:
        conn.close()
    progress = _progress(client, rm, case_id)
    documents = progress["stages"][0]
    assert documents["status"] == "needs_attention" and documents["attention"] >= 1
    assert progress["stage"] == "Documents"


def test_an_unreadable_upload_is_not_mistaken_for_no_upload(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    upload(client, rm, case_id, [("broken.pdf", b"%PDF-1.7 this is not a readable PDF")])
    run_jobs(published_data_root)
    files = client.get(f"/api/cases/{case_id}/files", headers=rm).json()
    assert [f["status"] for f in files if f["original_name"] == "broken.pdf"] == ["exception"]
    progress = _progress(client, rm, case_id)
    assert progress["stage"] == "Documents"
    assert progress["stages"][0]["status"] != "not_started"


def test_the_outputs_stage_needs_financial_statements(client: TestClient, published_data_root: Path):
    from tests.test_policy import FINANCIALS
    from tests.triangulation import add_doc

    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "bureau_commercial", {"pan": "AAACK1234F", "score": "Rank 3"})
    conn = db.connect(published_data_root)
    try:
        from engine import pipeline

        pipeline.refresh_case(conn, published_data_root, case_id)
    finally:
        conn.close()
    outputs = _progress(client, analyst, case_id)["stages"][5]
    assert outputs["status"] == "needs_attention" and outputs["done"] == 2
    add_doc(published_data_root, case_id, "audited_financial_statements", FINANCIALS)
    outputs = _progress(client, analyst, case_id)["stages"][5]
    assert outputs["status"] == "done" and outputs["done"] == 3
