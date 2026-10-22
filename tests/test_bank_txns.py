"""Classified bank-statement transactions of a case: kept, served behind the assessment gate, corrected by a person,
and raised for review when nothing settles them."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from engine import bank_txns, cases, db
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import bank

ROWS = [
    {"date": "2025-04-05", "description": "NEFT CR ORCHID TRADERS", "credit": 400_000},
    {"date": "2025-04-06", "description": "LOAN DISBURSAL TL 7781", "credit": 2_500_000},
    {"date": "2025-04-10", "description": "NEFT DR SALARY", "debit": 120_000},
    {"date": "2025-05-03", "description": "NACH DR VESTA CAPITAL 778811 EMI", "debit": 96_500},
    {"date": "2025-05-09", "description": "XQ77 MISC ADJ", "debit": 2_500},
    {"date": "2025-05-11", "description": "IMPS TRF TO A/C XXXX5678", "debit": 300_000},
]


def _case(client: TestClient, root: Path, **kw) -> tuple[dict, str]:
    headers = sign_in(client, ANALYST)
    return headers, make_case(client, headers, root, borrower="Kestrel Tools Pvt Ltd", **kw)


def _all(client, headers, case_id, **params) -> list[dict]:
    r = client.get(f"/api/cases/{case_id}/transactions", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _stated(client, headers, case_id) -> dict:
    return {r["narration"]: r for r in _all(client, headers, case_id)}


def test_the_transactions_are_behind_the_assessment_gate(client: TestClient, published_data_root: Path):
    headers, case_id = _case(client, published_data_root, assessment_open=False)
    for path in ("transactions", "transactions/summary"):
        r = client.get(f"/api/cases/{case_id}/{path}", headers=headers)
        assert (r.status_code, r.json()["detail"]) == (409, "assessment_not_open")


def test_every_statement_row_is_classified_with_its_evidence(client: TestClient, published_data_root: Path):
    headers, case_id = _case(client, published_data_root)
    bank(published_data_root, case_id, ROWS)
    bank(published_data_root, case_id, [{"date": "2025-05-11", "description": "IMPS TRF FROM A/C XXXX1234", "credit": 300_000}],
         last4="5678", bank_name="Harbourline Bank")
    rows = _stated(client, headers, case_id)
    assert len(rows) == 7
    r = rows["NEFT CR ORCHID TRADERS"]
    assert (r["category"], r["category_label"], r["direction"], r["method"]) == (
        "customer_receipt", "Receipt from a customer", "credit", "rule")
    assert r["counterparty"] == "ORCHID TRADERS" and r["rule_id"] == "customer_receipt_default" and r["evidence"]
    assert rows["NACH DR VESTA CAPITAL 778811 EMI"]["category"] == "loan_emi"
    assert rows["LOAN DISBURSAL TL 7781"]["category"] == "loan_disbursal"
    # a transfer between the borrower's own accounts is found from the account set
    assert rows["IMPS TRF TO A/C XXXX5678"]["category"] == "own_transfer_out"
    assert rows["IMPS TRF FROM A/C XXXX1234"]["category"] == "own_transfer_in"
    unmatched = rows["XQ77 MISC ADJ"]
    assert (unmatched["status"], unmatched["category"], unmatched["needs_review"]) == ("unmatched", "other_debit", True)


def test_the_list_filters_and_pages(client: TestClient, published_data_root: Path):
    headers, case_id = _case(client, published_data_root)
    bank(published_data_root, case_id, ROWS)
    assert [r["narration"] for r in _all(client, headers, case_id, category="salary")] == ["NEFT DR SALARY"]
    assert len(_all(client, headers, case_id, month="2025-05")) == 3
    assert [r["narration"] for r in _all(client, headers, case_id, q="vesta")] == ["NACH DR VESTA CAPITAL 778811 EMI"]
    assert [r["narration"] for r in _all(client, headers, case_id, needs_review=True)] == ["XQ77 MISC ADJ"]
    page = client.get(f"/api/cases/{case_id}/transactions", params={"limit": 2, "offset": 2}, headers=headers).json()
    assert (page["total"], len(page["items"]), page["offset"]) == (6, 2, 2)


def test_the_summary_totals_by_category_and_month(client: TestClient, published_data_root: Path):
    headers, case_id = _case(client, published_data_root)
    bank(published_data_root, case_id, ROWS)
    s = client.get(f"/api/cases/{case_id}/transactions/summary", headers=headers).json()
    assert (s["total"], s["by_rule"], s["by_person"], s["unsettled"]) == (6, 5, 0, 1)
    by = {c["category"]: c for c in s["categories"]}
    assert by["loan_emi"]["amount"] == 96_500 and by["loan_emi"]["count"] == 1 and by["loan_emi"]["direction"] == "debit"
    assert [m["month"] for m in s["months"]] == ["2025-04", "2025-05"]
    assert s["months"][0]["credits"] == 2_900_000 and s["months"][0]["by_category"]["salary"] == 120_000
    assert s["accounts"] == ["Lotuscrest Bank ·1234"] and s["config_version"]
    assert s["catalogue"][0] == {"id": "customer_receipt", "label": "Receipt from a customer", "direction": "credit"}
    assert {c["direction"] for c in s["catalogue"]} == {"credit", "debit"}


def test_a_row_the_rules_cannot_settle_raises_one_review_item_that_closes_when_it_is_settled(
    client: TestClient, published_data_root: Path
):
    headers, case_id = _case(client, published_data_root)
    bank(published_data_root, case_id, ROWS + [{"date": "2025-05-12", "description": "ZZ9 ODD ENTRY", "credit": 900}])
    _all(client, headers, case_id)
    items = [i for i in client.get("/api/review", params={"case_id": case_id}, headers=headers).json() if i["kind"] == "transactions"]
    assert len(items) == 1 and items[0]["summary"] == "2 transactions on Lotuscrest Bank ·1234 could not be classified"
    ids = {r["narration"]: r["txn_id"] for r in _all(client, headers, case_id, needs_review=True)}
    for narration, category in (("XQ77 MISC ADJ", "bank_charges"), ("ZZ9 ODD ENTRY", "customer_receipt")):
        r = client.put(f"/api/cases/{case_id}/transactions/{ids[narration]}/category", headers=headers,
                       json={"category": category, "reason": "Checked against the passbook"})
        assert r.status_code == 200, r.text
        assert (r.json()["category"], r.json()["method"], r.json()["needs_review"]) == (category, "manual", False)
    assert not [i for i in client.get("/api/review", params={"case_id": case_id}, headers=headers).json() if i["kind"] == "transactions"]
    decided = [i for i in client.get("/api/review", params={"case_id": case_id, "include_decided": True}, headers=headers).json()
               if i["kind"] == "transactions"]
    assert decided[0]["status"] == "decided" and decided[0]["reason"] == "All transactions classified"
    s = client.get(f"/api/cases/{case_id}/transactions/summary", headers=headers).json()
    assert (s["by_person"], s["unsettled"]) == (2, 0)


def test_a_decision_is_checked_logged_and_can_be_taken_back(client: TestClient, published_data_root: Path):
    headers, case_id = _case(client, published_data_root)
    bank(published_data_root, case_id, ROWS)
    rows = _stated(client, headers, case_id)
    credit, debit = rows["NEFT CR ORCHID TRADERS"]["txn_id"], rows["XQ77 MISC ADJ"]["txn_id"]
    put = lambda txn, body: client.put(f"/api/cases/{case_id}/transactions/{txn}/category", headers=headers, json=body)
    assert put(credit, {"category": "salary", "reason": "wrong way round"}).status_code == 422       # a debit category on a credit
    assert put(debit, {"category": "no_such_category", "reason": "typo"}).status_code == 422
    assert put("FV-NOPE", {"category": "salary", "reason": "no such row"}).status_code == 404
    assert put(debit, {"category": "salary", "reason": "x"}).status_code == 422                      # the reason is required
    assert put(debit, {"category": "bank_charges", "reason": "Quarterly service fee"}).status_code == 200
    conn = db.connect(published_data_root)
    try:
        logged = conn.execute("SELECT actor, detail FROM decision_log WHERE case_id = ? AND action = 'transaction.categorised'",
                              (case_id,)).fetchall()
    finally:
        conn.close()
    assert len(logged) == 1 and "Quarterly service fee" in logged[0]["detail"] and "other_debit" in logged[0]["detail"]
    back = client.delete(f"/api/cases/{case_id}/transactions/{debit}/category", headers=headers)
    assert back.status_code == 200 and (back.json()["category"], back.json()["needs_review"]) == ("other_debit", True)
    assert client.delete(f"/api/cases/{case_id}/transactions/{debit}/category", headers=headers).status_code == 404


def test_a_decision_survives_the_rows_being_classified_again(client: TestClient, published_data_root: Path):
    headers, case_id = _case(client, published_data_root)
    bank(published_data_root, case_id, ROWS)
    txn = _stated(client, headers, case_id)["XQ77 MISC ADJ"]["txn_id"]
    client.put(f"/api/cases/{case_id}/transactions/{txn}/category", headers=headers,
               json={"category": "bank_charges", "reason": "Quarterly service fee"})
    bank(published_data_root, case_id, [{"date": "2025-06-01", "description": "NEFT CR LATE CUSTOMER", "credit": 5_000}], last4="9999")
    conn = db.connect(published_data_root)
    try:
        result = bank_txns.refresh(conn, published_data_root, cases.get_case(conn, case_id))
    finally:
        conn.close()
    assert result["rewritten"] and result["rows"] == 7
    rows = _stated(client, headers, case_id)
    assert rows["XQ77 MISC ADJ"]["category"] == "bank_charges" and rows["XQ77 MISC ADJ"]["method"] == "manual"


def test_nothing_is_rewritten_when_nothing_changed(client: TestClient, published_data_root: Path):
    headers, case_id = _case(client, published_data_root)
    bank(published_data_root, case_id, ROWS)
    _all(client, headers, case_id)
    conn = db.connect(published_data_root)
    try:
        case = cases.get_case(conn, case_id)
        assert bank_txns.refresh(conn, published_data_root, case)["rewritten"] is False
    finally:
        conn.close()


def test_deleting_the_case_removes_its_classified_transactions(client: TestClient, published_data_root: Path):
    headers, case_id = _case(client, published_data_root)
    bank(published_data_root, case_id, ROWS)
    txn = _stated(client, headers, case_id)["XQ77 MISC ADJ"]["txn_id"]
    client.put(f"/api/cases/{case_id}/transactions/{txn}/category", headers=headers,
               json={"category": "bank_charges", "reason": "Quarterly service fee"})
    conn = db.connect(published_data_root)
    try:
        cases.delete_case(conn, case_id, actor="test", reason="test", root=published_data_root)
        for table in ("txn_class", "txn_class_basis", "txn_class_overrides"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE case_id = ?", (case_id,)).fetchone()[0] == 0
    finally:
        conn.close()
