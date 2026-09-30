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
    assert kinds == {"finding", "deviation", "query"}
    finding = next(i for i in cam["summary"] if i["kind"] == "finding" and "ASHWOOD" in i["text"])
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
