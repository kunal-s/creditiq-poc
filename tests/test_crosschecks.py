"""Cross-checks (FRD F-19): TC-22 identity, TC-23 turnover; manual reliance
(F-19.4), the query list (F-19.5), tolerance changes (F-19.6) and decisions on
findings (F-17.4). The rules are those the nine configured document types can
evaluate: bank-account and obligation rules return with a type that declares them."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from engine.configstore import writer
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

FY26 = months((2025, 4), 12)
MONTH_NAMES = ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"]
PERIODS = [f"{m} {2025 if i < 9 else 2026}" for i, m in enumerate(MONTH_NAMES)]  # FY 2025-26


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
    pan_doc = add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F", "company_name": "Kestrel Tools Pvt Ltd"})
    itr = add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK9876Q", "taxpayer_name": "Kestrel Tools Pvt Ltd"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-01"]
    assert f["outcome"] == "fail" and f["severity"] == "serious" and f["blocking"]
    values = {s["value"]: s for s in f["sides"]}
    assert values["AAACK1234F"]["evidence"][0]["document_id"] == pan_doc
    assert values["AAACK9876Q"]["evidence"][0]["document_id"] == itr
    assert "AAACK9876Q" in f["explanation"] and "AAACK1234F" in f["explanation"]


def test_tc22_a_directors_pan_is_not_the_entitys(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "pan": "ABCPV1234K"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F"})
    assert [f["outcome"] for f in _findings(client, analyst, published_data_root, case_id)["ID-01"]] == ["pass"]


def test_tc22_consistent_identities_pass(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F", "company_name": "Kestrel Tools Pvt Ltd"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F", "taxpayer_name": "KESTREL TOOLS PRIVATE LIMITED"})
    add_doc(published_data_root, case_id, "gstr_3b", {"gstin": "27AAACK1234F1Z0", "legal_name": "Kestrel Tools Private Limited"})
    found = _findings(client, analyst, published_data_root, case_id)
    assert [f["outcome"] for f in found["ID-01"]] == ["pass"]
    # Name variants of one company are one legal name (F-18.3).
    assert [f["outcome"] for f in found["ID-03"]] == ["pass"]
    # One GSTIN in every return: there is nothing to compare it with.
    assert [f["outcome"] for f in found["ID-02"]] == ["not_applicable"]


def test_tc22_two_gstins_across_returns_are_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "gstr_3b", {"gstin": "27AAACK1234F1Z0", "tax_period": "April 2025"})
    add_doc(published_data_root, case_id, "gstr_3b", {"gstin": "29AAACK1234F1Z5", "tax_period": "May 2025"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-02"]
    assert f["outcome"] == "fail" and {s["value"] for s in f["sides"]} == {"27AAACK1234F1Z0", "29AAACK1234F1Z5"}


def test_tc22_a_promoter_missing_from_one_source_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "board_resolution_borrowing", {"authorized_persons": ["Tarun Velankar", "Leela Varghese"]})
    add_doc(published_data_root, case_id, "memorandum_articles_of_association", {"directors": [{"name": "Tarun Velankar"}]})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-04"]
    assert f["outcome"] == "fail"
    assert "Leela Varghese is not in Memorandum and articles of association" in f["explanation"]


def test_tc22_the_kyc_received_is_a_source_of_the_promoter_set(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "board_resolution_borrowing", {"authorized_persons": ["Tarun Velankar", "Ishita Barve"]})
    add_doc(published_data_root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "din": "01234567"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-04"]
    assert f["outcome"] == "fail" and "Ishita Barve is not in KYC received" in f["explanation"]


# --- TC-23: turnover ---


def _turnover(root: Path, case_id: str, *, gst_months: list[str], gst_each: float, bank_each: float, audited_revenue: float | None = None) -> None:
    if audited_revenue is not None:
        audited(root, case_id, "2026-03-31", scale=audited_revenue / 118_000_000)
    for p in gst_months:
        gstr(root, case_id, p, gst_each)
    bank(root, case_id, [{"date": f"{p}-15", "description": "NEFT CR ORCHID TRADERS", "credit": bank_each} for p in FY26])


def test_tc23_gst_against_bank_beyond_tolerance_is_flagged_with_values(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=PERIODS, gst_each=4_000_000, bank_each=3_200_000)
    [f] = _findings(client, analyst, published_data_root, case_id)["TO-02"]
    assert f["outcome"] == "fail" and f["tolerance"] == "10%"
    assert [s["value"] for s in f["sides"]] == [48_000_000, 38_400_000]
    assert "20.0%" in f["explanation"] and "FY 2025-26" in f["title"]
    assert all(s["evidence"] for s in f["sides"])


def test_tc23_within_tolerance_passes(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=PERIODS, gst_each=4_000_000, bank_each=3_800_000)
    assert [f["outcome"] for f in _findings(client, analyst, published_data_root, case_id)["TO-02"]] == ["pass"]


def test_tc23_incomplete_coverage_is_stated(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=PERIODS[4:], gst_each=4_000_000, bank_each=3_000_000, audited_revenue=48_000_000)
    found = _findings(client, analyst, published_data_root, case_id)
    [to1] = found["TO-01"]
    assert to1["outcome"] == "incomplete"
    assert "GST outward supplies covers 8 of 12 months (Apr 2025, May 2025, Jun 2025… absent)" in to1["explanation"]
    [to3] = found["TO-03"]
    assert to3["outcome"] == "fail"  # 4.8 cr audited against 3.6 cr banked, 25%


def test_tc23_audited_turnover_is_read_from_the_printed_statement(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=PERIODS, gst_each=10_000_000, bank_each=9_800_000, audited_revenue=118_000_000)
    found = _findings(client, analyst, published_data_root, case_id)
    assert [f["outcome"] for f in found["TO-01"]] == ["pass"] and [f["outcome"] for f in found["TO-03"]] == ["pass"]  # 11.8 cr, 12 cr, 11.76 cr
    assert [s["value"] for s in found["TO-01"][0]["sides"]] == [118_000_000, 120_000_000]


# --- F-19.4, F-19.5, F-19.6, F-17.4 ---


def test_a_finding_that_relies_on_a_correction_says_so(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F"}, corrected={"pan": "AAACK5555Z"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-01"]
    corrected = next(s for s in f["sides"] if s["value"] == "AAACK5555Z")
    assert corrected["relies_on_manual"] is True


def _pan_mismatch(client, analyst, root: Path) -> str:
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(root, case_id, "income_tax_return", {"pan": "AAACK9876Q"})
    return case_id


def test_a_failure_with_a_query_feeds_the_query_list_until_waived(client, analyst, published_data_root):
    case_id = _pan_mismatch(client, analyst, published_data_root)
    _refresh(published_data_root, case_id)
    queries = client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
    asks = [q for q in queries if not q["resolved"] and "AAACK9876Q" in q["text"]]
    assert asks and asks[0]["group"] == "clarifications"

    review = client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
    item = next(i for i in review if i["kind"] == "finding" and "ID-01" in i["summary"])
    decided = client.post(f"/api/review/{item['id']}/decision", json={"decision": "waive", "reason": "The second PAN is a typing error in the return"},
                          headers=analyst)
    assert decided.status_code == 200, decided.text
    queries = client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
    assert not [q for q in queries if not q["resolved"] and "AAACK9876Q" in q["text"]]
    # The finding stays, with its decision on record.
    assert _findings(client, analyst, published_data_root, case_id)["ID-01"][0]["outcome"] == "fail"


def test_changing_one_tolerance_changes_exactly_its_findings(client, analyst, published_data_root, monkeypatch):
    case_id = _pan_mismatch(client, analyst, published_data_root)
    _turnover(published_data_root, case_id, gst_months=PERIODS, gst_each=4_000_000, bank_each=3_200_000, audited_revenue=40_000_000)
    before = {f["id"]: f for fs in _findings(client, analyst, published_data_root, case_id).values() for f in fs}

    authored = writer.load_authored_sections()
    tolerances = authored["tolerances"].model_copy(deep=True)
    next(t for t in tolerances.tolerances if t.key == "turnover_variance").value = 25
    monkeypatch.setattr(writer, "load_authored_sections", lambda: {**authored, "tolerances": tolerances})
    writer.publish(data_root=published_data_root, author="test", note="turnover tolerance 25%")

    after = {f["id"]: f for fs in _findings(client, analyst, published_data_root, case_id).values() for f in fs}
    changed = {fid for fid in before if (before[fid]["outcome"], before[fid]["tolerance"]) != (after[fid]["outcome"], after[fid]["tolerance"])}
    rules = {before[fid]["rule_id"] for fid in changed}
    assert rules and rules <= {"TO-01", "TO-02", "TO-03"}
    assert after[next(fid for fid in after if after[fid]["rule_id"] == "TO-02")]["outcome"] == "pass"
    assert [f["outcome"] for f in after.values() if f["rule_id"] == "ID-01"] == ["fail"]


def test_the_cross_verification_stage_waits_for_decisions(client, analyst, published_data_root):
    case_id = _pan_mismatch(client, analyst, published_data_root)
    _refresh(published_data_root, case_id)
    progress = client.get(f"/api/cases/{case_id}/progress", headers=analyst).json()
    cross = next(s for s in progress["stages"] if s["key"] == "cross_verification")
    assert cross["status"] == "needs_attention" and cross["attention"] >= 1


def test_declared_turnover_check_does_not_apply_without_a_declaration(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2026-03-31", scale=50_000_000 / 118_000_000)
    assert [f["outcome"] for f in _findings(client, analyst, published_data_root, case_id)["TO-04"]] == ["not_applicable"]
