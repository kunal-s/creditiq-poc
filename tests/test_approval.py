"""Approving authority (FRD F-21; FRD TC-27 = test plan TC-25; decision C.4-9).

The matrix is provisional until RBL supplies its own, so TC-27 is exercised here but not
scored. The worked examples are those of the delivery plan.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import approval
from engine.configstore import reader, writer
from tests.conftest import ANALYST, MANAGER, RM, make_case, sign_in

CR = 10_000_000  # one crore


@pytest.fixture(scope="module")
def matrix():
    return writer.load_authored_sections()["approval_matrix"]


@pytest.fixture(scope="module")
def categories():
    policy = writer.load_authored_sections()["policy"]
    return [c.key for c in policy.deviation_categories], {c.key: c.label for c in policy.deviation_categories}


def _lookup(matrix, categories, facilities, amount, deviations=(), unevaluated=()):
    order, labels = categories
    grouped: dict[str, list[tuple[str, str]]] = {}
    for norm_id, category in deviations:
        grouped.setdefault(category, []).append((norm_id, norm_id))
    return approval.lookup(matrix, order, labels, facilities, amount, grouped,
                           [(n, n, c) for n, c in unevaluated])


def _governing(result):
    return next(s for s in result.steps if s.governs)


@pytest.mark.parametrize("facilities,amount,deviations,key,rule,steps", [
    (["cash_credit"], 15_000_000, [], "credit_officer", "bands.working_capital[0]", 1),
    (["cash_credit"], 2 * CR, [], "credit_officer", "bands.working_capital[0]", 1),
    (["cash_credit"], 2 * CR + 1, [], "regional_credit_head", "bands.working_capital[1]", 1),
    (["cash_credit"], 60 * CR, [], "management_credit_committee", "bands.working_capital[4]", 1),
    (["cash_credit", "term_loan"], 4 * CR, [], "zonal_credit_committee", "bands.term[2]", 2),
    (["cash_credit", "term_loan"], 65_000_000, [("FR-05", "financial")], "head_office_credit_committee",
     "deviations.financial", 3),
    (["cash_credit"], 1 * CR, [("EL-01", "eligibility")], "regional_credit_head", "deviations.eligibility", 2),
    (["cash_credit"], 60 * CR, [("FR-05", "financial")], "management_credit_committee", "bands.working_capital[4]", 2),
])
def test_the_worked_examples(matrix, categories, facilities, amount, deviations, key, rule, steps):
    result = _lookup(matrix, categories, facilities, amount, deviations)
    assert result.outcome == "determined"
    assert result.required.key == key
    assert _governing(result).rule == rule
    assert len(result.steps) == steps


def test_bands_are_inclusive_and_record_their_bounds(matrix, categories):
    step = _lookup(matrix, categories, ["cash_credit"], 2 * CR + 1).steps[0]
    assert (step.band_from_inr, step.band_to_inr) == (2 * CR, 5 * CR)
    first = _lookup(matrix, categories, ["cash_credit"], 2 * CR).steps[0]
    assert (first.band_from_inr, first.band_to_inr) == (None, 2 * CR)
    top = _lookup(matrix, categories, ["cash_credit"], 60 * CR).steps[0]
    assert (top.band_from_inr, top.band_to_inr) == (50 * CR, None)


@pytest.mark.parametrize("facility", ["cash_credit", "term_loan", "bank_guarantee"])
def test_every_band_of_every_product_is_inclusive(matrix, categories, facility):
    product = next(p for p in matrix.products if facility in p.facilities)
    bands = matrix.bands[product.key]
    for i, band in enumerate(bands[:-1]):
        at = _lookup(matrix, categories, [facility], band.up_to_inr)
        assert at.required.key == band.authority and at.steps[0].rule == f"bands.{product.key}[{i}]"
        above = _lookup(matrix, categories, [facility], band.up_to_inr + 1)
        assert above.required.key == bands[i + 1].authority


def test_categories_never_stack(matrix, categories):
    # Base L1; eligibility needs max(L1 + 1, L2) = L2 and financial L1 + 1 = L2: not L3.
    result = _lookup(matrix, categories, ["cash_credit"], 1 * CR, [("EL-01", "eligibility"), ("FR-05", "financial")])
    assert result.required.key == "regional_credit_head"
    assert [s.authority.level for s in result.steps] == [1, 2, 2]
    assert _governing(result).rule == "deviations.eligibility"


def test_at_least_sets_a_floor(matrix, categories):
    security = _lookup(matrix, categories, ["cash_credit"], 1 * CR, [("SC-01", "security")])
    assert security.required.key == "zonal_credit_committee"
    step = _governing(security)
    assert step.levels_above == 1 and step.at_least.key == "zonal_credit_committee"


def test_a_step_beyond_the_top_says_capped(matrix, categories):
    result = _lookup(matrix, categories, ["cash_credit"], 60 * CR, [("FR-05", "financial")])
    deviation = next(s for s in result.steps if s.kind == "deviation")
    assert deviation.capped and deviation.authority.key == "management_credit_committee" and not deviation.governs
    assert not result.steps[0].capped


def test_a_deviation_step_names_its_norms(matrix, categories):
    result = _lookup(matrix, categories, ["cash_credit"], 1 * CR, [("FR-05", "financial"), ("FR-06", "financial")])
    step = _governing(result)
    assert step.category == "financial" and step.category_label == "Financial norms" and step.norms == ["FR-05", "FR-06"]


def test_an_unassessed_norm_makes_a_lower_bound(matrix, categories):
    result = _lookup(matrix, categories, ["cash_credit"], 1 * CR, unevaluated=[("EL-02", "eligibility")])
    assert result.required.key == "credit_officer"
    assert result.lower_bound and result.unevaluated == ["EL-02"]
    assert result.could_rise_to.key == "regional_credit_head"


def test_an_unassessed_norm_in_a_deviating_category_cannot_raise_it(matrix, categories):
    result = _lookup(matrix, categories, ["cash_credit"], 1 * CR, [("EL-01", "eligibility")], [("EL-02", "eligibility")])
    assert result.lower_bound and result.could_rise_to == result.required


def test_without_unassessed_norms_the_authority_is_final(matrix, categories):
    result = _lookup(matrix, categories, ["cash_credit"], 1 * CR, [("FR-05", "financial")])
    assert not result.lower_bound and result.could_rise_to is None and result.unevaluated == []


def test_passed_and_not_applicable_norms_never_escalate(client: TestClient, published_data_root: Path, monkeypatch):
    from engine import policy
    from engine.contracts import NormResult, PolicyAssessment

    def norm(norm_id, outcome, category):
        return NormResult(id=norm_id, family="eligibility", label=norm_id, formula="", required="", outcome=outcome,
                          category=category, category_label=category)

    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, facilities=["cash_credit"], amount_inr=1 * CR)
    monkeypatch.setattr(policy, "assess", lambda conn, root, case: PolicyAssessment(
        case_id=case.id, period="", config_version="v",
        norms=[norm("EL-03", "pass", "eligibility"), norm("SC-01", "not_applicable", "security")]))
    result = client.get(f"/api/cases/{case_id}/approving-authority", headers=analyst).json()
    assert result["required"]["key"] == "credit_officer" and len(result["steps"]) == 1 and not result["lower_bound"]


def test_a_facility_in_no_product_cannot_be_determined(matrix, categories):
    synthetic = matrix.model_copy(update={"products": [p for p in matrix.products if p.key != "term"]})
    result = _lookup(synthetic, categories, ["term_loan"], 1 * CR)
    assert result.outcome == "cannot_determine" and result.reason == "no_product" and result.required is None
    assert result.unmapped_facilities == ["term_loan"]
    mixed = _lookup(synthetic, categories, ["cash_credit", "term_loan"], 1 * CR)
    assert mixed.outcome == "determined" and mixed.unmapped_facilities == ["term_loan"]


def test_exactly_one_step_governs_and_every_step_names_its_rule(matrix, categories):
    result = _lookup(matrix, categories, ["cash_credit", "term_loan", "bank_guarantee"], 9 * CR,
                     [("EL-01", "eligibility"), ("FR-05", "financial"), ("DOC-01", "documentation")])
    assert sum(s.governs for s in result.steps) == 1
    assert all(s.rule for s in result.steps)
    assert result.products == ["working_capital", "term", "non_fund"]


def test_the_provisional_matrix_says_so(matrix, categories):
    assert _lookup(matrix, categories, ["cash_credit"], 1 * CR).provisional
    active = matrix.model_copy(update={
        "status": "active", "source": "rbl_supplied",
        "authorities": [a.model_copy(update={"status": "active"}) for a in matrix.authorities],
        "bands": {k: [b.model_copy(update={"status": "active"}) for b in v] for k, v in matrix.bands.items()},
        "deviations": [r.model_copy(update={"status": "active"}) for r in matrix.deviations],
    })
    result = _lookup(active, categories, ["cash_credit"], 1 * CR, [("FR-05", "financial")])
    assert not result.provisional and result.source == "rbl_supplied"


def test_financial_on_cc_four_crore_is_the_zonal_committee(matrix, categories):
    # Base L2 (working capital 2 to 5 cr) + 1.
    result = _lookup(matrix, categories, ["cash_credit"], 4 * CR, [("FR-05", "financial")])
    assert result.required.key == "zonal_credit_committee"


def _tc27_case(client: TestClient, headers: dict, root: Path) -> str:
    from tests.test_pd_note import _case
    from tests.triangulation import add_doc

    case_id = _case(client, headers, root)
    add_doc(root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2024-06-01"})
    return case_id


def test_tc27_the_required_authority_is_shown_with_the_rule_applied(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _tc27_case(client, analyst, published_data_root)
    response = client.get(f"/api/cases/{case_id}/approving-authority", headers=analyst)
    assert response.status_code == 200, response.text
    result = response.json()
    # Cash credit of 4 cr needs the Regional Credit Head (L2, 2 to 5 cr); every deviation category
    # asks one level more, the Zonal Credit Committee, and the first of the tied steps governs.
    assert result["required"]["key"] == "zonal_credit_committee"
    governing = [s for s in result["steps"] if s["governs"]]
    assert len(governing) == 1 and governing[0]["rule"] == "deviations.eligibility"
    assert governing[0]["norms"] == ["EL-01", "EL-05"]
    assert [s["rule"] for s in result["steps"] if s["kind"] == "amount"] == ["bands.working_capital[1]"]
    assert result["amount_inr"] == 40_000_000 and result["products"] == ["working_capital"]
    policy = client.get(f"/api/cases/{case_id}/policy", headers=analyst).json()
    deviating = {n["category"] for n in policy["norms"] if n["outcome"] == "deviation"}
    assert {s["category"] for s in result["steps"] if s["kind"] == "deviation"} == deviating
    unassessed = [n["id"] for n in policy["norms"] if n["outcome"] == "cannot_evaluate"]
    assert result["unevaluated"] == unassessed and result["lower_bound"] == bool(unassessed)
    assert result["provisional"] is True and result["source"] == "provisional"
    assert result["config_version"] == reader.published_version(published_data_root)["version"]
    again = client.get(f"/api/cases/{case_id}/approving-authority", headers=analyst).json()
    assert json.dumps(again, sort_keys=True) == json.dumps(result, sort_keys=True)


def test_the_default_case_with_a_deviation_goes_to_head_office(client: TestClient, published_data_root: Path):
    from tests.triangulation import audited

    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)  # cash credit and term loan, 6.5 cr
    audited(published_data_root, case_id, set_rows={"(a) Long-term borrowings": 100_000_000})
    result = client.get(f"/api/cases/{case_id}/approving-authority", headers=analyst).json()
    # Both bands need the Zonal Credit Committee (L3); the debt / equity deviation asks one more.
    assert [s["rule"] for s in result["steps"] if s["kind"] == "amount"] == ["bands.working_capital[2]", "bands.term[2]"]
    assert result["required"]["key"] == "head_office_credit_committee"
    governing = next(s for s in result["steps"] if s["governs"])
    assert governing["kind"] == "deviation" and governing["authority"]["level"] == 4


def test_the_authority_needs_the_findings_permission(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/approving-authority", headers=rm).status_code == 403
    manager = sign_in(client, MANAGER)
    assert client.get(f"/api/cases/{case_id}/approving-authority", headers=manager).status_code == 200


def test_authority_is_503_without_the_section_and_policy_still_200(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    version = reader.published_version(published_data_root)["version"]
    (published_data_root / "config_store" / "versions" / version / "approval_matrix.json").unlink()
    reader._load_section_json.cache_clear()
    response = client.get(f"/api/cases/{case_id}/approving-authority", headers=analyst)
    assert response.status_code == 503 and response.json()["detail"] == "approval matrix not published"
    assert client.get(f"/api/cases/{case_id}/policy", headers=analyst).status_code == 200


def test_the_matrix_is_readable_with_config_read(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    response = client.get("/api/config/approval-matrix", headers=analyst)
    assert response.status_code == 200 and response.json()["status"] == "provisional"
    assert client.get("/api/config/approval-matrix", headers=sign_in(client, RM)).status_code == 403
