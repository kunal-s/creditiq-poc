"""Story 7.2: a person's corrections on the Files tab. One page given its own type is read in a document of its own,
and the document it came from is read again without it; a document's period is set where none was found."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from engine import db, pipeline
from engine.contracts import IngestResult
from engine.contracts.ingest import IngestFileResult
from engine.store import case_files_dir
from tests.conftest import ANALYST, RM, make_case, sign_in
from tests.triangulation import add_doc

TEMPLATE = Path(__file__).parent / "fixtures" / "ingest" / "template"


def _template() -> IngestFileResult:
    path = next(p for p in TEMPLATE.parent.glob("670222eabe17f04cf7bc*.json"))
    return IngestFileResult.model_validate(json.loads(path.read_text()))


class Service:
    """Reads the requested pages of the file as the type asked, from a recorded result of a three-page file."""

    def __init__(self):
        self.requests = []

    def process(self, request, payloads):
        self.requests.append(request)
        f = request.files[0]
        canned = _template()
        pages = set(f.pages or [p.page for p in canned.pages])
        docs = [d.model_copy(update={"document_type": f.assigned_type or d.document_type})
                for d in canned.documents if d.page_from in pages]
        cls = canned.classification.model_copy(update={"type": f.assigned_type}) if f.assigned_type else canned.classification
        fr = canned.model_copy(update={"file_id": f.file_id, "name": f.original_name, "sha256": f.sha256, "classification": cls,
                                       "documents": docs, "pages": [p for p in canned.pages if p.page in pages]})
        return IngestResult.model_validate(
            {"contract_version": "2", "case_ref": request.case_ref, "config": {"version": request.config_version, "hash": "t"},
             "engine": {"version": "t", "ocr": "t", "model": "t"}, "files": [fr.model_dump(mode="json")]})


def _three_pages(root: Path, case_id: str) -> str:
    doc = add_doc(root, case_id, "income_tax_return", {"pan": "AAACK1234F", "assessment_year": "2025-26"})
    conn = db.connect(root)
    try:
        r = conn.execute("SELECT file_id FROM documents WHERE id = ?", (doc,)).fetchone()
        conn.execute("UPDATE documents SET page_from = 1, page_to = 3, pages = ? WHERE id = ?",
                     (json.dumps([{"n": n, "route": "text", "grade": "A"} for n in (1, 2, 3)]), doc))
        conn.execute("UPDATE files SET stored_name = 'f.pdf' WHERE id = ?", (r["file_id"],))
        conn.commit()
    finally:
        conn.close()
    folder = case_files_dir(case_id, root)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "f.pdf").write_bytes(b"%PDF-1.4")
    return doc


def test_a_page_given_its_own_type_is_read_alone_and_its_document_without_it(client: TestClient,
                                                                              published_data_root: Path):
    root = published_data_root
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, root)
    doc = _three_pages(root, case_id)
    queued = client.post(f"/api/cases/{case_id}/documents/{doc}/pages/2/type", headers=headers,
                         json={"type_id": "form_26as", "reason": "Page 2 is the tax credit statement."})
    assert queued.status_code == 200, queued.text
    service = Service()
    conn = db.connect(root)
    try:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (queued.json()["job_id"],)).fetchone()
        payload = json.loads(job["payload"])
        pipeline.retype_page(conn, root, job["id"], case_id, doc, payload["page"], payload["type_id"], service)
        rows = conn.execute("SELECT id, assigned_types, page_from, page_to, status FROM documents WHERE case_id = ?"
                            " AND status <> 'superseded' ORDER BY page_from", (case_id,)).fetchall()
        logged = conn.execute("SELECT detail FROM decision_log WHERE action = 'document.page_retyped'").fetchone()
    finally:
        conn.close()
    assert [r.files[0].pages for r in service.requests] == [[2], [1, 3]]
    assert [r.files[0].assigned_type for r in service.requests] == ["form_26as", "income_tax_return"]
    page2 = [r for r in rows if r["page_from"] == 2]
    assert page2 and json.loads(page2[0]["assigned_types"]) == ["form_26as"]
    assert json.loads(logged["detail"])["reason"] == "Page 2 is the tax credit statement."


def test_a_page_type_needs_a_known_type_a_page_of_the_document_and_the_right_role(client: TestClient,
                                                                                 published_data_root: Path):
    root = published_data_root
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, root)
    doc = _three_pages(root, case_id)
    url = f"/api/cases/{case_id}/documents/{doc}/pages"
    assert client.post(f"{url}/9/type", headers=headers, json={"type_id": "form_26as", "reason": "x"}).status_code == 422
    assert client.post(f"{url}/2/type", headers=headers, json={"type_id": "nope", "reason": "x"}).status_code == 422
    rm = sign_in(client, RM)
    assert client.post(f"{url}/2/type", headers=rm, json={"type_id": "form_26as", "reason": "x"}).status_code == 403


def test_a_period_set_by_a_person_is_the_one_the_checks_read(client: TestClient, published_data_root: Path):
    root = published_data_root
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, root)
    doc = add_doc(root, case_id, "audited_financial_statements", {"company_name": "Kestrel Tools"})
    set_ = client.put(f"/api/cases/{case_id}/documents/{doc}/period", headers=headers,
                      json={"start": "2024-04-01", "end": "2025-03-31", "reason": "Year printed on the auditor's report."})
    assert set_.status_code == 200, set_.text
    conn = db.connect(root)
    try:
        row = conn.execute("SELECT period, instance_key FROM documents WHERE id = ?", (doc,)).fetchone()
        logged = conn.execute("SELECT detail FROM decision_log WHERE action = 'document.period_set'").fetchone()
        from engine import facts, statements
        d = next(x for x in facts.load_documents(conn, root, case_id) if x.id == doc)
    finally:
        conn.close()
    assert row["instance_key"] == "2025-03-31" and json.loads(row["period"])["source"] == "person"
    assert str(statements.period_end(d)) == "2025-03-31"
    assert json.loads(logged["detail"])["to"] == {"start": "2024-04-01", "end": "2025-03-31"}
    bad = client.put(f"/api/cases/{case_id}/documents/{doc}/period", headers=headers,
                     json={"start": "2025-04-01", "end": "2025-03-31", "reason": "x"})
    assert bad.status_code == 422
