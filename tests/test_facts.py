"""Fact alignment (FRD F-18): identities, turnover by financial year, bank
credit cleansing, obligations, the account set, with evidence kept."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

FY26 = months((2025, 4), 12)  # FY 2025-26, April to March
MONTHS = ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"]


def _facts(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/facts", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_identities_are_collected_per_document(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    pan = add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F", "company_name": "Kestrel Tools Pvt Ltd"})
    add_doc(published_data_root, case_id, "income_tax_return",
            {"pan": "AAACK1234G", "taxpayer_name": "Kestrel Tools Private Limited", "assessment_year": "2026-27"})
    add_doc(published_data_root, case_id, "gstr_3b", {"gstin": "27AAACK1234F1Z0", "legal_name": "Kestrel Tools Private Limited"})
    add_doc(published_data_root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "pan": "ABCPV1234K"})
    facts = _facts(client, analyst, case_id)
    pans = {v["value"]: v for v in facts["identities"]["entity_pan"] if v["source"] != "gstr_3b"}
    # A director's PAN is not the entity's; the PAN within the GSTIN is (ID-01).
    assert {v["value"] for v in facts["identities"]["entity_pan"]} == {"AAACK1234F", "AAACK1234G"}
    within = next(v for v in facts["identities"]["entity_pan"] if v["source"] == "gstr_3b")
    assert within["value"] == "AAACK1234F" and within["label"].endswith("(PAN within the GSTIN)")
    assert pans["AAACK1234F"]["evidence"][0]["document_id"] == pan
    assert pans["AAACK1234F"]["field_ids"]
    assert [v["value"] for v in facts["identities"]["gstin"]] == ["27AAACK1234F1Z0"]
    assert len(facts["identities"]["legal_name"]) == 3  # the person's name is not the entity's


def test_turnover_is_aligned_by_financial_year(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2026-03-31")  # revenue from operations 118,000,000
    for name in MONTHS[4:]:  # April to July absent
        year = 2025 if name in MONTHS[:9] else 2026
        gstr(published_data_root, case_id, f"{name} {year}", 10_000_000)
    bank(published_data_root, case_id, [
        {"date": "2025-05-10", "description": "NEFT CR ORCHID TRADERS INV 44", "credit": 9_000_000},
        {"date": "2025-06-02", "description": "TL DISB LOAN A/C 88991", "credit": 5_000_000},
    ])
    facts = _facts(client, analyst, case_id)
    fy = next(y for y in facts["turnover"] if y["fy"] == "FY 2025-26")
    by = {f["source"]: f for f in fy["figures"]}
    assert by["financials"]["value"] == 118_000_000
    assert by["financials"]["evidence"] and by["financials"]["field_ids"]
    assert by["gst"]["value"] == 80_000_000 and by["gst"]["months_covered"] == 8
    assert by["gst"]["months_missing"] == ["Apr 2025", "May 2025", "Jun 2025", "Jul 2025"]
    # The loan disbursal is not business inflow (F-18.2).
    assert by["bank"]["value"] == 9_000_000 and by["bank"]["months_covered"] == 12


def test_bank_credits_are_cleansed_with_every_exclusion_kept(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, borrower="Kestrel Tools Pvt Ltd")
    bank(published_data_root, case_id, [
        {"date": "2025-04-05", "description": "NEFT CR ORCHID TRADERS", "credit": 400_000},
        {"date": "2025-04-06", "description": "LOAN DISBURSAL TL 7781", "credit": 2_500_000},
        {"date": "2025-04-07", "description": "REVERSAL OF CHG", "credit": 1_500},
        {"date": "2025-04-08", "description": "CHQ RET 004512 INSUFFICIENT FUNDS", "credit": 75_000},
        {"date": "2025-04-09", "description": "IMPS TRF FROM A/C XXXX5678 KESTREL TOOLS", "credit": 300_000},
    ])
    bank(published_data_root, case_id, [{"date": "2025-04-09", "description": "IMPS TRF TO A/C XXXX1234", "debit": 300_000}],
         last4="5678", bank_name="Harbourline Bank")
    facts = _facts(client, analyst, case_id)
    credits = next(c for c in facts["credits"] if c["account"].endswith("1234"))
    assert credits["gross"] == 3_276_500
    assert credits["net"] == 400_000
    assert sorted(e["rule"] for e in credits["exclusions"]) == ["loan_disbursal", "own_account_transfer", "returned_cheque", "reversal"]
    assert all(e["evidence"] for e in credits["exclusions"])


def test_recurring_lender_debits_become_obligations(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    bank(published_data_root, case_id, [
        {"date": f"{p}-05", "description": f"NACH DR ASHWOOD FINSERV UMRN{i}", "debit": 145_000 + i * 100}
        for i, p in enumerate(FY26[:6])
    ] + [{"date": "2025-04-20", "description": "NACH DR QUILLBY INSURANCE", "debit": 12_000}])
    facts = _facts(client, analyst, case_id)
    assert [o["lender"] for o in facts["obligations"]] == ["ASHWOOD FINSERV"]
    ob = facts["obligations"][0]
    assert len(ob["months"]) == 6 and 145_000 <= ob["typical_amount"] <= 145_500
    assert ob["evidence"]


def test_the_account_set_spans_statements_and_transfers(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    bank(published_data_root, case_id, [{"date": "2025-04-09", "description": "NEFT TRF TO A/C XXXXXX7777 SELF", "debit": 50_000}])
    bank(published_data_root, case_id, [{"date": "2025-04-10", "description": "RTGS CR CUSTOMER", "credit": 70_000}],
         last4="9999", bank_name="Harbourline Bank")
    facts = _facts(client, analyst, case_id)
    accounts = {a["last4"]: a for a in facts["accounts"]}
    assert accounts["1234"]["has_statement"] and accounts["9999"]["has_statement"]
    # An account named in a transfer narration is in the set, without a statement (F-18.5).
    assert not accounts["7777"]["has_statement"] and "Transfer in" in accounts["7777"]["sources"][0]
    assert not any(a["declared"] for a in accounts.values()) and facts["declaration_received"] is False
    assert facts["facilities"] == []  # no document the configured types can read declares facilities


def test_statement_lines_come_from_the_printed_rows(client: TestClient, published_data_root: Path):
    from engine import statements
    from engine.configstore import reader
    from engine import db
    from engine.facts import load_documents

    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2026-03-31")
    conn = db.connect(published_data_root)
    try:
        [doc] = load_documents(conn, published_data_root, case_id)
    finally:
        conn.close()
    lines = statements.lines(doc, reader.load_statements(published_data_root))
    assert lines["revenue_from_operations"].value == 118_000_000 and lines["profit_after_tax"].value == 6_400_000
    # Derived from the printed rows, with their evidence.
    assert lines["ebitda"].value == 7_500_000 + 3_500_000 + 4_000_000
    assert lines["net_worth"].value == 42_000_000 and lines["current_assets"].value == 59_000_000
    assert lines["current_liabilities"].value == 37_000_000 and lines["total_borrowings"].value == 27_000_000
    assert lines["net_worth"].evidence and lines["net_worth"].field_ids
    previous = statements.lines(doc, reader.load_statements(published_data_root), column="previous_period")
    assert previous["revenue_from_operations"].value == round(118_000_000 * 0.85)
    assert statements.period_end(doc).isoformat() == "2026-03-31"


def test_a_correction_is_used_and_flagged(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234X"}, corrected={"pan": "AAACK1234F"})
    [pan] = _facts(client, analyst, case_id)["identities"]["entity_pan"]
    assert pan["value"] == "AAACK1234F" and pan["relies_on_manual"] is True


def test_facts_need_the_data_permission(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/facts", headers=rm).status_code == 403
