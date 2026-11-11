"""F-08.1, F-08.2, F-08.6: a document of another type the service found inside a file (its second pass).

The Heronbay certificate of incorporation is served here as a two-page bundle whose second page is the
company's PAN letter: the canned result of the certificate, with the PAN letter's document added as a part
found on page 2. The part is its own logical document, satisfies its checklist item, keeps its fields
apart from the certificate's, and goes to a person, who confirms it or waives it as part of the certificate."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db
from tests.conftest import ANALYST, RM, case_files, fixture_file, make_case, run_jobs, sign_in, upload

INGEST = Path(__file__).resolve().parent / "fixtures" / "ingest"
COI = "heronbay certificate of incorporation.pdf"
PAN_SCAN = "scan_0412.pdf"
PARTIAL = [n for n, _ in case_files("partial")]


def _sha(name: str) -> str:
    return hashlib.sha256(fixture_file(name)).hexdigest()


@pytest.fixture()
def bundle_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The canned results, with the certificate's replaced by the two-page bundle's."""
    d = tmp_path / "ingest"
    shutil.copytree(INGEST, d)
    coi = json.loads((INGEST / f"{_sha(COI)}.json").read_text())
    pan = json.loads((INGEST / f"{_sha(PAN_SCAN)}@company_pan.json").read_text())
    part = pan["documents"][0]
    part.update(instance_no=len(coi["documents"]) + 1, page_from=2, page_to=2, origin="sibling", pages=[2],
                classification={"type": "company_pan", "confidence": 1.0, "tier": "sibling", "signals": {},
                                "candidates": [{"type": "company_pan", "score": 1.0}], "needs_review": True,
                                "reason": "found inside a file read as Certificate of Incorporation", "mixed_content": []})
    for f in part["fields"].values():
        if f.get("source"):
            f["source"]["page"] = 2
    for t in part["tables"].values():
        for row in t.get("rows", []):
            row["source"]["page"] = 2
    page2 = {**pan["pages"][0], "page": 2}
    coi["pages"] = [*coi["pages"], page2]
    coi["source"] = {**coi["source"], "pages": 2}
    coi["documents"].append(part)
    (d / f"{_sha(COI)}.json").write_text(json.dumps(coi))
    monkeypatch.setenv("CREDITIQ_INGEST_FIXTURES", str(d))
    return d


def _case(client: TestClient, root: Path) -> tuple[dict, dict, str]:
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, root, borrower="Heronbay Polymers Pvt Ltd", facilities=["cash_credit"],
                        amount_inr=30000000, collateral_present=False)
    upload(client, rm, case_id, [(n, fixture_file(n)) for n in PARTIAL])
    run_jobs(root)
    return rm, sign_in(client, ANALYST), case_id


def _checklist(client, headers, case_id):
    return {i["item_id"]: i for i in client.get(f"/api/cases/{case_id}/checklist", headers=headers).json()["items"]}


def test_a_found_part_is_its_own_document_and_satisfies_its_item(client, published_data_root, bundle_fixtures):
    rm, analyst, case_id = _case(client, published_data_root)
    docs = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    coi = [d for d in docs if d["classification"] and d["classification"]["types"] == ["certificate_of_incorporation"]]
    pan = [d for d in docs if d["classification"] and d["classification"]["types"] == ["company_pan"]]
    assert len(coi) == 1 and len(pan) == 1 and coi[0]["file_id"] == pan[0]["file_id"]
    coi, pan = coi[0], pan[0]
    assert coi["classification"]["exit_tier"] != "sibling" and pan["classification"]["exit_tier"] == "sibling"
    assert [p["n"] for p in pan["pages"]] == [2] and [p["n"] for p in coi["pages"]] == [1]

    # Each document keeps its own values: the certificate's company name is not the PAN letter's row.
    fields = client.get(f"/api/cases/{case_id}/fields", headers=analyst).json()
    by_doc = {}
    for f in fields:
        by_doc.setdefault(f["document_id"], {})[f["field"]] = f
    assert by_doc[pan["id"]]["pan"]["value"] == "AAACH5678Q" and by_doc[pan["id"]]["pan"]["evidence"]["page"] == 2
    assert "company_name" in by_doc[coi["id"]] and "company_name" in by_doc[pan["id"]]
    assert by_doc[coi["id"]]["company_name"]["id"] != by_doc[pan["id"]]["company_name"]["id"]

    # The checklist item a PAN letter serves is met by the part found in the certificate's file.
    item = _checklist(client, rm, case_id)["pan_entity"]
    assert item["status"] == "satisfied" and pan["id"] in item["document_ids"]

    # A person is asked to confirm the split.
    items = client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
    [split] = [i for i in items if i["kind"] == "split"]
    assert split["summary"].startswith("Company PAN found on page 2 of ")


def test_a_waived_part_is_held_in_the_files_own_document_and_stops_counting(client, published_data_root, bundle_fixtures):
    rm, analyst, case_id = _case(client, published_data_root)
    items = client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
    [split] = [i for i in items if i["kind"] == "split"]
    assert client.post(f"/api/review/{split['id']}/decision", json={"decision": "correct", "value": "x", "reason": "x"},
                       headers=analyst).status_code == 422
    assert client.post(f"/api/review/{split['id']}/decision", json={"decision": "waive"}, headers=analyst).status_code == 422
    done = client.post(f"/api/review/{split['id']}/decision",
                       json={"decision": "waive", "reason": "The PAN is printed on the certificate, not a separate letter"},
                       headers=analyst)
    assert done.status_code == 200
    docs = {d["id"]: d for d in client.get(f"/api/cases/{case_id}/documents", headers=rm).json()}
    pan = next(d for d in docs.values() if d["classification"] and d["classification"]["types"] == ["company_pan"])
    coi = next(d for d in docs.values() if d["classification"] and d["classification"]["types"] == ["certificate_of_incorporation"])
    assert pan["status"] == "duplicate" and pan["duplicate_of"] == coi["id"]
    assert _checklist(client, rm, case_id)["pan_entity"]["status"] == "missing"


def test_a_confirmed_part_stays(client, published_data_root, bundle_fixtures):
    rm, analyst, case_id = _case(client, published_data_root)
    [split] = [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json() if i["kind"] == "split"]
    assert client.post(f"/api/review/{split['id']}/decision", json={"decision": "confirm"}, headers=analyst).status_code == 200
    assert _checklist(client, rm, case_id)["pan_entity"]["status"] == "satisfied"
    conn = db.connect(published_data_root)
    try:
        flag = conn.execute("SELECT split_uncertain FROM documents WHERE id = ?", (split["ref"].removeprefix("document:"),)).fetchone()
    finally:
        conn.close()
    assert flag["split_uncertain"] == 1
