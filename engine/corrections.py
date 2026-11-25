"""A person's corrections on the Files tab (Story 7.2). Each is the engine's record: who, when, why and what it was
before go into the decision log, and the documents are read or checked again from it.

- A page given its own type: read as that type in a document of its own; the document it came from is read again
  without it (engine/pipeline.py retype_page).
- A document's period set where the service found none or found its title and its columns disagree: stored on the
  document as the person's, and the checks run again.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from . import case_types, jobs
from .configstore import reader
from .db import log_decision, transaction
from .util import dumps, now_iso


class CorrectionError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _document(conn: sqlite3.Connection, case_id: str, document_id: str) -> sqlite3.Row:
    doc = conn.execute("SELECT * FROM documents WHERE id = ? AND case_id = ?", (document_id, case_id)).fetchone()
    if doc is None or doc["status"] in ("superseded", "duplicate"):
        raise CorrectionError(404, "no such document on this case")
    return doc


def retype_page(conn: sqlite3.Connection, root: Path, case_id: str, document_id: str, page: int, type_id: str,
                reason: str, actor: str) -> str:
    from .pipeline import document_pages, effective_types

    doc = _document(conn, case_id, document_id)
    if page not in document_pages(doc):
        raise CorrectionError(422, f"page {page} is not a page of this document")
    known = {t.id for t in reader.load_document_types(root).types}
    if type_id not in known:
        raise CorrectionError(422, "a page is given a document type from the published list")
    if case_types.is_case_type(type_id):
        raise CorrectionError(422, "a type made for this case is assigned to a whole document")
    with transaction(conn):
        job_id = jobs.enqueue(conn, case_id=case_id, kind="retype_page",
                              payload={"document_id": document_id, "page": page, "type_id": type_id})
        log_decision(conn, at=now_iso(), actor=actor, case_id=case_id, action="document.page_retyped",
                     detail=dumps({"document_id": document_id, "page": page, "from_types": effective_types(doc),
                                   "to_type": type_id, "reason": reason.strip(), "job_id": job_id}))
    jobs.wake()
    return job_id


def period_key(root: Path, type_ids: list[str], start: date, end: date) -> str:
    """The instance key the engine reads for a period (as the service writes it): a month ("Apr 2025"), a quarter
    ("Apr-Jun 2025"), an assessment year for a type that prints one ("AY 2025-26"), else the period's last day."""
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    if months == 1:
        return f"{end:%b %Y}"
    if months == 3:
        return f"{start:%b}-{end:%b %Y}"
    docs = (reader.load_ingestion_section(root, "document_types") or {}).get("documents") or []
    by_assessment_year = any(d["document_type"] in type_ids and any(f["name"] == "assessment_year" for f in d["schema"]["fields"])
                             for d in docs)
    if by_assessment_year:
        return f"AY {end.year}-{str(end.year + 1)[2:]}"
    return end.isoformat()


def set_period(conn: sqlite3.Connection, root: Path, case_id: str, document_id: str, start: str, end: str,
               reason: str, actor: str) -> None:
    from .pipeline import effective_types

    doc = _document(conn, case_id, document_id)
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as e:
        raise CorrectionError(422, "the period is two dates") from e
    if first > last:
        raise CorrectionError(422, "the period starts after it ends")
    before = json.loads(doc["period"]) if doc["period"] else None
    period = {"range": {"start": start, "end": end, "kind": "set", "text": f"{start} to {end}"}, "status": "set",
              "source": "person", "by": actor, "reason": reason.strip()}
    from .pipeline import refresh_case

    with transaction(conn):
        conn.execute("UPDATE documents SET period = ?, instance_key = ? WHERE id = ?",
                     (json.dumps(period), period_key(root, effective_types(doc), first, last), document_id))
        log_decision(conn, at=now_iso(), actor=actor, case_id=case_id, action="document.period_set",
                     detail=dumps({"document_id": document_id, "from": before, "to": {"start": start, "end": end},
                                   "from_key": doc["instance_key"], "reason": reason.strip()}))
    refresh_case(conn, root, case_id)
