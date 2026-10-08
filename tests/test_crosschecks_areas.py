"""Cross-checks across the nine document types (docs/cross-verification-plan.md): the
identity, borrowing-authority, turnover-window, tax, statement, account and obligation
rules; values waiting for review (F-17.2) and documents not on file (F-19.3). Every
name is fictional."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]
SEP25_AUG26 = months((2025, 9), 12)


def _findings(client: TestClient, headers: dict, root: Path, case_id: str) -> dict[str, list[dict]]:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()
    response = client.get(f"/api/cases/{case_id}/findings", headers=headers)
    assert response.status_code == 200, response.text
    out: dict[str, list[dict]] = {}
    for f in response.json():
        out.setdefault(f["rule_id"], []).append(f)
    return out


def _outcomes(found: dict[str, list[dict]], rule: str) -> list[str]:
    return [f["outcome"] for f in found[rule]]


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _case(client: TestClient, analyst: dict, root: Path, **overrides) -> str:
    return make_case(client, analyst, root, **{"borrower": "Kestrel Tools Pvt Ltd", **overrides})


def _period(ym: str) -> str:
    return f"{MONTH_NAMES[int(ym[5:]) - 1]} {ym[:4]}"


# --- Identity ---


def test_the_pan_within_a_gstin_is_compared_with_the_entity_pan(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F"})
    gst = gstr(published_data_root, case_id, "April 2025", 1_000_000, gstin="27AAACX9999Q1Z3")
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-01"]
    assert f["outcome"] == "fail"
    odd = next(s for s in f["sides"] if s["differs"])
    assert odd["value"] == "AAACX9999Q" and odd["evidence"][0]["document_id"] == gst
    assert "(PAN within the GSTIN)" in odd["label"]
    # The PAN card and the return agree: theirs is the majority value, not highlighted.
    assert not next(s for s in f["sides"] if s["value"] == "AAACK1234F")["differs"]


def test_a_banks_truncated_account_name_is_the_same_legal_name(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"company_name": "Kestrel Tools Private Limited"})
    bank(published_data_root, case_id, [], holder="KESTREL TOOLS P")
    assert _outcomes(_findings(client, analyst, published_data_root, case_id), "ID-03") == ["pass"]


def test_a_cin_mismatch_is_flagged_and_a_missing_source_is_named(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"cin": "U28990MH2015PTC123456"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-05"]
    assert f["outcome"] == "incomplete"
    assert f["missing"] == ["Memorandum and articles of association"]
    assert f["explanation"] == "Memorandum and articles of association not on file."

    add_doc(published_data_root, case_id, "memorandum_articles_of_association", {"cin": "U28990MH2015PTC123465"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-05"]
    assert f["outcome"] == "fail" and f["blocking"] and f["severity"] == "serious"
    assert "U28990MH2015PTC123465" in f["explanation"] and f["query"]


def test_director_identifiers_disagreeing_are_flagged_by_person(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "memorandum_articles_of_association",
            {"directors": [{"name": "Tarun Velankar", "din": "01234567"}, {"name": "Ishita Barve", "din": "07654321"}]})
    add_doc(published_data_root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "din": "01234567", "pan": "ABCPV1234K"})
    add_doc(published_data_root, case_id, "director_kyc", {"person_name": "Ishita Barve", "din": "07654300", "pan": "AAACK1234F"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-06"]
    assert f["outcome"] == "fail"
    assert "DIN 07654300 on the KYC against 07654321 in the memorandum" in f["explanation"]
    assert "PAN AAACK1234F is not an individual's PAN" in f["explanation"]
    rows = {r["label"]: r for r in f["detail"]["rows"]}
    assert rows["Ishita Barve"]["flagged"] and not rows["Tarun Velankar"]["flagged"]
    assert f["detail"]["columns"] == ["DIN in the memorandum", "DIN on the KYC", "PAN on the KYC"]


def test_the_cin_is_held_against_the_incorporation_date_and_constitution(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation",
            {"cin": "U28990MH2015PTC123456", "date_of_incorporation": "2016-05-01"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-07"]
    assert f["outcome"] == "fail"
    rows = {r["label"]: r for r in f["detail"]["rows"]}
    assert rows["Year of incorporation"]["cells"] == ["2015", "2016"] and rows["Year of incorporation"]["flagged"]
    assert not rows["Company class"]["flagged"]


def test_a_director_in_the_memorandum_without_kyc_is_asked_about(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "memorandum_articles_of_association",
            {"directors": [{"name": "Tarun Velankar"}, {"name": "Leela Varghese"}]})
    add_doc(published_data_root, case_id, "director_kyc", {"person_name": "Tarun Velankar"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-08"]
    assert f["outcome"] == "fail" and f["severity"] == "mild" and not f["blocking"]
    assert f["explanation"].startswith("Leela Varghese named as director(s) in the memorandum")


# --- Borrowing authority ---


def test_a_resolution_below_the_amount_requested_blocks(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root, amount_inr=65_000_000)
    add_doc(published_data_root, case_id, "board_resolution_borrowing", {"borrowing_limit": 20_000_000})
    [f] = _findings(client, analyst, published_data_root, case_id)["BR-01"]
    assert f["outcome"] == "fail" and f["blocking"] and f["area"] == "authority"
    assert f["explanation"] == ("The board resolution authorises borrowing up to INR 2.00 cr; "
                                "the amount requested is INR 6.50 cr.")
    assert [s["differs"] for s in f["sides"]] == [True, False]


def test_a_resolution_covering_the_request_passes(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root, amount_inr=65_000_000)
    add_doc(published_data_root, case_id, "board_resolution_borrowing", {"borrowing_limit": 100_000_000})
    assert _outcomes(_findings(client, analyst, published_data_root, case_id), "BR-01") == ["pass"]


def test_a_signatory_who_is_not_a_director_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "board_resolution_borrowing",
            {"authorized_signatories": ["Tarun Velankar", "Rohan Mistry"]})
    add_doc(published_data_root, case_id, "director_kyc", {"person_name": "Tarun Velankar"})
    [f] = _findings(client, analyst, published_data_root, case_id)["BR-02"]
    assert f["outcome"] == "fail" and "Rohan Mistry is authorised to sign" in f["explanation"]
    assert {r["label"]: r["flagged"] for r in f["detail"]["rows"]} == {"Tarun Velankar": False, "Rohan Mistry": True}


@pytest.mark.parametrize("lender,outcome", [("Lotuscrest Bank Limited", "fail"), ("RBL Bank Ltd", "pass")])
def test_the_resolution_names_this_bank(client, analyst, published_data_root, lender, outcome):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "board_resolution_borrowing", {"lender_name": lender})
    assert _outcomes(_findings(client, analyst, published_data_root, case_id), "BR-03") == [outcome]


def test_a_resolution_dated_before_incorporation_or_after_the_appraisal_date_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2015-06-01"})
    add_doc(published_data_root, case_id, "board_resolution_borrowing", {"resolution_date": "2014-01-10"})
    [f] = _findings(client, analyst, published_data_root, case_id)["BR-04"]
    assert f["outcome"] == "fail" and "before the company was incorporated on 1 Jun 2015" in f["explanation"]

    late = _case(client, analyst, published_data_root, borrower="Orchid Castings Pvt Ltd")
    add_doc(published_data_root, late, "board_resolution_borrowing", {"resolution_date": "2026-12-01"})
    [f] = _findings(client, analyst, published_data_root, late)["BR-04"]
    assert f["outcome"] == "fail" and "after the appraisal date of 29 Sep 2026" in f["explanation"]


# --- Turnover over the months both sources cover ---


def test_gst_and_bank_are_compared_over_the_months_both_cover(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    for ym in SEP25_AUG26:
        gstr(published_data_root, case_id, _period(ym), 4_000_000)
    bank(published_data_root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR ORCHID TRADERS", "credit": 2_800_000}
                                         for ym in SEP25_AUG26], start="2025-09-01", end="2026-08-31")
    found = _findings(client, analyst, published_data_root, case_id)
    # The financial-year comparison only sees part of a year.
    assert set(_outcomes(found, "TO-02")) == {"incomplete"}
    [f] = found["TO-05"]
    assert f["outcome"] == "fail" and f["area"] == "turnover" and f["scope"] == "Sep 2025 to Aug 2026"
    assert [s["value"] for s in f["sides"]] == [48_000_000, 33_600_000] and all(s["differs"] for s in f["sides"])
    assert "30.0%" in f["explanation"] and f["tolerance"] == "10%"
    assert len(f["detail"]["rows"]) == 12 and all(r["flagged"] for r in f["detail"]["rows"])


def test_too_few_shared_months_leave_the_window_incomplete(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    for ym in months((2025, 4), 6):
        gstr(published_data_root, case_id, _period(ym), 4_000_000)
    bank(published_data_root, case_id, [{"date": "2025-09-15", "description": "NEFT CR ORCHID TRADERS", "credit": 4_000_000}],
         start="2025-09-01", end="2026-08-31")
    [f] = _findings(client, analyst, published_data_root, case_id)["TO-05"]
    assert f["outcome"] == "incomplete" and "share 1 month(s)" in f["explanation"]


# --- Tax ---


def test_an_audited_year_whose_return_is_due_but_absent_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2024-03-31")
    audited(published_data_root, case_id, "2025-03-31")
    audited(published_data_root, case_id, "2026-03-31")
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F", "assessment_year": "2025-26"})
    [f] = _findings(client, analyst, published_data_root, case_id)["TX-01"]
    assert f["outcome"] == "fail" and "FY 2023-24" in f["explanation"]
    rows = {r["label"]: r for r in f["detail"]["rows"]}
    # FY 2025-26's return is due on 31 Oct 2026, after the appraisal date.
    assert rows["FY 2025-26"]["cells"][0].startswith("Not yet due") and not rows["FY 2025-26"]["flagged"]
    assert rows["FY 2024-25"]["cells"] == ["✓"] and rows["FY 2023-24"]["flagged"]


def test_book_profit_against_the_return(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2025-03-31")  # profit before tax 75 lakh
    add_doc(published_data_root, case_id, "income_tax_return", {
        "pan": "AAACK1234F", "assessment_year": "2025-26",
        "income_computation": [{"particulars": "Profit as per profit and loss account", "amount": 6_000_000},
                               {"particulars": "Total income", "amount": 8_600_000}],
    })
    [f] = _findings(client, analyst, published_data_root, case_id)["TX-02"]
    assert f["outcome"] == "fail" and f["scope"] == "FY 2024-25"
    assert [s["value"] for s in f["sides"]] == [7_500_000, 6_000_000]
    assert "20.0%" in f["explanation"]


# --- Statements against each other and the bank ---


@pytest.mark.parametrize("scale,outcome", [(0.85, "pass"), (0.70, "fail")])
def test_previous_year_figures_against_that_years_statements(client, analyst, published_data_root, scale, outcome):
    case_id = _case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2026-03-31")  # its previous-year column is 0.85 of this year
    audited(published_data_root, case_id, "2025-03-31", scale=scale)
    [f] = _findings(client, analyst, published_data_root, case_id)["FS-01"]
    assert f["outcome"] == outcome and f["scope"] == "FY 2025-26"
    assert f["detail"]["columns"] == ["FY 2024-25 as shown in FY 2025-26", "FY 2024-25 statements", "Difference"]
    assert any(r["flagged"] for r in f["detail"]["rows"]) == (outcome == "fail")


def test_year_end_bank_balances_above_the_audited_figure_are_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2026-03-31")  # cash and bank balances 60 lakh
    bank(published_data_root, case_id, [
        {"date": "2026-03-20", "description": "NEFT CR ORCHID TRADERS", "credit": 1_000_000, "balance": 9_500_000},
        {"date": "2026-04-10", "description": "NEFT CR ORCHID TRADERS", "credit": 1_000_000, "balance": 10_500_000},
    ], start="2025-09-01", end="2026-08-31")
    [f] = _findings(client, analyst, published_data_root, case_id)["FS-02"]
    assert f["outcome"] == "fail" and f["sides"][0]["value"] == 9_500_000
    assert "INR 95.00 lakh" in f["explanation"] and "INR 60.00 lakh" in f["explanation"]


# --- Bank accounts ---


def test_a_declared_account_without_a_statement_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root, header={
        "existing_banking": {"value": "Current account with Lotuscrest Bank a/c 90100005678", "source": "person"}})
    bank(published_data_root, case_id, [], last4="1234")
    [f] = _findings(client, analyst, published_data_root, case_id)["BA-01"]
    assert f["outcome"] == "fail" and "·5678" in f["explanation"] and f["area"] == "accounts"


def test_an_account_seen_in_transfers_without_a_statement_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    bank(published_data_root, case_id, [{"date": "2025-05-02", "description": "NEFT TRANSFER TO A/C 778899001122", "debit": 500_000}])
    [f] = _findings(client, analyst, published_data_root, case_id)["BA-02"]
    assert f["outcome"] == "fail" and "·1122" in f["explanation"]


def test_a_statement_for_an_account_nobody_declared_is_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root, header={
        "existing_banking": {"value": "Current account with Lotuscrest Bank a/c 90100001234", "source": "person"}})
    bank(published_data_root, case_id, [], last4="1234")
    bank(published_data_root, case_id, [], last4="7777", bank_name="Ironleaf Bank")
    [f] = _findings(client, analyst, published_data_root, case_id)["BA-02"]
    assert f["outcome"] == "fail"
    assert f["explanation"] == "Ironleaf Bank ·7777 has a statement but was not declared."
    assert "Ironleaf Bank ·7777" in f["query"]
    rows = {r["label"]: r for r in f["detail"]["rows"]}
    assert rows["Ironleaf Bank ·7777"]["flagged"] and rows["Ironleaf Bank ·7777"]["cells"][:2] == ["—", "✓"]
    assert not rows["Lotuscrest Bank ·1234"]["flagged"]


def test_with_nothing_declared_statement_accounts_are_not_called_undeclared(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    bank(published_data_root, case_id, [], last4="1234")
    bank(published_data_root, case_id, [], last4="7777", bank_name="Ironleaf Bank")
    [f] = _findings(client, analyst, published_data_root, case_id)["BA-02"]
    assert f["outcome"] == "pass" and "none was declared" in f["explanation"]


# --- Obligations ---


def _emis(root: Path, case_id: str) -> None:
    bank(root, case_id, [{"date": f"{ym}-05", "description": "NACH DR ASHWOOD FINSERV", "debit": 145_000}
                         for ym in months((2025, 4), 6)])


@pytest.mark.parametrize("declared,outcome", [
    ("Cash credit with Lotuscrest Bank", "fail"),
    ("Term loan from Ashwood Finserv Ltd, EMI 1.45 lakh", "pass"),
    (None, "incomplete"),
])
def test_instalments_go_to_declared_lenders(client, analyst, published_data_root, declared, outcome):
    header = {"existing_banking": {"value": declared, "source": "person"}} if declared else {}
    case_id = _case(client, analyst, published_data_root, header=header)
    _emis(published_data_root, case_id)
    [f] = _findings(client, analyst, published_data_root, case_id)["OB-02"]
    assert f["outcome"] == outcome
    if outcome == "fail":
        assert "ASHWOOD FINSERV" in f["explanation"] and "ASHWOOD FINSERV" in f["query"]
        assert f["detail"]["rows"][0]["flagged"]


def test_instalments_with_no_borrowings_in_the_books_are_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2026-03-31", set_rows={"(a) Long-term borrowings": 0})
    _emis(published_data_root, case_id)
    [f] = _findings(client, analyst, published_data_root, case_id)["OB-03"]
    assert f["outcome"] == "fail" and "shows no long-term borrowings" in f["explanation"]


def test_borrowings_with_no_instalments_are_flagged(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2026-03-31")  # long-term borrowings 1.5 cr
    bank(published_data_root, case_id, [{"date": "2025-05-02", "description": "NEFT CR ORCHID TRADERS", "credit": 500_000}])
    [f] = _findings(client, analyst, published_data_root, case_id)["OB-03"]
    assert f["outcome"] == "fail" and "no instalments appear" in f["explanation"]


# --- Values waiting for review (F-17.2) and documents not on file (F-19.3) ---


def test_a_check_waits_for_a_value_under_review(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    doc = add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"}, pending={"pan"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK9876Q"})
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-01"]
    assert f["outcome"] == "incomplete" and f["explanation"].startswith("Waiting for review of Company PAN")
    assert next(s for s in f["sides"] if s["value"] == "AAACK1234F")["awaiting_review"]
    # Not raised to the review queue as a finding while it waits.
    review = client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
    assert not [i for i in review if i["kind"] == "finding"]

    conn = db.connect(published_data_root)
    try:
        conn.execute("UPDATE field_values SET status = 'accepted' WHERE document_id = ?", (doc,))
    finally:
        conn.close()
    [f] = _findings(client, analyst, published_data_root, case_id)["ID-01"]
    assert f["outcome"] == "fail"


def test_missing_documents_are_named_rather_than_not_applicable(client, analyst, published_data_root):
    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    found = _findings(client, analyst, published_data_root, case_id)
    [f] = found["ID-01"]
    assert f["outcome"] == "incomplete" and set(f["missing"]) == {"Income tax return", "GSTR-3B"}
    # A rule with nothing to apply to says so.
    assert _outcomes(found, "TO-04") == ["not_applicable"]
    # Every finding carries its area.
    assert {f["area"] for fs in found.values() for f in fs} == {
        "identity", "authority", "turnover", "tax", "financials", "accounts", "obligations"}
