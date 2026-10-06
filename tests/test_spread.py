"""The spread, interim layout (FRD F-22, decision C.4-8)."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.triangulation import audited


def _spread(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/spread", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _row(spread: dict, key: str) -> dict:
    return next(r for r in spread["rows"] if r["key"] == key)


def test_years_of_audited_statements_become_columns(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id, "2025-03-31", scale=0.85)
    audited(published_data_root, case_id, "2026-03-31", page=4)
    spread = _spread(client, analyst, case_id)
    assert spread["interim"] is True
    assert [(c["fy"], c["basis"]) for c in spread["columns"]] == [("FY 2024-25", "audited"), ("FY 2025-26", "audited")]
    revenue = _row(spread, "revenue_from_operations")
    assert [c["value"] for c in revenue["cells"]] == [round(118_000_000 * 0.85), 118_000_000]
    assert revenue["cells"][1]["evidence"][0]["page"] == 4


def test_derived_lines_and_ratios_show_their_workings(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id)
    spread = _spread(client, analyst, case_id)
    nwc = _row(spread, "net_working_capital")
    assert nwc["kind"] == "derived" and nwc["cells"][0]["value"] == 22_000_000  # 5.9 cr less 3.7 cr
    assert nwc["formula"] == "Current assets - Current liabilities"
    assert len(nwc["cells"][0]["evidence"]) == 2
    current = _row(spread, "current-ratio")
    assert current["section"] == "ratios" and round(current["cells"][0]["value"], 2) == 1.59
    # DSCR needs instalments, not a statement line: not a spread ratio.
    assert not [r for r in spread["rows"] if r["key"] == "dscr"]


def test_turnover_method_within_the_limit(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    wc = _spread(client, analyst, case_id)["working_capital"]
    assert wc["method"] == "turnover" and wc["column"] == "FY 2025-26 (audited)"
    assert [s["value"] for s in wc["steps"]] == [118_000_000, 29_500_000, 5_900_000, 23_600_000]
    assert wc["eligible"] == 23_600_000


def test_mpbf_above_the_limit(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=65_000_000)
    audited(published_data_root, case_id)
    wc = _spread(client, analyst, case_id)["working_capital"]
    assert wc["method"] == "mpbf"
    # CA 5.9 cr; other CL 3.7 - 1.2 = 2.5 cr; gap 3.4 cr; margin 1.475 cr; MPBF 1.925 cr.
    assert wc["eligible"] == 19_250_000
    assert wc["steps"][1]["value"] == 25_000_000


def test_no_working_capital_facility(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["term_loan"])
    assert _spread(client, analyst, case_id)["working_capital"]["method"] == "not_applicable"


def test_the_spread_needs_the_outputs_permission(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/spread", headers=rm).status_code == 403
