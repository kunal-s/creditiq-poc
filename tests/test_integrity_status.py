"""F-07A: what a file's integrity checks come to, and a person's conclusion on it.

The status is said once, in the engine, from the file's stored results and the
published configuration. Incomplete is never passed, an observation is never a
signal, a failure is never missing data, and the reviewer's decision is never
set by the checks.
"""

from __future__ import annotations

from engine.contracts.ingest import IngestIntegrityFinding
from engine.integrity_status import assess

CHECKS = {
    "PDF_INCREMENTAL_UPDATE": {"context": False},
    "PDF_COVERED_TEXT": {"context": False},
    "PDF_ID_PAIR_DIFFERS": {"context": True},
    "PDF_WRITTEN_BY_EDITING_TOOL": {"context": True, "prompts_review": True},
}


def _f(code, status="pass", context=False, failed=False):
    return IngestIntegrityFinding(code=code, family="layout", status=status, finding="x", tier="T1",
                                  impact="high", context=context,
                                  method={"execution_failed": "true"} if failed else {})


def _row(recommendation="no_notable_issue", status="registered", reason_code=None, content_type="application/pdf"):
    return {"status": status, "reason_code": reason_code, "integrity_recommendation": recommendation,
            "content_type": content_type}


ALL_PASS = [_f("PDF_INCREMENTAL_UPDATE"), _f("PDF_COVERED_TEXT"), _f("PDF_ID_PAIR_DIFFERS", context=True),
            _f("PDF_WRITTEN_BY_EDITING_TOOL", context=True)]


def test_every_configured_check_ran_and_nothing_stands_out_is_passed():
    s = assess(_row(), ALL_PASS, CHECKS)
    assert s.state == "passed" and s.passed == 4 and not s.pending


def test_a_configured_check_that_did_not_run_is_incomplete_never_passed():
    s = assess(_row(), [f for f in ALL_PASS if f.code != "PDF_COVERED_TEXT"], CHECKS)
    assert s.state == "incomplete" and s.pending == ["PDF_COVERED_TEXT"]


def test_a_check_the_older_configuration_did_not_name_is_pending_never_passed():
    """The document service reports a check its configuration left out as not run; under an
    older published configuration that would otherwise read as a pass."""
    old = {k: v for k, v in CHECKS.items() if k != "PDF_COVERED_TEXT"}
    not_run = IngestIntegrityFinding(code="PDF_COVERED_TEXT", family="layout", status="unable_to_determine",
                                     finding="Not run", tier="T1", impact="low", context=True,
                                     method={"not_configured": "true"})
    s = assess(_row(), [f for f in ALL_PASS if f.code != "PDF_COVERED_TEXT"] + [not_run], old)
    assert s.state == "incomplete"
    assert s.pending == ["PDF_COVERED_TEXT"] and s.unconfigured == ["PDF_COVERED_TEXT"]
    assert s.not_applicable == 0 and s.informational == []


def test_a_design_tool_is_an_observation_that_recommends_review_never_a_signal():
    found = [*ALL_PASS[:3], _f("PDF_WRITTEN_BY_EDITING_TOOL", "warning", context=True)]
    s = assess(_row(), found, CHECKS)
    assert s.state == "review_recommended"
    assert s.informational == ["PDF_WRITTEN_BY_EDITING_TOOL"] and s.suspicious == []


def test_an_observation_not_configured_to_prompt_review_stays_passed():
    found = [*ALL_PASS[:2], _f("PDF_ID_PAIR_DIFFERS", "warning", context=True), ALL_PASS[3]]
    assert assess(_row(), found, CHECKS).state == "passed"


def test_the_routings_priority_and_high_risk_are_suspicious():
    found = [_f("PDF_INCREMENTAL_UPDATE"), _f("PDF_COVERED_TEXT", "review_required"), *ALL_PASS[2:]]
    s = assess(_row("needs_review_priority"), found, CHECKS)
    assert s.state == "suspicious" and s.suspicious == ["PDF_COVERED_TEXT"]
    assert assess(_row("high_risk_indicators"), found, CHECKS).state == "suspicious_high"


def test_a_check_that_could_not_run_is_failed_and_missing_data_is_not():
    no_id = [*ALL_PASS[:2], _f("PDF_ID_PAIR_DIFFERS", "unable_to_determine", context=True), ALL_PASS[3]]
    assert assess(_row(), no_id, CHECKS).state == "passed"
    broken = [ALL_PASS[0], _f("PDF_COVERED_TEXT", "unable_to_determine", failed=True), *ALL_PASS[2:]]
    s = assess(_row(), broken, CHECKS)
    assert s.state == "failed" and s.failed == ["PDF_COVERED_TEXT"]


def test_processing_that_stopped_is_failed_with_the_checks_it_never_reached_pending():
    s = assess(_row(status="exception", reason_code="processing_failed"), ALL_PASS[:1], CHECKS)
    assert s.state == "failed" and s.stopped and "PDF_COVERED_TEXT" in s.pending


def test_evidence_found_before_a_failure_still_shows_as_suspicious():
    found = [_f("PDF_COVERED_TEXT", "review_required")]
    s = assess(_row("needs_review_priority", status="exception", reason_code="processing_failed"), found, CHECKS)
    assert s.state == "suspicious"


def test_a_file_not_yet_read_and_a_file_that_is_not_a_pdf():
    assert assess(_row(None), [], CHECKS).state == "not_checked"
    assert assess(_row(None, content_type="image/png"), [], CHECKS).state == "not_applicable"


def test_a_person_records_a_conclusion_with_a_reason_and_it_settles_the_queue_item(client, published_data_root):
    import json

    from engine import db
    from engine.review_items import raise_item
    from tests.conftest import ANALYST, RM, fixture_file, make_case, sign_in, upload

    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    name = "heronbay certificate of incorporation.pdf"
    upload(client, rm, case_id, [(name, fixture_file(name))])
    conn = db.connect(published_data_root)
    try:
        file_id = conn.execute("SELECT id FROM files WHERE case_id = ?", (case_id,)).fetchone()["id"]
        conn.execute("UPDATE files SET integrity = ?, integrity_recommendation = 'needs_review_priority' WHERE id = ?",
                     (json.dumps([{"code": "PDF_COVERED_TEXT", "family": "layout", "status": "review_required",
                                   "finding": "A block lies over printed text.", "tier": "T1", "impact": "high"}]),
                      file_id))
        raise_item(conn, case_id=case_id, kind="integrity", ref=f"file:{file_id}", summary="x")
    finally:
        conn.close()

    analyst = sign_in(client, ANALYST)
    files = {f["id"]: f for f in client.get(f"/api/cases/{case_id}/files", headers=analyst).json()}
    assert files[file_id]["integrity_status"]["state"] == "suspicious"
    assert files[file_id]["integrity_review"] is None  # never set by the checks

    url = f"/api/cases/{case_id}/files/{file_id}/integrity/review"
    assert client.post(url, json={"decision": "altered", "reason": ""}, headers=analyst).status_code == 422
    assert client.post(url, json={"decision": "tampered", "reason": "x y z"}, headers=analyst).status_code == 422
    unclear = client.post(url, json={"decision": "unclear", "reason": "Need the issuer's copy"}, headers=analyst)
    assert unclear.status_code == 200 and unclear.json()["integrity_review"]["decision"] == "unclear"
    item = lambda: next(i for i in client.get(f"/api/review?case_id={case_id}&include_decided=true",  # noqa: E731
                                              headers=analyst).json() if i["kind"] == "integrity")
    assert item()["status"] == "open"  # unclear leaves the queue item open

    altered = client.post(url, json={"decision": "altered", "reason": "Number pasted over the original"},
                          headers=analyst)
    review = altered.json()["integrity_review"]
    assert review["decision"] == "altered" and review["decided_by"] == "ananya-krishnan" and review["decided_at"]
    assert item()["status"] == "decided" and item()["decision"] == "confirm"
    # The checks' status is unchanged by the person's conclusion.
    assert altered.json()["integrity_status"]["state"] == "suspicious"


SCORE = {"impact_points": {"high": 60, "medium": 35, "low": 15},
         "tier_factor": {"T0": 1.0, "T1": 1.0, "T2": 0.75, "T3": 0.5},
         "same_family_share": 0.25, "other_family_share": 0.75, "cap": 95,
         "bands": {"strong": 70, "moderate": 40}}


def _signal(code, family, impact="high", tier="T1", context=False):
    return IngestIntegrityFinding(code=code, family=family, status="review_required", finding="x", tier=tier,
                                  impact=impact, context=context)


def test_evidence_strength_adds_up_what_stands_out_and_says_how():
    from engine.integrity_status import strength

    # Two indicators of one kind (the edited PT registration): the strongest, plus a share.
    total, band, parts = strength([_signal("PDF_COVERED_TEXT", "layout"), _signal("PDF_PICTURE_OVER_TEXT", "layout")],
                                  SCORE)
    assert (total, band) == (75, "strong")
    assert [p.adds for p in parts] == [60, 15] and sum(p.adds for p in parts) == 75
    # Independent kinds corroborate more than a repeat, but never reach certainty.
    assert strength([_signal("A", "layout"), _signal("B", "history")], SCORE)[0] == 95
    # One medium indicator alone is weak-to-moderate; an observation scores nothing.
    assert strength([_signal("C", "history", impact="medium")], SCORE)[:2] == (35, "weak")
    assert strength([_signal("D", "metadata", context=True)], SCORE)[:2] == (0, "none")
    # No scoring configured: no score at all, never a made-up one.
    assert strength([_signal("A", "layout")], None) == (None, None, [])


def test_the_score_travels_with_the_status_and_never_changes_the_state():
    found = [_signal("PDF_COVERED_TEXT", "layout"), _signal("PDF_PICTURE_OVER_TEXT", "layout")]
    s = assess(_row("needs_review_priority"), found, {"PDF_COVERED_TEXT": {}, "PDF_PICTURE_OVER_TEXT": {}}, SCORE)
    assert s.state == "suspicious" and s.score == 75 and s.band == "strong"
    assert assess(_row(), ALL_PASS, CHECKS, SCORE).score == 0
