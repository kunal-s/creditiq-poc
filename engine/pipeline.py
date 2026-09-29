"""The processing job (F-02): send registered files to the document-processing
sidecar (AD-2) and store what comes back.

For each file, in its own transaction: the logical documents (F-08), their
status per the state diagram (FRD section 7), the field values with
confidence (F-17.1), the review items (type, field, quality, split) and the
stage timings (F-02.4). A file is marked processed in the same transaction,
so a job killed part-way resumes with only the files not yet stored, and a
re-run stores nothing twice (document and review ids are deterministic).

After storing, the derived state is refreshed: parties and attribution
(F-10), the query list (F-14), and the case stage (Intake -> Readiness).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import confidence
from .configstore import reader
from .configstore.schema import ConfidenceSection, DictionarySection, DocumentTypeDef
from .contracts import IngestDocument, IngestFile, IngestRequest, IngestResult, TypeAssignment
from .db import log_decision, transaction
from .ingest_client import IngestError
from .review_items import close_item, raise_item
from .store import MESSAGE_FILE_NAME, case_files_dir
from .util import dumps, now_iso, stable_id

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "U": 3}

# Document statuses where no automatic step is pending (FRD section 7): the
# case leaves Intake once every document is in one of these.
FINAL_STATUSES = {"accepted", "in_review", "unclassified", "in_exception", "superseded", "duplicate"}


@dataclass
class Context:
    root: Path
    version: str
    types: dict[str, DocumentTypeDef]
    confidence: ConfidenceSection
    _dictionaries: dict[str, DictionarySection | None] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> "Context":
        return cls(
            root=root,
            version=reader.published_version(root)["version"],
            types={t.id: t for t in reader.load_document_types(root).types},
            confidence=reader.load_confidence(root),
        )

    def dictionary(self, dictionary_id: str | None) -> DictionarySection | None:
        if dictionary_id is None:
            return None
        if dictionary_id not in self._dictionaries:
            try:
                self._dictionaries[dictionary_id] = reader.load_dictionary(self.root, dictionary_id)
            except reader.NoPublishedConfig:
                self._dictionaries[dictionary_id] = None
        return self._dictionaries[dictionary_id]

    def field_def(self, type_ids: list[str], field_name: str) -> tuple[bool, str | None]:
        """(key field?, identifier kind) for a field across the document's types.
        Table cells "<table>[<row>].<column>" take the table's key flag and the
        column's identifier kind."""
        base, _, column = field_name.partition(".")
        base = base.split("[", 1)[0]
        key, ident = False, None
        for type_id in type_ids:
            t = self.types.get(type_id)
            d = self.dictionary(t.dictionary if t else None)
            if d is None:
                continue
            for f in d.fields:
                if f.name != base:
                    continue
                key = key or f.key_field
                if column:
                    for c in f.columns:
                        if c.name == column:
                            ident = ident or c.identifier
                            key = key or c.key_field
                else:
                    ident = ident or f.identifier
        return key, ident

    def type_name(self, type_id: str) -> str:
        t = self.types.get(type_id)
        return t.name if t else type_id


def document_grade(doc: IngestDocument) -> str:
    """F-07.3: the worst grade among non-blank pages (all blank: U)."""
    grades = [p.grade for p in doc.pages if "blank" not in p.reasons]
    if not grades:
        return "U"
    return max(grades, key=lambda g: GRADE_ORDER[g])


def _reasons(doc: IngestDocument, grades: tuple[str, ...]) -> list[str]:
    codes: list[str] = []
    for p in doc.pages:
        if p.grade in grades:
            for r in p.reasons:
                if r not in codes:
                    codes.append(r)
    return codes


def _file_label(file_row: sqlite3.Row) -> str:
    return file_row["archive_path"] or file_row["original_name"]


# --- Storing one document ---


def _store_fields(
    conn: sqlite3.Connection, ctx: Context, case_id: str, doc_id: str, doc: IngestDocument, types: list[str]
) -> str:
    """Insert the document's field values; returns the document status
    (accepted, or in_review when a key field is below the threshold)."""
    page_grades = {p.n: p.grade for p in doc.pages}
    cfg = ctx.confidence
    in_review = False
    label = ", ".join(ctx.type_name(t) for t in types)
    for f in doc.fields:
        fv_id = stable_id("FV", doc_id, f.field)
        key, ident = ctx.field_def(types, f.field)
        evidence = {"document_id": doc_id, "page": f.page, "bbox": list(f.bbox) if f.bbox else None} if f.page else None
        if f.value is None:
            status, conf, comps = "missing", None, {}
        else:
            scored = confidence.score(
                cfg,
                components=f.confidence_components,
                classification_confidence=doc.classification.confidence,
                page_grade=page_grades.get(f.page) if f.page else None,
                identifier_kind=ident,
                value=f.value,
                has_page=f.page is not None,
            )
            conf, comps = scored.confidence, scored.components
            status = "in_review" if key and conf < cfg.key_field_review_threshold else "accepted"
        conn.execute(
            """INSERT INTO field_values (id, case_id, document_id, field, value, raw, evidence, method, confidence,
                   confidence_components, status, missing_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO NOTHING""",
            (
                fv_id,
                case_id,
                doc_id,
                f.field,
                json.dumps(f.value),
                f.raw,
                json.dumps(evidence) if evidence else None,
                f.method,
                conf,
                json.dumps(comps),
                status,
                f.missing_reason,
            ),
        )
        if status == "in_review":
            in_review = True
            shown = f.raw if f.raw is not None else f.value
            raise_item(
                conn,
                case_id=case_id,
                kind="field",
                ref=f"field:{fv_id}",
                summary=f"{label}: {f.field} = {shown} (confidence {conf:.2f})",
                detail={"document_id": doc_id, "field_value_id": fv_id, "page": f.page},
            )
    return "in_review" if in_review else "accepted"


def _supersede(conn: sqlite3.Connection, case_id: str, doc_id: str, types: list[str], instance_key: str | None) -> None:
    """F-05.7 / F-07.5: a readable copy supersedes an unreadable document of
    the same type and instance."""
    rows = conn.execute(
        "SELECT * FROM documents WHERE case_id = ? AND status = 'in_exception' AND id <> ?", (case_id, doc_id)
    ).fetchall()
    for row in rows:
        old_types = set(effective_types(row))
        if not old_types & set(types) or (row["instance_key"] or None) != (instance_key or None):
            continue
        conn.execute("UPDATE documents SET status = 'superseded' WHERE id = ?", (row["id"],))
        conn.execute("UPDATE documents SET version_of = ? WHERE id = ?", (row["id"], doc_id))
        item = conn.execute(
            "SELECT id FROM review_items WHERE case_id = ? AND kind = 'quality' AND ref = ? AND status = 'open'",
            (case_id, f"document:{row['id']}"),
        ).fetchone()
        if item:
            close_item(
                conn, item_id=item["id"], decision="confirm", reason=f"Superseded by a better copy ({doc_id})",
                decided_by="system",
            )


def effective_types(row: sqlite3.Row) -> list[str]:
    """A person's type assignment wins over the classification (F-09.5 overlay)."""
    if row["assigned_types"]:
        return json.loads(row["assigned_types"])
    if row["classification"]:
        return json.loads(row["classification"]).get("types", [])
    return []


def _store_document(
    conn: sqlite3.Connection, ctx: Context, case_id: str, file_row: sqlite3.Row, doc: IngestDocument
) -> str | None:
    doc_id = stable_id("DOC", case_id, file_row["id"], doc.doc_key)
    if conn.execute("SELECT 1 FROM documents WHERE id = ?", (doc_id,)).fetchone():
        return None
    grade = document_grade(doc)
    types = list(doc.classification.types)
    duplicate_of = None
    if doc.duplicate_of_key:
        match = conn.execute(
            "SELECT id FROM documents WHERE case_id = ? AND doc_key = ? AND id <> ? ORDER BY created_at LIMIT 1",
            (case_id, doc.duplicate_of_key, doc_id),
        ).fetchone()
        duplicate_of = match["id"] if match else None
    if doc.duplicate_of_key and duplicate_of:
        status = "duplicate"
    elif grade == "U":
        status = "in_exception"
    elif not types:
        status = "unclassified"
    else:
        status = "extracted"
    conn.execute(
        """INSERT INTO documents (id, case_id, file_id, page_from, page_to, pages, grade, classification, status,
               instance_key, duplicate_of, config_version, doc_key, identity, defects, split_uncertain, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            doc_id,
            case_id,
            file_row["id"],
            doc.page_from,
            doc.page_to,
            json.dumps([p.model_dump() for p in doc.pages]),
            grade,
            doc.classification.model_dump_json(),
            status,
            doc.instance_key,
            duplicate_of,
            ctx.version,
            doc.doc_key,
            dumps(doc.identity),
            json.dumps([d.model_dump() for d in doc.defects]),
            int(doc.split_uncertain),
            now_iso(),
        ),
    )
    where = f"{_file_label(file_row)} p{doc.page_from}" + (f"-{doc.page_to}" if doc.page_to != doc.page_from else "")
    if status == "duplicate":
        return doc_id
    if status == "in_exception":
        codes = _reasons(doc, ("U",)) or ["ocr_floor"]
        raise_item(
            conn,
            case_id=case_id,
            kind="quality",
            ref=f"document:{doc_id}",
            summary=f"{where} grade U: {', '.join(codes)}",
            detail={"document_id": doc_id, "grade": "U", "reason_codes": codes},
        )
    elif status == "unclassified":
        candidates = ", ".join(f"{ctx.type_name(c.type_id)} {c.confidence:.2f}" for c in doc.classification.candidates)
        raise_item(
            conn,
            case_id=case_id,
            kind="type",
            ref=f"document:{doc_id}",
            summary=f"{where}: type not recognised" + (f" (candidates: {candidates})" if candidates else ""),
            detail={
                "document_id": doc_id,
                "candidates": [c.model_dump() for c in doc.classification.candidates],
            },
        )
    else:
        status = _store_fields(conn, ctx, case_id, doc_id, doc, types)
        conn.execute("UPDATE documents SET status = ? WHERE id = ?", (status, doc_id))
        _supersede(conn, case_id, doc_id, types, doc.instance_key)
    if grade == "C":
        codes = _reasons(doc, ("C",)) or ["ocr_floor"]
        raise_item(
            conn,
            case_id=case_id,
            kind="quality",
            ref=f"document:{doc_id}",
            summary=f"{where} grade C: {', '.join(codes)} (re-scan recommended)",
            detail={"document_id": doc_id, "grade": "C", "reason_codes": codes},
        )
    if doc.split_uncertain:
        raise_item(
            conn,
            case_id=case_id,
            kind="split",
            ref=f"document:{doc_id}",
            summary=f"{where}: split point uncertain",
            detail={"document_id": doc_id},
        )
    return doc_id


def _timing(conn: sqlite3.Connection, case_id: str, subject: str, stage: str, started_at: str, ms: int) -> None:
    conn.execute(
        "INSERT INTO stage_timings (case_id, subject, stage, started_at, ms) VALUES (?, ?, ?, ?, ?)",
        (case_id, subject, stage, started_at, int(ms)),
    )


def _store_file_result(
    conn: sqlite3.Connection, ctx: Context, case_id: str, file_row: sqlite3.Row, result: IngestResult, started_at: str
) -> None:
    t0 = time.perf_counter()
    with transaction(conn):
        outcome = next((o for o in result.files if o.file_id == file_row["id"]), None)
        if outcome is not None and outcome.status in ("exception", "rejected"):
            conn.execute(
                "UPDATE files SET status = ?, reason = ?, reason_code = COALESCE(reason_code, ?) WHERE id = ?",
                (outcome.status, outcome.reason, "corrupt" if outcome.status == "exception" else None, file_row["id"]),
            )
            if outcome.status == "exception":
                raise_item(
                    conn,
                    case_id=case_id,
                    kind="quality",
                    ref=f"file:{file_row['id']}",
                    summary=f"{_file_label(file_row)}: {outcome.reason or 'cannot be read'}",
                    detail={"file_id": file_row["id"], "reason_code": "corrupt"},
                )
        for doc in result.documents:
            if doc.file_id != file_row["id"]:
                continue
            d0 = time.perf_counter()
            doc_id = _store_document(conn, ctx, case_id, file_row, doc)
            if doc_id:
                _timing(conn, case_id, doc_id, "store", started_at, (time.perf_counter() - d0) * 1000)
        for t in result.timings:
            if t.file_id == file_row["id"]:
                _timing(conn, case_id, file_row["id"], t.stage, started_at, t.ms)
        _timing(conn, case_id, file_row["id"], "store", started_at, (time.perf_counter() - t0) * 1000)
        conn.execute("UPDATE files SET processed_at = ? WHERE id = ?", (now_iso(), file_row["id"]))


def process_files(
    conn: sqlite3.Connection, root: Path, job_id: str, case_id: str, file_ids: list[str], client
) -> None:
    placeholders = ",".join("?" * len(file_ids)) or "''"
    rows = conn.execute(
        f"""SELECT * FROM files WHERE case_id = ? AND id IN ({placeholders})
            AND status = 'registered' AND processed_at IS NULL ORDER BY uploaded_at, rowid""",
        (case_id, *file_ids),
    ).fetchall()
    if rows:
        ctx = Context.load(root)
        request = IngestRequest(
            case_ref=case_id,
            config_version=ctx.version,
            files=[
                IngestFile(
                    file_id=r["id"],
                    sha256=r["sha256"],
                    original_name=r["original_name"],
                    content_type=r["content_type"],
                    label_hint=r["label_hint"],
                )
                for r in rows
            ],
        )
        payloads = {r["id"]: (case_files_dir(case_id, root) / r["stored_name"]).read_bytes() for r in rows}
        started_at = now_iso()
        t0 = time.perf_counter()
        result = client.process(request, payloads)
        ingest_ms = (time.perf_counter() - t0) * 1000
        if result.config_version != ctx.version:
            raise IngestError(f"sidecar used configuration {result.config_version}, expected {ctx.version}")
        _timing(conn, case_id, case_id, "ingest", started_at, ingest_ms)
        for r in rows:
            _store_file_result(conn, ctx, case_id, r, result, started_at)
        log_decision(
            conn,
            at=now_iso(),
            actor="system",
            case_id=case_id,
            action="processing.run",
            detail=dumps(
                {
                    "job_id": job_id,
                    "config_version": result.config_version,
                    "engine_version": result.engine_version,
                    "model_provider": result.model_provider,
                    "files": [r["id"] for r in rows],
                }
            ),
        )
    refresh_case(conn, root, case_id, running_job=job_id)


def reextract_document(
    conn: sqlite3.Connection, root: Path, job_id: str, case_id: str, document_id: str, client
) -> None:
    """After a person assigns a type (F-09.5): extract that document again
    with the assigned type's dictionary."""
    doc = conn.execute("SELECT * FROM documents WHERE id = ? AND case_id = ?", (document_id, case_id)).fetchone()
    if doc is None or not doc["assigned_types"]:
        return
    file_row = conn.execute("SELECT * FROM files WHERE id = ?", (doc["file_id"],)).fetchone()
    ctx = Context.load(root)
    types = json.loads(doc["assigned_types"])
    request = IngestRequest(
        case_ref=case_id,
        config_version=ctx.version,
        files=[
            IngestFile(
                file_id=file_row["id"],
                sha256=file_row["sha256"],
                original_name=file_row["original_name"],
                content_type=file_row["content_type"],
                label_hint=file_row["label_hint"],
            )
        ],
        assignments=[
            TypeAssignment(file_id=file_row["id"], page_from=doc["page_from"], page_to=doc["page_to"], type_id=types[0])
        ],
    )
    payloads = {file_row["id"]: (case_files_dir(case_id, root) / file_row["stored_name"]).read_bytes()}
    started_at = now_iso()
    t0 = time.perf_counter()
    result = client.process(request, payloads)
    ms = (time.perf_counter() - t0) * 1000
    match = next(
        (d for d in result.documents if d.page_from == doc["page_from"] and d.page_to == doc["page_to"]), None
    )
    if match is None:
        raise IngestError(f"sidecar returned no document for pages {doc['page_from']}-{doc['page_to']}")
    with transaction(conn):
        conn.execute("DELETE FROM field_values WHERE document_id = ? AND method <> 'manual'", (document_id,))
        status = _store_fields(conn, ctx, case_id, document_id, match, types)
        conn.execute(
            "UPDATE documents SET status = ?, identity = ?, defects = ?, config_version = ? WHERE id = ?",
            (
                status,
                dumps(match.identity),
                json.dumps([d.model_dump() for d in match.defects]),
                ctx.version,
                document_id,
            ),
        )
        _timing(conn, case_id, document_id, "extract", started_at, ms)
        log_decision(
            conn,
            at=now_iso(),
            actor="system",
            case_id=case_id,
            action="processing.reextract",
            detail=dumps({"job_id": job_id, "document_id": document_id, "type_id": types[0],
                          "config_version": result.config_version}),
        )
    refresh_case(conn, root, case_id, running_job=job_id)


# --- Derived state ---


def refresh_case(conn: sqlite3.Connection, root: Path, case_id: str, *, running_job: str | None = None) -> None:
    from . import parties, queries

    parties.refresh(conn, root, case_id)
    queries.refresh(conn, root, case_id)
    _advance_stage(conn, case_id, running_job)


def _advance_stage(conn: sqlite3.Connection, case_id: str, running_job: str | None) -> None:
    """Intake -> Readiness once every submitted document is in a final state
    and nothing is waiting to be processed (FRD section 7)."""
    case = conn.execute("SELECT stage FROM cases WHERE id = ?", (case_id,)).fetchone()
    if case is None or case["stage"] != "Intake":
        return
    pending_files = conn.execute(
        "SELECT COUNT(*) FROM files WHERE case_id = ? AND status = 'registered' AND processed_at IS NULL", (case_id,)
    ).fetchone()[0]
    pending_jobs = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE case_id = ? AND status IN ('queued', 'running') AND id <> ?",
        (case_id, running_job or ""),
    ).fetchone()[0]
    statuses = [r["status"] for r in conn.execute("SELECT status FROM documents WHERE case_id = ?", (case_id,))]
    submitted = conn.execute(
        "SELECT COUNT(*) FROM files WHERE case_id = ? AND processed_at IS NOT NULL AND original_name <> ?",
        (case_id, MESSAGE_FILE_NAME),
    ).fetchone()[0]
    if pending_files or pending_jobs or not submitted or any(s not in FINAL_STATUSES for s in statuses):
        return
    with transaction(conn):
        conn.execute("UPDATE cases SET stage = 'Readiness' WHERE id = ? AND stage = 'Intake'", (case_id,))
        log_decision(
            conn, at=now_iso(), actor="system", case_id=case_id, action="case.stage",
            detail=dumps({"from": "Intake", "to": "Readiness"}),
        )
