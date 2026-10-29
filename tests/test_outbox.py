"""The send step behind the case assistant: a customer message is recorded against the case and logged."""

import sqlite3

import pytest

from engine import db
from tests.conftest import ANALYST, MANAGER, RM, make_case, sign_in

MSG = {"to": "customer@example.com", "subject": "Please resend corrected documents", "body": "Hello,\n\nPlease resend the bank statement.\n", "idempotency_key": "p_1"}


def _case(client, root):
    rm = sign_in(client, RM)
    return rm, make_case(client, rm, root)


def _log(root, case_id):
    conn = db.connect(root)
    try:
        return [dict(r) for r in conn.execute("SELECT actor, action, detail FROM decision_log WHERE case_id = ? AND action = 'message.send'", (case_id,))]
    finally:
        conn.close()


def test_a_message_is_recorded_listed_and_logged(client, published_data_root):
    rm, case_id = _case(client, published_data_root)
    r = client.post(f"/api/cases/{case_id}/messages", headers=rm, json=MSG)
    assert r.status_code == 200
    sent = r.json()
    assert sent["status"] == "recorded" and sent["to"] == MSG["to"] and sent["case_id"] == case_id
    assert [m["id"] for m in client.get(f"/api/cases/{case_id}/messages", headers=rm).json()] == [sent["id"]]
    [entry] = _log(published_data_root, case_id)
    assert entry["actor"] == "arjun-deshpande"
    assert "body_sha256" in entry["detail"] and "bank statement" not in entry["detail"]  # a fingerprint, not the text


def test_the_same_key_records_once(client, published_data_root):
    rm, case_id = _case(client, published_data_root)
    a = client.post(f"/api/cases/{case_id}/messages", headers=rm, json=MSG).json()
    b = client.post(f"/api/cases/{case_id}/messages", headers=rm, json=MSG).json()
    assert a["id"] == b["id"]
    assert len(client.get(f"/api/cases/{case_id}/messages", headers=rm).json()) == 1
    assert len(_log(published_data_root, case_id)) == 1


def test_a_key_cannot_be_reused_by_someone_else(client, published_data_root):
    rm, case_id = _case(client, published_data_root)
    client.post(f"/api/cases/{case_id}/messages", headers=rm, json=MSG)
    analyst = sign_in(client, ANALYST)
    r = client.post(f"/api/cases/{case_id}/messages", headers=analyst, json=MSG)
    assert r.status_code == 422


@pytest.mark.parametrize("change", [
    {"to": "not-an-address"}, {"to": "a@b.com, c@d.com"}, {"to": ""},
    {"subject": ""}, {"subject": "two\nlines"}, {"subject": "x" * 201},
    {"body": "   "}, {"body": "x" * 5001}, {"idempotency_key": ""},
])
def test_an_invalid_message_is_refused_and_nothing_is_recorded(client, published_data_root, change):
    rm, case_id = _case(client, published_data_root)
    r = client.post(f"/api/cases/{case_id}/messages", headers=rm, json={**MSG, **change})
    assert r.status_code == 422
    assert client.get(f"/api/cases/{case_id}/messages", headers=rm).json() == []
    assert _log(published_data_root, case_id) == []


def test_access_follows_the_user_and_the_case(client, published_data_root):
    rm, case_id = _case(client, published_data_root)
    assert client.post(f"/api/cases/{case_id}/messages", json=MSG).status_code == 401
    assert client.post("/api/cases/NOPE/messages", headers=rm, json=MSG).status_code == 404
    manager = sign_in(client, MANAGER)  # may read the case, has no right to send
    assert client.post(f"/api/cases/{case_id}/messages", headers=manager, json=MSG).status_code == 403
    assert client.get(f"/api/cases/{case_id}/messages", headers=manager).status_code == 200


def test_a_recorded_message_cannot_be_edited(client, published_data_root):
    rm, case_id = _case(client, published_data_root)
    client.post(f"/api/cases/{case_id}/messages", headers=rm, json=MSG)
    conn = db.connect(published_data_root)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("UPDATE outbox SET body = 'changed'")
    finally:
        conn.close()


def test_deleting_the_case_removes_its_messages_and_keeps_the_log(client, published_data_root):
    rm, case_id = _case(client, published_data_root)
    client.post(f"/api/cases/{case_id}/messages", headers=rm, json=MSG)
    assert client.request("DELETE", f"/api/cases/{case_id}", headers=rm, json={"reason": "testing"}).status_code == 204
    conn = db.connect(published_data_root)
    try:
        assert conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        conn.close()
    assert len(_log(published_data_root, case_id)) == 1
