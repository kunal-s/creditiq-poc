"""Policy norms and deviations (FRD F-20, TC-26)."""

from pathlib import Path

from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.triangulation import add_doc

FINANCIALS = {
    "period_end": "2026-03-31",
    "revenue_from_operations": 300_000_000,
    "depreciation": 4_000_000,
    "finance_costs": 6_000_000,
    "profit_before_tax": 18_000_000,
    "profit_after_tax": 13_500_000,
    "net_worth": 40_000_000,
    "long_term_borrowings": 30_000_000,
    "total_borrowings": 120_000_000,  # debt/equity 3.0x: a deviation
    "inventories": 30_000_000,
    "trade_receivables": 45_000_000,
    "trade_payables": 20_000_000,
    "current_assets": 90_000_000,
    "current_liabilities": 60_000_000,  # current ratio 1.5x: a pass
}


def _policy(client: TestClient, headers: dict, case_id: str) -> dict[str, dict]:
    response = client.get(f"/api/cases/{case_id}/policy", headers=headers)
    assert response.status_code == 200, response.text
    return {n["id"]: n for n in response.json()["norms"]}


def test_tc26_ratios_are_assessed_with_their_source_figures(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    fs = add_doc(published_data_root, case_id, "audited_financial_statements", FINANCIALS, page=4)
    norms = _policy(client, analyst, case_id)

    current = norms["FR-01"]
    assert current["outcome"] == "pass" and current["actual"] == 1.5
    assert current["required"] == "at least 1.20x"
    assert {i["name"] for i in current["inputs"]} == {"current_assets", "current_liabilities"}
    assert all(i["evidence"][0] == {"document_id": fs, "page": 4, "bbox": None} for i in current["inputs"])

    debt_equity = norms["FR-05"]
    assert debt_equity["outcome"] == "deviation" and debt_equity["actual"] == 3.0
    assert debt_equity["category"] == "financial" and debt_equity["category_label"] == "Financial norms"

    # Interest coverage: (PBT + finance costs) / finance costs = 4.0x.
    assert norms["FR-04"]["outcome"] == "pass" and norms["FR-04"]["actual"] == 4.0
    # Working-capital cycle: (30 + 45 - 20) / 300 * 365 = 66.9 days.
    assert norms["FR-06"]["outcome"] == "pass" and round(norms["FR-06"]["actual"]) == 67


def test_a_norm_without_its_inputs_cannot_be_evaluated(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "audited_financial_statements",
            {"period_end": "2026-03-31", "current_assets": 90_000_000})
    norms = _policy(client, analyst, case_id)
    assert norms["FR-01"]["outcome"] == "cannot_evaluate"
    assert norms["FR-01"]["missing"] == ["Current liabilities"]
    # Never a pass without its figures (F-20.3).
    assert norms["EL-02"]["outcome"] == "cannot_evaluate" and norms["EL-02"]["missing"] == ["Commercial bureau rank"]


def test_norms_apply_by_facility_and_collateral(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["term_loan"], collateral_present=False)
    add_doc(published_data_root, case_id, "audited_financial_statements", FINANCIALS)
    norms = _policy(client, analyst, case_id)
    for working_capital_only in ("EL-05", "FR-01", "FR-06"):
        assert norms[working_capital_only]["outcome"] == "not_applicable"
    assert norms["SC-01"]["outcome"] == "not_applicable"
    assert norms["FR-03"]["outcome"] != "not_applicable"  # a term loan is term debt


def test_eligibility_and_security_from_their_documents(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, amount_inr=40_000_000)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"incorporation_date": "2024-06-01"})
    add_doc(published_data_root, case_id, "bureau_commercial", {"score": "CMR-7"})
    add_doc(published_data_root, case_id, "valuation_report", {"market_value": 60_000_000})
    norms = _policy(client, analyst, case_id)
    assert norms["EL-01"]["outcome"] == "deviation" and norms["EL-01"]["actual"] == 2.3
    assert norms["EL-01"]["category_label"] == "Eligibility"
    assert norms["EL-02"]["outcome"] == "deviation" and norms["EL-02"]["actual"] == 7
    assert norms["SC-01"]["outcome"] == "pass" and norms["SC-01"]["actual"] == 1.5


def test_the_policy_stage_needs_attention_while_a_norm_cannot_be_evaluated(
    client: TestClient, published_data_root: Path
):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "pan_entity", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "bureau_commercial", {"pan": "AAACK1234F", "score": "Rank 3"})
    conn = db.connect(published_data_root)
    try:
        pipeline.refresh_case(conn, published_data_root, case_id)
    finally:
        conn.close()
    progress = client.get(f"/api/cases/{case_id}/progress", headers=analyst).json()
    stage = next(s for s in progress["stages"] if s["key"] == "policy")
    assert stage["status"] == "needs_attention" and stage["attention"] > 0


def test_policy_needs_the_findings_permission(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/policy", headers=rm).status_code == 403
