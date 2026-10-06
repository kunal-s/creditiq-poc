"""The PD question note (FRD F-24, TC-29)."""

from pathlib import Path

from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, months


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
    # Long-term borrowings of 10 cr: debt / equity 2.67x, a deviation.
    audited(root, case_id, set_rows={"(a) Long-term borrowings": 100_000_000}, page=4)
    bank(root, case_id, [{"date": f"{p}-05", "description": "NACH DR ASHWOOD FINSERV", "debit": 145_000} for p in months((2025, 4), 6)])
    add_doc(root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(root, case_id, "income_tax_return", {"pan": "AAACK9876Q"})  # a second PAN: a serious finding
    return case_id


def test_tc29_questions_come_from_findings_deviations_and_gaps_ranked(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    questions = _note(client, analyst, published_data_root, case_id)
    pan = next(q for q in questions if q["rule"] == "ID-01")
    assert pan["source"] == "finding" and pan["severity"] == "serious"
    assert "AAACK9876Q" in pan["text"] and pan["text"].endswith("why does the other document show a different one?")
    assert pan["evidence"]
    de = next(q for q in questions if q["rule"] == "FR-05")
    assert de["source"] == "deviation"
    assert de["text"].startswith("Debt / equity is 2.67x in FY 2025-26 against a norm of at most 2.00x.")
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
                if i["kind"] == "finding" and "ID-01" in i["summary"])
    client.post(f"/api/review/{item['id']}/decision",
                json={"decision": "waive", "reason": "The second PAN is a typing error in the return"}, headers=analyst)
    assert not [q for q in _note(client, analyst, published_data_root, case_id) if q["rule"] == "ID-01"]
