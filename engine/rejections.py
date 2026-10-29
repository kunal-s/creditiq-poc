"""What did not pass intake on a case, with the reason and the rule that raised it.

Read-only. Two sources, joined here because no single function lists them:
- files that were rejected or could not be opened (`files.status`, `reason`, `reason_code`);
- documents held for a person: the open quality and type review items that point at a document, with the
  wording for the reason codes from the published quality configuration (the same wording as the query list).
Nothing is decided or changed here.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from pathlib import Path

from .config import load_app_config
from .configstore import reader
from .contracts.documents import RejectionItem


def clean(text: str, limit: int) -> str:
    """Customer-chosen text (file names, reasons that quote them) reaches the case assistant's model: drop control
    and format characters, collapse whitespace and cap the length, so a file name cannot carry a block of text."""
    kept = "".join(" " if c.isspace() else c for c in text if not unicodedata.category(c).startswith("C") or c.isspace())
    kept = " ".join(kept.split())
    return kept if len(kept) <= limit else kept[: limit - 1].rstrip() + "…"


NAME_LIMIT, REASON_LIMIT = 120, 300


def _norm(text: str) -> str:
    return text.lower().replace("_", " ").strip()


def build(conn: sqlite3.Connection, root: Path, case_id: str, document_type: str | None = None) -> list[RejectionItem]:
    from .pipeline import effective_types

    wording = reader.reason_codes(root)
    types = {t.id: t.name for t in reader.load_document_types(root).types}
    phrasing = load_app_config()["rejection_phrasing"]
    items: list[RejectionItem] = []

    for f in conn.execute(
        "SELECT * FROM files WHERE case_id = ? AND status IN ('rejected', 'exception') ORDER BY uploaded_at, rowid", (case_id,)
    ):
        code = f["reason_code"]
        items.append(RejectionItem(
            kind="file", id=f["id"], document=clean(f["archive_path"] or f["original_name"], NAME_LIMIT), status=f["status"],
            reason=clean(f["reason"] or phrasing["held"], REASON_LIMIT), request=wording.get(code), rule=code,
        ))

    for item in conn.execute(
        """SELECT * FROM review_items WHERE case_id = ? AND status = 'open' AND kind IN ('quality', 'type')
           AND ref LIKE 'document:%' ORDER BY created_at, rowid""", (case_id,)
    ):
        detail = json.loads(item["detail"] or "{}")
        doc = conn.execute(
            "SELECT d.*, f.original_name, f.archive_path FROM documents d JOIN files f ON f.id = d.file_id WHERE d.id = ?",
            (detail.get("document_id"),),
        ).fetchone()
        if doc is None:
            continue
        pages = f"p{doc['page_from']}" + (f"-{doc['page_to']}" if doc["page_to"] != doc["page_from"] else "")
        names = [types[t] for t in effective_types(doc) if t in types]
        if item["kind"] == "quality":
            codes = detail.get("reason_codes") or []
            reason = " ".join(wording[c] for c in codes if c in wording) or wording.get("ocr_floor", phrasing["held"])
            rule = ", ".join(codes) or None
        else:
            reason, rule = phrasing["type_not_recognised"], "type_not_recognised"
        items.append(RejectionItem(
            kind="document", id=doc["id"], document=f"{clean(doc['archive_path'] or doc['original_name'], NAME_LIMIT)} {pages}",
            document_type=", ".join(names) or None, status=doc["status"], reason=reason, rule=rule,
        ))

    if document_type:
        want = _norm(document_type)
        items = [i for i in items if want in _norm(i.document) or want in _norm(i.document_type or "")]
    return items
