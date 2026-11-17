"""F-09.8 to F-09.10, F-15.8, F-17.7 (FRD decision 13): a document no published type fits is given a
type made for its case. The document is read by the model as that type, named fields or discovered
ones; a discovered value waits for a person; the type maps to no checklist item on its own, is never
edited in place, is offered on its own case only, and the Administrator sees it as a proposal."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db
from tests.conftest import ANALYST, MANAGER, RM, case_files, fixture_file, make_case, run_jobs, sign_in, upload

ADMIN = "nikhil.sawant@rblbank.com"
PARTIAL = [n for n, _ in case_files("partial")]


def _case(client: TestClient, root: Path) -> tuple[dict, dict, str]:
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, root, borrower="Heronbay Polymers Pvt Ltd", facilities=["cash_credit"],
                        amount_inr=30000000, collateral_present=False)
    upload(client, rm, case_id, [(n, fixture_file(n)) for n in PARTIAL + ["scan_0412.pdf"]])
    run_jobs(root)
    return rm, sign_in(client, ANALYST), case_id


def _make(client, headers, case_id, **body):
    return client.post(f"/api/cases/{case_id}/document-types", json=body, headers=headers)


def _type_item(client, headers, case_id):
    return next(i for i in client.get(f"/api/review?case_id={case_id}", headers=headers).json() if i["kind"] == "type")


def _assign(client, root, headers, case_id, type_id) -> dict:
    item = _type_item(client, headers, case_id)
    r = client.post(f"/api/review/{item['id']}/decision", json={"decision": "assign", "value": type_id, "reason": None},
                    headers=headers)
    assert r.status_code == 200, r.text
    assert run_jobs(root) == 1
    return item


def _unknown(client, headers, case_id) -> dict:
    return next(d for d in client.get(f"/api/cases/{case_id}/documents", headers=headers).json()
                if d["status"] == "unclassified")


def _fields(client, headers, case_id, doc_id) -> dict:
    return {f["field"]: f for f in client.get(f"/api/cases/{case_id}/fields?document_id={doc_id}", headers=headers).json()}


def test_named_fields_are_read_and_the_type_maps_to_no_checklist_item(client, published_data_root):
    rm, analyst, case_id = _case(client, published_data_root)
    doc = _unknown(client, rm, case_id)
    made = _make(client, analyst, case_id, name="Shop and establishment certificate",
                 description="Municipal registration of the premises",
                 fields=[{"name": "Registration number", "hint": "the number printed after Registration"},
                         {"name": "issue date"}])
    assert made.status_code == 201, made.text
    t = made.json()
    assert t["id"].startswith("CDT-") and [f["name"] for f in t["fields"]] == ["registration_number", "issue_date"]
    assert [x["id"] for x in client.get(f"/api/cases/{case_id}/document-types", headers=rm).json()] == [t["id"]]

    _assign(client, published_data_root, analyst, case_id, t["id"])
    after = next(d for d in client.get(f"/api/cases/{case_id}/documents", headers=rm).json() if d["id"] == doc["id"])
    assert after["classification"]["types"] == [t["id"]] and after["classification"]["exit_tier"] == "person"
    fields = _fields(client, analyst, case_id, doc["id"])
    assert fields["registration_number"]["value"] == "AAACH5678Q" and fields["registration_number"]["origin"] == "named"
    assert fields["issue_date"]["status"] == "missing"
    # F-09.9: no checklist item is satisfied by a case document type until a person maps it.
    items = client.get(f"/api/cases/{case_id}/checklist", headers=rm).json()["items"]
    assert all(doc["id"] not in i["document_ids"] for i in items)


def test_discovered_fields_wait_for_a_person(client, published_data_root):
    rm, analyst, case_id = _case(client, published_data_root)
    doc = _unknown(client, rm, case_id)
    t = _make(client, analyst, case_id, name="Shop and establishment certificate").json()
    assert t["fields"] == []
    _assign(client, published_data_root, analyst, case_id, t["id"])
    f = _fields(client, analyst, case_id, doc["id"])["registration_number"]
    assert f["origin"] == "discovered" and f["label"] == "Registration number" and f["status"] == "in_review"
    [item] = [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
              if i["kind"] == "field" and i["ref"] == f"field:{f['id']}"]
    assert item["summary"].startswith("Shop and establishment certificate: Registration number = AAACH5678Q")
    assert "proposed by the model" in item["summary"]


def test_a_type_is_checked_and_offered_on_its_own_case_only(client, published_data_root):
    rm, analyst, case_id = _case(client, published_data_root)
    assert _make(client, rm, case_id, name="Rent agreement").status_code == 403
    assert _make(client, analyst, case_id, name="  ").status_code == 422
    assert _make(client, analyst, case_id, name="company pan").status_code == 422  # a published type: assign it
    assert _make(client, analyst, case_id, name="Rent agreement",
                 fields=[{"name": "Rent"}, {"name": "rent "}]).status_code == 422
    assert _make(client, analyst, case_id, name="Rent agreement", fields=[{"name": "!!"}]).status_code == 422

    other = make_case(client, rm, published_data_root, borrower="Other Borrower Pvt Ltd", facilities=["cash_credit"],
                      amount_inr=1000000, collateral_present=False)
    foreign = _make(client, analyst, other, name="Rent agreement").json()
    item = _type_item(client, analyst, case_id)
    r = client.post(f"/api/review/{item['id']}/decision", json={"decision": "assign", "value": foreign["id"]},
                    headers=analyst)
    assert r.status_code == 422


def test_a_type_is_never_edited_in_place_and_its_making_is_logged(client, published_data_root):
    _, analyst, case_id = _case(client, published_data_root)
    first = _make(client, analyst, case_id, name="Rent agreement").json()
    second = _make(client, analyst, case_id, name="Rent agreement", fields=[{"name": "monthly rent"}],
                   replaces=first["id"]).json()
    assert second["replaces"] == first["id"] and second["id"] != first["id"]
    assert _make(client, analyst, case_id, name="Lease", replaces="CDT-NOPE").status_code == 404
    conn = sqlite3.connect(db.db_path(published_data_root))
    with pytest.raises(sqlite3.IntegrityError, match="never edited in place"):
        conn.execute("UPDATE case_document_types SET name = 'x' WHERE id = ?", (first["id"],))
    logged = conn.execute("SELECT COUNT(*) FROM decision_log WHERE action = 'document_type.case_made' AND case_id = ?",
                          (case_id,)).fetchone()[0]
    assert logged == 2


def test_the_administrator_sees_proposals_without_any_appraisal(client, published_data_root):
    rm, analyst, case_id = _case(client, published_data_root)
    t = _make(client, analyst, case_id, name="Rent agreement", fields=[{"name": "monthly rent"}]).json()
    _make(client, analyst, case_id, name="rent  agreement")
    admin = sign_in(client, ADMIN)
    assert client.get("/api/admin/case-document-types", headers=rm).status_code == 403
    [p] = client.get("/api/admin/case-document-types", headers=admin).json()
    assert p["name"] == "Rent agreement" and p["cases"] == 1 and [f["name"] for f in p["fields"]] == ["monthly_rent"]
    assert case_id not in str(p) and t["id"] not in str(p)


def _map(client, headers, case_id, type_id, **body):
    return client.post(f"/api/cases/{case_id}/document-types/{type_id}/mappings", json=body, headers=headers)


def test_a_mandatory_item_is_satisfied_only_once_a_checker_confirms_the_mapping(client, published_data_root):
    rm, analyst, case_id = _case(client, published_data_root)
    manager = sign_in(client, MANAGER)
    doc = _unknown(client, rm, case_id)
    t = _make(client, analyst, case_id, name="PAN allotment letter", fields=[{"name": "registration number"}]).json()
    _assign(client, published_data_root, analyst, case_id, t["id"])
    _checklist = lambda: {i["item_id"]: i for i in client.get(f"/api/cases/{case_id}/checklist", headers=rm).json()["items"]}
    assert _checklist()["pan_entity"]["status"] == "missing"

    assert _map(client, rm, case_id, t["id"], item_id="pan_entity", reason="x").status_code == 403
    assert _map(client, analyst, case_id, t["id"], item_id="nope").status_code == 422
    assert _map(client, analyst, case_id, t["id"], item_id="itr", reason="x").status_code == 422  # checked by years
    assert _map(client, analyst, case_id, t["id"], item_id="pan_entity").status_code == 422     # no reason
    made = _map(client, analyst, case_id, t["id"], item_id="pan_entity", reason="The allotment letter carries the PAN")
    assert made.status_code == 201 and made.json()["mappings"][0]["status"] == "proposed"
    assert _map(client, analyst, case_id, t["id"], item_id="pan_entity", reason="again").status_code == 409
    assert _checklist()["pan_entity"]["status"] == "missing"  # proposed is not mapped

    [item] = [i for i in client.get(f"/api/review?case_id={case_id}", headers=manager).json() if i["kind"] == "mapping"]
    decide = lambda h, d, reason=None: client.post(f"/api/review/{item['id']}/decision",
                                                   json={"decision": d, "reason": reason}, headers=h)
    assert decide(analyst, "confirm").status_code == 403  # the maker never checks
    assert decide(manager, "assign").status_code == 422
    assert decide(manager, "confirm").status_code == 200
    after = _checklist()["pan_entity"]
    assert doc["id"] in after["document_ids"] and after["status"] in ("satisfied", "in_review")
    [m] = client.get(f"/api/cases/{case_id}/document-types", headers=rm).json()[0]["mappings"]
    assert m["status"] == "confirmed" and m["decided_by"] != m["proposed_by"]


def test_a_refused_mapping_can_be_proposed_again(client, published_data_root):
    rm, analyst, case_id = _case(client, published_data_root)
    manager = sign_in(client, MANAGER)
    t = _make(client, analyst, case_id, name="PAN allotment letter").json()
    _map(client, analyst, case_id, t["id"], item_id="pan_entity", reason="carries the PAN")
    [item] = [i for i in client.get(f"/api/review?case_id={case_id}", headers=manager).json() if i["kind"] == "mapping"]
    r = client.post(f"/api/review/{item['id']}/decision", json={"decision": "waive", "reason": "not the entity's PAN"},
                    headers=manager)
    assert r.status_code == 200
    assert client.get(f"/api/cases/{case_id}/document-types", headers=rm).json()[0]["mappings"][0]["status"] == "refused"
    assert _map(client, analyst, case_id, t["id"], item_id="pan_entity", reason="second look").status_code == 201


def test_an_item_that_is_not_mandatory_is_mapped_at_once(client, published_data_root, monkeypatch):
    from engine import completeness

    rm, analyst, case_id = _case(client, published_data_root)
    real = completeness.applicable_items

    def relaxed(root, case, data):
        items, known = real(root, case, data)
        return [i.model_copy(update={"blocking": False}) if i.id == "board_resolution" else i for i in items], known

    monkeypatch.setattr(completeness, "applicable_items", relaxed)
    t = _make(client, analyst, case_id, name="Minutes of the board meeting").json()
    made = _map(client, analyst, case_id, t["id"], item_id="board_resolution")
    assert made.status_code == 201
    [m] = made.json()["mappings"]
    assert m["status"] == "confirmed" and m["decided_by"] == m["proposed_by"]
    assert not [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json() if i["kind"] == "mapping"]
