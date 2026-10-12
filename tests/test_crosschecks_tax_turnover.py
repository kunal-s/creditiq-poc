"""The turnover in the income tax return against the other turnover sources (TX-03 to TX-05), and
the income-tax rules running again in the turnover area (TX-01, TX-02). Every name is fictional."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]
FY26 = months((2025, 4), 12)  # April 2025 to March 2026


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _case(client: TestClient, analyst: dict, root: Path) -> str:
    return make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd")


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


def _itr(root: Path, case_id: str, assessment_year: str, turnover: int | None, profit: int | None = None) -> str:
    """An income tax return whose computation shows the turnover (and the book profit) when given."""
    rows = []
    if turnover is not None:
        rows.append({"particulars": "Revenue from operations", "amount": turnover})
    if profit is not None:
        rows.append({"particulars": "Profit as per profit and loss account", "amount": profit})
    rows.append({"particulars": "Total income", "amount": 8_600_000})
    return add_doc(root, case_id, "income_tax_return", {
        "pan": "AAACK1234F", "assessment_year": assessment_year, "income_computation": rows,
    })


def _gst_year(root: Path, case_id: str, monthly: int, count: int = 12) -> None:
    for ym in FY26[:count]:
        gstr(root, case_id, f"{MONTH_NAMES[int(ym[5:]) - 1]} {ym[:4]}", monthly)


def _bank_year(root: Path, case_id: str, monthly: int) -> None:
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": monthly}
                         for ym in FY26], start="2025-04-01", end="2026-03-31")


def _audited_revenue(client: TestClient, headers: dict, case_id: str, fy: str) -> float:
    facts = client.get(f"/api/cases/{case_id}/facts", headers=headers).json()
    year = next(y for y in facts["turnover"] if y["fy"] == fy)
    return next(f["value"] for f in year["figures"] if f["source"] == "financials")


@pytest.mark.parametrize("ratio,outcome", [(0.995, "pass"), (0.80, "fail")])
def test_turnover_in_the_return_against_the_audited_revenue(client, analyst, published_data_root, ratio, outcome):
    root = published_data_root
    case_id = _case(client, analyst, root)
    audited(root, case_id, "2026-03-31")
    _refresh(root, case_id)
    revenue = _audited_revenue(client, analyst, case_id, "FY 2025-26")
    _itr(root, case_id, "2026-27", round(revenue * ratio))
    [f] = _findings(client, analyst, root, case_id)["TX-03"]
    assert (f["outcome"], f["scope"], f["area"]) == (outcome, "FY 2025-26", "turnover")
    assert [s["label"] for s in f["sides"]] == ["Turnover in the income tax return", "Audited financial statements"]
    assert [s["value"] for s in f["sides"]] == [round(revenue * ratio), revenue]
    if outcome == "fail":
        assert "a variance of 20.0% (tolerance 1%)" in f["explanation"]
        assert f["query"].startswith("Please explain the difference between the turnover in the income tax return")
    else:
        assert f["explanation"] == "Variance 0.5% within 1%."


@pytest.mark.parametrize("filed,outcome,variance", [(11_940_000, "pass", "0.5%"), (9_000_000, "fail", "25.0%")])
def test_turnover_in_the_return_against_a_full_year_of_gst(client, analyst, published_data_root, filed, outcome,
                                                           variance):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _gst_year(root, case_id, 1_000_000)  # INR 12.00 cr over the year
    _itr(root, case_id, "2026-27", filed)
    [f] = _findings(client, analyst, root, case_id)["TX-04"]
    assert (f["outcome"], f["scope"]) == (outcome, "FY 2025-26")
    assert [s["value"] for s in f["sides"]] == [filed, 12_000_000]
    assert variance in f["explanation"]


def test_a_part_year_of_gst_leaves_the_comparison_incomplete(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _gst_year(root, case_id, 1_000_000, count=8)  # April to November 2025
    _itr(root, case_id, "2026-27", 12_000_000)
    [f] = _findings(client, analyst, root, case_id)["TX-04"]
    assert f["outcome"] == "incomplete"
    assert f["explanation"] == "GST outward supplies covers 8 of 12 months (Dec 2025, Jan 2026, Feb 2026… absent)."


@pytest.mark.parametrize("filed,outcome", [(11_940_000, "pass"), (15_000_000, "fail")])
def test_turnover_in_the_return_against_bank_credits(client, analyst, published_data_root, filed, outcome):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _bank_year(root, case_id, 1_000_000)  # INR 12.00 cr of business credits
    _itr(root, case_id, "2026-27", filed)
    [f] = _findings(client, analyst, root, case_id)["TX-05"]
    assert (f["outcome"], f["scope"]) == (outcome, "FY 2025-26")
    assert [s["value"] for s in f["sides"]] == [filed, 12_000_000]


def test_a_return_that_shows_no_turnover_leaves_nothing_to_compare(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    audited(root, case_id, "2026-03-31")
    _gst_year(root, case_id, 1_000_000)
    _itr(root, case_id, "2026-27", None, profit=7_500_000)
    found = _findings(client, analyst, root, case_id)
    for rule in ("TX-03", "TX-04", "TX-05"):
        [f] = found[rule]
        assert f["outcome"] == "not_applicable", rule
        assert f["explanation"] == "The income tax return on file does not show its turnover."


def test_a_source_that_does_not_reach_the_returns_year_leaves_nothing_to_compare(client, analyst,
                                                                                 published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _gst_year(root, case_id, 1_000_000)  # FY 2025-26
    _itr(root, case_id, "2025-26", 11_000_000)  # FY 2024-25
    [f] = _findings(client, analyst, root, case_id)["TX-04"]
    assert (f["outcome"], f["scope"]) == ("not_applicable", "FY 2024-25")
    assert f["explanation"] == ("GST outward supplies for FY 2024-25, the year the income tax return covers, "
                                "is not on file.")


def test_without_a_return_the_check_names_it(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    audited(root, case_id, "2026-03-31")
    [f] = _findings(client, analyst, root, case_id)["TX-03"]
    assert f["outcome"] == "incomplete"
    assert "Income tax return" in f["missing"]


def test_each_year_with_a_return_is_compared_on_its_own(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    audited(root, case_id, "2026-03-31")
    audited(root, case_id, "2025-03-31")
    _refresh(root, case_id)
    revenue26 = _audited_revenue(client, analyst, case_id, "FY 2025-26")
    revenue25 = _audited_revenue(client, analyst, case_id, "FY 2024-25")
    _itr(root, case_id, "2026-27", round(revenue26))
    _itr(root, case_id, "2025-26", round(revenue25 * 0.5))
    found = {f["scope"]: f["outcome"] for f in _findings(client, analyst, root, case_id)["TX-03"]}
    assert found == {"FY 2025-26": "pass", "FY 2024-25": "fail"}


def test_the_card_puts_the_return_beside_the_other_source(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _gst_year(root, case_id, 1_000_000)
    _itr(root, case_id, "2026-27", 9_000_000)
    _refresh(root, case_id)
    board = client.get(f"/api/cases/{case_id}/cross-verification", headers=analyst).json()
    item = next(i for i in board["items"] if i["finding"]["rule_id"] == "TX-04")
    f = item["finding"]
    assert f["finding_title"] == "Turnover in the tax return differs from GST returns"
    itr, gst = f["columns"]
    assert (itr["label"], itr["value"], itr["coverage"]) == ("Income tax return", 9_000_000, "AY 2026-27 · for FY 2025-26")
    assert itr["provenance"] == ["borrower_supplied"] and itr["rows"][0]["cells"] == [
        "Turnover as per the return", "AY 2026-27", 9_000_000]
    assert itr["evidence"], "the return's page"
    assert gst["label"] == "GST outward supplies (GSTR-3B)" and gst["value"] == 12_000_000
    [leg] = f["gaps"]
    assert (leg["amount"], leg["pct"], leg["breached"]) == (3_000_000, 25.0, True)
    assert f["gap_tolerance"] == "1%"
    [line] = f["highlights"]
    assert line["label"] == "Tax return against GST · FY 2025-26"
    assert [(x["label"], x["value"], x["differs"]) for x in line["facts"]] == [
        ("Tax return", 9_000_000, True), ("GST outward supplies", 12_000_000, False)]
    assert line["note"] == "25.0% apart · tolerance 1%"
    assert item["finding"]["area"] == "turnover"


def test_the_income_tax_rules_run_in_the_turnover_area(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    audited(root, case_id, "2025-03-31")  # profit before tax 75 lakh
    _itr(root, case_id, "2025-26", None, profit=6_000_000)
    found = _findings(client, analyst, root, case_id)
    [tx02] = found["TX-02"]
    assert (tx02["outcome"], tx02["area"]) == ("fail", "turnover")
    assert "TX-01" in found and found["TX-01"][0]["area"] == "turnover"
    board = client.get(f"/api/cases/{case_id}/cross-verification", headers=analyst).json()
    assert [a["area"] for a in board["areas"]] == ["identity", "turnover", "accounts", "obligations"]
    assert next(a for a in board["areas"] if a["area"] == "turnover")["rules"] == 10
    assert board["run"]["rules"] == 24
    line = next(i for i in board["items"] if i["finding"]["rule_id"] == "TX-02")["finding"]["highlights"][0]
    assert line["label"] == "Profit: audited against tax return · FY 2024-25"
    assert [x["label"] for x in line["facts"]] == ["Audited", "Tax return"]
