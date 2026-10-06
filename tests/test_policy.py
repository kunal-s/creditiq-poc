"""Policy norms and deviations (FRD F-20, TC-26)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.triangulation import add_doc, audited


def _policy(client: TestClient, headers: dict, case_id: str) -> dict[str, dict]:
    response = client.get(f"/api/cases/{case_id}/policy", headers=headers)
    assert response.status_code == 200, response.text
    return {n["id"]: n for n in response.json()["norms"]}


def test_tc26_ratios_are_assessed_with_their_source_figures(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    # Long-term borrowings raised to 10 cr: debt to equity (10 + 1.2 cr) / 4.2 cr is a deviation.
    fs = audited(published_data_root, case_id, set_rows={"(a) Long-term borrowings": 100_000_000}, page=4)
    norms = _policy(client, analyst, case_id)

    current = norms["FR-01"]  # 5.9 cr / 3.7 cr, from the printed rows
    assert current["outcome"] == "pass" and round(current["actual"], 2) == 1.59
    assert current["required"] == "at least 1.20x"
    assert {i["name"] for i in current["inputs"]} == {"current_assets", "current_liabilities"}
    assert all(i["evidence"][0] == {"document_id": fs, "page": 4, "bbox": None} for i in current["inputs"])

    debt_equity = norms["FR-05"]
    assert debt_equity["outcome"] == "deviation" and round(debt_equity["actual"], 2) == 2.67
    assert debt_equity["category"] == "financial" and debt_equity["category_label"] == "Financial norms"

    # Interest coverage: (PBT + finance costs) / finance costs = (75 + 35) / 35 lakh.
    assert norms["FR-04"]["outcome"] == "pass" and round(norms["FR-04"]["actual"], 2) == 3.14
    # Working-capital cycle: (2.5 + 2.4 - 2.0) cr / 11.8 cr * 365 = 89.7 days against 75.
    assert norms["FR-06"]["outcome"] == "deviation" and round(norms["FR-06"]["actual"], 1) == 89.7
    # Profit and net worth come from the same statements.
    assert norms["EL-03"]["outcome"] == "pass" and norms["EL-04"]["outcome"] == "pass"


def test_a_norm_without_its_inputs_cannot_be_evaluated(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    # One current-liability row is not printed, so current liabilities cannot be summed.
    audited(published_data_root, case_id, set_rows={"(c) Other current liabilities": None})
    norms = _policy(client, analyst, case_id)
    assert norms["FR-01"]["outcome"] == "cannot_evaluate"
    assert norms["FR-01"]["missing"] == ["Current liabilities"]
    # Never a pass without its figures (F-20.3).
    assert norms["EL-01"]["outcome"] == "cannot_evaluate" and norms["EL-01"]["missing"] == ["Years in business"]


def test_norms_apply_by_facility(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["term_loan"], collateral_present=False)
    audited(published_data_root, case_id)
    norms = _policy(client, analyst, case_id)
    for working_capital_only in ("EL-05", "FR-01", "FR-06"):
        assert norms[working_capital_only]["outcome"] == "not_applicable"
    assert norms["FR-03"]["outcome"] != "not_applicable"  # a term loan is term debt


def test_vintage_comes_from_the_certificate_of_incorporation(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, amount_inr=40_000_000)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2024-06-01"})
    norms = _policy(client, analyst, case_id)
    assert norms["EL-01"]["outcome"] == "deviation" and norms["EL-01"]["actual"] == 2.3
    assert norms["EL-01"]["category_label"] == "Eligibility"


def test_the_norms_the_documents_cannot_support_are_not_in_the_policy(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    assert not {"EL-02", "SC-01"} & set(_policy(client, analyst, case_id))


def test_the_policy_stage_needs_attention_while_a_norm_cannot_be_evaluated(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F"})  # two sources agree: cross-verification has begun
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


def test_figures_are_taken_from_any_copy_of_the_latest_year(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id, set_rows={"(c) Other current liabilities": None})  # a copy without that row
    audited(published_data_root, case_id)                                                   # a complete copy
    audited(published_data_root, case_id, "2025-03-31", scale=0.01)                         # an earlier year, never used
    norms = _policy(client, analyst, case_id)
    assert norms["FR-01"]["outcome"] == "pass" and round(norms["FR-01"]["actual"], 2) == 1.59
    assert norms["DOC-02"]["actual"] == 2
