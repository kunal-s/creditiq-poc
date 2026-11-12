"""A figure a Credit Analyst changes, checked by the Credit Manager (engine/figure_edits.py).

The analyst (maker) proposes a new value for a figure read from a document, with the reason and,
optionally, the paper it rests on. Until the Credit Manager (checker, never the maker) approves it,
the field and the figure in force are untouched; approved, both values are kept and the person's is
in force; sent back, nothing changes. Every step is logged."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from engine import db
from engine.review_items import raise_item
from tests.conftest import ANALYST, MANAGER, RM, case_files, fixture_file, make_case, run_jobs, sign_in, upload

COMPLETE = [n for n, _ in case_files("complete")]
REASON = "Revised figure per the auditor's letter of 14 Oct 2026"


def _case(client: TestClient, root: Path) -> tuple[dict, dict, dict, str]:
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, root, borrower="Kestrel Fabricators Private Limited",
                        facilities=["cash_credit"], amount_inr=30000000, collateral_present=False)
    names = [n for n in COMPLETE if "audited" in n]
    upload(client, rm, case_id, [(n, fixture_file(n)) for n in names])
    run_jobs(root)
    return rm, sign_in(client, ANALYST), sign_in(client, MANAGER), case_id


def _numeric_field(client: TestClient, headers: dict, case_id: str) -> dict:
    fields = client.get(f"/api/cases/{case_id}/fields", headers=headers).json()
    return next(f for f in fields if isinstance(f["value"], (int, float)) and not isinstance(f["value"], bool))


def _edit(client, headers, case_id, field_id, value, reason=REASON, file=None):
    # Always multipart, as the screen sends it: the two words as plain parts, the paper as a file.
    parts = [("value", (None, value)), ("reason", (None, reason))]
    if file:
        parts.append(("files", file))
    return client.post(f"/api/cases/{case_id}/fields/{field_id}/edit", files=parts, headers=headers)


def _field(client, headers, case_id, field_id):
    return next(f for f in client.get(f"/api/cases/{case_id}/fields", headers=headers).json() if f["id"] == field_id)


def test_the_analyst_changes_a_figure_with_a_reason_and_a_paper_and_it_waits_for_a_check(
    client: TestClient, published_data_root: Path
):
    _, analyst, manager, case_id = _case(client, published_data_root)
    f = _numeric_field(client, analyst, case_id)
    r = _edit(client, analyst, case_id, f["id"], "1,23,45,000", file=("letter.pdf", b"%PDF-1.7 letter", "application/pdf"))
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["kind"] == "manual_entry" and item["status"] == "open" and item["maker"] == "ananya-krishnan"
    assert item["edit"]["to_value"] == 12345000 and item["edit"]["from_value"] == f["value"]
    assert item["edit"]["reason"] == REASON and item["edit"]["attachment"]["name"] == "letter.pdf"

    # Nothing on the field moves until the check: the figure in force is what it was.
    now = _field(client, analyst, case_id, f["id"])
    assert (now["value"], now["corrected_value"], now["status"]) == (f["value"], f["corrected_value"], f["status"])
    # The Credit Manager sees it in the queue, with the paper.
    queue = client.get(f"/api/review?case_id={case_id}", headers=manager).json()
    assert any(i["id"] == item["id"] and i["edit"] for i in queue)
    paper = client.get(f"/api/review/{item['id']}/attachment", headers=manager)
    assert paper.status_code == 200 and paper.content == b"%PDF-1.7 letter"

    conn = db.connect(published_data_root)
    try:
        logged = conn.execute(
            "SELECT detail FROM decision_log WHERE action = 'figure.edited' AND case_id = ?", (case_id,)
        ).fetchone()
    finally:
        conn.close()
    assert json.loads(logged["detail"])["attachment"] == "letter.pdf"


def test_the_credit_manager_approves_and_the_analyst_cannot_check_their_own(
    client: TestClient, published_data_root: Path
):
    _, analyst, manager, case_id = _case(client, published_data_root)
    f = _numeric_field(client, analyst, case_id)
    r = _edit(client, analyst, case_id, f["id"], "4200000")
    assert r.status_code == 200, r.text
    item = r.json()
    own = client.post(f"/api/review/{item['id']}/decision", json={"decision": "confirm"}, headers=analyst)
    assert own.status_code == 403
    ok = client.post(f"/api/review/{item['id']}/decision", json={"decision": "confirm"}, headers=manager)
    assert ok.status_code == 200 and ok.json()["decided_by"] == "meenal-kulkarni"
    # Both values are kept; the person's is in force.
    now = _field(client, manager, case_id, f["id"])
    assert now["status"] == "corrected" and now["corrected_value"] == 4200000 and now["value"] == f["value"]


def test_a_change_sent_back_leaves_the_figure_as_it_was(client: TestClient, published_data_root: Path):
    _, analyst, manager, case_id = _case(client, published_data_root)
    f = _numeric_field(client, analyst, case_id)
    item = _edit(client, analyst, case_id, f["id"], "4200000").json()
    no_reason = client.post(f"/api/review/{item['id']}/decision", json={"decision": "waive"}, headers=manager)
    assert no_reason.status_code == 422
    back = client.post(f"/api/review/{item['id']}/decision",
                       json={"decision": "waive", "reason": "The letter covers another year"}, headers=manager)
    assert back.status_code == 200
    now = _field(client, manager, case_id, f["id"])
    assert now["status"] == f["status"] and now["corrected_value"] == f["corrected_value"]
    assert all(i["id"] != item["id"] for i in client.get(f"/api/review?case_id={case_id}", headers=manager).json())


def test_who_may_change_a_figure_and_what_a_change_needs(client: TestClient, published_data_root: Path):
    rm, analyst, manager, case_id = _case(client, published_data_root)
    f = _numeric_field(client, analyst, case_id)
    # Only the maker role changes figures: not the RM, not the Credit Manager.
    assert _edit(client, rm, case_id, f["id"], "100").status_code == 403
    assert _edit(client, manager, case_id, f["id"], "100").status_code == 403
    # A reason of substance, a number for a number, a change at all, a paper of a known kind.
    assert _edit(client, analyst, case_id, f["id"], "100", reason="typo").status_code == 422
    assert _edit(client, analyst, case_id, f["id"], "about a crore").status_code == 422
    assert _edit(client, analyst, case_id, f["id"], str(f["value"])).status_code == 422
    assert _edit(client, analyst, case_id, f["id"], "100", file=("run.exe", b"MZ", "application/octet-stream")).status_code == 422
    assert _edit(client, analyst, case_id, "FV-nope", "100").status_code == 404
    # A date stays a date.
    fields = client.get(f"/api/cases/{case_id}/fields", headers=analyst).json()
    dated = next(x for x in fields if isinstance(x["value"], str) and len(x["value"]) == 10
                 and x["value"][4] == "-")
    assert _edit(client, analyst, case_id, dated["id"], "12,34,567").status_code == 422
    assert _edit(client, analyst, case_id, dated["id"], "31-02-2026").status_code == 422


def test_a_name_or_a_date_changes_as_written(client: TestClient, published_data_root: Path):
    _, analyst, manager, case_id = _case(client, published_data_root)
    fields = client.get(f"/api/cases/{case_id}/fields", headers=analyst).json()
    dated = next(x for x in fields if isinstance(x["value"], str) and len(x["value"]) == 10
                 and x["value"][4] == "-")
    named = next(x for x in fields if isinstance(x["value"], str) and x["id"] != dated["id"]
                 and not x["value"][:4].isdigit())
    # A date typed day first is kept as the documents keep it.
    item = _edit(client, analyst, case_id, dated["id"], "15-09-2026").json()
    assert item["edit"]["to_value"] == "2026-09-15"
    item2 = _edit(client, analyst, case_id, named["id"], "M/s. Iyer and Co., Chartered Accountants").json()
    assert item2["edit"]["to_value"] == "M/s. Iyer and Co., Chartered Accountants"
    for i in (item, item2):
        assert client.post(f"/api/review/{i['id']}/decision", json={"decision": "confirm"},
                           headers=manager).status_code == 200
    assert _field(client, manager, case_id, dated["id"])["corrected_value"] == "2026-09-15"
    assert _field(client, manager, case_id, named["id"])["status"] == "corrected"


def test_while_a_change_waits_the_value_is_not_decided_another_way(client: TestClient, published_data_root: Path):
    _, analyst, manager, case_id = _case(client, published_data_root)
    f = _numeric_field(client, analyst, case_id)
    # The figure also waits for a check of its reading (as a low-confidence value does).
    conn = db.connect(published_data_root)
    try:
        with db.transaction(conn):
            check_id = raise_item(conn, case_id=case_id, kind="field", ref=f"field:{f['id']}",
                                  summary="low confidence", detail={"field_value_id": f["id"]})
    finally:
        conn.close()
    item = _edit(client, analyst, case_id, f["id"], "4200000").json()
    # The system's value cannot be confirmed past the change that waits.
    refused = client.post(f"/api/review/{check_id}/decision", json={"decision": "confirm"}, headers=analyst)
    assert refused.status_code == 409
    # Approving the change settles that check too.
    assert client.post(f"/api/review/{item['id']}/decision", json={"decision": "confirm"},
                       headers=manager).status_code == 200
    still_open = client.get(f"/api/review?case_id={case_id}", headers=analyst).json()
    assert all(i["id"] != check_id for i in still_open)
