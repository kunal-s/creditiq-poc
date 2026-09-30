"""Cross-checks (FRD F-19): TC-22 identity, TC-23 turnover, TC-24 bank
accounts, TC-25 obligations; manual reliance (F-19.4), the query list
(F-19.5), tolerance changes (F-19.6) and decisions on findings (F-17.4)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from engine.configstore import writer
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, months

FY26 = months((2025, 4), 12)


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


def _case(client: TestClient, analyst: dict, root: Path) -> str:
    return make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd")


# --- TC-22: identity ---


def test_tc22_a_pan_mismatch_is_flagged_with_both_sources(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    pan_doc = add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "gst_registration_certificate", {"gstin": "27AAACK1234F1Z0", "pan": "AAACK1234F"})
    bureau = add_doc(published_data_root, case_id, "bureau_commercial", {"pan": "AAACK9876Q"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-01"]
    assert f["outcome"] == "fail" and f["severity"] == "serious" and f["blocking"]
    values = {s["value"]: s for s in f["sides"]}
    assert values["AAACK1234F"]["evidence"][0]["document_id"] == pan_doc
    assert values["AAACK9876Q"]["evidence"][0]["document_id"] == bureau
    assert "AAACK9876Q" in f["explanation"] and "AAACK1234F" in f["explanation"]


def test_tc22_consistent_identities_pass(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234F", "name": "Kestrel Tools Pvt Ltd"})
    add_doc(published_data_root, case_id, "gst_registration_certificate",
            {"gstin": "27AAACK1234F1Z0", "pan": "AAACK1234F", "legal_name": "KESTREL TOOLS PRIVATE LIMITED"})
    add_doc(published_data_root, case_id, "gstr_3b", {"gstin": "27AAACK1234F1Z0", "period": "2025-09"})
    found = _findings(client, analyst, published_data_root, case_id)
    assert [f["outcome"] for f in found["ID-01"]] == ["pass"]
    assert [f["outcome"] for f in found["ID-02"]] == ["pass"]
    # Name variants of one company are one legal name (F-18.3).
    assert [f["outcome"] for f in found["ID-03"]] == ["pass"]


def test_tc22_a_promoter_missing_from_one_source_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "board_resolution",
            {"directors": [{"name": "Tarun Velankar"}, {"name": "Leela Varghese"}]})
    add_doc(published_data_root, case_id, "gst_registration_certificate",
            {"persons": [{"name": "Tarun Velankar"}]})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-04"]
    assert f["outcome"] == "fail"
    assert "Leela Varghese is not in GST registration certificate" in f["explanation"]


# --- TC-23: turnover ---


def _turnover(root: Path, case_id: str, *, gst_months: list[str], gst_each: float, bank_each: float,
              audited: float | None = None) -> None:
    if audited is not None:
        add_doc(root, case_id, "audited_financial_statements",
                {"period_end": "2026-03-31", "revenue_from_operations": audited})
    for p in gst_months:
        add_doc(root, case_id, "gstr_3b", {"period": p, "outward_taxable_supplies": gst_each})
    add_doc(root, case_id, "bank_statement", {
        "bank": "Lotuscrest Bank", "account_number_masked": "XXXX1234",
        "period_from": "2025-04-01", "period_to": "2026-03-31",
        "transactions": [{"date": f"{p}-15", "narration": "NEFT CR ORCHID TRADERS", "credit": bank_each} for p in FY26],
    })


def test_tc23_gst_against_bank_beyond_tolerance_is_flagged_with_values(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=FY26, gst_each=4_000_000, bank_each=3_200_000)
    [f] = _findings(client, analyst, published_data_root, case_id)["TO-02"]
    assert f["outcome"] == "fail" and f["tolerance"] == "10%"
    assert [s["value"] for s in f["sides"]] == [48_000_000, 38_400_000]
    assert "20.0%" in f["explanation"] and "FY 2025-26" in f["title"]
    assert all(s["evidence"] for s in f["sides"])


def test_tc23_within_tolerance_passes(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=FY26, gst_each=4_000_000, bank_each=3_800_000)
    assert [f["outcome"] for f in _findings(client, analyst, published_data_root, case_id)["TO-02"]] == ["pass"]


def test_tc23_incomplete_coverage_is_stated(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=FY26[4:], gst_each=4_000_000, bank_each=3_000_000,
              audited=48_000_000)
    found = _findings(client, analyst, published_data_root, case_id)
    [to1] = found["TO-01"]
    assert to1["outcome"] == "incomplete"
    assert "GST outward supplies covers 8 of 12 months (Apr 2025, May 2025, Jun 2025… absent)" in to1["explanation"]
    [to3] = found["TO-03"]
    assert to3["outcome"] == "fail"  # 4.8 cr audited against 3.6 cr banked, 25%


# --- TC-24: bank accounts ---


def test_tc24_accounts_without_statements_and_undeclared_accounts(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "bank_statement", {
        "bank": "Lotuscrest Bank", "account_number_masked": "XXXX1234",
        "period_from": "2025-04-01", "period_to": "2026-03-31",
        "transactions": [{"date": "2025-04-09", "narration": "NEFT TRF TO A/C XXXXXX7777 SELF", "debit": 50_000}],
    })
    add_doc(published_data_root, case_id, "existing_facilities_declaration", {
        "declaration_date": "2026-09-10", "nil_declared": True,
        "accounts": [{"bank": "Lotuscrest Bank", "account_number_masked": "XXXX1234"},
                     {"bank": "Harbourline Bank", "account_number_masked": "XXXX9999"}],
    })
    found = _findings(client, analyst, published_data_root, case_id)
    [ba1] = found["BA-01"]
    assert ba1["outcome"] == "fail" and "Harbourline Bank ·9999" in ba1["explanation"]
    [ba2] = found["BA-02"]
    assert ba2["outcome"] == "fail"
    # Only the undeclared account is named, with where it was seen.
    assert ba2["explanation"].endswith("not declared: Account ·7777 (Transfer in Lotuscrest Bank ·1234).")


def test_tc24_without_a_declaration_the_check_is_incomplete(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "bank_statement", {
        "bank": "Lotuscrest Bank", "account_number_masked": "XXXX1234",
        "period_from": "2025-04-01", "period_to": "2026-03-31"})
    found = _findings(client, analyst, published_data_root, case_id)
    assert [f["outcome"] for f in found["BA-01"]] == ["incomplete"]
    assert "No declaration" in found["BA-01"][0]["explanation"]


# --- TC-25: obligations ---


def _emi_case(client, analyst, root: Path, *, declared: list[dict], sanction: dict | None = None) -> str:
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "bank_statement", {
        "bank": "Lotuscrest Bank", "account_number_masked": "XXXX1234",
        "period_from": "2025-04-01", "period_to": "2026-03-31",
        "transactions": [{"date": f"{p}-05", "narration": "NACH DR ASHWOOD FINSERV", "debit": 145_000}
                         for p in FY26[:6]],
    })
    add_doc(root, case_id, "existing_facilities_declaration", {
        "declaration_date": "2026-09-10", "nil_declared": not declared, "facilities": declared,
    })
    if sanction:
        add_doc(root, case_id, "sanction_letter_other_lender", sanction)
    return case_id


def test_tc25_an_emi_to_an_undeclared_lender_is_flagged(client, analyst, published_data_root):
    case_id = _emi_case(client, analyst, published_data_root, declared=[],
                        sanction={"lender": "Ashwood Finserv Ltd", "facility": "Term loan", "emi": 145_000})
    found = _findings(client, analyst, published_data_root, case_id)
    [ob2] = found["OB-02"]
    assert ob2["outcome"] == "fail" and ob2["blocking"]
    assert "ASHWOOD FINSERV" in ob2["explanation"] and "6 months" in ob2["explanation"]
    [ob1] = found["OB-01"]
    assert ob1["outcome"] == "fail"
    assert "is not in Declaration of existing facilities" in ob1["explanation"]


def test_tc25_emis_to_declared_lenders_pass(client, analyst, published_data_root):
    case_id = _emi_case(client, analyst, published_data_root,
                        declared=[{"lender": "Ashwood Finserv Limited", "facility": "Term loan", "emi": 145_000}],
                        sanction={"lender": "ASHWOOD FINSERV LTD", "facility": "Term loan"})
    found = _findings(client, analyst, published_data_root, case_id)
    assert [f["outcome"] for f in found["OB-02"]] == ["pass"]
    assert [f["outcome"] for f in found["OB-01"]] == ["pass"]


# --- F-19.4, F-19.5, F-19.6, F-17.4 ---


def test_a_finding_that_relies_on_a_correction_says_so(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "bureau_commercial", {"pan": "AAACK1234F"}, corrected={"pan": "AAACK5555Z"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-01"]
    corrected = next(s for s in f["sides"] if s["value"] == "AAACK5555Z")
    assert corrected["relies_on_manual"] is True


def test_a_failure_with_a_query_feeds_the_query_list_until_waived(client, analyst, published_data_root):
    case_id = _emi_case(client, analyst, published_data_root, declared=[])
    _refresh(published_data_root, case_id)
    queries = client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
    asks = [q for q in queries if not q["resolved"] and "ASHWOOD FINSERV" in q["text"]]
    assert asks and asks[0]["group"] == "clarifications"

    review = client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
    item = next(i for i in review if i["kind"] == "finding" and "OB-02" in i["summary"])
    decided = client.post(f"/api/review/{item['id']}/decision",
                          json={"decision": "waive", "reason": "Instalments are for a lease, not a loan"},
                          headers=analyst)
    assert decided.status_code == 200, decided.text
    queries = client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
    assert not [q for q in queries if not q["resolved"] and "ASHWOOD FINSERV" in q["text"]]
    # The finding stays, with its decision on record.
    assert _findings(client, analyst, published_data_root, case_id)["OB-02"][0]["outcome"] == "fail"


def test_changing_one_tolerance_changes_exactly_its_findings(client, analyst, published_data_root, monkeypatch):
    case_id = _case(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=FY26, gst_each=4_000_000, bank_each=3_200_000,
              audited=40_000_000)
    add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "bureau_commercial", {"pan": "AAACK9876Q"})
    before = {f["id"]: f for fs in _findings(client, analyst, published_data_root, case_id).values() for f in fs}

    authored = writer.load_authored_sections()
    tolerances = authored["tolerances"].model_copy(deep=True)
    next(t for t in tolerances.tolerances if t.key == "turnover_variance").value = 25
    monkeypatch.setattr(writer, "load_authored_sections", lambda: {**authored, "tolerances": tolerances})
    writer.publish(data_root=published_data_root, author="test", note="turnover tolerance 25%")

    after = {f["id"]: f for fs in _findings(client, analyst, published_data_root, case_id).values() for f in fs}
    changed = {fid for fid in before if (before[fid]["outcome"], before[fid]["tolerance"])
               != (after[fid]["outcome"], after[fid]["tolerance"])}
    rules = {before[fid]["rule_id"] for fid in changed}
    assert rules and rules <= {"TO-01", "TO-02", "TO-03"}
    assert after[next(fid for fid in after if after[fid]["rule_id"] == "TO-02")]["outcome"] == "pass"
    assert [f["outcome"] for f in after.values() if f["rule_id"] == "ID-01"] == ["fail"]


def test_the_cross_verification_stage_waits_for_decisions(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "bureau_commercial", {"pan": "AAACK9876Q"})
    _refresh(published_data_root, case_id)
    progress = client.get(f"/api/cases/{case_id}/progress", headers=analyst).json()
    cross = next(s for s in progress["stages"] if s["key"] == "cross_verification")
    assert cross["status"] == "needs_attention" and cross["attention"] >= 1
