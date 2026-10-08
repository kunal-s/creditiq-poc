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
                if isinstance(row, dict):
                    for col, v in row.items():
                        out[f"{name}[{i}].{col}"] = v
                else:
                    out[f"{name}[{i}]"] = row
        else:
            out[name] = value
    return out


def add_doc(root: Path, case_id: str, type_id: str, fields: dict, *, page: int = 1,
            corrected: dict | None = None, pending: set[str] | None = None) -> str:
    """File one accepted document of `type_id` with these field values.
    Table fields are lists of row dicts. `corrected` maps a field to a
    person's correction of it; fields in `pending` still wait for review."""
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
                    "corrected" if fix is not None else ("in_review" if name in (pending or set()) else "accepted"),
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


# --- The nine document types, as the service reads them ---


def bank(root: Path, case_id: str, transactions: list[dict], *, last4: str = "1234", bank_name: str = "Lotuscrest Bank",
         start: str = "2025-04-01", end: str = "2026-03-31", holder: str = "Kestrel Tools Pvt Ltd") -> str:
    """A bank statement; each transaction has date, description and debit or credit."""
    return add_doc(root, case_id, "bank_statement", {
        "account_holder_name": holder, "account_number": f"90100000{last4}", "bank_name": bank_name,
        "statement_period_start": start, "statement_period_end": end, "transactions": transactions,
    })


def gstr(root: Path, case_id: str, period: str, taxable: int, *, gstin: str = "27AAACK1234F1Z0") -> str:
    """One GSTR-3B; `period` as printed, "April 2025"."""
    return add_doc(root, case_id, "gstr_3b", {
        "gstin": gstin, "legal_name": "Kestrel Tools Private Limited", "tax_period": period,
        "outward_supplies": [{"description": "(a) Outward taxable supplies", "taxable_value": taxable}],
    })


def audited(root: Path, case_id: str, year_end: str = "2026-03-31", *, scale: float = 1.0, set_rows: dict[str, int | None] | None = None,
            page: int = 1, **fields) -> str:
    """Audited statements with the balance sheet and profit and loss rows as printed. `scale` scales every
    figure; `set_rows` replaces a printed row's current-year figure by its label (None: the row is not printed)."""
    from tests.fixtures.build_fixtures import statement_tables

    tables = statement_tables(year_end, scale=scale)
    year = int(year_end[:4])
    doc = {"company_name": "Kestrel Tools Private Limited", "financial_year": f"FY{year} (ended 31 March {year})"}
    for name, t in tables.items():
        rows = [dict(r["cells"]) for r in t["rows"]]
        for label, value in (set_rows or {}).items():
            for r in rows:
                if r["particulars"] == label:
                    r["current_period"] = value
        doc[name] = rows
    return add_doc(root, case_id, "audited_financial_statements", {**doc, **fields}, page=page)
