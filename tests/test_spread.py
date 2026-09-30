"""The spread, interim layout (FRD F-22, decision C.4-8)."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.test_policy import FINANCIALS
from tests.triangulation import add_doc


def _spread(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/spread", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _row(spread: dict, key: str) -> dict:
    return next(r for r in spread["rows"] if r["key"] == key)


def test_years_and_kinds_of_statement_become_columns(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "audited_financial_statements",
            {"period_end": "2025-03-31", "revenue_from_operations": 250_000_000})
    add_doc(published_data_root, case_id, "audited_financial_statements", FINANCIALS, page=4)
    add_doc(published_data_root, case_id, "projected_financial_statements",
            {"period_end": "2027-03-31", "revenue_from_operations": 360_000_000})
    add_doc(published_data_root, case_id, "provisional_financial_statements",
            {"period_end": "2026-08-31", "revenue_from_operations": 140_000_000})
    spread = _spread(client, analyst, case_id)
    assert spread["interim"] is True
    assert [(c["fy"], c["basis"]) for c in spread["columns"]] == [
        ("FY 2024-25", "audited"), ("FY 2025-26", "audited"), ("FY 2026-27", "provisional"),
        ("FY 2026-27", "projected"),
    ]
    revenue = _row(spread, "revenue_from_operations")
    assert [c["value"] for c in revenue["cells"]] == [250_000_000, 300_000_000, 140_000_000, 360_000_000]
    assert revenue["cells"][1]["evidence"][0]["page"] == 4


def test_derived_lines_and_ratios_show_their_workings(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "audited_financial_statements", FINANCIALS)
    spread = _spread(client, analyst, case_id)
    nwc = _row(spread, "net_working_capital")
    assert nwc["kind"] == "derived" and nwc["cells"][0]["value"] == 30_000_000
    assert nwc["formula"] == "Current assets - Current liabilities"
    assert len(nwc["cells"][0]["evidence"]) == 2
    current = _row(spread, "current-ratio")
    assert current["section"] == "ratios" and current["cells"][0]["value"] == 1.5
    # DSCR needs instalments, not a statement line: not a spread ratio.
    assert not [r for r in spread["rows"] if r["key"] == "dscr"]


def test_turnover_method_within_the_limit(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    add_doc(published_data_root, case_id, "audited_financial_statements", FINANCIALS)
    add_doc(published_data_root, case_id, "projected_financial_statements",
            {"period_end": "2027-03-31", "revenue_from_operations": 360_000_000})
    wc = _spread(client, analyst, case_id)["working_capital"]
    assert wc["method"] == "turnover" and wc["column"] == "FY 2026-27 (projected)"
    assert [s["value"] for s in wc["steps"]] == [360_000_000, 90_000_000, 18_000_000, 72_000_000]
    assert wc["eligible"] == 72_000_000


def test_mpbf_above_the_limit(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=65_000_000)
    add_doc(published_data_root, case_id, "audited_financial_statements",
            {**FINANCIALS, "short_term_borrowings": 25_000_000})
    wc = _spread(client, analyst, case_id)["working_capital"]
    assert wc["method"] == "mpbf"
    # CA 9.0 cr; other CL 6.0 - 2.5 = 3.5 cr; gap 5.5 cr; margin 2.25 cr; MPBF 3.25 cr.
    assert wc["eligible"] == 32_500_000
    assert wc["steps"][1]["value"] == 35_000_000


def test_no_working_capital_facility(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["term_loan"])
    assert _spread(client, analyst, case_id)["working_capital"]["method"] == "not_applicable"


def test_the_spread_needs_the_outputs_permission(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/spread", headers=rm).status_code == 403
