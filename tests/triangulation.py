"""Documents with known field values, filed straight into the store, for the
triangulation tests (F-18, F-19). The reading itself is tested elsewhere;
these tests start from what was read. Every name is fictional."""

from __future__ import annotations

import json
from pathlib import Path

from engine import db
from engine.util import stable_id

_count = 0


def _flatten(fields: dict) -> dict[str, object]:
    out: dict[str, object] = {}
    for name, value in fields.items():
        if isinstance(value, list):
            for i, row in enumerate(value):
                for col, v in row.items():
                    out[f"{name}[{i}].{col}"] = v
        else:
            out[name] = value
    return out


def add_doc(root: Path, case_id: str, type_id: str, fields: dict, *, page: int = 1,
            corrected: dict | None = None) -> str:
    """File one accepted document of `type_id` with these field values.
    Table fields are lists of row dicts. `corrected` maps a field to a
    person's correction of it."""
    global _count
    _count += 1
    file_id = stable_id("F", case_id, type_id, _count)
    doc_id = stable_id("D", case_id, type_id, _count)
    conn = db.connect(root)
    try:
        conn.execute(
            """INSERT INTO files (id, case_id, sha256, original_name, content_type, size_bytes, channel,
               uploaded_by, uploaded_at, status, processed_at) VALUES (?, ?, ?, ?, 'application/pdf', 1, 'upload',
               'test', '2026-09-29T00:00:00Z', 'registered', '2026-09-29T00:00:00Z')""",
            (file_id, case_id, file_id, f"{type_id}-{_count}.pdf"),
        )
        classification = {"types": [type_id], "confidence": 0.95, "exit_tier": "signals", "signals": [],
                           "candidates": []}
        conn.execute(
            """INSERT INTO documents (id, case_id, file_id, page_from, page_to, pages, grade, classification, status,
               created_at) VALUES (?, ?, ?, ?, ?, '[]', 'A', ?, 'accepted', ?)""",
            (doc_id, case_id, file_id, page, page, json.dumps(classification), f"2026-09-29T00:00:{_count:02d}Z"),
        )
        for name, value in _flatten(fields).items():
            fix = (corrected or {}).get(name)
            conn.execute(
                """INSERT INTO field_values (id, case_id, document_id, field, value, raw, evidence, method,
                   confidence, status, corrected_value) VALUES (?, ?, ?, ?, ?, ?, ?, 'deterministic', 0.95, ?, ?)""",
                (
                    stable_id("FV", doc_id, name),
                    case_id,
                    doc_id,
                    name,
                    json.dumps(value),
                    str(value),
                    json.dumps({"document_id": doc_id, "page": page}),
                    "corrected" if fix is not None else "accepted",
                    json.dumps(fix) if fix is not None else None,
                ),
            )
    finally:
        conn.close()
    return doc_id


def months(start: tuple[int, int], count: int) -> list[str]:
    y, m = start
    out = []
    for _ in range(count):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out
