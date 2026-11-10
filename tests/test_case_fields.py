"""Case fields (T2.1): product, case type, application and customer IDs,
branch and bank stage are stored, checked against configuration, defaulted
with their source, and matched in the duplicate check."""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from engine import db
from tests.conftest import ANALYST, RM, new_case, sign_in


def test_defaults_are_filled_and_their_source_kept(client: TestClient):
    created = client.post("/api/cases", json=new_case(), headers=sign_in(client, RM))
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["product"] == "bbg"
    assert case["bank_stage"] == "login"
    assert case["case_type"] == "unknown"
    # The RM (config/roles.yaml) sits at Mumbai hub.
    assert case["branch"] == "mumbai_hub"
    assert case["application_id"] is None and case["customer_id"] is None
    assert case["header"]["product"]["source"] == "default:config"
    assert case["header"]["bank_stage"]["source"] == "default:config"
    assert case["header"]["branch"]["source"] == "default:rm"
    assert "case_type" not in case["header"]


def test_confirmed_values_are_stored_as_given(client: TestClient):
    rm = sign_in(client, RM)
    body = new_case(
        product="bbg", case_type="renewal", application_id="  APP-0001 ", customer_id="C-77",
        branch="head_office", bank_stage="pd",
        header={"branch": {"value": "head_office", "proposed": None, "source": "person"}},
    )
    case = client.post("/api/cases", json=body, headers=rm).json()
    assert (case["case_type"], case["branch"], case["bank_stage"]) == ("renewal", "head_office", "pd")
    assert case["application_id"] == "APP-0001" and case["customer_id"] == "C-77"
    assert case["header"]["branch"]["source"] == "person"
    assert "bank_stage" not in case["header"]   # given, not defaulted: no default recorded
    listed = next(c for c in client.get("/api/cases", headers=rm).json() if c["id"] == case["id"])
    assert (listed["product"], listed["case_type"], listed["bank_stage"]) == ("bbg", "renewal", "pd")


def test_unknown_choices_are_refused(client: TestClient):
    rm = sign_in(client, RM)
    for field, value in (("product", "lap"), ("case_type", "refinance"), ("branch", "pune"), ("bank_stage", "disbursal")):
        assert client.post("/api/cases", json=new_case(**{field: value}), headers=rm).status_code == 422, field


def test_application_id_is_a_duplicate_key(client: TestClient):
    rm = sign_in(client, RM)
    first = client.post("/api/cases", json=new_case(application_id="APP-9"), headers=rm)
    assert first.status_code == 201
    again = client.post("/api/cases", json=new_case(borrower="Unrelated Name Works", application_id="app-9"),
                        headers=rm)
    assert again.status_code == 409
    assert first.json()["id"] in again.text


def test_creation_log_records_the_fields(client: TestClient, published_data_root):
    case = client.post("/api/cases", json=new_case(case_type="takeover"), headers=sign_in(client, RM)).json()
    conn = db.connect(published_data_root)
    try:
        import json
        detail = json.loads(conn.execute(
            "SELECT detail FROM decision_log WHERE case_id = ? AND action = 'case.created'", (case["id"],)
        ).fetchone()["detail"])
    finally:
        conn.close()
    assert detail["case_type"] == "takeover" and detail["product"] == "bbg" and detail["bank_stage"] == "login"


def test_cases_from_before_the_migration_read_as_business_banking(tmp_path):
    path = tmp_path / "creditiq.sqlite3"
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    for n, script in enumerate(db.MIGRATIONS[:19], start=1):
        conn.executescript(f"BEGIN IMMEDIATE; {script}; PRAGMA user_version = {n}; COMMIT;")
    conn.execute(
        """INSERT INTO cases (id, borrower, constitution, facilities, amount_inr, channel, stage, as_of,
               created_by, created_at) VALUES ('BBG-2026-000001', 'Old Borrower', 'unknown', '["cash_credit"]',
               100, 'email', 'Intake', '2026-10-01', 'u-rm-1', '2026-10-01T00:00:00')"""
    )
    db.migrate(conn)
    row = conn.execute("SELECT product, case_type, branch, bank_stage FROM cases").fetchone()
    conn.close()
    assert tuple(row) == ("bbg", None, None, None)


def test_analyst_reads_the_fields(client: TestClient):
    case = client.post("/api/cases", json=new_case(customer_id="C-1"), headers=sign_in(client, RM)).json()
    read = client.get(f"/api/cases/{case['id']}", headers=sign_in(client, ANALYST)).json()
    assert read["customer_id"] == "C-1" and read["product"] == "bbg"


# --- Checklist preview at intake ---

def _preview(client: TestClient, headers: dict, **body) -> dict:
    r = client.post("/api/cases/checklist-preview", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_preview_matches_the_checklist_of_a_created_case(client: TestClient):
    rm = sign_in(client, RM)
    body = {"constitution": "private_limited", "facilities": ["cash_credit", "term_loan"], "amount_inr": 65000000,
            "collateral_present": True, "product": "bbg", "case_type": "renewal"}
    preview = _preview(client, rm, **body)
    assert preview["provisional"] is False and preview["items"]
    case = client.post("/api/cases", json=new_case(**body), headers=rm).json()
    real = client.get(f"/api/cases/{case['id']}/checklist", headers=sign_in(client, ANALYST)).json()
    assert {i["id"] for i in preview["items"]} == {i["item_id"] for i in real["items"]}
    # Each item names the document types that can satisfy it.
    assert all(i["document_types"] for i in preview["items"] if i["id"] != "sourcing_message")


def test_preview_is_provisional_until_the_constitution_is_known(client: TestClient):
    rm = sign_in(client, RM)
    unknown = _preview(client, rm, facilities=["cash_credit"], amount_inr=1)
    known = _preview(client, rm, constitution="private_limited", facilities=["cash_credit"], amount_inr=1)
    assert unknown["provisional"] is True
    assert {i["id"] for i in unknown["items"]} < {i["id"] for i in known["items"]}


def test_preview_refuses_unknown_choices_and_needs_create_permission(client: TestClient):
    rm = sign_in(client, RM)
    assert client.post("/api/cases/checklist-preview", json={"facilities": ["mortgage"]}, headers=rm).status_code == 422
    assert client.post("/api/cases/checklist-preview", json={"product": "lap"}, headers=rm).status_code == 422
    assert client.post("/api/cases/checklist-preview", json={}).status_code == 401
