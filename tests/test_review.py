"""F-17: the review queue and its decisions. TC-09 (unclassified goes to
review with candidates and is never mapped until a person assigns a type),
the correction overlay (both values kept), maker-checker for manual entry,
waivers for non-mandatory items only, and decisions never touching
configuration."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from engine import db
from engine.configstore import reader
from tests.conftest import ANALYST, MANAGER, RM, fixture_file, make_case, run_jobs, sign_in, upload


def _case(client: TestClient, root: Path, names: list[str]) -> tuple[dict, dict, str]:
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, root, borrower="Heronbay Polymers Pvt Ltd", facilities=["cash_credit"],
                        amount_inr=30000000, collateral_present=False)
    upload(client, rm, case_id, [(n, fixture_file(n)) for n in names])
    run_jobs(root)
    return rm, sign_in(client, ANALYST), case_id


def _items(client, headers, case_id, kind=None, include_decided=False):
    url = f"/api/review?case_id={case_id}" + ("&include_decided=true" if include_decided else "")
    items = client.get(url, headers=headers).json()
    return [i for i in items if kind is None or i["kind"] == kind]


def _decide(client, headers, item_id, **body):
    return client.post(f"/api/review/{item_id}/decision", json=body, headers=headers)


def _checklist(client, headers, case_id):
    return {i["item_id"]: i for i in client.get(f"/api/cases/{case_id}/checklist", headers=headers).json()["items"]}


def test_tc09_unclassified_goes_to_review_with_candidates_and_is_not_mapped(client, published_data_root):
    rm, analyst, case_id = _case(client, published_data_root, ["partial_bundle.pdf", "scan_0412.pdf"])
    [item] = _items(client, analyst, case_id, "type")
    assert "Udyam registration certificate 0.41" in item["summary"]
    docs = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    unknown = next(d for d in docs if d["status"] == "unclassified")
    assert unknown["classification"]["types"] == []
    assert [c["type_id"] for c in unknown["classification"]["candidates"]][0] == "udyam_certificate"
    # Not assigned to any checklist item, not even its top candidate's.
    checklist = _checklist(client, rm, case_id)
    assert checklist["udyam"]["status"] == "missing"
    assert all(unknown["id"] not in i["document_ids"] for i in checklist.values())

    # An assignment must come from the closed list.
    assert _decide(client, analyst, item["id"], decision="assign", value="utility_bill").status_code == 422
    decided = _decide(client, analyst, item["id"], decision="assign", value="udyam_certificate",
                      reason="Udyam certificate, scanned without its header")
    assert decided.status_code == 200 and decided.json()["decision"] == "assign"
    # Extraction re-runs for that document with the assigned type.
    assert run_jobs(published_data_root) == 1
    doc = next(d for d in client.get(f"/api/cases/{case_id}/documents", headers=rm).json() if d["id"] == unknown["id"])
    assert doc["classification"]["types"] == ["udyam_certificate"]
    assert doc["classification"]["exit_tier"] == "person"
    assert doc["status"] == "accepted"
    fields = client.get(f"/api/cases/{case_id}/fields?document_id={doc['id']}", headers=analyst).json()
    assert {f["field"]: f["value"] for f in fields}["udyam_number"] == "UDYAM-MH-18-0099887"
    assert _checklist(client, rm, case_id)["udyam"]["status"] == "satisfied"


def test_f17_correction_keeps_both_values(client: TestClient, published_data_root: Path):
    rm, analyst, case_id = _case(client, published_data_root, ["gst_sep_photo.pdf"])
    field_items = _items(client, analyst, case_id, "field")
    # Grade C: every key field goes to review (F-07.2).
    assert len(field_items) == 4
    target = next(i for i in field_items if "outward_taxable_supplies" in i["summary"])
    assert _decide(client, analyst, target["id"], decision="correct", value=9150000).status_code == 422  # no reason
    assert _decide(client, analyst, target["id"], decision="waive", reason="x").status_code == 422
    done = _decide(client, analyst, target["id"], decision="correct", value=9150000, reason="Read from the portal copy")
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "decided" and body["decided_by"] == "ananya-krishnan" and body["reason"]
    value = next(
        f for f in client.get(f"/api/cases/{case_id}/fields", headers=analyst).json()
        if f["field"] == "outward_taxable_supplies"
    )
    assert value["value"] == 9100000 and value["corrected_value"] == 9150000 and value["status"] == "corrected"
    # Deciding twice is refused.
    assert _decide(client, analyst, target["id"], decision="confirm").status_code == 409
    # Once every value is decided, the document is accepted.
    for item in _items(client, analyst, case_id, "field"):
        assert _decide(client, analyst, item["id"], decision="confirm").status_code == 200
    docs = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    assert docs[0]["status"] == "accepted"
    conn = db.connect(published_data_root)
    try:
        log = [json.loads(r["detail"]) for r in conn.execute(
            "SELECT detail FROM decision_log WHERE action = 'review.decided' AND case_id = ?", (case_id,))]
    finally:
        conn.close()
    corrected = next(entry for entry in log if entry["decision"] == "correct")
    assert corrected["system_value"] == 9100000 and corrected["corrected_value"] == 9150000


def test_f17_manual_entry_needs_a_different_checker(client: TestClient, published_data_root: Path):
    rm, analyst, case_id = _case(client, published_data_root, ["partial_bundle.pdf", "itr_blurred.pdf"])
    manager = sign_in(client, MANAGER)
    [quality] = [i for i in _items(client, analyst, case_id, "quality") if "grade U" in i["summary"]]
    # A grade-U document is not simply confirmed.
    assert _decide(client, analyst, quality["id"], decision="confirm").status_code == 422
    # The maker needs the maker permission (the credit manager is a checker).
    entry = {"decision": "correct", "reason": "Values typed from the borrower's portal printout",
             "values": {"assessment_year": "2025-26", "total_income": 5100000}}
    assert _decide(client, manager, quality["id"], **entry).status_code == 403
    assert _decide(client, analyst, quality["id"], **{**entry, "values": {"not_a_field": 1}}).status_code == 422
    assert _decide(client, analyst, quality["id"], **entry).status_code == 200
    [manual] = _items(client, analyst, case_id, "manual_entry")
    assert manual["maker"] == "ananya-krishnan"
    fields = client.get(f"/api/cases/{case_id}/fields", headers=analyst).json()
    entered = [f for f in fields if f["method"] == "manual"]
    assert {f["field"] for f in entered} == {"assessment_year", "total_income"}
    assert all(f["confidence"] == 0.7 and f["status"] == "in_review" for f in entered)
    # The maker cannot check their own entry.
    assert _decide(client, analyst, manual["id"], decision="confirm").status_code == 403
    checked = _decide(client, manager, manual["id"], decision="confirm")
    assert checked.status_code == 200
    assert checked.json()["decided_by"] == "meenal-kulkarni" and checked.json()["maker"] == "ananya-krishnan"
    docs = {d["id"]: d for d in client.get(f"/api/cases/{case_id}/documents", headers=rm).json()}
    assert docs[json.loads(json.dumps(manual))["ref"].split(":", 1)[1]]["status"] == "accepted"
    # The ITR item now counts the manually entered year, with the other still missing.
    itr = _checklist(client, rm, case_id)["itr"]
    assert itr["status"] == "insufficient" and "AY 2026-27" in itr["deficiency"]


def test_f07_better_copy_supersedes_the_unreadable_one(client: TestClient, published_data_root: Path):
    rm, analyst, case_id = _case(client, published_data_root, ["itr_blurred.pdf"])
    upload(client, rm, case_id, [("itr_clear.pdf", fixture_file("itr_clear.pdf"))])
    run_jobs(published_data_root)
    docs = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    old = next(d for d in docs if d["grade"] == "U")
    new = next(d for d in docs if d["grade"] == "A")
    assert old["status"] == "superseded" and new["version_of"] == old["id"]
    assert not [i for i in _items(client, analyst, case_id, "quality") if "grade U" in i["summary"]]


def test_f17_waive_only_non_mandatory_items(client: TestClient, published_data_root: Path):
    rm, analyst, case_id = _case(client, published_data_root, ["itr_blurred.pdf", "gst_sep_photo.pdf"])
    quality = {i["summary"].split(" ")[0]: i for i in _items(client, analyst, case_id, "quality")}
    # The ITR is mandatory: no waiver.
    refused = _decide(client, analyst, quality["itr_blurred.pdf"]["id"], decision="waive", reason="Not needed")
    assert refused.status_code == 422 and "non-mandatory" in refused.json()["detail"]
    assert _decide(client, analyst, quality["itr_blurred.pdf"]["id"], decision="waive").status_code == 422


def test_f17_waiving_a_non_mandatory_exception_waives_its_item(client, published_data_root, tmp_path):
    """A quality exception on a document serving only non-mandatory items
    (the Udyam registration) can be waived with a reason."""
    rm, analyst, case_id = _case(client, published_data_root, ["scan_0412.pdf"])
    [type_item] = _items(client, analyst, case_id, "type")
    _decide(client, analyst, type_item["id"], decision="assign", value="udyam_certificate", reason="Udyam")
    run_jobs(published_data_root)
    conn = db.connect(published_data_root)
    try:
        doc_id = conn.execute("SELECT id FROM documents WHERE case_id = ?", (case_id,)).fetchone()[0]
        conn.execute("UPDATE documents SET status = 'in_exception', grade = 'U' WHERE id = ?", (doc_id,))
        conn.execute(
            "INSERT INTO review_items (id, case_id, kind, ref, summary, created_at, status, detail)"
            " VALUES ('RV-T', ?, 'quality', ?, 'scan_0412.pdf grade U', '2026-09-29', 'open', ?)",
            (case_id, f"document:{doc_id}", json.dumps({"document_id": doc_id, "reason_codes": ["blur"]})),
        )
    finally:
        conn.close()
    assert _decide(client, analyst, "RV-T", decision="waive", reason="MSME status confirmed on the portal").status_code == 200
    udyam = _checklist(client, rm, case_id)["udyam"]
    assert udyam["status"] == "waived" and "MSME status confirmed" in udyam["deficiency"]


def test_f17_decisions_never_change_configuration(client: TestClient, published_data_root: Path):
    before = reader.published_version(published_data_root)
    rm, analyst, case_id = _case(client, published_data_root, ["gst_sep_photo.pdf"])
    for item in _items(client, analyst, case_id, "field"):
        _decide(client, analyst, item["id"], decision="correct", value="x", reason="test")
    assert reader.published_version(published_data_root) == before


def test_f17_decision_permissions(client: TestClient, published_data_root: Path):
    rm, analyst, case_id = _case(client, published_data_root, ["gst_sep_photo.pdf"])
    item = _items(client, analyst, case_id, "field")[0]
    assert client.post(f"/api/review/{item['id']}/decision", json={"decision": "confirm"}).status_code == 401
    assert _decide(client, rm, item["id"], decision="confirm").status_code == 403
    assert _decide(client, analyst, "RV-NOPE", decision="confirm").status_code == 404
