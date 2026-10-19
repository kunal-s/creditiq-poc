"""The draft CAM's review (F-23): a section in a person's words, a copilot redraft kept by a person,
a figure overridden, data asked for; each kept with who and when, laid over the engine's draft."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cam_copilot, db, pipeline
from engine.configstore import reader
from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.triangulation import audited


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


def _cam(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/cam", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _section(cam: dict, section_id: str) -> dict:
    return next(s for s in cam["sections"] if s["id"] == section_id)


def _paragraphs(section: dict) -> list[dict]:
    return [b["paragraph"] for b in section["blocks"] if b["kind"] == "paragraph"]


def _log(root: Path, case_id: str) -> list[str]:
    conn = db.connect(root)
    try:
        return [r["action"] for r in conn.execute(
            "SELECT action FROM decision_log WHERE case_id = ? AND action LIKE 'cam.%' ORDER BY rowid", (case_id,))]
    finally:
        conn.close()


def test_a_section_in_a_persons_words_keeps_each_paragraphs_citations_and_can_be_restored(
        client: TestClient, analyst, published_data_root: Path):
    case_id = _case(client, analyst, published_data_root)
    drafted = _paragraphs(_section(_cam(client, analyst, case_id), "analysis"))
    assert drafted and all(p["citations"] for p in drafted[:1])
    words = [f"In my words, paragraph {i + 1}." for i in range(len(drafted))]
    response = client.put(f"/api/cases/{case_id}/cam/sections/analysis/words", json={"paragraphs": words},
                          headers=analyst)
    assert response.status_code == 200, response.text
    section = _section(response.json(), "analysis")
    assert section["review"]["state"] == "edited" and section["review"]["by"] == "ananya-krishnan"
    assert [p["text"] for p in _paragraphs(section)] == words
    # Paragraph n keeps the citations of the drafted paragraph n.
    assert [p["citations"] for p in _paragraphs(section)] == [p["citations"] for p in drafted]
    # Back to the engine's draft.
    response = client.delete(f"/api/cases/{case_id}/cam/sections/analysis/words", headers=analyst)
    section = _section(response.json(), "analysis")
    assert section["review"]["state"] == "machine"
    assert [p["text"] for p in _paragraphs(section)] == [p["text"] for p in drafted]
    assert _log(published_data_root, case_id) == ["cam.edited", "cam.restored"]


def test_the_risk_assessment_and_the_recommendation_take_a_persons_words(
        client: TestClient, analyst, published_data_root: Path):
    case_id = _case(client, analyst, published_data_root)
    client.put(f"/api/cases/{case_id}/cam/sections/summary/words", json={"paragraphs": ["The risk is revenue quality."]},
               headers=analyst)
    cam = client.put(f"/api/cases/{case_id}/cam/sections/recommendation/words",
                     json={"paragraphs": ["Recommended for sanction.", "On conditions."]}, headers=analyst).json()
    assert cam["summary_review"]["paragraphs"] == ["The risk is revenue quality."]
    assert cam["recommendation"] == "Recommended for sanction.\n\nOn conditions."
    assert cam["recommendation_review"]["state"] == "edited"


def test_an_override_is_listed_under_its_section_with_the_value_drafted_and_the_reason(
        client: TestClient, analyst, published_data_root: Path):
    case_id = _case(client, analyst, published_data_root)
    body = {"figure": "Assessed drawing power", "original": "INR 18.50 cr", "value": "INR 15.80 cr",
            "reason": "Sized on independently evidenced turnover"}
    cam = client.post(f"/api/cases/{case_id}/cam/sections/facility/overrides", json=body, headers=analyst).json()
    section = _section(cam, "facility")
    [override] = section["review"]["overrides"]
    assert {k: override[k] for k in body} == body and override["by"] == "ananya-krishnan" and override["at"]
    table = [b["table"] for b in section["blocks"] if b["kind"] == "table"][-1]
    assert table["title"] == "Figures overridden by the analyst"
    assert [c["text"] for c in table["rows"][0][:4]] == ["Assessed drawing power", "INR 18.50 cr", "INR 15.80 cr",
                                                         "Sized on independently evidenced turnover"]
    # Every field is needed, and a reason of at least 3 characters.
    for missing in ("figure", "reason"):
        response = client.post(f"/api/cases/{case_id}/cam/sections/facility/overrides",
                               json={**body, missing: " "}, headers=analyst)
        assert response.status_code == 422
    assert _log(published_data_root, case_id) == ["cam.override"]


def test_data_asked_for_from_a_section_goes_on_the_query_list(client: TestClient, analyst, published_data_root: Path):
    case_id = _case(client, analyst, published_data_root)
    text = "Please provide the debtors' ageing as at 31 March 2026."
    cam = client.post(f"/api/cases/{case_id}/cam/sections/conduct/requests", json={"text": text},
                      headers=analyst).json()
    assert [r["text"] for r in _section(cam, "conduct")["review"]["requests"]] == [text]
    queries = client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
    asked = [q for q in queries if q["source_kind"] == "cam"]
    assert [(q["group"], q["text"]) for q in asked] == [("clarifications", text)]


def test_an_unknown_section_is_refused_and_the_rm_may_not_review(client: TestClient, analyst,
                                                                  published_data_root: Path):
    case_id = _case(client, analyst, published_data_root)
    response = client.put(f"/api/cases/{case_id}/cam/sections/nowhere/words", json={"paragraphs": ["x"]},
                          headers=analyst)
    assert response.status_code == 404
    rm = sign_in(client, RM)
    response = client.put(f"/api/cases/{case_id}/cam/sections/analysis/words", json={"paragraphs": ["x"]}, headers=rm)
    assert response.status_code == 403


def test_the_copilot_is_unavailable_without_its_key(client: TestClient, analyst, published_data_root: Path,
                                                     monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    case_id = _case(client, analyst, published_data_root)
    assert _cam(client, analyst, case_id)["copilot"] is False
    response = client.post(f"/api/cases/{case_id}/cam/sections/analysis/regenerate", json={}, headers=analyst)
    assert response.status_code == 503


def test_a_copilot_redraft_is_recorded_replayed_kept_only_when_kept_and_never_brings_in_a_figure(
        client: TestClient, analyst, published_data_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls: list[dict] = []

    def answer(cfg, body):
        calls.append(body)
        user = body["messages"][1]["content"]
        lines = [line.split(". ", 1)[1] for line in user.splitlines() if line[:1].isdigit() and ". " in line]
        return [f"Redrafted: {line}" for line in lines]

    monkeypatch.setattr(cam_copilot, "_call", answer)
    case_id = _case(client, analyst, published_data_root)
    assert _cam(client, analyst, case_id)["copilot"] is True
    cfg = reader.load_cam(published_data_root).copilot
    first = client.post(f"/api/cases/{case_id}/cam/sections/analysis/regenerate",
                        json={"instruction": "Shorter."}, headers=analyst)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["recorded"] is False and result["model"] == cfg.model
    assert all(p.startswith("Redrafted: ") for p in result["paragraphs"])
    # Only the configured sampling parameters are sent.
    assert {k: calls[0][k] for k in ("temperature", "seed")} == {"temperature": cfg.temperature, "seed": cfg.seed}
    # The same request is answered from the recording, not asked again.
    again = client.post(f"/api/cases/{case_id}/cam/sections/analysis/regenerate",
                        json={"instruction": "Shorter."}, headers=analyst).json()
    assert again["recorded"] is True and again["paragraphs"] == result["paragraphs"] and len(calls) == 1
    # Nothing is kept until a person keeps it.
    assert _section(_cam(client, analyst, case_id), "analysis")["review"]["state"] == "machine"
    kept = client.put(f"/api/cases/{case_id}/cam/sections/analysis/words",
                      json={"paragraphs": result["paragraphs"], "source": "copilot", "model": cfg.model},
                      headers=analyst).json()
    review = _section(kept, "analysis")["review"]
    assert review["state"] == "regenerated" and review["model"] == cfg.model
    # An answer that brings in a figure the section does not hold is refused.
    monkeypatch.setattr(cam_copilot, "_call", lambda cfg, body: ["Turnover is INR 987654321.55 cr."])
    response = client.post(f"/api/cases/{case_id}/cam/sections/analysis/regenerate",
                           json={"instruction": "Different."}, headers=analyst)
    assert response.status_code == 422 and "figures the section does not hold" in response.json()["detail"]
