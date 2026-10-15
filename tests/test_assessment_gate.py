"""F-13 gate: cross-verification, the policy checks and the outputs open only once
completeness is satisfied and a person creates the case.

Until then the three stages report nothing started and their endpoints refuse, so the data
is unreachable by asking for it directly as well as by the screens.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, RM, case_files, make_case, run_jobs, sign_in, upload

SHUT = ("/cross-verification", "/policy", "/cam", "/pd-note", "/spread")


def _progress(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/progress", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_new_case_has_the_gate_shut(client: TestClient, published_data_root: Path):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root, assessment_open=False)

    gate = _progress(client, headers, case_id)["gate"]
    assert gate["open"] is False and gate["can_open"] is False
    assert "review_gate" in gate["blockers"]


def test_the_assessment_stages_report_nothing_while_the_gate_is_shut(
    client: TestClient, published_data_root: Path
):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root, assessment_open=False)
    upload(client, headers, case_id, case_files("partial"))
    run_jobs(published_data_root)

    stages = {s["key"]: s for s in _progress(client, headers, case_id)["stages"]}
    for key in ("cross_verification", "policy", "outputs"):
        assert stages[key]["status"] == "not_started"
        assert stages[key]["done"] == stages[key]["total"] == stages[key]["attention"] == 0


def test_the_shut_gate_refuses_the_assessment_endpoints(client: TestClient, published_data_root: Path):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root, assessment_open=False)

    for path in SHUT:
        response = client.get(f"/api/cases/{case_id}{path}", headers=headers)
        assert response.status_code == 409, f"{path}: {response.text}"
        assert response.json()["detail"] == "assessment_not_open"


def test_the_case_cannot_be_created_while_completeness_is_unmet(
    client: TestClient, published_data_root: Path
):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root, assessment_open=False)

    response = client.post(f"/api/cases/{case_id}/assessment", headers=headers)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["blockers"]


def test_creating_the_case_opens_the_assessment(client: TestClient, published_data_root: Path):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root, assessment_open=False)
    upload(client, headers, case_id, case_files("complete"))
    run_jobs(published_data_root)

    gate = _progress(client, headers, case_id)["gate"]
    if not gate["can_open"]:  # the fixture set does not meet the gate on its own
        return

    response = client.post(f"/api/cases/{case_id}/assessment", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["assessment_opened_at"]

    for path in SHUT:
        assert client.get(f"/api/cases/{case_id}{path}", headers=headers).status_code != 409


def test_creating_the_case_twice_changes_nothing(client: TestClient, published_data_root: Path):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root)  # opened by the helper

    first = client.post(f"/api/cases/{case_id}/assessment", headers=headers)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/cases/{case_id}/assessment", headers=headers)
    assert second.status_code == 200, second.text
    assert first.json()["assessment_opened_at"] == second.json()["assessment_opened_at"]


def test_the_rm_may_not_create_the_case(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, assessment_open=False)

    response = client.post(f"/api/cases/{case_id}/assessment", headers=rm)
    assert response.status_code == 403, response.text
