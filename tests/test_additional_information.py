"""Story 6.5: a document's extra data (Story 6.4) is read through one endpoint, for the assistant; no screen shows it."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from engine import db
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc

EXTRA = {"pairs": [{"label": "Goodwill", "values": ["12,34,567"], "page": 7, "line_id": "p7.l2"}],
         "tables": [{"description": "Earnings per equity share", "described_by": "heading", "page": 8,
                     "columns": [], "rows": [["Basic EPS", "8.00"], ["Diluted EPS", "8.00"]], "line_ids": []}]}


def test_the_assistant_reads_each_item_with_its_document_and_page(client: TestClient, published_data_root: Path):
    headers = sign_in(client, ANALYST)
    case_id = make_case(client, headers, published_data_root)
    doc = add_doc(published_data_root, case_id, "audited_financial_statements", {"company_name": "Kestrel Tools"})
    conn = db.connect(published_data_root)
    try:
        conn.execute("UPDATE documents SET extra = ? WHERE id = ?", (json.dumps(EXTRA), doc))
        conn.commit()
    finally:
        conn.close()
    got = client.get(f"/api/cases/{case_id}/additional-information", headers=headers)
    assert got.status_code == 200, got.text
    items = got.json()
    assert [(i["page"], i["kind"], i["label"], i["value"]) for i in items] == [
        (7, "pair", "Goodwill", "12,34,567"), (8, "table", "Earnings per equity share", "Basic EPS: 8.00; Diluted EPS: 8.00")]
    assert items[0]["document"].startswith("Audited financial statements")
    none = client.get(f"/api/cases/{case_id}/additional-information?document_type=bank_statement", headers=headers)
    assert none.json() == []
