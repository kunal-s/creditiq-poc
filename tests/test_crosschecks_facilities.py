"""Existing facilities and the bureau (test plan TC-20, TC-23; FRD TC-22, TC-25): the declaration of
existing facilities, sanction letters and the commercial bureau report reconciled with each other
(OB-01), with the bank statements (OB-02, BA-01) and as sources of identity (ID-01, ID-02, ID-04).
Every name is fictional."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, bank, gstr, months

CO = "Kestrel Tools Private Limited"
TIDEWATER = {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12_000_000,
             "outstanding": 7_500_000, "emi": 250_000}
LOTUSCREST = {"lender": "Lotuscrest Bank", "facility": "Cash credit", "sanctioned_amount": 20_000_000,
              "outstanding": 18_500_000}


def declaration(root: Path, case_id: str, facilities=(), accounts=()) -> str:
    return add_doc(root, case_id, "existing_facilities_declaration", {
        "company_name": CO, "declaration_date": "2026-09-15", "facilities": list(facilities),
        "bank_accounts": [{"bank": b, "account_number": n, "account_type": "Current account"} for b, n in accounts]})


def sanction(root: Path, case_id: str, lender: str, amount: int, emi: int | None = None) -> str:
    row = {"facility": "Term loan", "sanctioned_amount": amount, **({"emi": emi} if emi else {})}
    return add_doc(root, case_id, "sanction_letter", {"lender_name": lender, "borrower_name": CO, "sanction_date": "2024-04-12",
                                                      "facilities": [row]})


def bureau(root: Path, case_id: str, facilities=(), parties=(), *, pan: str = "AAACK1234F", gstin: str | None = None) -> str:
    fields = {"company_name": CO, "pan": pan, "report_date": "2026-09-20", "credit_rank": "4",
              "credit_facilities": [{**f, "overdue": 0, "status": "Standard"} for f in facilities],
              "related_parties": [{"name": n, "relationship": "Director", "pan": p} for n, p in parties]}
    if gstin:
        fields["gstin"] = gstin
    return add_doc(root, case_id, "commercial_bureau_report", fields)


def emis(root: Path, case_id: str, narration: str = "NACH DR TIDEWATER FIN EMI 000123", amount: int = 250_000) -> None:
    bank(root, case_id, [{"date": f"{ym}-10", "description": narration, "debit": amount} for ym in months((2025, 4), 6)])


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _findings(client: TestClient, headers: dict, root: Path, case_id: str) -> dict[str, list[dict]]:
    _refresh(root, case_id)
    response = client.get(f"/api/cases/{case_id}/findings", headers=headers)
    assert response.status_code == 200, response.text
    out: dict[str, list[dict]] = {}
    for f in response.json():
        out.setdefault(f["rule_id"], []).append(f)
    return out


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _case(client: TestClient, analyst: dict, root: Path, **overrides) -> str:
    return make_case(client, analyst, root, **{"borrower": "Kestrel Tools Pvt Ltd", **overrides})


def _one(client, analyst, root, case_id, rule: str) -> dict:
    [f] = _findings(client, analyst, root, case_id)[rule]
    return f


# --- OB-01: declared facilities against the sanction letters and the bureau ---


def test_facilities_that_agree_across_the_three_sources_pass(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id, [TIDEWATER, LOTUSCREST])
    sanction(published_data_root, case_id, "Tidewater Finance Limited", 12_000_000)
    bureau(published_data_root, case_id, [TIDEWATER, LOTUSCREST])
    f = _one(client, analyst, published_data_root, case_id, "OB-01")
    assert f["outcome"] == "pass" and f["area"] == "obligations"
    rows = {r["label"]: r for r in f["detail"]["rows"]}
    assert rows["Tidewater Finance Limited"]["cells"] == [12_000_000, 12_000_000, 12_000_000, 7_500_000]
    assert not any(r["flagged"] for r in rows.values())


def test_a_facility_the_bureau_reports_but_the_declaration_omits_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id, [TIDEWATER])
    bureau(published_data_root, case_id, [TIDEWATER, LOTUSCREST])
    f = _one(client, analyst, published_data_root, case_id, "OB-01")
    assert f["outcome"] == "fail" and f["severity"] == "serious"
    assert f["explanation"] == "The existing facilities do not reconcile: Lotuscrest Bank: not declared."
    assert "Lotuscrest Bank" in f["query"]
    rows = {r["label"]: r for r in f["detail"]["rows"]}
    assert rows["Lotuscrest Bank"]["flagged"] and rows["Lotuscrest Bank"]["cells"][0] == "—"
    assert not rows["Tidewater Finance Limited"]["flagged"]


def test_sanctioned_amounts_that_differ_beyond_tolerance_are_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id, [TIDEWATER])
    sanction(published_data_root, case_id, "TIDEWATER FINANCE LTD", 15_000_000)
    f = _one(client, analyst, published_data_root, case_id, "OB-01")
    assert f["outcome"] == "fail"
    assert "sanctioned amounts differ: declared INR 1.20 cr, sanction letter INR 1.50 cr" in f["explanation"]


def test_a_declared_facility_neither_source_shows_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id, [TIDEWATER, LOTUSCREST])
    bureau(published_data_root, case_id, [TIDEWATER])
    f = _one(client, analyst, published_data_root, case_id, "OB-01")
    assert f["outcome"] == "fail"
    assert "Lotuscrest Bank: declared, but neither a sanction letter nor the bureau report shows it" in f["explanation"]


def test_a_nil_declaration_against_a_facility_in_the_bureau_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id)  # declares none
    bureau(published_data_root, case_id, [TIDEWATER])
    f = _one(client, analyst, published_data_root, case_id, "OB-01")
    assert f["outcome"] == "fail" and "Tidewater Finance Limited: not declared" in f["explanation"]
    declared = next(s for s in f["sides"] if s["label"] == "Declaration of existing facilities")
    assert declared["value"] == "None declared" and declared["differs"] and declared["evidence"]


def test_the_sourcing_message_counts_as_a_declaration(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root, header={
        "existing_banking": {"value": "Term loan from Tidewater Finance, EMI 2.5 lakh", "source": "person"}})
    bureau(published_data_root, case_id, [TIDEWATER])
    f = _one(client, analyst, published_data_root, case_id, "OB-01")
    assert f["outcome"] == "pass" and f["detail"]["rows"][0]["cells"][0] == "✓"


def test_reconciliation_waits_for_a_sanction_letter_or_the_bureau(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id, [TIDEWATER])
    f = _one(client, analyst, published_data_root, case_id, "OB-01")
    assert f["outcome"] == "incomplete" and f["missing"] == ["Sanction letter", "Commercial bureau report"]


def test_reconciliation_does_not_apply_with_nothing_declared_or_on_file(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    gstr(published_data_root, case_id, "April 2025", 1_000_000)
    assert _one(client, analyst, published_data_root, case_id, "OB-01")["outcome"] == "not_applicable"


# --- OB-02 and BA-01 against the declaration document ---


def test_instalments_against_a_nil_declaration_are_undeclared(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id)
    emis(published_data_root, case_id)
    f = _one(client, analyst, published_data_root, case_id, "OB-02")
    assert f["outcome"] == "fail" and "TIDEWATER FIN" in f["explanation"]
    assert any(s["label"] == "Declaration of existing facilities" and s["value"] == "None declared" for s in f["sides"])


def test_instalments_to_a_lender_the_declaration_names_are_declared(client, analyst, published_data_root):
    # The narration abbreviates the lender ("TIDEWATER FIN"); the declaration prints it in full.
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id, [TIDEWATER])
    emis(published_data_root, case_id)
    assert _one(client, analyst, published_data_root, case_id, "OB-02")["outcome"] == "pass"


def test_accounts_the_declaration_lists_are_declared(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    declaration(published_data_root, case_id, accounts=[("Lotuscrest Bank", "901000001234"), ("Lotuscrest Bank", "901000005678")])
    bank(published_data_root, case_id, [], last4="1234")
    found = _findings(client, analyst, published_data_root, case_id)
    [ba1] = found["BA-01"]
    assert ba1["outcome"] == "fail" and "Lotuscrest Bank ·5678" in ba1["explanation"]
    assert ba1["sides"][0]["label"] == "Declared accounts"
    assert [f["outcome"] for f in found["BA-02"]] == ["pass"]


# --- The bureau as a source of identity and of the promoter set (TC-20) ---


def test_the_bureau_is_a_source_of_the_entity_pan(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F"})
    report = bureau(published_data_root, case_id, pan="AAACK9999Z")
    f = _one(client, analyst, published_data_root, case_id, "ID-01")
    assert f["outcome"] == "fail"
    odd = next(s for s in f["sides"] if s["differs"])
    assert odd["value"] == "AAACK9999Z" and odd["label"] == "Commercial bureau report"
    assert odd["evidence"][0]["document_id"] == report


def test_the_bureau_gstin_is_compared_with_the_returns(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    gstr(published_data_root, case_id, "April 2025", 1_000_000, gstin="27AAACK1234F1Z0")
    bureau(published_data_root, case_id, gstin="29AAACK1234F1Z5")
    f = _one(client, analyst, published_data_root, case_id, "ID-02")
    assert f["outcome"] == "fail" and {s["value"] for s in f["sides"]} == {"27AAACK1234F1Z0", "29AAACK1234F1Z5"}


def test_a_director_the_bureau_names_without_kyc_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "pan": "ABCPV1234K"})
    bureau(published_data_root, case_id, parties=[("Tarun Velankar", "ABCPV1234K"), ("Rohan Mistry", "ABCPM4321Q")])
    f = _one(client, analyst, published_data_root, case_id, "ID-04")
    assert f["outcome"] == "fail" and "Rohan Mistry is not in KYC received" in f["explanation"]
    assert f["detail"]["columns"] == ["KYC received", "Commercial bureau report"]
    # The bureau's related parties join the case's party set, with their PAN (F-10.2).
    parties = {p["name"]: p for p in client.get(f"/api/cases/{case_id}/parties", headers=analyst).json()}
    assert parties["Rohan Mistry"]["pan"] == "ABCPM4321Q" and parties["Rohan Mistry"]["role"] == "director"


# --- The facts and the CAM ---


def test_facilities_are_collected_from_each_source_with_their_evidence(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    decl = declaration(published_data_root, case_id, [TIDEWATER])
    letter = sanction(published_data_root, case_id, "Tidewater Finance Limited", 12_000_000, emi=250_000)
    report = bureau(published_data_root, case_id, [TIDEWATER])
    _refresh(published_data_root, case_id)
    facts = client.get(f"/api/cases/{case_id}/facts", headers=analyst).json()
    by_source = {f["source"]: f for f in facts["facilities"]}
    assert set(by_source) == {"existing_facilities_declaration", "sanction_letter", "commercial_bureau_report"}
    assert by_source["sanction_letter"]["lender"] == "Tidewater Finance Limited" and by_source["sanction_letter"]["emi"] == 250_000
    assert by_source["commercial_bureau_report"]["outstanding"] == 7_500_000
    assert [by_source[s]["evidence"][0]["document_id"] for s in ("existing_facilities_declaration", "sanction_letter",
                                                                 "commercial_bureau_report")] == [decl, letter, report]
    assert facts["declaration_received"] is True and facts["declaration"]["value"] == "Tidewater Finance Limited"
    cam = client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()
    section = next(s for s in cam["sections"] if s["id"] == "obligations")
    assert any("Declaration of existing facilities: Tidewater Finance Limited" in p["text"] for p in section["paragraphs"])
