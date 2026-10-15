"""The settings an Administrator edits on the Administration screen (F-00.6): tolerances, norm
thresholds, cross-check rules and the approval matrix, published as a new version from the app.
Every name is fictional."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cli, db, pipeline
from engine.configstore import reader
from tests.conftest import ANALYST, MANAGER, RM, make_case, sign_in
from tests.triangulation import bank, gstr, months

ADMIN = "nikhil.sawant@rblbank.com"
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]


@pytest.fixture()
def admin(client: TestClient) -> dict:
    return sign_in(client, ADMIN)


def _settings(client: TestClient, headers: dict) -> dict:
    response = client.get("/api/admin/settings", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _publish(client: TestClient, headers: dict, changes: dict, note: str = "Tolerances agreed with credit policy"):
    return client.post("/api/admin/settings/publish", json={"note": note, "changes": changes}, headers=headers)


def _gst_and_bank_four_percent_apart(client: TestClient, headers: dict, root: Path) -> str:
    """GST INR 12.00 cr and INR 11.52 cr banked over FY 2025-26: 4% apart, a fail at 1%, a pass at 10%."""
    case_id = make_case(client, headers, root, borrower="Kestrel Tools Pvt Ltd")
    for ym in months((2025, 4), 12):
        gstr(root, case_id, f"{MONTH_NAMES[int(ym[5:]) - 1]} {ym[:4]}", 1_000_000)
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 960_000}
                         for ym in months((2025, 4), 12)], start="2025-04-01", end="2026-03-31")
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()
    return case_id


def _to02(client: TestClient, headers: dict, case_id: str) -> dict:
    findings = client.get(f"/api/cases/{case_id}/findings", headers=headers).json()
    return next(f for f in findings if f["rule_id"] == "TO-02")


def test_the_administrator_signs_in_to_administration_only(client):
    headers = sign_in(client, ADMIN)
    me = client.get("/api/auth/session", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["navGroups"] == ["administration", "help"]
    assert client.get("/api/cases", headers=headers).status_code == 403


def test_the_settings_are_read_as_published(client, admin):
    settings = _settings(client, admin)
    tolerances = {t["key"]: t for t in settings["tolerances"]}
    assert (tolerances["turnover_variance"]["value"], tolerances["turnover_variance"]["unit"]) == (1, "%")
    assert tolerances["turnover_variance"]["rules"][:3] == ["TO-01", "TO-02", "TO-03"]
    assert tolerances["name_match"]["value"] == 0.9
    ratios = {r["key"]: r for r in settings["ratios"]}
    assert (ratios["current-ratio"]["kind"], ratios["current-ratio"]["acceptable"], ratios["current-ratio"]["norms"]) == (
        "min", 1.2, ["FR-01"])
    assert {n["id"] for n in settings["norms"]} >= {"EL-01", "EL-05", "DOC-01"}
    assert not any(n["id"].startswith("FR-") for n in settings["norms"]), "ratio norms change through their ratio"
    rules = {r["id"]: r for r in settings["rules"]}
    assert len(rules) == 30 and rules["BR-01"]["enabled"] is False and rules["ID-01"]["blocking"] is True
    matrix = settings["matrix"]
    assert [p["key"] for p in matrix["products"]] == ["working_capital", "term", "non_fund"]
    assert matrix["products"][0]["bands"][-1]["up_to_inr"] is None
    assert settings["origin"] == "cli"
    # Anyone who reads administration sees them; an RM does not.
    assert client.get("/api/admin/settings", headers=sign_in(client, ANALYST)).status_code == 200
    assert client.get("/api/admin/settings", headers=sign_in(client, RM)).status_code == 403


@pytest.mark.parametrize("email", [ANALYST, MANAGER, RM])
def test_only_the_administrator_may_preview_or_publish(client, email):
    headers = sign_in(client, email)
    changes = {"tolerances": {"turnover_variance": 2}}
    assert client.post("/api/admin/settings/preview", json=changes, headers=headers).status_code == 403
    assert _publish(client, headers, changes).status_code == 403


def test_a_preview_lists_each_change_and_publishes_nothing(client, admin, published_data_root):
    before = reader.published_version(published_data_root)["version"]
    settings = _settings(client, admin)
    bands = [dict(b) for b in settings["matrix"]["products"][0]["bands"]]
    bands[0]["up_to_inr"] = 25_000_000
    response = client.post("/api/admin/settings/preview", headers=admin, json={
        "tolerances": {"turnover_variance": 2, "name_match": 0.9},
        "ratios": {"current-ratio": {"acceptable": 1.3}},
        "norms": {"EL-05": 25},
        "rules": {"TO-04": {"severity": "moderate", "blocking": False}},
        "bands": {"working_capital": bands},
        "deviations": {"documentation": {"at_least": "zonal_credit_committee"}},
    })
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["problems"] == []
    assert [(c["section"], c["item"], c["field"], c["before"], c["after"]) for c in preview["changes"]] == [
        ("tolerances", "turnover_variance", "value", 1, 2),
        ("policy", "current-ratio", "acceptable", 1.2, 1.3),
        ("policy", "EL-05", "threshold", 20, 25),
        # The turnover method's requirement follows the norm: 30% less the 5% margin.
        ("policy", "working_capital", "turnover_requirement_pct", 25, 30),
        ("crosschecks", "TO-04", "severity", "mild", "moderate"),
        ("approval_matrix", "working_capital", "up_to_inr", 20_000_000, 25_000_000),
        ("approval_matrix", "documentation", "at_least", None, "Zonal Credit Committee"),
    ]
    first = preview["changes"][0]
    assert (first["label"], first["unit"]) == ("Turnover variance between sources", "%")
    # name_match 0.9 and blocking false are what is published already: not changes.
    assert reader.published_version(published_data_root)["version"] == before


def test_publishing_creates_a_version_from_the_app_and_reruns_every_case(client, admin, published_data_root):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _gst_and_bank_four_percent_apart(client, analyst, root)
    assert _to02(client, analyst, case_id)["outcome"] == "fail"
    before = reader.published_version(root)["version"]

    response = _publish(client, admin, {"tolerances": {"turnover_variance": 10}}, note="  Back to 10% for the pilot  ")
    assert response.status_code == 200, response.text
    published = response.json()
    assert published["version"] != before and published["cases_rerun"] == 1 and published["cases_failed"] == []
    assert [(c["item"], c["before"], c["after"]) for c in published["changes"]] == [("turnover_variance", 1, 10)]

    # The new version is in force, recorded as edited on the screen, with who and why.
    record = reader.published_version(root)
    assert (record["version"], record["origin"], record["author"], record["note"]) == (
        published["version"], "app", "Nikhil Sawant", "Back to 10% for the pilot")
    assert reader.load_tolerances(root).tolerances[0].value == 10
    newest = client.get("/api/config/versions", headers=admin).json()[0]
    assert (newest["current"], newest["origin"], newest["sections_changed"]) == (True, "app", ["tolerances"])
    assert _settings(client, admin)["origin"] == "app"
    # Every case re-ran under it: the same figures now pass.
    to02 = _to02(client, analyst, case_id)
    assert to02["outcome"] == "pass" and to02["explanation"] == "Variance 4.0% within 10%."
    # And the audit trail has it.
    entry = next(e for e in client.get("/api/audit", headers=admin).json()["entries"] if e["action"] == "config.published")
    assert entry["actor"] == "nikhil-sawant" and entry["case_id"] is None
    assert entry["detail"]["version"] == published["version"] and entry["detail"]["note"] == "Back to 10% for the pilot"


def test_a_rule_switched_off_on_the_screen_stops_running(client, admin, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root, borrower="Kestrel Tools Pvt Ltd")
    response = _publish(client, admin, {"rules": {"TO-04": {"enabled": False}}}, note="TO-04 paused")
    assert response.status_code == 200, response.text
    board = client.get(f"/api/cases/{case_id}/cross-verification", headers=analyst).json()
    assert board["run"]["rules"] == 23
    assert not any(i["finding"]["rule_id"] == "TO-04" for i in board["items"])


def test_policy_and_matrix_changes_reach_their_screens(client, admin):
    settings = _settings(client, admin)
    bands = [dict(b) for b in settings["matrix"]["products"][1]["bands"]]
    bands[0]["authority"] = "regional_credit_head"
    response = _publish(client, admin, {"norms": {"EL-01": 2}, "bands": {"term": bands}}, note="Vintage two years")
    assert response.status_code == 200, response.text
    policy = client.get("/api/config/policy", headers=admin).json()
    assert next(n for n in policy["norms"] if n["id"] == "EL-01")["threshold"] == 2
    matrix = client.get("/api/config/approval-matrix", headers=admin).json()
    assert matrix["bands"]["term"][0] == {"up_to_inr": 10_000_000, "authority": "regional_credit_head",
                                          "status": "provisional"}


def _bands(client, headers, mutate):
    bands = [dict(b) for b in _settings(client, headers)["matrix"]["products"][0]["bands"]]
    mutate(bands)
    return {"bands": {"working_capital": bands}}


@pytest.mark.parametrize("changes,problem", [
    ({"tolerances": {"name_match": 1.2}}, "Minimum name similarity to treat two names as one: give a similarity between 0.5 and 1."),
    ({"tolerances": {"turnover_variance": 150}}, "Turnover variance between sources: give a percentage between 0 and 100."),
    ({"tolerances": {"emi_min_occurrences": 2.5}}, "give a whole number, 0 or more."),
    ({"tolerances": {"cash_variance": 5}}, "There is no tolerance 'cash_variance'."),
    ({"ratios": {"current-ratio": {"marginal": 1.4}}}, "Current ratio: the marginal value cannot be above the acceptable one for a minimum."),
    ({"norms": {"FR-01": 1.5}}, "FR-01 takes its threshold from Current ratio: change it there."),
    ({"rules": {"XX-99": {"enabled": False}}}, "There is no cross-check 'XX-99'."),
    ({"deviations": {"documentation": {"at_least": "board"}}}, "there is no authority 'board'."),
    ({}, "Nothing has changed."),
    ({"tolerances": {"turnover_variance": 1}}, "Nothing has changed."),
])
def test_values_that_cannot_be_published_are_refused_with_the_reason(client, admin, published_data_root, changes,
                                                                     problem):
    before = reader.published_version(published_data_root)["version"]
    preview = client.post("/api/admin/settings/preview", json=changes, headers=admin).json()
    assert any(problem in p for p in preview["problems"]), preview
    response = _publish(client, admin, changes)
    assert response.status_code == 422
    assert any(problem in p for p in response.json()["detail"]["problems"])
    assert reader.published_version(published_data_root)["version"] == before


@pytest.mark.parametrize("mutate,problem", [
    (lambda b: b.pop(), "Working capital: give all 5 amount bands."),
    (lambda b: b[1].update(up_to_inr=10_000_000), "Working capital: the amount bands must rise from one to the next."),
    (lambda b: b[-1].update(up_to_inr=900_000_000), "every band but the last needs an upper amount; the last is open."),
    (lambda b: b[0].update(authority="board"), "Working capital: there is no authority 'board'."),
])
def test_amount_bands_that_cannot_be_published_are_refused(client, admin, mutate, problem):
    preview = client.post("/api/admin/settings/preview", json=_bands(client, admin, mutate), headers=admin).json()
    assert problem in "; ".join(preview["problems"]), preview


def test_a_note_is_required(client, admin):
    response = _publish(client, admin, {"tolerances": {"turnover_variance": 2}}, note="  ok ")
    assert response.status_code == 422
    assert response.json()["detail"]["problems"][0] == "A note of at least 3 characters is required."


def test_a_publish_from_the_files_does_not_undo_screen_edits_unnoticed(client, admin, published_data_root, capsys):
    root = published_data_root
    assert _publish(client, admin, {"tolerances": {"turnover_variance": 2}}).status_code == 200
    edited = reader.published_version(root)["version"]
    args = ["config", "publish", "--author", "test", "--no-rerun", "--data-root", str(root)]
    assert cli.main(args) == 1
    assert "edited on the Administration screen" in capsys.readouterr().err
    assert reader.published_version(root)["version"] == edited
    # Replacing them is a deliberate choice.
    assert cli.main([*args, "--discard-app-edits"]) == 0
    record = reader.published_version(root)
    assert record["origin"] == "cli" and reader.load_tolerances(root).tolerances[0].value == 1
    # Once the files are published again, nothing is at risk.
    assert cli.main(args) == 0
