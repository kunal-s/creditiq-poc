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
    # Private limited, CC + TL above the MPBF limit, with collateral.
    assert {"coi", "board_resolution", "fs_projected", "cma_data", "stock_statement", "title_document"} <= items
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
