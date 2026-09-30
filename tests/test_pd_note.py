"""The PD question note (FRD F-24, TC-29)."""

from pathlib import Path

from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, make_case, sign_in
from tests.test_policy import FINANCIALS
from tests.triangulation import add_doc, months


def _note(client: TestClient, headers: dict, root: Path, case_id: str) -> list[dict]:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()
    response = client.get(f"/api/cases/{case_id}/pd-note", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["questions"]


def _case(client: TestClient, analyst: dict, root: Path) -> str:
    case_id = make_case(client, analyst, root, facilities=["cash_credit"], amount_inr=40_000_000)
    add_doc(root, case_id, "audited_financial_statements", FINANCIALS)  # debt/equity 3.0x: a deviation
    add_doc(root, case_id, "bank_statement", {
        "bank": "Lotuscrest Bank", "account_number_masked": "XXXX1234",
        "period_from": "2025-04-01", "period_to": "2026-03-31",
        "transactions": [{"date": f"{p}-05", "narration": "NACH DR ASHWOOD FINSERV", "debit": 145_000}
                         for p in months((2025, 4), 6)],
    })
    add_doc(root, case_id, "existing_facilities_declaration", {"declaration_date": "2026-09-10", "nil_declared": True})
    return case_id


def test_tc29_questions_come_from_findings_deviations_and_gaps_ranked(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    questions = _note(client, analyst, published_data_root, case_id)
    ob2 = next(q for q in questions if q["rule"] == "OB-02")
    assert ob2["source"] == "finding" and ob2["severity"] == "serious"
    assert "ASHWOOD FINSERV" in ob2["text"] and ob2["text"].endswith("what is outstanding on them?")
    assert ob2["evidence"]
    de = next(q for q in questions if q["rule"] == "FR-05")
    assert de["source"] == "deviation"
    assert de["text"].startswith("Debt / equity is 3.00x in FY 2025-26 against a norm of at most 2.00x.")
    gaps = [q for q in questions if q["source"] == "gap"]
    assert gaps and all(q["severity"] == "mild" for q in gaps)
    # Serious first, then moderate, then mild (F-24.1).
    order = [{"serious": 0, "moderate": 1, "mild": 2}[q["severity"]] for q in questions]
    assert order == sorted(order)


def test_a_finding_found_not_valid_is_not_asked(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    _note(client, analyst, published_data_root, case_id)
    item = next(i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
                if i["kind"] == "finding" and "OB-02" in i["summary"])
    client.post(f"/api/review/{item['id']}/decision",
                json={"decision": "waive", "reason": "An equipment lease, disclosed separately"}, headers=analyst)
    assert not [q for q in _note(client, analyst, published_data_root, case_id) if q["rule"] == "OB-02"]
