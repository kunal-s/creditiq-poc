"""The case's pending fields and how they are filled (Epic 6 of the classification restructure).

The required fields (config/ingestion/fields.yaml required_fields, Story 1.7) are every field something in the engine
reads. After a batch of files is stored, each one whose own documents left it empty is pending (Story 6.1): a field of
the case, or a statement line for each financial year the checklist requires. The service is then asked for the
pending fields, file by file in upload order and page by page (Story 6.3):

1. from the leftovers (Story 6.2): the pages no type was found for, and the pages where a document printed something
   no field and no table claimed (its extra data);
2. for a field that may be swept, from the pages of other document types (Story 6.8), the service reading those that
   score highest for it.

A value found is stored on the document whose page printed it, with that page, and always waits for a person: it
never replaces a value read from the field's own document, and nothing is adjusted toward another document's value.
Fields of other scopes (an account, a person, a month, a facility) are read only from their own documents.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import facts as facts_module
from . import statements
from .configstore import reader
from .db import log_decision, transaction
from .review_items import raise_item
from .util import dumps, fy_end, now_iso, stable_id

FILLED_ORIGINS = ("leftover", "sweep")
LINE_STATES = ("printed", "nil", "edited", "not_printed")


@dataclass(frozen=True)
class Pending:
    name: str
    label: str
    sweep: bool
    sources: tuple[str, ...]
    period_end: str | None = None

    @property
    def field(self) -> str:
        """The name a value found for it is stored under."""
        return f"{self.name}@{self.period_end}" if self.period_end else self.name

    @property
    def source_types(self) -> set[str]:
        return {s.split(".", 1)[0] for s in self.sources}


def _label(name: str, period_end: str | None, kind: str | None = None) -> str:
    text = name.replace("_", " ")
    text = text.upper() if kind == "identifier" and " " not in text else text[:1].upper() + text[1:]
    if period_end:
        d = date.fromisoformat(period_end)
        text += f", FY {d.year - 1}-{str(d.year)[2:]}"
    return text


def required_years(root: Path, as_of: date) -> list[date]:
    """The financial years the checklist asks statements for (coverage kind financial_year), latest first."""
    ends = {fy_end(as_of, i.coverage.offset) for i in reader.load_checklist_taxonomy(root).items
            if i.coverage is not None and i.coverage.kind == "financial_year" and i.coverage.offset}
    return sorted(ends, reverse=True)


def _year_lines(docs: list[facts_module.Doc], root: Path, types: set[str]) -> dict[date, set[str]]:
    """The statement lines each financial year has, from its own statements or the next year's comparative column."""
    cfg = reader.load_statements(root)
    start = reader.load_alignment(root).financial_year_start_month
    out: dict[date, set[str]] = {}
    for d in docs:
        if not set(d.types) & types:
            continue
        end = statements.period_end(d)
        if end is None:
            continue
        year = facts_module.fy_of(end.year, end.month, start)
        for column, offset in ((None, 0), ("previous_period", 1)):
            lines = statements.lines(d, cfg, column=column)
            got = {k for k, v in lines.items() if v.state in LINE_STATES}
            out.setdefault(facts_module.fy_end_date(year - offset, start), set()).update(got)
    return out


def pending(conn: sqlite3.Connection, root: Path, case_id: str, as_of: date) -> list[Pending]:
    """Story 6.1: the required fields of the case and of each required year that nothing has supplied yet."""
    required = (reader.load_ingestion_section(root, "fields") or {}).get("required_fields") or {}
    docs = facts_module.load_documents(conn, root, case_id)
    filled = {r["field"] for r in conn.execute(
        f"SELECT field FROM field_values WHERE case_id = ? AND origin IN ({','.join('?' * len(FILLED_ORIGINS))})",
        (case_id, *FILLED_ORIGINS))}
    years = required_years(root, as_of)
    out: list[Pending] = []
    for name, spec in required.items():
        sources = tuple(spec.get("from") or ())
        per, sweep = spec.get("per"), bool(spec.get("sweep"))
        if per == "case" and spec.get("kind") in ("text", "identifier", "date", "amount"):
            have = any(set(d.types) & {s.split(".", 1)[0]}
                       and d.get(s.split(".", 1)[1]) is not None for d in docs for s in sources if ":" not in s)
            if not have and name not in filled:
                out.append(Pending(name, _label(name, None, spec.get("kind")), sweep, sources))
        elif per == "financial_year" and all(".line:" in s for s in sources):
            keys = {s.split(".line:", 1)[1] for s in sources}
            lines = _year_lines(docs, root, {s.split(".", 1)[0] for s in sources})
            for end in years:
                p = Pending(name, _label(name, end.isoformat()), sweep, sources, end.isoformat())
                if not (lines.get(end, set()) & keys) and p.field not in filled:
                    out.append(p)
    return out


def _documents(conn: sqlite3.Connection, case_id: str) -> list[sqlite3.Row]:
    """The case's documents in upload order, then page order (Story 6.3)."""
    return conn.execute(
        """SELECT d.*, f.sha256, f.original_name, f.content_type, f.stored_name, f.label_hint
           FROM documents d JOIN files f ON f.id = d.file_id
           WHERE d.case_id = ? AND d.status NOT IN ('superseded', 'rejected', 'in_exception')
           ORDER BY f.uploaded_at, f.rowid, d.page_from, d.id""", (case_id,)).fetchall()


def _pages(row: sqlite3.Row) -> list[int]:
    pages = [p.get("n") or p.get("page") for p in json.loads(row["pages"] or "[]")]
    return [int(p) for p in pages if p] or list(range(row["page_from"], row["page_to"] + 1))


def _leftover_pages(row: sqlite3.Row) -> list[int]:
    if row["status"] == "unclassified":
        return _pages(row)
    extra = json.loads(row["extra"]) if row["extra"] else {}
    return sorted({int(i["page"]) for i in (extra.get("pairs") or []) + (extra.get("tables") or []) if i.get("page")})


def fill(conn: sqlite3.Connection, root: Path, case_id: str, as_of: date, client, config_version: str) -> list[dict]:
    """Stories 6.2 and 6.8: ask the service for the pending fields, leftovers first, then the sweep; store each value
    found and raise it for review. Returns what was stored."""
    if not hasattr(client, "fill"):
        return []
    todo = pending(conn, root, case_id, as_of)
    if not todo:
        return []
    from .ingest_client import IngestError
    from .pipeline import effective_types
    from .store import case_files_dir

    docs = _documents(conn, case_id)
    types = {t.id: t.name for t in reader.load_document_types(root).types}
    stored: list[dict] = []
    for stage in ("leftover", "sweep"):
        by_file: dict[str, list[sqlite3.Row]] = {}
        for d in docs:
            by_file.setdefault(d["file_id"], []).append(d)
        for file_id, rows in by_file.items():
            if not todo:
                break
            for_stage = [p for p in todo if stage == "leftover" or p.sweep]
            if stage == "leftover":
                pages = sorted({n for r in rows for n in _leftover_pages(r)})
                asked = for_stage
            else:
                # Only other document types' pages: a field's own documents have already been read for it.
                own = {r["id"]: set(effective_types(r)) for r in rows}
                pages = sorted({n for r in rows if r["status"] != "unclassified" for n in _pages(r)})
                asked = [p for p in for_stage if not any(own[r["id"]] & p.source_types for r in rows)]
            if not pages or not asked:
                continue
            first = rows[0]
            request = {"case_ref": case_id, "config_version": config_version,
                       "file": {"file_id": file_id, "sha256": first["sha256"], "original_name": first["original_name"],
                                "content_type": first["content_type"], "label_hint": first["label_hint"]},
                       "pages": pages, "fields": [{"name": p.name, "period_end": p.period_end} for p in asked],
                       "select": stage == "sweep"}
            try:
                answer = client.fill(request, (case_files_dir(case_id, root) / first["stored_name"]).read_bytes())
            except (IngestError, OSError):
                continue          # the service is unavailable: the fields stay pending for the next batch
            wanted = {(p.name, p.period_end): p for p in asked}
            for v in answer.get("found") or []:
                p = wanted.pop((v.get("field"), v.get("period_end")), None)
                if p is None or int(v.get("page") or 0) not in pages:
                    continue
                doc = next((r for r in rows if int(v["page"]) in _pages(r)), None)
                if doc is None:
                    continue
                with transaction(conn):
                    stored.append(_store(conn, case_id, doc, p, v, stage, types))
                todo.remove(p)
    if stored:
        log_decision(conn, at=now_iso(), actor="system", case_id=case_id, action="processing.fill",
                     detail=dumps({"filled": [{"field": s["field"], "document_id": s["document_id"], "page": s["page"],
                                               "origin": s["origin"]} for s in stored]}))
    return stored


def _store(conn: sqlite3.Connection, case_id: str, doc: sqlite3.Row, p: Pending, v: dict, origin: str,
           types: dict[str, str]) -> dict:
    from .pipeline import effective_types

    fv_id = stable_id("FV", doc["id"], f"fill:{p.field}")
    evidence = {"document_id": doc["id"], "page": int(v["page"]), "bbox": v.get("bbox"),
                **({"line": v["line"]} if v.get("line") else {})}
    conn.execute(
        """INSERT INTO field_values (id, case_id, document_id, field, value, raw, evidence, method, confidence,
               confidence_components, status, missing_reason, origin, label)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, '{}', 'in_review', NULL, ?, ?)
           ON CONFLICT(id) DO NOTHING""",
        (fv_id, case_id, doc["id"], p.field, json.dumps(v.get("value")), v.get("raw_text"), json.dumps(evidence),
         v.get("method") or "model", origin, p.label))
    doc_types = effective_types(doc)
    where = " + ".join(types.get(t, t.replace("_", " ")) for t in doc_types) if doc_types else "Unplaced pages"
    where += f" ({doc['original_name']})"
    raise_item(conn, case_id=case_id, kind="field", ref=f"field:{fv_id}",
               summary=f"{p.label} = {v.get('raw_text')} (source: {where}, page {v['page']}; please confirm)",
               detail={"document_id": doc["id"], "field_value_id": fv_id, "page": int(v["page"]), "origin": origin})
    return {"field": p.field, "document_id": doc["id"], "page": int(v["page"]), "origin": origin, "field_value_id": fv_id}
