"""F-10: a borrower identifier taken from the documents onto the case. Only the value the latest
cross-check found the same on every document is accepted; the case keeps where it came from and
the decision log keeps who recorded it."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from engine import db
from tests.conftest import ANALYST, RM, make_case, sign_in


def _finding(root: Path, case_id: str, rule: str, outcome: str, values: list[str]) -> None:
    conn = db.connect(root)
    try:
        sides = [{"label": f"Document {i + 1}", "value": v, "evidence": [{"document_id": f"DOC-{i}", "page": 1}]}
                 for i, v in enumerate(values)]
        conn.execute(
            """INSERT INTO findings (id, case_id, rule_id, title, outcome, severity, blocking, explanation, sides,
               run_id) VALUES (?, ?, ?, ?, ?, 'serious', 1, '', ?, 'XR-TEST-001')""",
            (f"FND-{rule}", case_id, rule, rule, outcome, json.dumps(sides)),
        )
        conn.commit()
    finally:
        conn.close()


def test_the_agreed_pan_is_recorded_with_its_source_and_logged(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, sign_in(client, RM), published_data_root)
    _finding(published_data_root, case_id, "ID-01", "pass", ["AAACK1234F"])

    r = client.post(f"/api/cases/{case_id}/identifiers/pan", json={"value": "aaack1234f"}, headers=analyst)
    assert r.status_code == 200, r.text
    case = r.json()
    assert case["pan"] == "AAACK1234F"
    assert case["header"]["pan"]["source"] == "document:DOC-0:p1"

    conn = db.connect(published_data_root)
    try:
        row = conn.execute(
            "SELECT actor, detail FROM decision_log WHERE case_id = ? AND action = 'case.identifier_recorded'",
            (case_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and json.loads(row["detail"])["value"] == "AAACK1234F"


def test_a_value_the_documents_do_not_agree_on_is_refused(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, sign_in(client, RM), published_data_root)
    _finding(published_data_root, case_id, "ID-02", "fail", ["27AAACK1234F1Z0", "27AAACK9999F1Z0"])

    r = client.post(f"/api/cases/{case_id}/identifiers/gstin", json={"value": "27AAACK1234F1Z0"}, headers=analyst)
    assert r.status_code == 409
    other = client.post(f"/api/cases/{case_id}/identifiers/udyam", json={"value": "X"}, headers=analyst)
    assert other.status_code == 409


def test_a_role_that_cannot_decide_may_not_record(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root)
    _finding(published_data_root, case_id, "ID-01", "pass", ["AAACK1234F"])
    assert client.post(f"/api/cases/{case_id}/identifiers/pan", json={"value": "AAACK1234F"}, headers=rm).status_code == 403
