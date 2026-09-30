"""Fact alignment (FRD F-18): identities, turnover by financial year, bank
credit cleansing, obligations, the account set, with evidence kept."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.triangulation import add_doc, months

FY26 = months((2025, 4), 12)  # FY 2025-26, April to March


def _facts(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/facts", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _statement(root: Path, case_id: str, transactions: list[dict], *, last4: str = "1234") -> str:
    return add_doc(root, case_id, "bank_statement", {
        "bank": "Lotuscrest Bank",
        "account_number_masked": f"XXXXXX{last4}",
        "period_from": "2025-04-01",
        "period_to": "2026-03-31",
        "transactions": transactions,
    })


def test_identities_are_collected_per_document(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    pan = add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234F", "name": "Kestrel Tools Pvt Ltd"})
    add_doc(published_data_root, case_id, "gst_registration_certificate",
            {"gstin": "27AAACK1234F1Z0", "legal_name": "Kestrel Tools Private Limited", "pan": "AAACK1234G"})
    facts = _facts(client, analyst, case_id)
    pans = {v["value"]: v for v in facts["identities"]["entity_pan"]}
    assert set(pans) == {"AAACK1234F", "AAACK1234G"}
    assert pans["AAACK1234F"]["evidence"][0]["document_id"] == pan
    assert pans["AAACK1234F"]["field_ids"]
    assert len(facts["identities"]["legal_name"]) == 2


def test_turnover_is_aligned_by_financial_year(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "audited_financial_statements",
            {"period_end": "2026-03-31", "revenue_from_operations": 120_000_000})
    for period in FY26[4:]:  # April to July absent
        add_doc(published_data_root, case_id, "gstr_3b", {"period": period, "outward_taxable_supplies": 10_000_000})
    _statement(published_data_root, case_id, [
        {"date": "2025-05-10", "narration": "NEFT CR ORCHID TRADERS INV 44", "credit": 9_000_000},
        {"date": "2025-06-02", "narration": "TL DISB LOAN A/C 88991", "credit": 5_000_000},
    ])
    facts = _facts(client, analyst, case_id)
    fy = next(y for y in facts["turnover"] if y["fy"] == "FY 2025-26")
    by = {f["source"]: f for f in fy["figures"]}
    assert by["financials"]["value"] == 120_000_000
    assert by["gst"]["value"] == 80_000_000 and by["gst"]["months_covered"] == 8
    assert by["gst"]["months_missing"] == ["Apr 2025", "May 2025", "Jun 2025", "Jul 2025"]
    # The loan disbursal is not business inflow (F-18.2).
    assert by["bank"]["value"] == 9_000_000 and by["bank"]["months_covered"] == 12


def test_bank_credits_are_cleansed_with_every_exclusion_kept(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, borrower="Kestrel Tools Pvt Ltd")
    _statement(published_data_root, case_id, [
        {"date": "2025-04-05", "narration": "NEFT CR ORCHID TRADERS", "credit": 400_000},
        {"date": "2025-04-06", "narration": "LOAN DISBURSAL TL 7781", "credit": 2_500_000},
        {"date": "2025-04-07", "narration": "REVERSAL OF CHG", "credit": 1_500},
        {"date": "2025-04-08", "narration": "CHQ RET 004512 INSUFFICIENT FUNDS", "credit": 75_000},
        {"date": "2025-04-09", "narration": "IMPS TRF FROM A/C XXXX5678 KESTREL TOOLS", "credit": 300_000},
    ])
    add_doc(published_data_root, case_id, "bank_statement", {
        "bank": "Harbourline Bank", "account_number_masked": "XXXX5678",
        "period_from": "2025-04-01", "period_to": "2026-03-31",
        "transactions": [{"date": "2025-04-09", "narration": "IMPS TRF TO A/C XXXX1234", "debit": 300_000}],
    })
    facts = _facts(client, analyst, case_id)
    credits = next(c for c in facts["credits"] if c["account"].endswith("1234"))
    assert credits["gross"] == 3_276_500
    assert credits["net"] == 400_000
    assert sorted(e["rule"] for e in credits["exclusions"]) == [
        "loan_disbursal", "own_account_transfer", "returned_cheque", "reversal",
    ]
    assert all(e["evidence"] for e in credits["exclusions"])


def test_recurring_lender_debits_become_obligations(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    _statement(published_data_root, case_id, [
        {"date": f"{p}-05", "narration": f"NACH DR ASHWOOD FINSERV UMRN{i}", "debit": 145_000 + i * 100}
        for i, p in enumerate(FY26[:6])
    ] + [{"date": "2025-04-20", "narration": "NACH DR QUILLBY INSURANCE", "debit": 12_000}])
    facts = _facts(client, analyst, case_id)
    assert [o["lender"] for o in facts["obligations"]] == ["ASHWOOD FINSERV"]
    ob = facts["obligations"][0]
    assert len(ob["months"]) == 6 and 145_000 <= ob["typical_amount"] <= 145_500
    assert ob["evidence"]


def test_the_account_set_spans_statements_declaration_and_transfers(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    _statement(published_data_root, case_id, [
        {"date": "2025-04-09", "narration": "NEFT TRF TO A/C XXXXXX7777 SELF", "debit": 50_000},
    ])
    add_doc(published_data_root, case_id, "existing_facilities_declaration", {
        "declaration_date": "2026-09-10", "nil_declared": True,
        "accounts": [
            {"bank": "Lotuscrest Bank", "account_number_masked": "XXXX1234"},
            {"bank": "Harbourline Bank", "account_number_masked": "XXXX9999"},
        ],
    })
    facts = _facts(client, analyst, case_id)
    accounts = {a["last4"]: a for a in facts["accounts"]}
    assert accounts["1234"]["declared"] and accounts["1234"]["has_statement"]
    assert accounts["9999"]["declared"] and not accounts["9999"]["has_statement"]
    assert not accounts["7777"]["declared"] and not accounts["7777"]["has_statement"]
    assert facts["declaration_received"] is True


def test_a_correction_is_used_and_flagged(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234X"}, corrected={"pan": "AAACK1234F"})
    [pan] = _facts(client, analyst, case_id)["identities"]["entity_pan"]
    assert pan["value"] == "AAACK1234F" and pan["relies_on_manual"] is True


def test_facts_need_the_data_permission(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/facts", headers=rm).status_code == 403
