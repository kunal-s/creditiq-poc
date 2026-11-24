"""Epic 6: the case's pending fields (6.1), filled from the leftovers (6.2) in upload order (6.3), then by the sweep of
other document types (6.8): scenarios 19 and 33. The service is a fake that answers from a table, as the real one would
from the pages."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pending
from engine.store import case_files_dir
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited

AS_OF = date(2026, 6, 30)
CIN = "U17291TZ2016PTC027431"


class Service:
    """Answers a fill request from `answers`: {(file name prefix, field, period_end): (value, raw, page)}."""

    def __init__(self, answers: dict):
        self.answers, self.requests = answers, []

    def fill(self, request: dict, payload: bytes) -> dict:
        self.requests.append(request)
        name = request["file"]["original_name"]
        found = []
        for f in request["fields"]:
            for (prefix, field, end), (value, raw, page) in self.answers.items():
                if name.startswith(prefix) and field == f["name"] and end == f.get("period_end") and page in request["pages"]:
                    found.append({"field": field, "period_end": end, "value": value, "raw_text": raw, "method": "model",
                                  "page": page, "bbox": None, "line": raw})
        return {"found": found, "pages_read": request["pages"], "trace": []}


def _on_disk(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        for r in conn.execute("SELECT id FROM files WHERE case_id = ?", (case_id,)).fetchall():
            conn.execute("UPDATE files SET stored_name = ? WHERE id = ?", (f"{r['id']}.pdf", r["id"]))
            folder = case_files_dir(case_id, root)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{r['id']}.pdf").write_bytes(b"%PDF-1.4")
        conn.commit()
    finally:
        conn.close()


def _unplaced(root: Path, case_id: str, page: int = 1) -> str:
    doc_id = add_doc(root, case_id, "unknown", {}, page=page)
    conn = db.connect(root)
    try:
        conn.execute("UPDATE documents SET status = 'unclassified', classification = ? WHERE id = ?",
                     ('{"types": [], "confidence": 0, "exit_tier": "none", "signals": [], "candidates": []}', doc_id))
        conn.commit()
    finally:
        conn.close()
    return doc_id


@pytest.fixture()
def case(client: TestClient, published_data_root: Path) -> str:
    return make_case(client, sign_in(client, ANALYST), published_data_root, borrower="Kestrel Tools Pvt Ltd")


def test_6_1_a_field_its_own_documents_supply_is_not_pending(case, published_data_root):
    root = published_data_root
    add_doc(root, case, "certificate_of_incorporation", {"company_name": "Kestrel Tools Private Limited", "cin": CIN,
                                                         "date_of_incorporation": "2016-03-18"})
    audited(root, case, "2026-03-31")
    conn = db.connect(root)
    try:
        todo = {p.field for p in pending.pending(conn, root, case, AS_OF)}
    finally:
        conn.close()
    assert "cin" not in todo and "legal_name" not in todo and "date_of_incorporation" not in todo
    assert "gstin" in todo                                               # no GST return on file
    # FY 2025-26 from its own statements, FY 2024-25 from their comparative column; FY 2023-24 has none.
    assert "revenue_from_operations@2024-03-31" in todo
    assert "revenue_from_operations@2025-03-31" not in todo and "revenue_from_operations@2026-03-31" not in todo


def test_scenario_33_the_cin_found_on_the_auditors_report_waits_for_a_person(case, published_data_root):
    root = published_data_root
    cert = add_doc(root, case, "certificate_of_incorporation", {"company_name": "Kestrel Tools Private Limited"})
    afs = audited(root, case, "2026-03-31")
    _on_disk(root, case)
    service = Service({("audited_financial_statements", "cin", None): (CIN, CIN, 1)})
    conn = db.connect(root)
    try:
        stored = pending.fill(conn, root, case, AS_OF, service, "v")
        row = conn.execute("SELECT * FROM field_values WHERE document_id = ? AND field = 'cin'", (afs,)).fetchone()
        item = conn.execute("SELECT summary FROM review_items WHERE ref = ?", (f"field:{row['id']}",)).fetchone()
        own = conn.execute("SELECT COUNT(*) FROM field_values WHERE document_id = ? AND field = 'cin'", (cert,)).fetchone()[0]
        again = pending.pending(conn, root, case, AS_OF)
    finally:
        conn.close()
    assert [s["origin"] for s in stored if s["field"] == "cin"] == ["sweep"]
    assert (row["status"], row["origin"], row["raw"]) == ("in_review", "sweep", CIN)
    assert item["summary"].startswith(f"CIN = {CIN} (source: Audited financial statements")
    assert item["summary"].endswith("page 1; please confirm)")
    assert own == 0                                                       # the certificate's own record is untouched
    assert "cin" not in {p.field for p in again}                          # filled once, not asked for again
    # The sweep never asks a field's own documents: the certificate's file was not sent for the CIN.
    assert all("cin" not in {f["name"] for f in r["fields"]} or r["file"]["original_name"].startswith("audited")
               for r in service.requests if r["select"])


def test_scenario_19_a_figure_printed_only_on_an_unplaced_page_is_filled_from_it(case, published_data_root):
    root = published_data_root
    audited(root, case, "2026-03-31")
    loose = _unplaced(root, case, page=3)
    _on_disk(root, case)
    service = Service({("unknown", "revenue_from_operations", "2024-03-31"): (98765432, "9,87,65,432", 3)})
    conn = db.connect(root)
    try:
        pending.fill(conn, root, case, AS_OF, service, "v")
        row = conn.execute("SELECT * FROM field_values WHERE document_id = ?", (loose,)).fetchone()
    finally:
        conn.close()
    assert (row["field"], row["origin"], row["status"]) == ("revenue_from_operations@2024-03-31", "leftover", "in_review")
    assert '"page": 3' in row["evidence"]
    # 6.3: the leftovers are asked first, file by file in upload order.
    assert service.requests[0]["select"] is False and service.requests[0]["pages"] == [3]


def test_nothing_is_asked_when_nothing_is_pending(case, published_data_root):
    service = Service({})
    conn = db.connect(published_data_root)
    try:
        assert pending.fill(conn, published_data_root, case, AS_OF, object(), "v") == []   # a client without fill
    finally:
        conn.close()
    assert service.requests == []
