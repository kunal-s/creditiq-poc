"""The case's additional information (Story 6.5): each document's extra data (Story 6.4) as items the assistant reads,
in upload order then page order. Read-only; nothing here is shown on screen or used by a check."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .configstore import reader
from .contracts.extra import AdditionalInformation

ROW_CHARS = 1500


def build(conn: sqlite3.Connection, root: Path, case_id: str, document_type: str | None = None) -> list[AdditionalInformation]:
    from .pipeline import effective_types

    names = {t.id: t.name for t in reader.load_document_types(root).types}
    out: list[AdditionalInformation] = []
    for row in conn.execute(
        """SELECT d.*, f.original_name FROM documents d JOIN files f ON f.id = d.file_id
           WHERE d.case_id = ? AND d.extra IS NOT NULL AND d.status NOT IN ('superseded', 'rejected')
           ORDER BY f.uploaded_at, f.rowid, d.page_from, d.id""", (case_id,)):
        types = effective_types(row)
        tid = types[0] if types else "unclassified"
        if document_type and document_type != tid:
            continue
        label = " + ".join(names.get(t, t.replace("_", " ")) for t in types) or "Unplaced pages"
        doc = f"{label} ({row['original_name']})"
        extra = json.loads(row["extra"])
        items = [(p["page"], "pair", p["label"], " | ".join(p["values"])) for p in extra.get("pairs") or []]
        for t in extra.get("tables") or []:
            rows = "; ".join(f"{r[0]}: {' | '.join(r[1:])}" for r in t["rows"])
            head = f"[{' | '.join(t['columns'])}] " if t.get("columns") else ""
            items.append((t["page"], "table", t.get("description") or "Table", (head + rows)[:ROW_CHARS]))
        for page, kind, lab, value in sorted(items, key=lambda x: x[0]):
            out.append(AdditionalInformation(document_id=row["id"], document=doc, document_type=tid, page=page, kind=kind,
                                             label=lab, value=value))
    return out
