"""F-01.5: deleting a case removes everything it owns, keeps a log record,
and never reuses the case ID."""

import json

from fastapi.testclient import TestClient

from engine import db
from engine.store import case_files_dir
from tests.conftest import ANALYST, MANAGER, RM, new_case, sign_in


def _create(client, headers, **overrides):
    body = new_case(message_text="Example Tools Pvt Ltd wants CC 50L.", **overrides)
    r = client.post("/api/cases", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _delete(client, case_id, headers, reason="testing restart"):
    return client.request("DELETE", f"/api/cases/{case_id}", json={"reason": reason}, headers=headers)


def test_delete_removes_rows_and_files_and_logs(client: TestClient, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id = _create(client, analyst)
    files_dir = case_files_dir(case_id, published_data_root)
    assert files_dir.exists()  # the pasted message is stored as the first document

    assert _delete(client, case_id, analyst).status_code == 204
    assert client.get(f"/api/cases/{case_id}", headers=analyst).status_code == 404
    assert case_id not in [c["id"] for c in client.get("/api/cases", headers=analyst).json()]
    assert not files_dir.parent.exists()

    conn = db.connect(published_data_root)
    try:
        for table in ("files", "documents", "field_values", "declared_figures", "review_items", "query_items"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE case_id = ?", (case_id,)).fetchone()[0] == 0
        entry = conn.execute(
            "SELECT * FROM decision_log WHERE case_id = ? AND action = 'case.deleted'", (case_id,)
        ).fetchone()
        assert entry is not None and json.loads(entry["detail"])["reason"] == "testing restart"
    finally:
        conn.close()


def test_the_same_borrower_can_be_created_again_with_a_new_id(client: TestClient):
    analyst = sign_in(client, ANALYST)
    first = _create(client, analyst)
    assert _delete(client, first, analyst).status_code == 204
    # No duplicate warning any more, and the ID is not reused.
    second = _create(client, analyst)
    assert second != first


def test_rm_deletes_only_own_cases(client: TestClient):
    rm = sign_in(client, RM)
    analyst = sign_in(client, ANALYST)
    theirs = _create(client, analyst)
    assert _delete(client, theirs, rm).status_code == 404
    mine = _create(client, rm, borrower="Second Example Traders", pan=None)
    assert _delete(client, mine, rm).status_code == 204


def test_delete_needs_a_session_a_permission_and_a_reason(client: TestClient):
    analyst = sign_in(client, ANALYST)
    case_id = _create(client, analyst)
    assert client.request("DELETE", f"/api/cases/{case_id}", json={"reason": "x y"}).status_code == 401
    assert _delete(client, case_id, analyst, reason="").status_code == 422
    assert _delete(client, "BBG-2026-999999", sign_in(client, MANAGER)).status_code == 404


def test_delete_is_refused_while_the_case_is_processing(client: TestClient, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id = _create(client, analyst)
    conn = db.connect(published_data_root)
    try:
        conn.execute(
            "INSERT INTO jobs (id, case_id, kind, payload, status, created_at) "
            "VALUES ('J-busy', ?, 'process', '{}', 'running', '2026-09-29T00:00:00')",
            (case_id,),
        )
    finally:
        conn.close()
    assert _delete(client, case_id, analyst).status_code == 409
