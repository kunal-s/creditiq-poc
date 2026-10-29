"""Customer messages recorded for sending.

The case assistant's send step ends here: the message is stored against the case and an entry goes to the decision
log. Delivery itself is a later, configured step; until then a recorded message is the whole effect, and
nothing leaves the bank. The same idempotency key returns the message already recorded, so a retry cannot send twice.
"""

from __future__ import annotations

import json
import re
import sqlite3
from hashlib import sha256

from . import db
from .contracts.documents import MessageRequest, OutboxMessage
from .util import now_iso

_ADDRESS = re.compile(r"^[^@\s,;<>()\[\]]{1,64}@[^@\s,;<>()\[\]]{1,190}\.[^@\s,;<>()\[\]]{2,24}$")
SUBJECT_LIMIT, BODY_LIMIT, KEY_LIMIT = 200, 5000, 64


class MessageError(ValueError):
    """The message cannot be recorded as given; the text says what to fix."""


def _check(m: MessageRequest) -> None:
    if not _ADDRESS.match(m.to.strip()):
        raise MessageError("The recipient address is not valid.")
    if not m.subject.strip() or len(m.subject) > SUBJECT_LIMIT or "\n" in m.subject or "\r" in m.subject:
        raise MessageError(f"The subject must be one line of up to {SUBJECT_LIMIT} characters.")
    if not m.body.strip() or len(m.body) > BODY_LIMIT:
        raise MessageError(f"The message must be 1 to {BODY_LIMIT} characters.")
    if not m.idempotency_key.strip() or len(m.idempotency_key) > KEY_LIMIT:
        raise MessageError("The idempotency key is missing.")


def _view(r: sqlite3.Row) -> OutboxMessage:
    return OutboxMessage(
        id=r["id"], case_id=r["case_id"], to=r["to_address"], subject=r["subject"], status=r["status"],
        created_at=r["created_at"], created_by=r["created_by"],
    )


def record(conn: sqlite3.Connection, case_id: str, actor: str, m: MessageRequest) -> OutboxMessage:
    _check(m)
    key = m.idempotency_key.strip()
    now = now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT * FROM outbox WHERE idempotency_key = ?", (key,)).fetchone()
        if row is not None:
            if row["case_id"] != case_id or row["created_by"] != actor:
                raise MessageError("The idempotency key belongs to another message.")
            conn.execute("COMMIT")
            return _view(row)
        cur = conn.execute(
            "INSERT INTO outbox (case_id, idempotency_key, to_address, subject, body, status, created_at, created_by)"
            " VALUES (?, ?, ?, ?, ?, 'recorded', ?, ?)",
            (case_id, key, m.to.strip(), m.subject.strip(), m.body, now, actor),
        )
        # The log carries the recipient, the subject and a fingerprint of the body, not the body itself.
        db.log_decision(
            conn, at=now, actor=actor, case_id=case_id, action="message.send",
            detail=json.dumps({"outbox_id": cur.lastrowid, "to": m.to.strip(), "subject": m.subject.strip(),
                               "body_sha256": sha256(m.body.encode()).hexdigest()}),
        )
        row = conn.execute("SELECT * FROM outbox WHERE id = ?", (cur.lastrowid,)).fetchone()
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return _view(row)


def listing(conn: sqlite3.Connection, case_id: str) -> list[OutboxMessage]:
    rows = conn.execute("SELECT * FROM outbox WHERE case_id = ? ORDER BY id DESC", (case_id,)).fetchall()
    return [_view(r) for r in rows]
