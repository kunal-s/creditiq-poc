"""CAM templates (F-23; FRD decision C.4-12): the configured default, templates analysts make
(bank-wide, never edited in place), and the one each appraisal's memo follows."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.triangulation import audited

TEMPLATE = {
    "name": "Short memo",
    "description": "Three sections for renewals.",
    "sections": [
        {"title": "The borrower", "purpose": "Who they are.", "parts": ["borrower_profile", "promoters"]},
        {"title": "Numbers", "parts": ["financial_performance", "policy"]},
        {"title": "Analyst's note", "purpose": "Anything else credit should know.", "parts": []},
    ],
}


@pytest.fixture
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _case(client: TestClient, headers: dict, root: Path) -> str:
    case_id = make_case(client, headers, root)
    audited(root, case_id)
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()
    return case_id


def _create(client: TestClient, headers: dict, body: dict | None = None):
    return client.post("/api/cam/templates", json=body or TEMPLATE, headers=headers)


def test_the_default_comes_first_with_the_parts_a_template_may_draw_on(client: TestClient, analyst,
                                                                         published_data_root: Path):
    listing = client.get("/api/cam/templates", headers=analyst).json()
    [default] = listing["templates"]
    assert default["id"] == "default" and default["default"] is True
    assert [s["title"] for s in default["sections"]][:2] == ["Borrower and Group Profile",
                                                              "Facility Requested and Purpose"]
    assert len(listing["parts"]) == 12 and {"kind": "turnover", "id": "turnover"}.items() <= listing["parts"][6].items()
    assert listing["closing"] == ["Risk Assessment and Rating", "Recommendation"]


def test_an_analyst_makes_a_template_kept_bank_wide_with_who_and_when(client: TestClient, analyst,
                                                                       published_data_root: Path):
    made = _create(client, analyst)
    assert made.status_code == 201, made.text
    t = made.json()
    assert t["name"] == "Short memo" and t["created_by"] == "ananya-krishnan" and t["created_at"]
    assert [(s["title"], s["parts"]) for s in t["sections"]] == [
        ("The borrower", ["borrower_profile", "promoters"]), ("Numbers", ["financial_performance", "policy"]),
        ("Analyst's note", [])]
    # Section ids never take a part's id, so a link to a part still finds it.
    assert [s["id"] for s in t["sections"]] == ["the_borrower", "numbers", "analyst_s_note"]
    assert [x["name"] for x in client.get("/api/cam/templates", headers=analyst).json()["templates"]] == [
        "Default template", "Short memo"]


@pytest.mark.parametrize("change,status,message", [
    ({"name": "ab"}, 422, "at least 3 characters"),
    ({"sections": []}, 422, "between 1 and 15"),
    ({"sections": [{"title": " ", "parts": []}]}, 422, "needs a title"),
    ({"sections": [{"title": "A", "parts": ["nowhere"]}]}, 422, "Unknown part"),
    ({"sections": [{"title": "A", "parts": ["turnover"]}, {"title": "B", "parts": ["turnover"]}]}, 422,
     "one section only"),
])
def test_a_template_is_refused_with_why(client: TestClient, analyst, published_data_root: Path, change, status,
                                         message):
    response = _create(client, analyst, {**TEMPLATE, **change})
    assert response.status_code == status and message in response.json()["detail"]


def test_a_name_is_used_once(client: TestClient, analyst, published_data_root: Path):
    _create(client, analyst)
    response = _create(client, analyst, {**TEMPLATE, "name": "short MEMO"})
    assert response.status_code == 409


def test_an_appraisal_follows_the_template_chosen_for_it_and_its_edits_survive_a_switch(
        client: TestClient, analyst, published_data_root: Path):
    case_id = _case(client, analyst, published_data_root)
    other = make_case(client, analyst, published_data_root, borrower="Another Works Pvt Ltd")
    tid = _create(client, analyst).json()["id"]
    client.put(f"/api/cases/{case_id}/cam/sections/profile/words", json={"paragraphs": ["My words."]},
               headers=analyst)
    cam = client.put(f"/api/cases/{case_id}/cam/template", json={"template_id": tid}, headers=analyst).json()
    assert (cam["template_id"], cam["template_name"]) == (tid, "Short memo")
    assert [s["title"] for s in cam["sections"]] == ["The borrower", "Numbers", "Analyst's note"]
    # The closing sections follow, numbered after the template's own.
    assert (cam["summary_number"], cam["recommendation_number"]) == (4, 5)
    # A section with no parts is left for the analyst to write; a person's words fill it.
    note = cam["sections"][2]
    assert note["blank"] is True and note["blocks"] == [] and note["empty"] == "For the analyst to write."
    cam = client.put(f"/api/cases/{case_id}/cam/sections/analyst_s_note/words",
                     json={"paragraphs": ["Renewal on the same terms."]}, headers=analyst).json()
    assert [b["paragraph"]["text"] for b in cam["sections"][2]["blocks"]] == ["Renewal on the same terms."]
    # Another case keeps the default.
    assert client.get(f"/api/cases/{other}/cam", headers=analyst).json()["template_id"] == "default"
    # Back to the default: the section edited there reads as it was left.
    cam = client.put(f"/api/cases/{case_id}/cam/template", json={"template_id": "default"}, headers=analyst).json()
    profile = next(s for s in cam["sections"] if s["id"] == "profile")
    assert cam["template_id"] == "default" and profile["review"]["paragraphs"] == ["My words."]
    conn = db.connect(published_data_root)
    try:
        actions = [r["action"] for r in conn.execute(
            "SELECT action FROM decision_log WHERE action LIKE 'cam.template%' ORDER BY rowid")]
    finally:
        conn.close()
    assert actions == ["cam.template_created", "cam.template_chosen", "cam.template_chosen"]


def test_the_pd_note_numbers_sections_by_the_template_the_case_follows(client: TestClient, analyst,
                                                                         published_data_root: Path):
    case_id = _case(client, analyst, published_data_root)
    tid = _create(client, analyst).json()["id"]
    client.put(f"/api/cases/{case_id}/cam/template", json={"template_id": tid}, headers=analyst)
    note = client.get(f"/api/cases/{case_id}/pd-note", headers=analyst)
    assert note.status_code == 200
    statuses = {q["status"] for q in note.json()["questions"] if q["source"] == "observation"}
    assert statuses <= {"section 1", "section 2", "section 3", None}


def test_an_unknown_template_is_refused_and_the_rm_may_not_choose(client: TestClient, analyst,
                                                                   published_data_root: Path):
    case_id = _case(client, analyst, published_data_root)
    response = client.put(f"/api/cases/{case_id}/cam/template", json={"template_id": "nowhere"}, headers=analyst)
    assert response.status_code == 404
    rm = sign_in(client, RM)
    assert client.put(f"/api/cases/{case_id}/cam/template", json={"template_id": "default"},
                      headers=rm).status_code == 403
    assert _create(client, rm).status_code == 403
