"""CreditIQ against RBL's reference record (FRD F-25.2 to F-25.5): the deviations area (test
plan TC-24's pass rule) and the approving-authority area (TC-25, not scored on the
provisional matrix)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import comparison, db
from engine.configstore import reader
from tests.conftest import ANALYST, MANAGER, RM, sign_in
from tests.test_reference import IMPORTER, do_import, record_json, write_json


def _case(client: TestClient, root: Path) -> str:
    from tests.test_pd_note import _case as pd_case
    from tests.triangulation import add_doc

    case_id = pd_case(client, sign_in(client, ANALYST), root)
    add_doc(root, case_id, "certificate_of_incorporation", {"date_of_incorporation": "2024-06-01"})
    return case_id


def _import(root: Path, case_id: str, tmp: Path, name: str = "record.json", **changes) -> None:
    record = record_json(case_id)
    for key, value in changes.items():
        if key == "approval_key":
            record["approval"]["authority_key"] = value
        elif key == "values":
            for d in record["deviations"]:
                if d.get("norm_id") in value:
                    d["recorded_value"] = value[d["norm_id"]]
        else:
            record[key] = value
    stored, problems = do_import(root, case_id, write_json(tmp, record, name))
    assert stored is not None, problems


@pytest.fixture()
def manager(client: TestClient) -> dict:
    return sign_in(client, MANAGER)


@pytest.fixture()
def confirmed(client: TestClient, published_data_root: Path, tmp_path: Path, manager: dict) -> str:
    case_id = _case(client, published_data_root)
    _import(published_data_root, case_id, tmp_path)
    assert client.post(f"/api/cases/{case_id}/reference/confirm", headers=manager).status_code == 200
    return case_id


def _get(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/comparison", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _items(result: dict, area: str = "deviations") -> dict[str, dict]:
    return {i["key"]: i for i in result["items"] if i["area"] == area}


def _decide(client, headers, case_id, key, verdict="valid", reason="Checked against the record", area="deviations"):
    return client.put(f"/api/cases/{case_id}/comparison/{area}/{key}/adjudication",
                      json={"verdict": verdict, "reason": reason}, headers=headers)


def test_tc24_the_deviations_are_compared_with_rbls_record(client, confirmed: str, manager: dict):
    result = _get(client, manager, confirmed)
    counts = result["counts"]
    assert (counts["agree"], counts["differ"], counts["new"], counts["missed"]) == (1, 1, 5, 3)
    items = _items(result)
    assert {k: i["status"] for k, i in items.items()} == {
        "FR-05": "agree", "FR-06": "differ",
        "EL-01": "new", "EL-05": "new", "FR-02": "new", "DOC-01": "new", "DOC-02": "new",
        "EL-02": "missed", "FR-01": "missed", "REC-5": "missed",
    }
    for status in ("agree", "differ", "new", "missed"):
        assert counts[status] == sum(1 for i in items.values() if i["status"] == status)
    assert items["FR-06"]["notes"] == ["value_differs"]
    assert items["EL-02"]["notes"] == ["cannot_evaluate"] and items["EL-02"]["norm"]["missing"]
    assert items["FR-01"]["notes"] == ["pass"]
    assert items["REC-5"]["notes"] == ["no_norm"] and items["REC-5"]["norm"] is None
    assert items["REC-5"]["label"] == "Pricing below card rate"
    assert items["FR-05"]["record_deviation"]["source_ref"] == "CAM p.14, deviation table row 1"
    norms = client.get(f"/api/cases/{confirmed}/policy", headers=sign_in(client, ANALYST)).json()["norms"]
    assert counts["no_deviation_either_side"] == len(norms) - 9  # every norm on neither side
    assert result["provisional_norms"] is True and result["provisional_matrix"] is True


def test_every_creditiq_side_carries_the_norm_and_its_evidence(client, confirmed: str, manager: dict):
    for key, item in _items(_get(client, manager, confirmed)).items():
        if item["status"] in ("agree", "differ", "new"):
            norm = item["norm"]
            assert norm["id"] == key and norm["outcome"] == "deviation"
            assert all(i["evidence"] or i["basis"] in ("checklist", "case") for i in norm["inputs"]), key


def test_a_category_mismatch_is_noted_but_still_agrees(client, published_data_root: Path, tmp_path: Path, manager):
    case_id = _case(client, published_data_root)
    record = record_json(case_id)
    record["deviations"][0]["category"] = "eligibility"
    do_import(published_data_root, case_id, write_json(tmp_path, record))
    item = _items(_get(client, manager, case_id))["FR-05"]
    assert item["status"] == "agree" and item["notes"] == ["category_differs"]


def test_a_record_of_no_deviations_makes_every_deviation_new(client, published_data_root: Path, tmp_path: Path, manager):
    case_id = _case(client, published_data_root)
    _import(published_data_root, case_id, tmp_path, deviations_recorded=False, deviations=[])
    result = _get(client, manager, case_id)
    statuses = {i["status"] for i in _items(result).values()}
    assert statuses == {"new"} and result["counts"]["new"] == 7


@pytest.mark.parametrize("value,status", [("2.67x", "agree"), ("2.7x", "agree"), ("2.6x", "differ"), ("high", "agree")])
def test_values_agree_at_the_records_precision(value, status):
    assert comparison.values_agree(2.6667, value, "x") == (status == "agree")


@pytest.mark.parametrize("actual,recorded,unit", [
    (2.25, "2.3 years", "years"), (2.25, "2.2 years", "years"), (1.125, "1.13x", "x"), (2.675, "2.68x", "x"),
    (92.5, "93 days", "days"),
])
def test_a_tie_agrees_whichever_way_the_record_rounded(actual, recorded, unit):
    assert comparison.values_agree(actual, recorded, unit)


def test_a_bureau_rank_code_is_read_as_its_rank():
    assert comparison.values_agree(7, "CMR-7", "rank") and comparison.values_agree(7, "CMR7", "rank")
    assert not comparison.values_agree(8, "CMR-7", "rank")
    assert comparison.parse_recorded("-40 lakh", "inr") == (-40.0, 0, 1e5)


def test_rupee_values_read_crore_and_lakh():
    assert comparison.parse_recorded("Rs 1,50,00,000", "inr") == (15_000_000.0, 0, 1.0)
    assert comparison.values_agree(15_000_000, "1.5 cr", "inr")
    assert comparison.values_agree(-4_000_000, "-40 lakh", "inr")
    assert not comparison.values_agree(15_000_000, "1.4 cr", "inr")
    assert comparison.values_agree(None, "1.4 cr", "inr")  # an unbounded figure is never a difference
    assert comparison.values_agree(4_000_000, "Rs 0.40 Crs", "inr")
    assert comparison.values_agree(4_000_000, "Rs 40 L", "inr")


@pytest.mark.parametrize("recorded", [
    "-40 lakh", "−40 lakh", "(-) 40 lakh", "(-)Rs 40 lakh", "(40.00) lakh", "Rs (40.00) lakh", "₹(40) lakh",
    "Net loss of Rs 40 lakh", "Negative net worth of INR 40 lakh", "Deficit 0.40 cr",
])
def test_a_negative_amount_reads_negative_however_the_record_writes_it(recorded):
    assert comparison.values_agree(-4_000_000, recorded, "inr"), recorded
    assert not comparison.values_agree(4_000_000, recorded, "inr"), recorded


def test_brackets_that_are_not_a_negative_amount_stay_positive():
    assert comparison.values_agree(4_000_000, "Profit (Rs 40 lakh)", "inr")   # a parenthesis, not accounting brackets
    assert comparison.values_agree(7, "CMR rank (7)", "rank")                 # brackets mean negative for amounts only
    assert comparison.parse_recorded("(-) 0.5x", "x") == (-0.5, 1, 1.0)


def test_a_negative_net_worth_agrees_with_the_record_of_it(client, published_data_root: Path, tmp_path: Path, manager):
    from tests.conftest import make_case
    from tests.triangulation import audited

    case_id = make_case(client, sign_in(client, ANALYST), published_data_root)
    audited(published_data_root, case_id, set_rows={"(b) Reserves and surplus": -150_000_000})   # net worth -14 cr
    record = record_json(case_id, deviations=[
        {"row": 2, "norm_id": "EL-03", "description": "Net worth eroded", "category": "eligibility",
         "recorded_value": "Negative net worth of Rs (14.00) cr", "source_ref": "CAM p.6"},
        {"row": 3, "norm_id": "FR-05", "description": "Leverage on a negative net worth", "category": "financial",
         "recorded_value": "Not meaningful", "source_ref": "CAM p.6"}])
    stored, problems = do_import(published_data_root, case_id, write_json(tmp_path, record))
    assert stored is not None, problems
    items = _items(_get(client, manager, case_id))
    assert items["EL-03"]["status"] == "agree" and items["EL-03"]["creditiq_text"] == "INR -14.00 cr"
    assert items["FR-05"]["status"] == "agree"   # unbounded on CreditIQ's side: never a difference


@pytest.mark.parametrize("key,status,notes", [
    ("zonal_credit_committee", "agree", []),
    ("regional_credit_head", "differ", ["lower"]),
    ("head_office_credit_committee", "differ", ["higher"]),
    (None, "differ", ["not_in_matrix"]),
])
def test_tc25_the_recorded_authority_is_compared(client, published_data_root: Path, tmp_path: Path, manager,
                                                 key, status, notes):
    case_id = _case(client, published_data_root)
    _import(published_data_root, case_id, tmp_path, approval_key=key)
    item = _items(_get(client, manager, case_id), "approving_authority")["approval"]
    assert item["status"] == status and item["notes"] == notes
    required = item["required"]
    assert required["required"]["key"] == "zonal_credit_committee"
    assert [s["rule"] for s in required["steps"] if s["governs"]] == ["deviations.eligibility"]
    # The record's own deviations (eligibility and financial, plus a row with no category) need
    # the same committee: any difference is the matrix applied differently, not other deviations.
    assert item["authority_on_record_deviations"]["key"] == "zonal_credit_committee"
    assert item["scored"] is False


def test_the_authority_is_scored_only_on_an_active_matrix(client, confirmed: str, manager, monkeypatch):
    result = _get(client, manager, confirmed)
    assert [s["area"] for s in result["scores"]] == ["deviations"]
    real = reader.load_approval_matrix

    def active(root):
        m = real(root)
        return m.model_copy(update={
            "status": "active", "source": "rbl_supplied",
            "authorities": [a.model_copy(update={"status": "active"}) for a in m.authorities],
            "bands": {k: [b.model_copy(update={"status": "active"}) for b in v] for k, v in m.bands.items()},
            "deviations": [r.model_copy(update={"status": "active"}) for r in m.deviations],
        })

    monkeypatch.setattr(reader, "load_approval_matrix", active)
    result = _get(client, manager, confirmed)
    item = _items(result, "approving_authority")["approval"]
    assert item["scored"] is True and result["provisional_matrix"] is False
    score = next(s for s in result["scores"] if s["area"] == "approving_authority")
    assert (score["found_in_record"], score["recorded_total"]) == (1, 1)


def test_adjudication_rules(client, published_data_root: Path, tmp_path: Path, manager):
    case_id = _case(client, published_data_root)
    _import(published_data_root, case_id, tmp_path)
    assert _decide(client, manager, case_id, "FR-06").status_code == 409  # not yet confirmed
    assert client.post(f"/api/cases/{case_id}/reference/confirm", headers=manager).status_code == 200

    response = _decide(client, manager, case_id, "FR-06", "valid", "Record rounds the cycle up")
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["adjudication"]["verdict"] == "valid" and item["adjudication"]["decided_by_name"] == "Meenal Kulkarni"
    assert not item["adjudication"]["stale"]
    assert _decide(client, manager, case_id, "EL-01", "not_valid", "Vintage counted from the earlier firm").status_code == 200
    assert _decide(client, manager, case_id, "FR-05").status_code == 409   # agree
    assert _decide(client, manager, case_id, "EL-02").status_code == 409   # missed
    assert _decide(client, manager, case_id, "FR-99").status_code == 404
    assert _decide(client, manager, case_id, "FR-06", reason="ok").status_code == 422
    # Spaces are not a reason: the reason is trimmed before it is checked, and kept trimmed.
    assert _decide(client, manager, case_id, "FR-06", reason="   ").status_code == 422
    assert _decide(client, manager, case_id, "FR-06", reason="  ok  ").status_code == 422
    trimmed = _decide(client, manager, case_id, "FR-06", "valid", "  Record rounds the cycle up  ")
    assert trimmed.status_code == 200 and trimmed.json()["adjudication"]["reason"] == "Record rounds the cycle up"
    assert client.put(f"/api/cases/{case_id}/comparison/pricing/FR-06/adjudication",
                      json={"verdict": "valid", "reason": "fine reason"}, headers=manager).status_code == 422

    conn = db.connect(published_data_root)
    try:
        logged = conn.execute("SELECT detail FROM decision_log WHERE case_id = ? AND action = 'comparison.adjudicated'",
                              (case_id,)).fetchall()
    finally:
        conn.close()
    assert len(logged) == 3  # FR-06, EL-01, then FR-06 again with its reason trimmed
    detail = json.loads(logged[0]["detail"])
    assert detail["key"] == "FR-06" and detail["snapshot"]["status"] == "differ"

    result = _get(client, manager, case_id)
    assert result["counts"]["to_adjudicate"] == 1 + 5 - 2   # one difference, five new; FR-06 and EL-01 decided
    deviations = next(s for s in result["scores"] if s["area"] == "deviations")
    assert (deviations["found_in_record"], deviations["recorded_total"], deviations["flagged_total"]) == (2, 5, 7)
    assert deviations["valid"] == 1 + 1 and deviations["pending"] == 4


def test_a_changed_item_makes_its_decision_stale(client, confirmed: str, manager, published_data_root: Path, tmp_path: Path):
    from tests.triangulation import add_doc

    assert _decide(client, manager, confirmed, "FR-06").status_code == 200
    assert _decide(client, manager, confirmed, "EL-01").status_code == 200
    # A bureau rank of 7 turns EL-02 into a deviation: the record now agrees on it.
    add_doc(published_data_root, confirmed, "commercial_bureau_report", {"company_name": "Kestrel", "credit_rank": "7"})
    items = _items(_get(client, manager, confirmed))
    assert items["EL-02"]["status"] == "agree"
    assert not items["FR-06"]["adjudication"]["stale"]
    # A re-imported record that now says 90 days changes FR-06: the earlier decision is stale.
    _import(published_data_root, confirmed, tmp_path, "second.json", values={"FR-06": "90 days"})
    assert client.post(f"/api/cases/{confirmed}/reference/confirm", headers=manager).status_code == 200
    result = _get(client, manager, confirmed)
    items = _items(result)
    assert items["FR-06"]["status"] == "agree" and items["FR-06"]["adjudication"]["stale"]
    assert not items["EL-01"]["adjudication"]["stale"]
    deviations = next(s for s in result["scores"] if s["area"] == "deviations")
    # Three agree (FR-05, FR-06, EL-02) plus EL-01 upheld; FR-06's stale decision is not counted.
    assert (deviations["found_in_record"], deviations["valid"]) == (3, 4)


def test_adjudications_never_change_the_appraisal(client, confirmed: str, manager):
    analyst = sign_in(client, ANALYST)
    paths = ["policy", "approving-authority", "cam", "pd-note"]

    def snapshot():
        out = {}
        for p in paths:
            body = client.get(f"/api/cases/{confirmed}/{p}", headers=analyst).json()
            body.pop("generated_at", None)
            out[p] = json.dumps(body, sort_keys=True)
        return out

    before = snapshot()
    for key, verdict in (("FR-06", "valid"), ("EL-01", "not_valid"), ("DOC-02", "valid")):
        assert _decide(client, manager, confirmed, key, verdict).status_code == 200
    assert snapshot() == before


def test_without_a_record_the_comparison_is_empty(client, published_data_root: Path, manager):
    case_id = _case(client, published_data_root)
    result = _get(client, manager, case_id)
    assert result["record"] is None and result["items"] == [] and result["scores"] == []


def test_the_comparison_is_for_the_reviewer_only(client, confirmed: str):
    for email in (RM, ANALYST):
        headers = sign_in(client, email)
        assert client.get(f"/api/cases/{confirmed}/comparison", headers=headers).status_code == 403
        assert _decide(client, headers, confirmed, "FR-06").status_code == 403


def test_the_importer_is_recorded_and_the_reviewer_differs(client, confirmed: str, manager):
    record = _get(client, manager, confirmed)["record"]
    assert record["imported_by"] == IMPORTER and record["confirmed_by"] == "meenal-kulkarni"


def test_the_matrix_on_the_records_own_deviations_is_its_own_lookup(client, published_data_root: Path, tmp_path: Path,
                                                                  manager):
    # A record with no deviations: on its own terms the matrix asks only for the amount authority.
    case_id = _case(client, published_data_root)
    _import(published_data_root, case_id, tmp_path, deviations_recorded=False, deviations=[])
    item = _items(_get(client, manager, case_id), "approving_authority")["approval"]
    assert item["required"]["required"]["key"] == "zonal_credit_committee"
    assert item["authority_on_record_deviations"]["key"] == "regional_credit_head"


def test_a_recorded_key_the_matrix_no_longer_has_is_not_in_the_matrix(client, confirmed: str, manager, monkeypatch):
    real = reader.load_approval_matrix

    def renamed(root):
        m = real(root)
        rename = {a.key: f"{a.key}_v2" for a in m.authorities}
        return m.model_copy(update={
            "authorities": [a.model_copy(update={"key": rename[a.key]}) for a in m.authorities],
            "bands": {k: [b.model_copy(update={"authority": rename[b.authority]}) for b in v] for k, v in m.bands.items()},
            "deviations": [r.model_copy(update={"at_least": rename.get(r.at_least) if r.at_least else None})
                           for r in m.deviations],
        })

    monkeypatch.setattr(reader, "load_approval_matrix", renamed)
    item = _items(_get(client, manager, confirmed), "approving_authority")["approval"]
    assert item["status"] == "differ" and item["notes"] == ["not_in_matrix"]


def test_the_analyst_never_reads_the_reviewers_decisions_in_the_audit_trail(client, confirmed: str, manager):
    assert _decide(client, manager, confirmed, "FR-06", "valid", "Record rounds the cycle up").status_code == 200

    def adjudicated(headers: dict) -> list[dict]:
        page = client.get(f"/api/audit?case_id={confirmed}", headers=headers).json()
        return [e["detail"] for e in page["entries"] if e["action"] == "comparison.adjudicated"]

    assert adjudicated(sign_in(client, ANALYST)) == [{}]
    seen = adjudicated(manager)
    assert seen[0]["snapshot"]["record_text"] == "92 days" and seen[0]["reason"] == "Record rounds the cycle up"
