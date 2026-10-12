"""The draft CAM (FRD F-23, TC-28)."""

from pathlib import Path

from fastapi.testclient import TestClient

from engine import db, pipeline
from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.test_pd_note import _case


def _cam(client: TestClient, headers: dict, root: Path, case_id: str) -> dict:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()
    response = client.get(f"/api/cases/{case_id}/cam", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_tc28_sections_follow_the_configured_list(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    assert cam["interim_template"] is True
    assert [s["id"] for s in cam["sections"]] == [
        "borrower", "proposal", "promoters", "financials", "working_capital", "banking", "obligations",
        "verification", "policy", "documentation",
    ]


def test_every_figure_in_the_memo_is_cited(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    sections = {s["id"]: s for s in cam["sections"]}
    table = sections["financials"]["table"]
    assert table and table["rows"]
    for row in table["rows"]:
        for cell in row[1:]:
            if cell["text"] != "—":
                assert cell["citations"], row[0]["text"]
    ob = [p for p in sections["obligations"]["paragraphs"] if "ASHWOOD FINSERV" in p["text"]]
    assert ob and all(p["citations"] for p in ob)
    wc = sections["working_capital"]
    assert wc["table"] and "eligible bank finance" in wc["paragraphs"][1]["text"]


def test_tc28_the_memo_ends_in_the_summary_and_an_empty_recommendation(
    client: TestClient, published_data_root: Path
):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    kinds = {i["kind"] for i in cam["summary"]}
    assert kinds == {"finding", "deviation", "query", "unassessed"}
    finding = next(i for i in cam["summary"] if i["kind"] == "finding" and "AAACK9876Q" in i["text"])
    assert finding["severity"] == "serious" and finding["citations"]
    assert cam["recommendation_title"] == "Recommendation" and cam["recommendation"] == ""


def test_the_same_case_gives_the_same_memo(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    assert _cam(client, analyst, published_data_root, case_id) == _cam(client, analyst, published_data_root, case_id)


def test_an_empty_case_still_drafts(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    assert next(s for s in cam["sections"] if s["id"] == "financials")["empty"] == "Nothing on file yet."


def test_the_cam_needs_the_outputs_permission(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/cam", headers=rm).status_code == 403


def _with_vintage(client: TestClient, analyst: dict, root: Path, incorporated: str = "2024-06-01") -> str:
    from tests.triangulation import add_doc

    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "certificate_of_incorporation", {"date_of_incorporation": incorporated})
    return case_id


def test_the_summary_lists_exactly_the_policy_deviations(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _with_vintage(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    norms = client.get(f"/api/cases/{case_id}/policy", headers=analyst).json()["norms"]
    deviations = {n["id"]: n for n in norms if n["outcome"] == "deviation"}
    items = [i for i in cam["summary"] if i["kind"] == "deviation"]
    assert {i["ref"] for i in items} == set(deviations)
    for i in items:
        n = deviations[i["ref"]]
        assert i["text"].startswith(n["category_label"]) and n["actual_text"] in i["text"] and n["required"] in i["text"]
        if i["ref"] != "DOC-01":
            assert i["citations"], i["ref"]
    applicable = [n for n in norms if n["outcome"] != "not_applicable"]
    counts = {o: sum(1 for n in applicable if n["outcome"] == o) for o in ("deviation", "cannot_evaluate", "pass")}
    policy = next(s for s in cam["sections"] if s["id"] == "policy")
    assert policy["paragraphs"][0]["text"] == (
        f"{len(applicable)} applicable norm(s) on the FY 2025-26 statements: {counts['deviation']} deviation(s), "
        f"{counts['cannot_evaluate']} could not be assessed, {counts['pass']} passed.")


def test_unassessed_norms_are_summarised(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    cam = _cam(client, analyst, published_data_root, case_id)
    unassessed = {i["ref"]: i["text"] for i in cam["summary"] if i["kind"] == "unassessed"}
    assert unassessed["EL-01"] == "Business vintage could not be assessed: Years in business not on file."
    assert "EL-02" in unassessed


def test_the_memo_says_the_norms_are_interim(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    policy = next(s for s in _cam(client, analyst, published_data_root, case_id)["sections"] if s["id"] == "policy")
    assert any("interim proposal" in p["text"] for p in policy["paragraphs"])


def test_the_vintage_sentence_never_rounds_up(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = _with_vintage(client, analyst, published_data_root, "2023-10-17")
    borrower = next(s for s in _cam(client, analyst, published_data_root, case_id)["sections"] if s["id"] == "borrower")
    assert any("in business for 2.9 years" in p["text"] for p in borrower["paragraphs"])
