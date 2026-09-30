"""Review decisions (F-17.5): confirm, correct, waive or assign.

Every decision is an overlay with its reason: the system's value and the
person's are both kept (field values keep `value` and `corrected_value`;
a type assignment keeps the original classification), and the decision is
written to the append-only decision log. Nothing here touches
configuration (principle 4).

- field:        confirm, or correct (value and reason required).
- type:         assign a type from the closed list (extraction then re-runs
                for that document), or waive with a reason (not needed).
- quality:      confirm a readable grade-C copy; waive with a reason when
                every checklist item the document serves is non-mandatory;
                correct = manual entry of the values (F-07.5) by a maker,
                which a different person with the checker permission
                confirms on the resulting manual_entry item (F-03.4).
- party:        confirm the attribution, or correct it (value: party id,
                or "none") with a reason (F-10.5).
- split:        confirm.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import cases, completeness, jobs
from .configstore import reader
from .contracts import ReviewDecisionRequest, ReviewItem
from .db import log_decision, transaction
from .pipeline import effective_types, refresh_case
from .review_items import close_item, reopen_item
from .util import dumps, now_iso, stable_id


class ReviewError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _require(cond: bool, message: str, status: int = 422) -> None:
    if not cond:
        raise ReviewError(status, message)


def _item(conn: sqlite3.Connection, item_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM review_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise ReviewError(404, f"no review item {item_id!r}")
    return row


def _doc(conn: sqlite3.Connection, detail: dict) -> sqlite3.Row | None:
    if not detail.get("document_id"):
        return None
    return conn.execute("SELECT * FROM documents WHERE id = ?", (detail["document_id"],)).fetchone()


def _settle_document(conn: sqlite3.Connection, document_id: str) -> None:
    """A document in review is accepted once no value of it awaits review."""
    open_values = conn.execute(
        "SELECT COUNT(*) FROM field_values WHERE document_id = ? AND status = 'in_review'", (document_id,)
    ).fetchone()[0]
    if not open_values:
        conn.execute("UPDATE documents SET status = 'accepted' WHERE id = ? AND status = 'in_review'", (document_id,))


def _items_served(conn: sqlite3.Connection, root: Path, case_id: str, types: list[str]):
    case = cases.get_case(conn, case_id)
    data = completeness.load_case_data(conn, case)
    items, _ = completeness.applicable_items(root, case, data)
    type_defs = {t.id: t for t in reader.load_document_types(root).types}
    served = {i for t in types if t in type_defs for i in type_defs[t].satisfies}
    return [i for i in items if i.id in served]


def decide(
    conn: sqlite3.Connection, root: Path, item_id: str, body: ReviewDecisionRequest, user: dict
) -> ReviewItem:
    item = _item(conn, item_id)
    _require(item["status"] == "open", "this item has already been decided", 409)
    kind, decision = item["kind"], body.decision
    reason = (body.reason or "").strip() or None
    detail = json.loads(item["detail"] or "{}")
    case_id = item["case_id"]
    permissions = set(user["permissions"])
    log: dict = {"item_id": item_id, "kind": kind, "ref": item["ref"], "decision": decision, "reason": reason}
    decided_by = user["id"]
    queue_reextract: str | None = None

    if decision in ("correct", "waive"):
        _require(reason is not None, f"a reason is required to {decision}")

    with transaction(conn):
        if kind == "field":
            fv = conn.execute("SELECT * FROM field_values WHERE id = ?", (detail.get("field_value_id"),)).fetchone()
            _require(fv is not None, "the field value no longer exists", 409)
            if decision == "confirm":
                conn.execute("UPDATE field_values SET status = 'accepted' WHERE id = ?", (fv["id"],))
            elif decision == "correct":
                _require(body.value is not None, "a corrected value is required")
                conn.execute(
                    "UPDATE field_values SET corrected_value = ?, status = 'corrected' WHERE id = ?",
                    (json.dumps(body.value), fv["id"]),
                )
                log.update(field=fv["field"], system_value=json.loads(fv["value"]), corrected_value=body.value)
            else:
                raise ReviewError(422, "a field value is confirmed or corrected")
            _settle_document(conn, fv["document_id"])

        elif kind == "type":
            doc = _doc(conn, detail)
            _require(doc is not None, "the document no longer exists", 409)
            if decision == "assign":
                type_ids = {t.id for t in reader.load_document_types(root).types}
                _require(isinstance(body.value, str) and body.value in type_ids,
                         "assign needs a document type id from the closed list")
                conn.execute(
                    "UPDATE documents SET assigned_types = ?, status = 'classified' WHERE id = ?",
                    (json.dumps([body.value]), doc["id"]),
                )
                log.update(document_id=doc["id"], assigned_type=body.value,
                           classification=json.loads(doc["classification"] or "null"))
                queue_reextract = doc["id"]
            elif decision == "waive":
                log.update(document_id=doc["id"])
            else:
                raise ReviewError(422, "an unclassified document is assigned a type, or waived as not needed")

        elif kind == "quality":
            doc = _doc(conn, detail)
            if decision == "confirm":
                _require(doc is None or doc["grade"] != "U",
                         "an unreadable document needs a better copy, manual entry or a waiver")
            elif decision == "waive":
                if doc is not None:
                    served = _items_served(conn, root, case_id, effective_types(doc))
                    mandatory = [i.name for i in served if i.blocking]
                    _require(not mandatory, "only a non-mandatory item can be waived: " + ", ".join(mandatory))
                    for i in served:
                        conn.execute(
                            """INSERT INTO checklist_waivers (case_id, item_id, reason, decided_by, decided_at,
                                   review_item_id) VALUES (?, ?, ?, ?, ?, ?)
                               ON CONFLICT(case_id, item_id) DO NOTHING""",
                            (case_id, i.id, reason, user["id"], now_iso(), item_id),
                        )
                    log.update(waived_items=[i.id for i in served])
            elif decision == "correct":
                _manual_entry(conn, root, item, doc, body, user, reason, log)
            else:
                raise ReviewError(422, "a quality exception is confirmed, waived or entered manually")

        elif kind == "manual_entry":
            _require("manual.check" in permissions, "confirming a manual entry needs the checker permission", 403)
            _require(item["maker"] != user["id"], "the checker must be a different person from the maker", 403)
            _require(decision == "confirm", "a manual entry is confirmed by the checker")
            doc = _doc(conn, detail)
            _require(doc is not None, "the document no longer exists", 409)
            conn.execute(
                "UPDATE field_values SET status = 'accepted' WHERE document_id = ? AND method = 'manual'", (doc["id"],)
            )
            conn.execute("UPDATE documents SET status = 'accepted' WHERE id = ?", (doc["id"],))
            log.update(document_id=doc["id"], maker=item["maker"])

        elif kind == "party":
            doc = _doc(conn, detail)
            _require(doc is not None, "the document no longer exists", 409)
            if decision == "confirm":
                override = doc["party_id"] or "none"
            elif decision == "correct":
                value = str(body.value or "")
                exists = conn.execute(
                    "SELECT 1 FROM parties WHERE id = ? AND case_id = ?", (value, case_id)
                ).fetchone()
                _require(value == "none" or exists is not None, "correct needs a party id of this case, or 'none'")
                override = value
            else:
                raise ReviewError(422, "an attribution is confirmed or corrected")
            conn.execute("UPDATE documents SET party_override = ? WHERE id = ?", (override, doc["id"]))
            log.update(document_id=doc["id"], system_party=doc["party_id"], party=override)

        elif kind == "split":
            _require(decision == "confirm", "an uncertain split is confirmed")
        elif kind == "finding":
            # F-17.4, C5: a person accepts the flag as valid (confirm) or finds
            # it not valid (waive, with the reason). The finding itself stays.
            _require(decision in ("confirm", "waive"), "a finding is confirmed as valid or waived with a reason")
        else:
            raise ReviewError(422, f"{kind} items are decided elsewhere")

        close_item(conn, item_id=item_id, decision=decision, reason=reason, decided_by=decided_by)
        if queue_reextract:
            log["job_id"] = jobs.enqueue(
                conn, case_id=case_id, kind="reextract", payload={"document_id": queue_reextract}
            )
        log_decision(conn, at=now_iso(), actor=user["id"], case_id=case_id, action="review.decided",
                     detail=dumps(log))

    refresh_case(conn, root, case_id)
    row = conn.execute("SELECT * FROM review_items WHERE id = ?", (item_id,)).fetchone()
    return ReviewItem(**dict(row))


def _manual_entry(
    conn: sqlite3.Connection,
    root: Path,
    item: sqlite3.Row,
    doc: sqlite3.Row | None,
    body: ReviewDecisionRequest,
    user: dict,
    reason: str | None,
    log: dict,
) -> None:
    """F-07.5: the maker enters the values of an unreadable document from its
    type's dictionary; they wait for a checker."""
    _require("manual.make" in set(user["permissions"]), "manual entry needs the maker permission", 403)
    _require(doc is not None, "manual entry is for a document; this exception is a whole file")
    _require(bool(body.values), "manual entry needs the values, by field")
    types = effective_types(doc)
    if not types:
        type_ids = {t.id for t in reader.load_document_types(root).types}
        _require(isinstance(body.value, str) and body.value in type_ids,
                 "give the document's type (value) with a manual entry, as it could not be classified")
        types = [body.value]
        conn.execute("UPDATE documents SET assigned_types = ? WHERE id = ?", (json.dumps(types), doc["id"]))
    type_defs = {t.id: t for t in reader.load_document_types(root).types}
    allowed: set[str] = set()
    for t in types:
        if t in type_defs and type_defs[t].dictionary:
            try:
                allowed |= {f.name for f in reader.load_dictionary(root, type_defs[t].dictionary).fields}
            except reader.NoPublishedConfig:
                pass
    unknown = [k for k in body.values if k.split("[", 1)[0].split(".", 1)[0] not in allowed]
    _require(not unknown, f"not fields of this document type: {', '.join(unknown)}")
    cap = reader.load_confidence(root).manual_entry_cap
    for name, value in body.values.items():
        conn.execute(
            """INSERT INTO field_values (id, case_id, document_id, field, value, raw, evidence, method, confidence,
                   confidence_components, status)
               VALUES (?, ?, ?, ?, ?, NULL, ?, 'manual', ?, ?, 'in_review')
               ON CONFLICT(id) DO UPDATE SET value = excluded.value, method = 'manual',
                   confidence = excluded.confidence, status = 'in_review'""",
            (
                stable_id("FV", doc["id"], name),
                item["case_id"],
                doc["id"],
                name,
                json.dumps(value),
                json.dumps({"document_id": doc["id"], "page": doc["page_from"], "bbox": None}),
                cap,
                json.dumps({"cap.manual_entry": cap}),
            ),
        )
    reopen_item(
        conn,
        case_id=item["case_id"],
        kind="manual_entry",
        ref=f"document:{doc['id']}",
        summary=f"Manual entry of {len(body.values)} value(s) by {user['name']}, awaiting a checker",
        detail={"document_id": doc["id"], "fields": sorted(body.values)},
        maker=user["id"],
    )
    log.update(document_id=doc["id"], manual_values=body.values)
