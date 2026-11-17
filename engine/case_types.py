"""Case document types (F-09.8 to F-09.10, F-15.8; FRD decision 13).

When no type in the published list fits an unclassified document, a person
may make a type for that case: a name, an optional description and,
optionally, the fields to read. The document is then read by the model as
that type (F-15.8). A case document type:

- belongs to one case and is offered only there;
- is never offered to the classifier, so it changes no other case;
- is never edited in place: a change is a new type naming the one it replaces;
- satisfies no checklist item unless a person maps it (F-09.9).

It is a recorded decision, not configuration: it lives in the case store,
and becomes part of the closed list only when the Administrator publishes
it (F-09.10). Its id is `CDT-...`, which never collides with a published id.
"""

from __future__ import annotations

import json
import re
import sqlite3

from pathlib import Path

from .contracts import (
    CaseDocumentType,
    CaseDocumentTypeField,
    CaseDocumentTypeProposal,
    CaseTypeMapping,
    NewCaseDocumentType,
    NewCaseTypeMapping,
)
from .contracts.ingest import CaseField, CaseType
from .db import log_decision, transaction
from .review_items import raise_item
from .util import dumps, now_iso, stable_id

PREFIX = "CDT-"
MAX_FIELDS = 20
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class CaseTypeError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def is_case_type(type_id: str | None) -> bool:
    return bool(type_id) and type_id.startswith(PREFIX)


def field_name(label: str) -> str:
    """A field's dictionary name from what a person typed: "Sanction date" -> sanction_date."""
    return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")[:40]


def _row(conn: sqlite3.Connection, r: sqlite3.Row) -> CaseDocumentType:
    maps = conn.execute("SELECT * FROM case_type_mappings WHERE case_type_id = ? ORDER BY proposed_at, id", (r["id"],))
    return CaseDocumentType(
        id=r["id"], case_id=r["case_id"], name=r["name"], description=r["description"],
        fields=[CaseDocumentTypeField(**f) for f in json.loads(r["fields"])],
        replaces=r["replaces"], made_by=r["made_by"], made_at=r["made_at"],
        mappings=[CaseTypeMapping(**{k: m[k] for k in CaseTypeMapping.model_fields}) for m in maps],
    )


def list_for_case(conn: sqlite3.Connection, case_id: str) -> list[CaseDocumentType]:
    rows = conn.execute("SELECT * FROM case_document_types WHERE case_id = ? ORDER BY made_at, id", (case_id,))
    return [_row(conn, r) for r in rows]


def get(conn: sqlite3.Connection, case_id: str, type_id: str) -> CaseDocumentType | None:
    r = conn.execute("SELECT * FROM case_document_types WHERE case_id = ? AND id = ?", (case_id, type_id)).fetchone()
    return _row(conn, r) if r else None


def names(conn: sqlite3.Connection, case_id: str) -> dict[str, str]:
    """The case's own types by id, for labels next to the published names."""
    return {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM case_document_types WHERE case_id = ?", (case_id,))}


def create(conn: sqlite3.Connection, case_id: str, body: NewCaseDocumentType, user: dict,
           published_names: set[str]) -> CaseDocumentType:
    name = " ".join(body.name.split())
    if not name or len(name) > 80:
        raise CaseTypeError(422, "a case document type needs a name of up to 80 characters")
    if name.casefold() in {n.casefold() for n in published_names}:
        raise CaseTypeError(422, f"{name} is already a published document type: assign it from the list")
    fields, seen = [], set()
    for f in body.fields:
        fname = field_name(f.name)
        if not _NAME.match(fname):
            raise CaseTypeError(422, f"{f.name!r} is not a usable field name")
        if fname in seen:
            raise CaseTypeError(422, f"the field {fname} is named twice")
        seen.add(fname)
        hint = " ".join((f.hint or "").split()) or None
        fields.append({"name": fname, "hint": hint[:200] if hint else None})
    if len(fields) > MAX_FIELDS:
        raise CaseTypeError(422, f"a case document type reads at most {MAX_FIELDS} fields")
    if body.replaces and get(conn, case_id, body.replaces) is None:
        raise CaseTypeError(404, f"no case document type {body.replaces!r} on this case")
    at = now_iso()
    type_id = stable_id("CDT", case_id, name, json.dumps(fields), at)
    description = " ".join((body.description or "").split()) or None
    with transaction(conn):
        conn.execute(
            """INSERT INTO case_document_types (id, case_id, name, description, fields, replaces, made_by, made_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (type_id, case_id, name, description, json.dumps(fields), body.replaces, user["id"], at),
        )
        log_decision(
            conn, at=at, actor=user["id"], case_id=case_id, action="document_type.case_made",
            detail=json.dumps({"type_id": type_id, "name": name, "fields": [f["name"] for f in fields],
                               "replaces": body.replaces}),
        )
    return get(conn, case_id, type_id)  # type: ignore[return-value]


def satisfies(conn: sqlite3.Connection, case_id: str) -> dict[str, set[str]]:
    """F-09.9: the checklist items each case document type is confirmed to satisfy."""
    out: dict[str, set[str]] = {}
    for r in conn.execute("SELECT case_type_id, item_id FROM case_type_mappings WHERE case_id = ? AND status = 'confirmed'",
                          (case_id,)):
        out.setdefault(r["case_type_id"], set()).add(r["item_id"])
    return out


def map_to_item(conn: sqlite3.Connection, root: Path, case_id: str, type_id: str, body: NewCaseTypeMapping,
                user: dict) -> CaseDocumentType:
    """F-09.9: map a case document type to one of the case's checklist items. An item that is not mandatory
    is mapped at once; a mandatory one is proposed here and confirmed by a checker on the review queue (never
    the maker). Only an item one valid document suffices for can be mapped: an item checked by years,
    periods, accounts or parties reads fields only a published type has."""
    from . import cases, completeness  # completeness reads the mappings back: imported here, not at the top

    t = get(conn, case_id, type_id)
    if t is None:
        raise CaseTypeError(404, f"no case document type {type_id!r} on this case")
    case = cases.get_case(conn, case_id)
    items, _ = completeness.applicable_items(root, case, completeness.load_case_data(conn, case))
    item = next((i for i in items if i.id == body.item_id), None)
    if item is None:
        raise CaseTypeError(422, f"{body.item_id!r} is not a checklist item of this case")
    if item.coverage is not None:
        raise CaseTypeError(422, f"{item.name} is checked by {item.coverage.kind.replace('_', ' ')}: it needs a published type")
    open_or_done = conn.execute(
        "SELECT status FROM case_type_mappings WHERE case_type_id = ? AND item_id = ? AND status <> 'refused'",
        (type_id, item.id),
    ).fetchone()
    if open_or_done:
        raise CaseTypeError(409, f"{t.name} is already {open_or_done['status']} for {item.name}")
    reason = " ".join((body.reason or "").split()) or None
    if item.blocking and not reason:
        raise CaseTypeError(422, "mapping to a mandatory item needs a reason for the checker")
    at = now_iso()
    mapping_id = stable_id("MAP", case_id, type_id, item.id, at)
    with transaction(conn):
        conn.execute(
            """INSERT INTO case_type_mappings (id, case_id, case_type_id, item_id, status, reason, proposed_by, proposed_at,
                   decided_by, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mapping_id, case_id, type_id, item.id, "proposed" if item.blocking else "confirmed", reason, user["id"], at,
             None if item.blocking else user["id"], None if item.blocking else at),
        )
        if item.blocking:
            raise_item(conn, case_id=case_id, kind="mapping", ref=f"mapping:{mapping_id}", maker=user["id"],
                       summary=f"{t.name} to satisfy {item.name} (mandatory): {reason}",
                       detail={"mapping_id": mapping_id, "case_type_id": type_id, "item_id": item.id})
        log_decision(conn, at=at, actor=user["id"], case_id=case_id,
                     action="document_type.mapping_proposed" if item.blocking else "document_type.mapped",
                     detail=dumps({"mapping_id": mapping_id, "type_id": type_id, "item_id": item.id, "reason": reason}))
    return get(conn, case_id, type_id)  # type: ignore[return-value]


def decide_mapping(conn: sqlite3.Connection, detail: dict, decision: str, user: dict) -> dict:
    """The checker's decision on a proposed mapping to a mandatory item (inside the review transaction):
    confirm maps it; waive refuses it. Returns what the decision log keeps."""
    m = conn.execute("SELECT * FROM case_type_mappings WHERE id = ?", (detail.get("mapping_id"),)).fetchone()
    if m is None or m["status"] != "proposed":
        raise CaseTypeError(409, "the mapping is no longer waiting for a checker")
    if "manual.check" not in set(user["permissions"]):
        raise CaseTypeError(403, "a mapping to a mandatory item is confirmed by a checker")
    if m["proposed_by"] == user["id"]:
        raise CaseTypeError(403, "the maker of a mapping cannot also check it")
    if decision not in ("confirm", "waive"):
        raise CaseTypeError(422, "a mapping is confirmed, or refused by waiving it with a reason")
    status = "confirmed" if decision == "confirm" else "refused"
    conn.execute("UPDATE case_type_mappings SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
                 (status, user["id"], now_iso(), m["id"]))
    return {"mapping_id": m["id"], "case_type_id": m["case_type_id"], "item_id": m["item_id"], "mapping": status}


def as_ingest(t: CaseDocumentType) -> CaseType:
    """What the document-processing service is told about the type (F-15.8)."""
    return CaseType(id=t.id, name=t.name, description=t.description,
                    fields=[CaseField(name=f.name, hint=f.hint) for f in t.fields])


def proposals(conn: sqlite3.Connection) -> list[CaseDocumentTypeProposal]:
    """F-09.10: every case document type, grouped by name, for the Administrator. Counts and dates
    only: the Administrator has no access to appraisals, so no case or borrower is named."""
    groups: dict[str, dict] = {}
    rows = conn.execute(
        """SELECT t.id, t.case_id, t.name, t.description, t.fields, t.made_at,
                  (SELECT COUNT(*) FROM documents d WHERE d.assigned_types = json_array(t.id)) AS documents
           FROM case_document_types t ORDER BY t.made_at, t.id"""
    )
    for r in rows:
        g = groups.setdefault(r["name"].casefold(), {"name": r["name"], "description": None, "fields": [],
                                                     "cases": set(), "documents": 0, "first_made": r["made_at"],
                                                     "last_made": r["made_at"]})
        g["description"] = r["description"] or g["description"]
        for f in json.loads(r["fields"]):
            if f["name"] not in [x["name"] for x in g["fields"]]:
                g["fields"].append(f)
        g["cases"].add(r["case_id"])
        g["documents"] += r["documents"]
        g["last_made"] = r["made_at"]
    return [
        CaseDocumentTypeProposal(
            name=g["name"], description=g["description"],
            fields=[CaseDocumentTypeField(**f) for f in g["fields"]],
            cases=len(g["cases"]), documents=g["documents"], first_made=g["first_made"], last_made=g["last_made"],
        )
        for g in sorted(groups.values(), key=lambda g: (-len(g["cases"]), g["name"].casefold()))
    ]
