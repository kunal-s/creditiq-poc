"""Wave 0 API behaviour (docs/functional-requirements.md F-01, F-03, F-12)."""

import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from engine import db
from tests.conftest import ANALYST, RM, new_case, sign_in

DATA_ENDPOINTS = [
    "/api/cases",
    "/api/meta",
    "/api/review",
    "/api/config/version",
    "/api/config/document-types",
]


@pytest.mark.parametrize("path", DATA_ENDPOINTS)
def test_data_endpoints_need_a_session(client: TestClient, path: str):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_wrong_password_is_refused(client: TestClient):
    assert client.post("/api/auth/login", json={"email": RM, "password": "wrong"}).status_code == 401


def test_session_survives_a_new_connection_and_logout_ends_it(client: TestClient):
    headers = sign_in(client, RM)
    assert client.get("/api/auth/session", headers=headers).json()["role"] == "rm"
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/session", headers=headers).status_code == 401


def test_role_without_permission_gets_403(client: TestClient):
    rm = sign_in(client, RM)
    # An RM has no review.read permission (config/roles.yaml).
    assert client.get("/api/review", headers=rm).status_code == 403


def test_create_case_issues_sequential_ids_in_the_configured_format(client: TestClient):
    rm = sign_in(client, RM)
    first = client.post("/api/cases", json=new_case(), headers=rm)
    second = client.post("/api/cases", json=new_case(borrower="Second Borrower"), headers=rm)
    assert first.status_code == 201, first.text
    a, b = first.json()["id"], second.json()["id"]
    assert re.fullmatch(r"BBG-\d{4}-\d{6}", a)
    assert int(b[-6:]) == int(a[-6:]) + 1
    assert first.json()["stage"] == "Intake"
    assert first.json()["rm"] == "Arjun Deshpande"


def test_create_case_rejects_unknown_choices(client: TestClient):
    rm = sign_in(client, RM)
    assert client.post("/api/cases", json=new_case(channel="fax"), headers=rm).status_code == 422
    assert client.post("/api/cases", json=new_case(facilities=["mortgage"]), headers=rm).status_code == 422
    assert client.post("/api/cases", json=new_case(amount_inr=0), headers=rm).status_code == 422


def test_rm_sees_only_own_cases_and_analyst_sees_all(client: TestClient):
    rm = sign_in(client, RM)
    analyst = sign_in(client, ANALYST)
    mine = client.post("/api/cases", json=new_case(), headers=rm).json()["id"]
    theirs = client.post("/api/cases", json=new_case(borrower="Analyst Case"), headers=analyst).json()["id"]

    assert [c["id"] for c in client.get("/api/cases", headers=rm).json()] == [mine]
    assert {c["id"] for c in client.get("/api/cases", headers=analyst).json()} == {mine, theirs}
    # Not disclosed to the RM, not even its existence.
    assert client.get(f"/api/cases/{theirs}", headers=rm).status_code == 404


def test_checklist_is_derived_from_the_case(client: TestClient):
    rm = sign_in(client, RM)
    case_id = client.post("/api/cases", json=new_case(), headers=rm).json()["id"]
    readiness = client.get(f"/api/cases/{case_id}/checklist", headers=rm).json()
    items = {i["item_id"] for i in readiness["items"]}
    # Private limited: the company documents, and what every case needs.
    assert {"coi", "moa_aoa", "board_resolution", "pan_entity", "kyc_promoters", "gst_returns"} <= items
    assert "partnership_deed" not in items
    assert readiness["provisional"] is False
    assert readiness["gate_met"] is False  # nothing received yet
    assert all(i["status"] == "missing" for i in readiness["items"])


def test_unknown_constitution_gives_a_provisional_checklist(client: TestClient):
    rm = sign_in(client, RM)
    case_id = client.post("/api/cases", json=new_case(constitution="unknown"), headers=rm).json()["id"]
    readiness = client.get(f"/api/cases/{case_id}/checklist", headers=rm).json()
    items = {i["item_id"] for i in readiness["items"]}
    assert readiness["provisional"] is True
    assert "coi" not in items and "partnership_deed" not in items
    assert "pan_entity" in items


def test_case_creation_is_logged_and_the_log_is_append_only(client: TestClient, published_data_root):
    rm = sign_in(client, RM)
    client.post("/api/cases", json=new_case(), headers=rm)
    conn = db.connect(published_data_root)
    try:
        actions = [r["action"] for r in conn.execute("SELECT action FROM decision_log ORDER BY seq")]
        assert "case.created" in actions
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM decision_log")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("UPDATE decision_log SET actor = 'x'")
    finally:
        conn.close()


def test_maker_cannot_check_their_own_entry(published_data_root):
    conn = db.connect(published_data_root)
    try:
        conn.execute(
            "INSERT INTO cases (id, borrower, constitution, facilities, amount_inr, channel, stage, as_of,"
            " created_by, created_at) VALUES ('C1', 'B', 'unknown', '[]', 1, 'email', 'Intake', '2026-09-29',"
            " 'u', '2026-09-29')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO review_items (id, case_id, kind, ref, summary, created_at, status, maker, decided_by)"
                " VALUES ('R1', 'C1', 'manual_entry', 'f', 's', 'now', 'decided', 'same', 'same')"
            )
    finally:
        conn.close()


def test_a_file_whose_processing_stopped_says_so_and_is_read_again(client, published_data_root, monkeypatch):
    """A step that stopped is not a judgement on the file: it is not called
    corrupt, the reason says which step, and the file can be read again from its
    row (uploading it again would be taken as a duplicate)."""
    from engine.ingest_client import StubIngestClient
    from tests.conftest import ANALYST, RM, fixture_file, make_case, run_jobs, sign_in, upload

    plain = StubIngestClient.process
    stopped = {"once": True}

    def process(self, request, payloads):
        result = plain(self, request, payloads)
        if not stopped["once"]:
            return result
        stopped["once"] = False
        files = [f.model_copy(update={"status": "failed", "documents": [], "decision": None,
                                      "error": {"stage": "classify+1", "type": "KeyError",
                                                "message": "'PDF_COVERED_TEXT'"}})
                 for f in result.files]
        return result.model_copy(update={"files": files})

    monkeypatch.setattr(StubIngestClient, "process", process)
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    name = "heronbay certificate of incorporation.pdf"
    upload(client, rm, case_id, [(name, fixture_file(name))])
    run_jobs(published_data_root)
    [file] = [f for f in client.get(f"/api/cases/{case_id}/files", headers=rm).json() if f["original_name"] == name]
    from engine import db

    conn = db.connect(published_data_root)
    try:
        code = conn.execute("SELECT reason_code FROM files WHERE id = ?", (file["id"],)).fetchone()[0]
    finally:
        conn.close()
    assert file["status"] == "exception" and code == "processing_failed"
    assert file["reason"].startswith("Processing stopped after the classify step (KeyError)")
    assert "PDF_COVERED_TEXT" not in file["reason"]

    analyst = sign_in(client, ANALYST)
    again = client.post(f"/api/cases/{case_id}/files/{file['id']}/read-again", headers=rm)
    assert again.status_code == 200
    assert again.json()["status"] == "registered" and again.json()["reason"] is None
    quality = [i for i in client.get(f"/api/review?case_id={case_id}&include_decided=true", headers=analyst).json()
               if i["kind"] == "quality" and file["id"] in i["ref"]]
    assert quality and all(i["status"] == "decided" for i in quality)
    assert run_jobs(published_data_root) == 1
    read = next(f for f in client.get(f"/api/cases/{case_id}/files", headers=rm).json() if f["id"] == file["id"])
    assert read["status"] != "exception"
    # Only a file in exception is read again.
    assert client.post(f"/api/cases/{case_id}/files/{file['id']}/read-again", headers=rm).status_code == 409


def test_f07a_a_files_checks_run_again_and_its_documents_stay(client, published_data_root, monkeypatch):
    """A file read before a check existed, or before the configuration naming it
    was published, has its integrity checks run again on request; its documents
    and values are left as they are, and its documents' type is passed along."""
    from engine.contracts.ingest import IngestIntegrityFinding
    from engine.ingest_client import StubIngestClient
    from tests.conftest import RM, fixture_file, make_case, run_jobs, sign_in, upload

    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    name = "heronbay certificate of incorporation.pdf"
    upload(client, rm, case_id, [(name, fixture_file(name))])
    run_jobs(published_data_root)
    [file] = [f for f in client.get(f"/api/cases/{case_id}/files", headers=rm).json() if f["original_name"] == name]
    docs_before = sorted(d["id"] for d in client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
                         if d["file_id"] == file["id"])

    plain = StubIngestClient.process
    seen: dict = {}
    covered = [IngestIntegrityFinding(code="PDF_COVERED_TEXT", family="layout", status="review_required",
                                      finding="1 block laid over printed text hides it.", tier="T1", impact="high")]

    def process(self, request, payloads):
        seen["type"] = request.files[0].assigned_type
        untyped = request.model_copy(update={"files": [f.model_copy(update={"assigned_type": None})
                                                       for f in request.files]})
        result = plain(self, untyped, payloads)
        files = [f.model_copy(update={"integrity": covered, "integrity_recommendation": "needs_review_priority"})
                 for f in result.files]
        return result.model_copy(update={"files": files})

    monkeypatch.setattr(StubIngestClient, "process", process)
    asked = client.post(f"/api/cases/{case_id}/files/{file['id']}/integrity/recheck", headers=rm)
    assert asked.status_code == 202
    assert run_jobs(published_data_root) == 1
    after = next(f for f in client.get(f"/api/cases/{case_id}/files", headers=rm).json() if f["id"] == file["id"])
    assert [f["code"] for f in after["integrity"]] == ["PDF_COVERED_TEXT"]
    assert after["integrity_recommendation"] == "needs_review_priority"
    docs_after = sorted(d["id"] for d in client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
                        if d["file_id"] == file["id"])
    assert docs_after == docs_before
    assert seen["type"] is not None  # the documents' type went with it
    assert client.post(f"/api/cases/{case_id}/files/F-NOPE/integrity/recheck", headers=rm).status_code == 404


def test_f07a_the_figures_read_are_served_apart_from_the_file_list(client, published_data_root):
    """Every figure the page checks read, with its place, font and column, is
    served on its own: a statement prints thousands, and the file list is
    fetched on every screen of the case."""
    import json

    from engine import db
    from tests.conftest import ANALYST, RM, fixture_file, make_case, sign_in, upload

    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    name = "heronbay certificate of incorporation.pdf"
    upload(client, rm, case_id, [(name, fixture_file(name))])
    figures = [{"page": 1, "rect": [0.8, 0.29, 0.9, 0.3], "text": "2,31,900.00", "font": "Arial",
                "size": 9.0, "right": 538.2, "column": 7}]
    conn = db.connect(published_data_root)
    try:
        conn.execute("UPDATE files SET integrity_figures = ? WHERE case_id = ?", (json.dumps(figures), case_id))
        file_id = conn.execute("SELECT id FROM files WHERE case_id = ?", (case_id,)).fetchone()["id"]
    finally:
        conn.close()

    analyst = sign_in(client, ANALYST)
    files = client.get(f"/api/cases/{case_id}/files", headers=analyst).json()
    assert "integrity_figures" not in files[0]
    served = client.get(f"/api/cases/{case_id}/files/{file_id}/figures", headers=analyst)
    assert served.status_code == 200 and served.json() == figures
    assert client.get(f"/api/cases/{case_id}/files/F-NOPE/figures", headers=analyst).status_code == 404
    page = client.get(f"/api/cases/{case_id}/files/{file_id}/pages/1", headers=analyst)
    assert page.status_code == 200 and page.headers["content-type"] == "image/png"


def test_store_migrates_to_version_19(published_data_root):
    from engine import db

    conn = db.connect(published_data_root)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS) == 19
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finding_columns = {r["name"] for r in conn.execute("PRAGMA table_info(findings)")}
        case_columns = {r["name"] for r in conn.execute("PRAGMA table_info(cases)")}
        file_columns = {r["name"] for r in conn.execute("PRAGMA table_info(files)")}
    finally:
        conn.close()
    assert {"reference_records", "reference_items", "comparison_adjudications"} <= tables
    # 19: a person's conclusion on a file's integrity (F-07A).
    assert "integrity_reviews" in tables
    # 16: what a file's own bytes say about its history (F-07A).
    assert {"integrity", "integrity_recommendation", "integrity_facts", "integrity_figures"} <= file_columns  # 16-18
    # 15: customer messages recorded for sending.
    assert "outbox" in tables
    # 14: a person's edit of a statement line, with the document's own figure beside it.
    assert "statement_edits" in tables
    # 12: classified bank-statement transactions.
    assert {"txn_class", "txn_class_basis", "txn_class_overrides", "txn_model_labels"} <= tables   # 13: the model's answers
    # 7: the cross-verification board.
    assert {"finding_refs", "crosscheck_runs", "query_additions"} <= tables and "card" in finding_columns
    # 9: the assessment gate.
    assert {"assessment_opened_at", "assessment_opened_by"} <= case_columns
    # 8: escalations kept with their discrepancies.
    assert "finding_escalations" in tables
    # 10: the draft CAM's review: words, overrides, data requests, recorded copilot answers.
    assert {"cam_reviews", "cam_overrides", "cam_requests", "cam_model_calls"} <= tables
    # 11: CAM templates analysts make, and the template each case follows.
    assert {"cam_templates", "case_cam_templates"} <= tables


def test_f07a_each_file_carries_its_integrity_checks(client, published_data_root):
    """The Files tab shows, beside each file, every integrity check run on it.
    The store kept them all along; the file record has to carry them."""
    import json

    from engine import db
    from tests.conftest import ANALYST, RM, fixture_file, make_case, sign_in, upload

    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    name = "heronbay certificate of incorporation.pdf"
    upload(client, rm, case_id, [(name, fixture_file(name))])
    found = [{"code": "PDF_INCREMENTAL_UPDATE", "family": "history", "status": "pass",
              "finding": "The file holds one revision.", "tier": "T1", "impact": "medium"}]
    conn = db.connect(published_data_root)
    try:
        conn.execute("UPDATE files SET integrity = ?, integrity_recommendation = ?, integrity_facts = ? WHERE case_id = ?",
                     (json.dumps(found), "no_notable_issue",
                      json.dumps({"size_bytes": 3047, "info": {"Producer": "pdfmake"}, "fonts": ["Roboto-Regular"]}),
                      case_id))
    finally:
        conn.close()

    files = client.get(f"/api/cases/{case_id}/files", headers=sign_in(client, ANALYST)).json()
    assert files[0]["integrity_recommendation"] == "no_notable_issue"
    assert [f["code"] for f in files[0]["integrity"]] == ["PDF_INCREMENTAL_UPDATE"]
    facts = files[0]["integrity_facts"]
    assert facts["info"] == {"Producer": "pdfmake"} and facts["fonts"] == ["Roboto-Regular"]
