"""The documents the draft CAM and the PD note cite (FRD F-23.2, F-24.2).

Each document is numbered in the order the output first cites it, read from the top, so the screen
and the downloads give it the same number: one source per document, with the distinct pages cited.
A document is named by its type and by the year, period, account, person or lender it is for, when
the document states it: always for audited statements, income tax returns, bank statements and
sanction letters, and for the other types where the case has several; the file it was read from is
named too.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .configstore import reader
from .contracts import Cam, Evidence, OutputSource, PdNote
from .pipeline import effective_types
from .util import assessment_year_start, fy_end_of, month_label, parse_period

INACTIVE = ("superseded", "duplicate")
# The fields that tell two documents of one type apart, read only where the case has several.
QUALIFIER_FIELDS = {
    "audited_financial_statements": ("financial_year",),
    "income_tax_return": ("assessment_year",),
    "gstr_3b": ("tax_period",),
    "gstr_1": ("tax_period",),
    "bank_statement": ("bank_name", "account_number"),
    "director_kyc": ("person_name",),
    "sanction_letter": ("lender_name",),
}
# The types named by year, account or lender even where the case has one of them.
ALWAYS_QUALIFIED = {"audited_financial_statements", "income_tax_return", "bank_statement", "sanction_letter"}


def cam_citations(cam: Cam) -> list[Evidence]:
    """Every citation in the memo in reading order: the sections and their blocks in order (a
    paragraph's, each fact's, a table's cells row by row, left to right), then the summary."""
    out: list[Evidence] = []
    for section in cam.sections:
        for block in section.blocks:
            if block.paragraph is not None:
                out += block.paragraph.citations
            for fact in block.facts:
                out += fact.value.citations
            if block.table is not None:
                out += [e for row in block.table.rows for cell in row for e in cell.citations]
    return out + [e for item in cam.summary for e in item.citations]


def pd_citations(note: PdNote) -> list[Evidence]:
    """Every citation in the note in reading order: the header's, the people to meet, each question's
    evidence, then the documents to collect."""
    return ([e for fact in note.header for e in fact.value.citations] + [e for p in note.people for e in p.evidence]
            + [e for q in note.questions for e in q.evidence] + [e for d in note.documents_to_collect for e in d.citations])


def sources(conn: sqlite3.Connection, root: Path, case_id: str, citations: Iterable[Evidence]) -> list[OutputSource]:
    """One source per document cited, numbered from 1 in the order of first citation."""
    pages: dict[str, set[int]] = {}
    for e in citations:
        pages.setdefault(e.document_id, set()).add(e.page)
    named = documents(conn, root, case_id) if pages else {}
    out = []
    for n, (doc_id, cited) in enumerate(pages.items(), start=1):
        label, file_name = named.get(doc_id, ("Document", None))
        out.append(OutputSource(number=n, document_id=doc_id, label=label, file_name=file_name, pages=sorted(cited)))
    return out


def documents(conn: sqlite3.Connection, root: Path, case_id: str) -> dict[str, tuple[str, str | None]]:
    """Each of the case's documents as the outputs name it: (label, file name)."""
    names = {t.id: t.name for t in reader.load_document_types(root).types}
    rows = conn.execute(
        """SELECT d.id, d.status, d.classification, d.assigned_types, f.original_name FROM documents d
           JOIN files f ON f.id = d.file_id WHERE d.case_id = ? ORDER BY d.created_at, d.id""",
        (case_id,),
    ).fetchall()
    types = {r["id"]: effective_types(r) for r in rows}
    several = {t for t in QUALIFIER_FIELDS
               if t in ALWAYS_QUALIFIED or sum(1 for r in rows if r["status"] not in INACTIVE and t in types[r["id"]]) > 1}
    fields = _fields(conn, case_id, sorted({f for t in several for f in QUALIFIER_FIELDS[t]}))
    out = {}
    for r in rows:
        label = " + ".join(names.get(t, t.replace("_", " ")) for t in types[r["id"]]) or "Unclassified document"
        qualifier = next(filter(None, (_qualifier(t, fields.get(r["id"], {})) for t in types[r["id"]] if t in several)),
                         None)
        out[r["id"]] = (f"{label} · {qualifier}" if qualifier else label, r["original_name"])
    return out


def _fields(conn: sqlite3.Connection, case_id: str, names: list[str]) -> dict[str, dict[str, object]]:
    """The named fields of the case's documents, as corrected where a person corrected them."""
    if not names:
        return {}
    out: dict[str, dict[str, object]] = {}
    marks = ", ".join("?" for _ in names)
    for r in conn.execute(
        f"""SELECT document_id, field, value, corrected_value, status FROM field_values
            WHERE case_id = ? AND field IN ({marks}) AND status NOT IN ('missing', 'rejected')""",
        (case_id, *names),
    ):
        raw = r["corrected_value"] if r["status"] == "corrected" and r["corrected_value"] is not None else r["value"]
        value = json.loads(raw) if raw is not None else None
        if value not in (None, ""):
            out.setdefault(r["document_id"], {})[r["field"]] = value
    return out


def _qualifier(type_id: str, fields: dict[str, object]) -> str | None:
    if type_id == "audited_financial_statements":
        end = fy_end_of(fields.get("financial_year"))
        return f"FY {end.year - 1}-{str(end.year)[2:]}" if end else None
    if type_id == "income_tax_return":
        start = assessment_year_start(fields.get("assessment_year"))
        return f"AY {start}-{str(start + 1)[2:]}" if start else None
    if type_id in ("gstr_3b", "gstr_1"):
        period = parse_period(fields.get("tax_period"))
        return month_label(period) if period else None
    if type_id == "bank_statement":
        digits = "".join(c for c in str(fields.get("account_number") or "") if c.isdigit())
        bank = str(fields.get("bank_name") or "").strip()
        account = f"·{digits[-4:]}" if len(digits) >= 4 else ""
        return " ".join(p for p in (bank, account) if p) or None
    return str(fields.get(QUALIFIER_FIELDS[type_id][0]) or "").strip() or None
