"""The consolidated pre-login query list (F-14).

One list for the RM to take to the customer, in three groups:
- documents needed: missing checklist items and coverage gaps;
- documents to redo: defective or outdated copies, and quality exceptions
  with the plain re-scan request from config/quality.yaml;
- clarifications: label mismatches and party flags still open.

Phrasing comes from config/app.yaml `query_phrasing`. The list is refreshed
whenever the case changes; an item that no longer applies is kept and shown
as resolved (F-14.4). Nothing is sent from the system (F-14.3).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import cases, completeness
from .config import load_app_config
from .configstore import reader
from .parties import hint_types
from .util import stable_id


def _phrasing() -> dict[str, str]:
    return load_app_config()["query_phrasing"]


def _join_names(names: list[str]) -> str:
    names = [n for n in dict.fromkeys(names) if n]
    if len(names) <= 1:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " and " + names[-1]


def build(conn: sqlite3.Connection, root: Path, case_id: str) -> list[dict]:
    case = cases.get_case(conn, case_id)
    if case is None:
        return []
    phr = _phrasing()
    out: list[dict] = []

    def add(group: str, text: str, source_kind: str, source_ref: str, evidence: list[dict] | None = None) -> None:
        out.append(
            {
                "id": stable_id("Q", case_id, source_kind, source_ref),
                "case_id": case_id,
                "grp": group,
                "text": text,
                "source_kind": source_kind,
                "source_ref": source_ref,
                "evidence": json.dumps(evidence or []),
            }
        )

    # Checklist: missing items and deficiencies (F-13).
    _, results = completeness.evaluate(conn, root, case)
    for r in results:
        if r.state.status == "missing" and r.missing_request:
            add("documents_needed", phr["missing"].format(request=r.missing_request), "checklist", r.item.id)
        for d in r.deficiencies:
            ref = f"{r.item.id}:{d.code}"
            if d.kind == "gap":
                add("documents_needed", phr["gap"].format(request=d.request), "checklist", ref, d.evidence)
            elif d.kind == "outdated":
                text = phr["outdated"].format(name=d.name, max_age_days=d.extra["max_age_days"], date=d.extra["date"])
                add("documents_to_redo", text, "checklist", ref, d.evidence)
            else:
                add("documents_to_redo", phr["redo"].format(name=d.name, deficiency=d.request), "checklist", ref,
                    d.evidence)

    # Quality exceptions (F-07.4): the configured re-scan request.
    reason_text = reader.load_quality(root).reason_codes
    types = {t.id: t for t in reader.load_document_types(root).types}
    for item in conn.execute(
        "SELECT * FROM review_items WHERE case_id = ? AND kind = 'quality' AND status = 'open' ORDER BY created_at",
        (case_id,),
    ).fetchall():
        detail = json.loads(item["detail"] or "{}")
        codes = detail.get("reason_codes") or ([detail["reason_code"]] if detail.get("reason_code") else [])
        request = " ".join(reason_text[c] for c in codes if c in reason_text) or reason_text.get("ocr_floor", "")
        label, evidence = _subject(conn, detail, types)
        add("documents_to_redo", phr["quality"].format(document=label, request=request), "quality", item["ref"],
            evidence)

    # Label mismatches (F-10.1), one per file.
    seen_files: set[str] = set()
    for doc in conn.execute(
        """SELECT d.*, f.original_name, f.archive_path, f.label_hint FROM documents d JOIN files f ON f.id = d.file_id
           WHERE d.case_id = ? AND d.label_mismatch = 1 AND d.status NOT IN ('duplicate', 'superseded')
           ORDER BY d.created_at, d.id""",
        (case_id,),
    ).fetchall():
        if doc["file_id"] in seen_files:
            continue
        seen_files.add(doc["file_id"])
        in_file = conn.execute(
            """SELECT d.* FROM documents d WHERE d.file_id = ? AND d.status NOT IN ('duplicate', 'superseded')""",
            (doc["file_id"],),
        ).fetchall()
        from .pipeline import effective_types

        content = _join_names([types[t].name for d in in_file for t in effective_types(d) if t in types])
        label = _join_names(sorted({types[t].name for t in hint_types(doc["label_hint"]) if t in types}))
        text = phr["label"].format(file=doc["original_name"], label=label.lower(), content=content.lower())
        add("clarifications", text, "label", f"file:{doc['file_id']}", [{"document_id": doc["id"], "page": doc["page_from"]}])

    # Party flags (F-10.3) still open.
    for item in conn.execute(
        "SELECT * FROM review_items WHERE case_id = ? AND kind = 'party' AND status = 'open' ORDER BY created_at",
        (case_id,),
    ).fetchall():
        detail = json.loads(item["detail"] or "{}")
        doc = conn.execute(
            """SELECT d.*, f.original_name, f.label_hint FROM documents d JOIN files f ON f.id = d.file_id
               WHERE d.id = ?""",
            (detail.get("document_id"),),
        ).fetchone()
        if doc is None:
            continue
        from .pipeline import effective_types

        content = _join_names([types[t].name for t in effective_types(doc) if t in types]).lower()
        evidence = [{"document_id": doc["id"], "page": doc["page_from"]}]
        if detail.get("flag") == "refiled":
            party = conn.execute("SELECT name FROM parties WHERE id = ?", (doc["party_id"],)).fetchone()
            text = phr["party_refiled"].format(
                file=doc["original_name"],
                label_party=detail.get("label_party") or "another person",
                party=party["name"] if party else "",
            )
        else:
            text = phr["party_unmatched"].format(file=doc["original_name"], content=content)
        add("clarifications", text, "party", item["ref"], evidence)
    return out


def _subject(conn: sqlite3.Connection, detail: dict, types: dict) -> tuple[str, list[dict]]:
    if detail.get("document_id"):
        doc = conn.execute(
            "SELECT d.*, f.original_name FROM documents d JOIN files f ON f.id = d.file_id WHERE d.id = ?",
            (detail["document_id"],),
        ).fetchone()
        if doc is not None:
            from .pipeline import effective_types

            names = [types[t].name for t in effective_types(doc) if t in types]
            pages = f"p{doc['page_from']}" + (f"-{doc['page_to']}" if doc["page_to"] != doc["page_from"] else "")
            label = (names[0] + f" ({doc['original_name']} {pages})") if names else f"{doc['original_name']} {pages}"
            return label, [{"document_id": doc["id"], "page": doc["page_from"]}]
    if detail.get("file_id"):
        f = conn.execute("SELECT original_name FROM files WHERE id = ?", (detail["file_id"],)).fetchone()
        if f is not None:
            return f["original_name"], []
    return "A document", []


def refresh(conn: sqlite3.Connection, root: Path, case_id: str) -> None:
    desired = {q["id"]: q for q in build(conn, root, case_id)}
    conn.execute("BEGIN IMMEDIATE")
    try:
        existing = {r["id"] for r in conn.execute("SELECT id FROM query_items WHERE case_id = ?", (case_id,))}
        for q in desired.values():
            if q["id"] in existing:
                conn.execute(
                    "UPDATE query_items SET grp = :grp, text = :text, evidence = :evidence, resolved = 0 WHERE id = :id",
                    q,
                )
            else:
                conn.execute(
                    """INSERT INTO query_items (id, case_id, grp, text, source_kind, source_ref, evidence, resolved)
                       VALUES (:id, :case_id, :grp, :text, :source_kind, :source_ref, :evidence, 0)""",
                    q,
                )
        for qid in existing - desired.keys():
            conn.execute("UPDATE query_items SET resolved = 1 WHERE id = ?", (qid,))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
