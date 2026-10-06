"""The case's party set, KYC attribution and label checks (F-10).

- F-10.2 The party set is built from constitution documents (board
  resolution, partnership deed, GST registration persons), consumer bureau
  reports and the application message; each party carries its source.
- F-10.3 Personal documents are attributed by PAN or DIN first, then by
  normalised name (tolerance `name_match`). A document whose file label names
  a different party is re-filed under the matching party and flagged; one
  that matches no party is flagged as possibly not belonging to the case.
  Both flags are party review items (F-10.5: a person confirms or overrides).
- F-10.1 The label hint (file name and folders) is compared with the
  classified type; a disagreement sets `label_mismatch`. The hint never
  feeds classification.

Rebuilt from the stored documents every time, so the result depends only on
the case's documents and person decisions, never on processing order.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .config import load_app_config
from .configstore import reader
from .configstore.schema import PartyList
from .contracts import Party
from .names import normalise_name, similarity, tokens
from .review_items import close_item, raise_item
from .util import stable_id

_CELL = re.compile(r"^(\w+)\[(\d+)\]\.(\w+)$")
_ITEM = re.compile(r"^(\w+)\[(\d+)\]$")


def party_list_spec(type_def) -> PartyList | None:
    """The people a document type names (config/document_types.yaml `party_list`), or None."""
    return type_def.party_list if type_def is not None else None


def party_entries(fields: dict[str, tuple[object, int | None]], spec: PartyList) -> list[dict]:
    """The people listed in a document's fields: name, and DIN, PAN and designation where printed."""
    if spec.name_key:
        out = []
        for row in table_rows(fields, spec.field):
            name = row.get(spec.name_key, (None, None))
            if name[0]:
                out.append({"name": str(name[0]), "page": name[1],
                            "din": _ident(row.get(spec.din_key)) if spec.din_key else None,
                            "pan": _ident(row.get(spec.pan_key)) if spec.pan_key else None,
                            "designation": row.get(spec.designation_key, (None, None))[0] if spec.designation_key else None})
        return out
    items = []
    for key, (value, page) in fields.items():
        m = _ITEM.match(key)
        if m and m[1] == spec.field and value:
            items.append((int(m[2]), {"name": str(value), "page": page, "din": None, "pan": None, "designation": None}))
    return [e for _, e in sorted(items, key=lambda p: p[0])]


@dataclass
class _Party:
    name: str
    role: str
    source: str
    pan: str | None = None
    din: str | None = None
    ord: int = 0
    id: str = ""
    kyc: list[str] = field(default_factory=list)


def name_tolerance(root: Path) -> float:
    try:
        for t in reader.load_tolerances(root).tolerances:
            if t.key == "name_match":
                return float(t.value)
    except reader.NoPublishedConfig:
        pass
    return 0.85


def _role_from_designation(designation: str | None, default: str | None) -> str:
    text = (designation or "").lower()
    for word, role in (("director", "director"), ("managing", "director"), ("partner", "partner"),
                       ("proprietor", "proprietor"), ("guarantor", "guarantor")):
        if word in text:
            return role
    return default or "promoter"


def field_map(conn: sqlite3.Connection, document_id: str) -> dict[str, tuple[object, int | None]]:
    """field -> (effective value, page): a correction wins over the read value."""
    out: dict[str, tuple[object, int | None]] = {}
    for row in conn.execute(
        "SELECT field, value, corrected_value, status, evidence FROM field_values WHERE document_id = ?",
        (document_id,),
    ):
        value = json.loads(row["value"]) if row["value"] is not None else None
        if row["status"] == "corrected" and row["corrected_value"] is not None:
            value = json.loads(row["corrected_value"])
        page = json.loads(row["evidence"]).get("page") if row["evidence"] else None
        out[row["field"]] = (value, page)
    return out


def table_rows(fields: dict[str, tuple[object, int | None]], table: str) -> list[dict[str, tuple[object, int | None]]]:
    rows: dict[int, dict] = {}
    for name, value in fields.items():
        m = _CELL.match(name)
        if m and m[1] == table:
            rows.setdefault(int(m[2]), {})[m[3]] = value
    return [rows[i] for i in sorted(rows)]


def _active_documents(conn: sqlite3.Connection, case_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT d.*, f.label_hint, f.original_name, f.archive_path FROM documents d JOIN files f ON f.id = d.file_id
           WHERE d.case_id = ? AND d.status NOT IN ('duplicate', 'superseded') ORDER BY d.created_at, d.id""",
        (case_id,),
    ).fetchall()


def _types(row: sqlite3.Row) -> list[str]:
    from .pipeline import effective_types

    return effective_types(row)


def build_party_set(conn: sqlite3.Connection, root: Path, case_id: str) -> list[_Party]:
    tol = name_tolerance(root)
    case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    header = json.loads(case["header"] or "{}")
    parties: list[_Party] = []

    def add(p: _Party) -> None:
        if not normalise_name(p.name):
            return
        for q in parties:
            same = (p.pan and q.pan and p.pan == q.pan) or (p.din and q.din and p.din == q.din)
            if same or (q.role != "borrower" and p.role != "borrower" and similarity(p.name, q.name) >= tol):
                q.pan = q.pan or p.pan
                q.din = q.din or p.din
                if q.role == "promoter" and p.role != "promoter":
                    q.role = p.role
                return
        p.ord = len(parties)
        parties.append(p)

    borrower_source = (header.get("borrower") or {}).get("source") or "person"
    add(_Party(name=case["borrower"], role="borrower", source=borrower_source, pan=case["pan"]))

    type_defs = {t.id: t for t in reader.load_document_types(root).types}
    for doc in _active_documents(conn, case_id):
        fields = None
        for type_id in _types(doc):
            spec = party_list_spec(type_defs.get(type_id))
            if spec is None:
                continue
            fields = fields if fields is not None else field_map(conn, doc["id"])
            for entry in party_entries(fields, spec):
                add(_Party(name=entry["name"], role=_role_from_designation(entry["designation"], spec.role),
                           source=f"document:{doc['id']}:p{entry['page'] or doc['page_from']}",
                           pan=entry["pan"], din=entry["din"]))

    promoters = header.get("promoters") or {}
    if promoters.get("value"):
        for name in str(promoters["value"]).split(";"):
            add(_Party(name=name.strip(), role="promoter", source=promoters.get("source") or "person"))

    for p in parties:
        p.id = stable_id("PTY", case_id, normalise_name(p.name))
    return parties


def _ident(pair) -> str | None:
    if not pair or pair[0] in (None, ""):
        return None
    return str(pair[0]).strip().upper()


def _hint_party(hint: str | None, parties: list[_Party]) -> _Party | None:
    """The one party whose full name appears in the file label, if any."""
    if not hint:
        return None
    hint_tokens = set(tokens(hint))
    found = [
        p
        for p in parties
        if p.role != "borrower" and (name := [t for t in tokens(p.name) if len(t) > 1]) and set(name) <= hint_tokens
    ]
    return found[0] if len(found) == 1 else None


def hint_types(hint: str | None) -> set[str]:
    if not hint:
        return set()
    out = set()
    for type_id, patterns in (load_app_config().get("label_keywords") or {}).items():
        if any(re.search(p, hint, re.IGNORECASE) for p in patterns):
            out.add(type_id)
    return out


def refresh(conn: sqlite3.Connection, root: Path, case_id: str) -> list[_Party]:
    tol = name_tolerance(root)
    types_cfg = {t.id: t for t in reader.load_document_types(root).types}
    parties = build_party_set(conn, root, case_id)
    by_id = {p.id: p for p in parties}
    people = [p for p in parties if p.role != "borrower"]
    docs = _active_documents(conn, case_id)

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM parties WHERE case_id = ?", (case_id,))
        for p in parties:
            conn.execute(
                "INSERT INTO parties (id, case_id, name, role, pan, din, source, ord) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (p.id, case_id, p.name, p.role, p.pan, p.din, p.source, p.ord),
            )

        # F-10.1: label hint against the classified types, per file.
        file_types: dict[str, set[str]] = {}
        for doc in docs:
            file_types.setdefault(doc["file_id"], set()).update(_types(doc))
        for doc in docs:
            types = _types(doc)
            expected = hint_types(doc["label_hint"])
            mismatch = bool(types) and bool(expected) and not (expected & file_types[doc["file_id"]])
            if "application_message" in types:
                mismatch = False
            conn.execute("UPDATE documents SET label_mismatch = ? WHERE id = ?", (int(mismatch), doc["id"]))

        # F-10.3: attribution of personal documents.
        for doc in docs:
            types = _types(doc)
            if not any(types_cfg.get(t) and types_cfg[t].personal for t in types):
                continue
            party_id, flag, summary, labelled = _attribute(conn, doc, people, tol)
            if doc["party_override"]:
                party_id = None if doc["party_override"] == "none" else doc["party_override"]
                flag = None
            conn.execute(
                "UPDATE documents SET party_id = ?, party_flag = ? WHERE id = ?", (party_id, flag, doc["id"])
            )
            if party_id in by_id:
                by_id[party_id].kyc.append(doc["id"])
            ref = f"party:{doc['id']}"
            if flag:
                raise_item(
                    conn,
                    case_id=case_id,
                    kind="party",
                    ref=ref,
                    summary=summary,
                    detail={"document_id": doc["id"], "flag": flag, "party_id": party_id, "label_party": labelled},
                )
            else:
                item = conn.execute(
                    "SELECT id FROM review_items WHERE case_id = ? AND kind = 'party' AND ref = ? AND status = 'open'",
                    (case_id, ref),
                ).fetchone()
                if item and not doc["party_override"]:
                    close_item(
                        conn, item_id=item["id"], decision="confirm",
                        reason="The document now matches a party on the case.", decided_by="system",
                    )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return parties


def _attribute(
    conn: sqlite3.Connection, doc: sqlite3.Row, people: list[_Party], tol: float
) -> tuple[str | None, str | None, str, str | None]:
    identity = json.loads(doc["identity"] or "{}")
    fields = field_map(conn, doc["id"])
    name = identity.get("name") or (fields.get("person_name") or (None, None))[0]
    pan = (identity.get("pan") or (fields.get("pan") or (None, None))[0] or "").strip().upper() or None
    din = (identity.get("din") or "").strip() or None
    label = doc["archive_path"] or doc["original_name"]

    match = None
    if pan:
        match = next((p for p in people if p.pan and p.pan == pan), None)
    if match is None and din:
        match = next((p for p in people if p.din and p.din == din), None)
    if match is None and name:
        scored = sorted(((similarity(name, p.name), p.ord, p) for p in people), key=lambda s: (-s[0], s[1]))
        if scored and scored[0][0] >= tol:
            match = scored[0][2]
    labelled = _hint_party(doc["label_hint"], people)
    if match is None:
        who = name or "an unnamed person"
        return None, "no_party", f"{label}: {who} matches no party on this case; may not belong to this case", None
    if labelled is not None and labelled.id != match.id:
        how = "PAN" if pan and match.pan == pan else ("DIN" if din and match.din == din else "name")
        return (
            match.id,
            "refiled",
            f"{label}: labelled {labelled.name}, {how} matches {match.name}; filed under {match.name}",
            labelled.name,
        )
    return match.id, None, "", None


def list_parties(conn: sqlite3.Connection, case_id: str) -> list[Party]:
    kyc: dict[str, list[str]] = {}
    for row in conn.execute(
        """SELECT id, party_id FROM documents WHERE case_id = ? AND party_id IS NOT NULL
           AND status NOT IN ('duplicate', 'superseded') ORDER BY created_at, id""",
        (case_id,),
    ):
        kyc.setdefault(row["party_id"], []).append(row["id"])
    return [
        Party(
            id=row["id"],
            case_id=case_id,
            name=row["name"],
            role=row["role"],
            pan=row["pan"],
            din=row["din"],
            source=row["source"],
            kyc_document_ids=kyc.get(row["id"], []),
        )
        for row in conn.execute("SELECT * FROM parties WHERE case_id = ? ORDER BY ord", (case_id,))
    ]
