"""Policy norms and deviations (FRD F-20; FRD TC-26 = test plan TC-24)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline, policy
from engine.configstore import reader
from engine.configstore.schema import PolicyNorm
from engine.contracts import CaseDetail, NormInput
from tests.conftest import ANALYST, RM, make_case, set_as_of, sign_in
from tests.triangulation import add_doc, audited, bank, months, row_index

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _assessment(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/policy", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _policy(client: TestClient, headers: dict, case_id: str) -> dict[str, dict]:
    return {n["id"]: n for n in _assessment(client, headers, case_id)["norms"]}


def _inputs(norm: dict) -> dict[str, dict]:
    return {i["name"]: i for i in norm["inputs"]}


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


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
    # A deviation's source figures carry their evidence too (TC-24: "with the source").
    assert all(i["evidence"][0]["document_id"] == fs for i in debt_equity["inputs"])

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
    coi = add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2024-06-01"})
    el01 = _policy(client, analyst, case_id)["EL-01"]
    # 27 completed months to 29 Sep 2026: 2.25 years, written truncated.
    assert el01["outcome"] == "deviation" and el01["actual"] == 2.25 and el01["actual_text"] == "2.2 years"
    assert el01["category_label"] == "Eligibility"
    assert el01["inputs"][0]["evidence"][0]["document_id"] == coi


def test_the_norms_the_documents_cannot_support_are_not_in_the_policy(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    norms = _policy(client, analyst, case_id)
    # Security cover waits for a valuation document type; the bureau rank is read from the bureau report.
    assert "SC-01" not in norms and "EL-02" in norms


def test_the_policy_stage_needs_attention_while_a_norm_cannot_be_evaluated(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F"})  # two sources agree: cross-verification has begun
    _refresh(published_data_root, case_id)
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
    first = audited(published_data_root, case_id, set_rows={"(c) Other current liabilities": None})  # a copy without that row
    complete = audited(published_data_root, case_id)                                                 # a complete copy
    audited(published_data_root, case_id, "2025-03-31", scale=0.01)                                  # an earlier year, never used
    norms = _policy(client, analyst, case_id)
    assert norms["FR-01"]["outcome"] == "pass" and round(norms["FR-01"]["actual"], 2) == 1.59
    assert norms["DOC-02"]["actual"] == 2
    # Each figure says which copy it came from.
    figures = _inputs(norms["FR-01"])
    assert figures["current_assets"]["evidence"][0]["document_id"] == first
    assert figures["current_liabilities"]["evidence"][0]["document_id"] == complete


# --- Leverage on a net worth of zero or less, and zero divisors ---


def test_negative_net_worth_is_never_a_pass_on_leverage(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id, set_rows={"(b) Reserves and surplus": -150_000_000})
    norms = _policy(client, analyst, case_id)
    assert norms["EL-03"]["outcome"] == "deviation"
    for norm_id in ("FR-02", "FR-05"):
        n = norms[norm_id]
        assert n["outcome"] == "deviation" and n["actual"] is None
        assert n["reason"] == "denominator_not_positive" and n["reason_inputs"] == ["Net worth"]
        assert "unbounded" in n["actual_text"]
    _refresh(published_data_root, case_id)
    cam = client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()
    assert {"FR-02", "FR-05"} <= {i["ref"] for i in cam["summary"] if i["kind"] == "deviation"}
    questions = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()["questions"]
    for norm_id in ("FR-02", "FR-05"):
        q = next(q for q in questions if q["rule"] == norm_id)
        assert q["source"] == "deviation" and "unbounded" in q["text"]


def test_zero_net_worth_is_a_deviation_on_leverage(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id, set_rows={"(b) Reserves and surplus": -10_000_000})  # share capital is INR 1 cr
    norms = _policy(client, analyst, case_id)
    for norm_id in ("FR-02", "FR-05"):
        assert norms[norm_id]["outcome"] == "deviation" and norms[norm_id]["reason"] == "denominator_not_positive"


@pytest.mark.parametrize("rows,norm_id,inputs", [
    ({"Finance costs": 0}, "FR-04", ["Finance costs"]),
    ({"(a) Short-term borrowings": 0, "(b) Trade payables": 0, "(c) Other current liabilities": 0,
      "(d) Short-term provisions": 0}, "FR-01", ["Current liabilities"]),
])
def test_a_zero_denominator_is_named_and_never_a_pass(client: TestClient, analyst, published_data_root: Path, rows, norm_id, inputs):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id, set_rows=rows)
    n = _policy(client, analyst, case_id)[norm_id]
    assert n["outcome"] == "cannot_evaluate" and n["missing"] == []
    assert n["reason"] == "zero_denominator" and n["reason_inputs"] == inputs
    _refresh(published_data_root, case_id)
    texts = [i["text"] for i in client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()["summary"]]
    questions = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()["questions"]
    assert not any("is zero not on file" in t for t in texts + [q["text"] for q in questions])
    if norm_id == "FR-04":
        q = next(q for q in questions if q["rule"] == "FR-04")
        assert q["text"] == "Interest coverage could not be computed because Finance costs is zero. What explains it?"


def test_a_missing_denominator_is_still_named_missing(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id, set_rows={"Finance costs": None})
    n = _policy(client, analyst, case_id)["FR-04"]
    assert n["outcome"] == "cannot_evaluate" and n["missing"] == ["Finance costs"] and n["reason"] is None


# --- Business vintage ---


@pytest.mark.parametrize("incorporated,as_of,outcome,actual", [
    ("2023-09-29", "2026-09-29", "pass", 3.0),
    ("2023-09-30", "2026-09-29", "deviation", 2.9167),   # one day short
    ("2023-10-17", "2026-09-29", "deviation", 2.9167),
    ("2024-03-01", "2027-03-01", "pass", 3.0),
    ("2024-02-29", "2027-02-28", "deviation", 2.9167),   # 29 February is not reached in 2027
    ("2024-02-29", "2027-03-01", "pass", 3.0),
])
def test_vintage_is_compared_on_completed_months(client: TestClient, analyst, published_data_root: Path,
                                                incorporated, as_of, outcome, actual):
    case_id = make_case(client, analyst, published_data_root)
    set_as_of(published_data_root, case_id, as_of)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": incorporated})
    n = _policy(client, analyst, case_id)["EL-01"]
    assert n["outcome"] == outcome and n["actual"] == actual
    if outcome == "deviation":
        assert n["actual_text"] == "2.9 years"  # truncated, never rounded up to the norm


def test_vintage_applies_to_companies_only(client: TestClient, analyst, published_data_root: Path):
    firm = make_case(client, analyst, published_data_root, constitution="partnership", borrower="Orchid Weaves")
    assert _policy(client, analyst, firm)["EL-01"]["outcome"] == "not_applicable"
    company = make_case(client, analyst, published_data_root, borrower="Kestrel Tools Pvt Ltd")
    assert _policy(client, analyst, company)["EL-01"]["outcome"] == "cannot_evaluate"
    unknown = make_case(client, analyst, published_data_root, constitution="unknown", borrower="Larkspur Castings")
    assert _policy(client, analyst, unknown)["EL-01"]["outcome"] == "cannot_evaluate"


# --- Thresholds and display ---


def test_thresholds_are_inclusive(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id, set_rows={"(a) Inventories": 10_400_000})  # current assets 4.44 cr / 3.7 cr
    n = _policy(client, analyst, case_id)["FR-01"]
    assert n["actual"] == 1.2 and n["outcome"] == "pass"


def test_a_deviation_never_displays_equal_to_its_norm(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id, set_rows={"(a) Inventories": 20_376_000})
    n = _policy(client, analyst, case_id)["FR-06"]
    assert n["outcome"] == "deviation" and round(n["actual"], 1) == 75.4 and n["actual_text"] == "75.4 days"
    _refresh(published_data_root, case_id)
    texts = [i["text"] for i in client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()["summary"]]
    assert any("75.4 days against at most 75 days" in t for t in texts)


@pytest.mark.parametrize("value,unit,threshold,text", [
    (20.0424, "%", 20, "20.04%"),
    (75.047, "days", 75, "75.05 days"),
    (1.19996, "x", 1.2, "1.19996x"),
    (3.0004, "x", 3.0, "3.0004x"),
    (75.4, "days", 75, "75.4 days"),
    (2.6667, "x", 2.0, "2.67x"),
    (75.0000001, "days", 75, "75.0000001 days"),   # a deviation at the 7th decimal still shows it
    (20.00000001, "%", 20, "20.00000001%"),
])
def test_a_deviation_reads_as_a_different_number_from_its_norm(value, unit, threshold, text):
    assert policy.actual_text(value, unit, threshold, "deviation") == text
    shown = float(text.rstrip("x%").replace(" days", ""))
    assert shown != threshold


@pytest.mark.parametrize("value,unit,text", [
    (1, "years", "1 year"), (1.05, "years", "1 year"), (2, "years", "2 years"), (0, "years", "0 years"),
    (1.5, "years", "1.5 years"), (1, "days", "1 day"), (0.6, "days", "1 day"), (90, "days", "90 days"),
    (-1, "days", "-1 day"),
    # A value that rounds to zero is never written with a minus sign.
    (-0.4, "days", "0 days"), (-0.04, "%", "0.0%"), (-0.004, "x", "0.00x"),
])
def test_values_are_worded_with_their_unit(value, unit, text):
    assert policy.unit_text(value, unit) == text


def test_one_year_of_statements_reads_one_year(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    n = _policy(client, analyst, case_id)["DOC-02"]
    assert n["outcome"] == "deviation" and n["actual_text"] == "1 year" and n["required"] == "at least 2 years"
    _refresh(published_data_root, case_id)
    texts = [i["text"] for i in client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()["summary"]]
    questions = [q["text"] for q in client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()["questions"]]
    assert any("1 year against at least 2 years" in t for t in texts)
    assert not any("1 years" in t for t in texts + questions)


# --- The overview: counts and families (the Policy page) ---


def test_counts_and_families_summarise_the_norms(client: TestClient, analyst, published_data_root: Path):
    from tests.test_pd_note import _case

    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2024-06-01"})
    assessment = _assessment(client, analyst, case_id)
    outcomes = [n["outcome"] for n in assessment["norms"]]
    assert assessment["counts"] == {"deviations": outcomes.count("deviation"), "cannot_evaluate": 1,
                                    "passed": outcomes.count("pass"), "not_applicable": 0}
    assert assessment["counts"]["deviations"] == 7
    groups = assessment["groups"]
    assert [g["family"] for g in groups] == ["eligibility", "ratios", "documentation", "security_cover"]
    by_family = {g["family"]: g for g in groups}
    for family, group in by_family.items():
        norms = [n for n in assessment["norms"] if n["family"] == family]
        assert group["norms"] == len(norms)
        assert sum(group["counts"].values()) == len(norms)
    eligibility = by_family["eligibility"]
    # EL-01 and EL-05 deviate, EL-02 (no bureau report) cannot be evaluated, EL-03 and EL-04 pass.
    assert eligibility["status"] == "deviation"
    assert eligibility["counts"] == {"deviations": 2, "cannot_evaluate": 1, "passed": 2, "not_applicable": 0}
    # Deviations first, then the norms that cannot be evaluated, then passed ones; three at most.
    assert eligibility["highlights"] == ["EL-01", "EL-05", "EL-02"]
    assert by_family["ratios"]["highlights"] == ["FR-02", "FR-05", "FR-06"]
    assert by_family["documentation"] == {
        "family": "documentation", "norms": 2, "status": "deviation", "highlights": ["DOC-01", "DOC-02"],
        "counts": {"deviations": 2, "cannot_evaluate": 0, "passed": 0, "not_applicable": 0}}
    # No security-cover norm is configured until a valuation document is in scope.
    assert by_family["security_cover"] == {
        "family": "security_cover", "norms": 0, "status": "no_norms", "highlights": [],
        "counts": {"deviations": 0, "cannot_evaluate": 0, "passed": 0, "not_applicable": 0}}


def test_a_family_is_clear_or_waits_on_a_norm_it_cannot_evaluate(client: TestClient, analyst, published_data_root: Path):
    # A partnership (EL-01 does not apply) asking for 6.5 cr (EL-05 does not apply): the other
    # eligibility norms pass. Inventories of 1.5 cr keep the cycle within 75 days, so among the
    # ratios only the DSCR, with no proposed instalment for the term loan, cannot be evaluated.
    case_id = make_case(client, analyst, published_data_root, constitution="partnership", borrower="Orchid Weaves")
    audited(published_data_root, case_id, set_rows={"(a) Inventories": 15_000_000})
    audited(published_data_root, case_id, "2025-03-31", scale=0.85)
    add_doc(published_data_root, case_id, "commercial_bureau_report", {"company_name": "Orchid Weaves", "credit_rank": "4"})
    by_family = {g["family"]: g for g in _assessment(client, analyst, case_id)["groups"]}

    eligibility = by_family["eligibility"]
    assert eligibility["status"] == "clear"
    assert eligibility["counts"] == {"deviations": 0, "cannot_evaluate": 0, "passed": 3, "not_applicable": 2}
    assert eligibility["highlights"] == ["EL-02", "EL-03", "EL-04"]   # a norm that does not apply is not shown
    ratios = by_family["ratios"]
    assert ratios["status"] == "cannot_evaluate"
    assert ratios["counts"] == {"deviations": 0, "cannot_evaluate": 1, "passed": 5, "not_applicable": 0}
    assert ratios["highlights"] == ["FR-03", "FR-01", "FR-02"]
    assert by_family["documentation"]["status"] == "deviation"   # blocking checklist items are still open


def test_a_request_just_over_the_turnover_norm_reads_over_it(client: TestClient, analyst, published_data_root: Path):
    # 2.365 cr against revenue of 11.8 cr is 20.04%, over the 20% norm.
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=23_650_000)
    audited(published_data_root, case_id)
    n = _policy(client, analyst, case_id)["EL-05"]
    assert n["outcome"] == "deviation" and n["actual_text"] == "20.04%"
    _refresh(published_data_root, case_id)
    texts = [i["text"] for i in client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()["summary"]]
    questions = [q["text"] for q in client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()["questions"]]
    assert any("20.04% against at most 20%" in t for t in texts)
    assert not any("20.0% against" in t for t in texts + questions)


def test_formula_definition_and_source_are_reported(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    norms = _policy(client, analyst, case_id)
    configured = {n.id: n for n in reader.load_policy(published_data_root).norms}
    for norm_id, n in norms.items():
        assert n["formula"] == policy.words(configured[norm_id].expression)
    fr05 = norms["FR-05"]
    assert fr05["definition"] == "Total debt ÷ Tangible net worth" and fr05["required"] == "at most 2.00x"
    assert fr05["provisional"] is True and fr05["source"] == "provisional"
    assert norms["EL-05"]["note"] == configured["EL-05"].note
    assert norms["FR-03"]["formula"] == ("(Profit after tax + Depreciation) ÷ (Annual instalments on existing facilities "
                                         "+ Annual instalments on the proposed term loan)")


def test_the_assessment_records_its_config_version(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    version = client.get("/api/config/version", headers=analyst).json()["version"]
    assert _assessment(client, analyst, case_id)["config_version"] == version


# --- Every source figure has a source ---


def test_amount_requested_cites_the_sourcing_message(client: TestClient, analyst, published_data_root: Path):
    message = "Kestrel Tools Pvt Ltd needs CC of 4 cr for working capital."
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000,
                        message_text=message, header={"amount_inr": {"value": "40000000", "proposed": "4 cr",
                                                                     "source": "message:31-35"}})
    conn = db.connect(published_data_root)
    try:
        message_doc = conn.execute("SELECT id FROM documents WHERE case_id = ? ORDER BY created_at LIMIT 1", (case_id,)).fetchone()["id"]
    finally:
        conn.close()
    amount = _inputs(_policy(client, analyst, case_id)["EL-05"])["amount_requested"]
    assert amount["basis"] == "document" and amount["evidence"][0] == {"document_id": message_doc, "page": 1, "bbox": None}

    direct = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000,
                       borrower="Orchid Castings Pvt Ltd")
    amount = _inputs(_policy(client, analyst, direct)["EL-05"])["amount_requested"]
    assert amount["basis"] == "case" and amount["evidence"] == []


def test_doc01_lists_the_open_blocking_items(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id)
    doc01 = _policy(client, analyst, case_id)["DOC-01"]
    figure = doc01["inputs"][0]
    readiness = client.get(f"/api/cases/{case_id}/checklist", headers=analyst).json()
    open_items = [i["item_id"] for i in readiness["items"] if i["blocking"] and i["status"] not in ("satisfied", "waived")]
    assert figure["basis"] == "checklist" and figure["refs"] == open_items and len(open_items) == doc01["actual"]


def test_every_evaluated_input_has_a_source(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    audited(published_data_root, case_id)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2015-06-12"})
    add_doc(published_data_root, case_id, "commercial_bureau_report", {"company_name": "Kestrel Tools Private Limited", "credit_rank": "4"})
    bank(published_data_root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR ORCHID TRADERS", "credit": 1_000_000}
                                         for ym in months((2025, 10), 6)], start="2025-10-01", end="2026-03-31")
    for n in _policy(client, analyst, case_id).values():
        if n["outcome"] in ("pass", "deviation"):
            for i in n["inputs"]:
                assert i["evidence"] or i["basis"] in ("case", "checklist", "statements_coverage", "not_requested"), (n["id"], i["name"])


# --- Instalments and DSCR ---


def _instalment_docs(root: Path, case_id: str, lender: str = "Marlow Bank", emi: int = 300_000) -> str:
    decl = add_doc(root, case_id, "existing_facilities_declaration", {
        "company_name": "Kestrel Tools Private Limited",
        "facilities": [{"lender": lender, "facility": "Term loan", "sanctioned_amount": 15_000_000, "emi": emi}]})
    return decl


def test_declared_and_sanctioned_emis_count_once_in_dscr(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["term_loan"],
                        header={"proposed_emi_inr": {"value": "200000", "source": "person"}})
    audited(published_data_root, case_id)
    decl = _instalment_docs(published_data_root, case_id)
    add_doc(published_data_root, case_id, "sanction_letter", {"lender_name": "Marlow Bank", "borrower_name": "Kestrel Tools Private Limited",
                                                               "facilities": [{"facility": "Term loan", "sanctioned_amount": 15_000_000, "emi": 300_000}]})
    bank(published_data_root, case_id, [{"date": f"{ym}-05", "description": "NACH DR MARLOW BANK", "debit": 300_000}
                                         for ym in months((2025, 4), 6)])
    fr03 = _policy(client, analyst, case_id)["FR-03"]
    figures = _inputs(fr03)
    assert figures["annual_instalments"]["value"] == 3_600_000
    assert decl in {e["document_id"] for e in figures["annual_instalments"]["evidence"]}
    assert figures["proposed_instalments"]["value"] == 2_400_000 and figures["proposed_instalments"]["relies_on_manual"] is True
    assert fr03["actual"] == 1.7333 and fr03["outcome"] == "pass"  # (64 + 40 lakh) / (36 + 24 lakh)


def test_a_declared_emi_makes_dscr_apply_without_a_term_loan(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    _instalment_docs(published_data_root, case_id)
    fr03 = _policy(client, analyst, case_id)["FR-03"]
    assert fr03["outcome"] != "not_applicable" and fr03["actual"] == 2.8889
    assert _inputs(fr03)["proposed_instalments"]["basis"] == "not_requested"


def test_dscr_waits_for_the_proposed_instalment(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["term_loan"])
    audited(published_data_root, case_id)
    statement = bank(published_data_root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR ORCHID TRADERS", "credit": 1_000_000}
                                                     for ym in months((2025, 10), 6)], start="2025-10-01", end="2026-03-31")
    fr03 = _policy(client, analyst, case_id)["FR-03"]
    assert fr03["outcome"] == "cannot_evaluate" and fr03["missing"] == ["Annual instalments on the proposed term loan"]
    existing = _inputs(fr03)["annual_instalments"]
    assert existing["value"] == 0 and existing["basis"] == "statements_coverage"
    assert existing["evidence"][0]["document_id"] == statement


@pytest.mark.parametrize("start,end,expect_missing", [("2026-02-01", "2026-03-31", True), ("2025-10-01", "2026-03-31", False)])
def test_zero_instalments_need_enough_statement_months(client: TestClient, analyst, published_data_root: Path, start, end, expect_missing):
    case_id = make_case(client, analyst, published_data_root, facilities=["term_loan"],
                        header={"proposed_emi_inr": {"value": "200000", "source": "person"}})
    audited(published_data_root, case_id)
    bank(published_data_root, case_id, [{"date": f"{end[:7]}-15", "description": "NEFT CR ORCHID TRADERS", "credit": 1_000_000}],
         start=start, end=end)
    fr03 = _policy(client, analyst, case_id)["FR-03"]
    if expect_missing:
        assert fr03["missing"] == ["Annual instalments on existing facilities"]
    else:
        assert _inputs(fr03)["annual_instalments"]["value"] == 0 and fr03["outcome"] == "pass"


def test_dscr_formula_is_the_expression_evaluated(client: TestClient, analyst, published_data_root: Path):
    # Finance costs of 35 lakh do not move the interim DSCR: (64 + 40 lakh) / 36 lakh.
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    bank(published_data_root, case_id, [{"date": f"{ym}-05", "description": "NACH DR ASHWOOD FINSERV", "debit": 300_000}
                                         for ym in months((2025, 4), 6)])
    fr03 = _policy(client, analyst, case_id)["FR-03"]
    assert fr03["actual"] == 2.8889 and fr03["definition"].startswith("(PAT + depreciation + interest on term debt)")


@pytest.mark.parametrize("amount,outcome_is_na", [(40_000_000, False), (50_000_000, False), (65_000_000, True)])
def test_el05_applies_only_under_the_turnover_method(client: TestClient, analyst, published_data_root: Path, amount, outcome_is_na):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=amount)
    audited(published_data_root, case_id)
    assert (_policy(client, analyst, case_id)["EL-05"]["outcome"] == "not_applicable") == outcome_is_na


# --- The commercial bureau rank ---


def test_bureau_rank_comes_from_the_commercial_bureau_report(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "commercial_bureau_report", {"company_name": "Kestrel", "credit_rank": "4"}, page=2)
    n = _policy(client, analyst, case_id)["EL-02"]
    assert n["outcome"] == "pass" and n["actual"] == 4 and n["required"] == "at most rank 6"
    assert n["inputs"][0]["evidence"][0]["page"] == 2

    cmr = make_case(client, analyst, published_data_root, borrower="Orchid Castings Pvt Ltd")
    add_doc(published_data_root, cmr, "commercial_bureau_report", {"company_name": "Orchid", "credit_rank": "CMR-7"})
    n = _policy(client, analyst, cmr)["EL-02"]
    assert n["outcome"] == "deviation" and n["actual"] == 7 and n["category_label"] == "Eligibility"

    unrated = make_case(client, analyst, published_data_root, borrower="Larkspur Textiles Pvt Ltd")
    add_doc(published_data_root, unrated, "commercial_bureau_report", {"company_name": "Larkspur", "credit_rank": "NA"})
    assert _policy(client, analyst, unrated)["EL-02"]["missing"] == ["Commercial bureau rank"]

    two = make_case(client, analyst, published_data_root, borrower="Saffron Looms Pvt Ltd")
    add_doc(published_data_root, two, "commercial_bureau_report", {"company_name": "Saffron", "credit_rank": "8", "report_date": "2026-06-10"})
    add_doc(published_data_root, two, "commercial_bureau_report", {"company_name": "Saffron", "credit_rank": "3", "report_date": "2026-01-10"})
    assert _policy(client, analyst, two)["EL-02"]["actual"] == 8  # the latest report, whatever the filing order


def test_a_missing_bureau_report_is_not_asked_of_the_promoter(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    assert _policy(client, analyst, case_id)["EL-02"]["outcome"] == "cannot_evaluate"
    _refresh(published_data_root, case_id)
    questions = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()["questions"]
    assert not any(q["rule"] == "EL-02" for q in questions)


def test_a_missing_bureau_report_still_holds_the_policy_stage(client: TestClient, analyst, published_data_root: Path):
    # Every other norm evaluates: EL-02 alone needs attention, until a report is on file.
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2015-06-12"})
    audited(published_data_root, case_id, "2026-03-31", set_rows={"(a) Long-term borrowings": 100_000_000})
    audited(published_data_root, case_id, "2025-03-31", scale=0.85)
    add_doc(published_data_root, case_id, "company_pan", {"pan": "AAACK1234F"})
    add_doc(published_data_root, case_id, "income_tax_return", {"pan": "AAACK1234F"})

    def stage() -> dict:
        _refresh(published_data_root, case_id)
        progress = client.get(f"/api/cases/{case_id}/progress", headers=analyst).json()
        return next(s for s in progress["stages"] if s["key"] == "policy")

    held = stage()
    assert held["status"] == "needs_attention" and held["attention"] == 1
    add_doc(published_data_root, case_id, "commercial_bureau_report", {"company_name": "Kestrel", "credit_rank": "4"})
    released = stage()
    assert released["status"] == "done" and released["attention"] == 0


# --- Figures waiting for review (F-17.2) ---


def test_a_norm_waits_for_its_figures_to_be_reviewed(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root)
    cell = f"balance_sheet[{row_index('balance_sheet', '(a) Long-term borrowings')}].current_period"
    fs = audited(published_data_root, case_id, pending={cell})
    norms = _policy(client, analyst, case_id)
    assert norms["FR-02"]["outcome"] == "cannot_evaluate" and norms["FR-02"]["reason"] == "awaiting_review"
    assert "Long-term borrowings" in norms["FR-02"]["reason_inputs"]
    assert "Total borrowings" in norms["FR-05"]["reason_inputs"]
    assert _inputs(norms["FR-02"])["long_term_borrowings"]["awaiting_review"] is True
    _refresh(published_data_root, case_id)
    cam = client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()
    assert not {"FR-02", "FR-05"} & {i["ref"] for i in cam["summary"] if i["kind"] == "deviation"}
    questions = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst).json()["questions"]
    assert not {"FR-02", "FR-05"} & {q["rule"] for q in questions}

    conn = db.connect(published_data_root)
    try:
        conn.execute("UPDATE field_values SET status = 'accepted' WHERE document_id = ?", (fs,))
    finally:
        conn.close()
    assert _policy(client, analyst, case_id)["FR-02"]["outcome"] == "pass"

    coi_case = make_case(client, analyst, published_data_root, borrower="Orchid Castings Pvt Ltd")
    add_doc(published_data_root, coi_case, "certificate_of_incorporation", {"date_of_incorporation": "2015-06-12"},
            pending={"date_of_incorporation"})
    el01 = _policy(client, analyst, coi_case)["EL-01"]
    assert el01["reason"] == "awaiting_review" and el01["reason_inputs"] == ["Years in business"]


# --- Collateral norms, should one be configured ---


def test_collateral_norms_apply_only_with_collateral():
    norm = PolicyNorm(id="SC-T", family="security_cover", expression="realisable_value / amount_requested", label="Security cover",
                      unit="x", kind="min", threshold=1.25, category="security", applies_when="collateral",
                      source="provisional", status="provisional")
    without = CaseDetail(id="C1", borrower="Kestrel", constitution="private_limited", facilities=["cash_credit"],
                         amount_inr=40_000_000, stage="Documents", rm="arjun-deshpande", created_at="2026-09-29T00:00:00Z",
                         open_review_items=0, pan=None, gstin=None, cin=None, udyam=None, collateral_present=False,
                         channel="email", as_of="2026-09-29", created_by="arjun-deshpande", config_version=None, header={})
    inputs = policy.Inputs(values={"amount_requested": NormInput(name="amount_requested", label="Amount requested", value=40_000_000)})
    assert policy.evaluate(norm, None, without, inputs, {"security": "Security cover"}).outcome == "not_applicable"
    with_collateral = without.model_copy(update={"collateral_present": True})
    r = policy.evaluate(norm, None, with_collateral, inputs, {"security": "Security cover"})
    assert r.outcome == "cannot_evaluate" and r.missing == ["Collateral realisable value"]


# --- The test plan's TC-24 (FRD TC-26) against an expected deviation record ---


def test_tc26_deviations_match_the_expected_record(client: TestClient, analyst, published_data_root: Path):
    from tests.test_pd_note import _case

    case_id = _case(client, analyst, published_data_root)
    add_doc(published_data_root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2024-06-01"})
    expected = json.loads((FIXTURES / "TC-26" / "expected_deviations.json").read_text(encoding="utf-8"))
    norms = _policy(client, analyst, case_id)
    deviations = {(n["id"], n["category"]) for n in norms.values() if n["outcome"] == "deviation"}
    assert deviations == {(e["id"], e["category"]) for e in expected["deviations"]}
    documents = client.get(f"/api/cases/{case_id}/documents", headers=analyst).json()
    types = {d["id"]: set(d["classification"]["types"]) for d in documents if d.get("classification")}
    for e in expected["deviations"]:
        n = norms[e["id"]]
        assert abs(n["actual"] - e["actual"]) <= 0.01, e["id"]
        # Each deviation is listed with its source: a page for every figure read from a document, the
        # checklist for DOC-01, the case record for the amount asked (this case has no sourcing message).
        assert all(i["evidence"] or i["basis"] in ("checklist", "case") for i in n["inputs"]), e["id"]
        if e["source"] == "checklist":
            assert [i["basis"] for i in n["inputs"]] == ["checklist"], e["id"]
            assert sorted(n["inputs"][0]["refs"]) == sorted(e["open_items"]), e["id"]
        else:
            cited = {t for i in n["inputs"] for ev in i["evidence"] for t in types.get(ev["document_id"], set())}
            assert e["source"] in cited, (e["id"], cited)


# --- Instalments on existing facilities: each facility once (FR-03) ---


def _declaration(root: Path, case_id: str, rows: list[tuple[str, int]], facility: str = "Term loan") -> str:
    return add_doc(root, case_id, "existing_facilities_declaration", {
        "company_name": "Kestrel Tools Private Limited",
        "facilities": [{"lender": lender, "facility": facility, "sanctioned_amount": 15_000_000, "emi": emi}
                       for lender, emi in rows]})


def _sanction(root: Path, case_id: str, lender: str, emis: list[int]) -> str:
    return add_doc(root, case_id, "sanction_letter", {
        "lender_name": lender, "borrower_name": "Kestrel Tools Private Limited",
        "facilities": [{"facility": "Term loan", "sanctioned_amount": 15_000_000, "emi": emi} for emi in emis]})


def _debits(root: Path, case_id: str, narration: str, amount: int) -> str:
    return bank(root, case_id, [{"date": f"{ym}-05", "description": narration, "debit": amount}
                                for ym in months((2025, 4), 6)])


def _instalments(client: TestClient, analyst: dict, case_id: str) -> tuple[float, dict]:
    fr03 = _policy(client, analyst, case_id)["FR-03"]
    return _inputs(fr03)["annual_instalments"]["value"], fr03


def test_two_lenders_sharing_a_first_word_are_two_lenders(client: TestClient, analyst, published_data_root: Path):
    # Indian Bank (declared, 2 lakh) and Indian Overseas Bank (a sanction letter and its debits, 6 lakh).
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    _declaration(published_data_root, case_id, [("Indian Bank", 200_000)])
    _sanction(published_data_root, case_id, "Indian Overseas Bank", [600_000])
    _debits(published_data_root, case_id, "NACH DR INDIAN OVERSEAS BANK", 600_000)
    annual, fr03 = _instalments(client, analyst, case_id)
    assert annual == 9_600_000
    assert fr03["outcome"] == "deviation" and fr03["actual"] == 1.0833  # 1.04 cr / 96 lakh


def test_a_narration_abbreviating_a_declared_lender_is_that_facility(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    _declaration(published_data_root, case_id, [("Tidewater Finance Limited", 145_000)])
    _debits(published_data_root, case_id, "NACH DR TIDEWATER FIN", 145_000)
    assert _instalments(client, analyst, case_id)[0] == 145_000 * 12


def test_a_renewed_sanction_letter_restating_a_loan_counts_once(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    _sanction(published_data_root, case_id, "Marlow Bank", [300_000])
    _sanction(published_data_root, case_id, "Marlow Bank", [300_000])
    annual, fr03 = _instalments(client, analyst, case_id)
    assert annual == 3_600_000 and fr03["outcome"] == "pass" and fr03["actual"] == 2.8889


def test_a_second_copy_of_the_declaration_counts_once(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    _declaration(published_data_root, case_id, [("Marlow Bank", 300_000)])
    _declaration(published_data_root, case_id, [("Marlow Bank", 300_000)])
    assert _instalments(client, analyst, case_id)[0] == 3_600_000


def test_two_loans_in_one_letter_are_two_loans(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=40_000_000)
    audited(published_data_root, case_id)
    _sanction(published_data_root, case_id, "Marlow Bank", [300_000, 200_000])
    assert _instalments(client, analyst, case_id)[0] == 6_000_000


# --- Where an input typed by a person comes from ---


def test_an_instalment_typed_by_the_rm_cites_the_case_not_the_message(client: TestClient, analyst, published_data_root: Path):
    case_id = make_case(client, analyst, published_data_root, facilities=["term_loan"],
                        message_text="Kestrel Tools needs a term loan of Rs 65 lakh for a new press line.",
                        header={"proposed_emi_inr": {"value": "200000", "proposed": None, "source": "person"}})
    audited(published_data_root, case_id)
    proposed = _inputs(_policy(client, analyst, case_id)["FR-03"])["proposed_instalments"]
    assert proposed["value"] == 2_400_000 and proposed["evidence"] == [] and proposed["basis"] == "case"
    assert proposed["relies_on_manual"] is True


# --- An expression the evaluator does not support ---


def test_an_unsupported_expression_cannot_be_evaluated_and_never_crashes():
    norm = PolicyNorm(id="EL-03", family="eligibility", expression="net_worth * True", label="Positive net worth",
                      unit="inr", kind="min", threshold=1, category="eligibility", source="provisional",
                      status="provisional")
    case = CaseDetail(id="c", borrower="b", constitution="private_limited", facilities=["cash_credit"],
                      amount_inr=1, stage="Intake", rm="r", created_at="2026-09-29T00:00:00Z", open_review_items=0,
                      pan=None, gstin=None, cin=None, udyam=None, collateral_present=False, channel="email",
                      as_of="2026-09-29", created_by="r", config_version="v", header={})
    inputs = policy.Inputs()
    inputs.put("net_worth", 10_000_000)
    result = policy.evaluate(norm, None, case, inputs, {"eligibility": "Eligibility"})
    assert result.outcome == "cannot_evaluate" and result.missing == ["a supported expression"]
