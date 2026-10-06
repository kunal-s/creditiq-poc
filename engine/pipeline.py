"""The processing job (F-02): send registered files to the document-processing
service (AD-2a) and store what comes back.

For each file, in its own transaction: the logical documents (F-08), their
status per the state diagram (FRD section 7), the field values with
confidence (F-17.1), the review items (type, field, quality, split) and the
stage timings (F-02.4). A file is marked processed in the same transaction,
so a job killed part-way resumes with only the files not yet stored, and a
re-run stores nothing twice (document and review ids are deterministic).

The service answers per file (contract version 2). This module maps that answer onto the
engine's own tables: one row per logical document, one `field_values` row per scalar, per
list element ("name[i]" or "name[i].key") and per table cell ("table[row].column"). Boxes arrive in
page points and are stored normalised to 0..1 (top-left origin) for the evidence viewer.

After storing, the derived state is refreshed: parties and attribution
(F-10), the query list (F-14), and the case stage (FRD §7, engine/progress.py).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from .configstore import reader
from .configstore.schema import DocumentTypeDef
from .contracts import Candidate, Classification, IngestFile, IngestFileResult, IngestRequest, IngestResult, PageInfo
from .contracts.ingest import IngestDocument, IngestField
from .db import log_decision, transaction
from .ingest_client import IngestError
from .review_items import close_item, raise_item
from .store import case_files_dir
from .util import dumps, now_iso, stable_id

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "U": 3}
ROUTE = {"text_layer": "text", "ocr": "ocr", "sheet": "sheet"}
METHOD = {"identifier": "deterministic", "alias": "deterministic", "pattern": "deterministic", "model": "model"}


@dataclass
class Context:
    root: Path
    version: str
    types: dict[str, DocumentTypeDef]

    @classmethod
    def load(cls, root: Path) -> "Context":
        return cls(root=root, version=reader.published_version(root)["version"],
                   types={t.id: t for t in reader.load_document_types(root).types})

    def type_name(self, type_id: str) -> str:
        t = self.types.get(type_id)
        return t.name if t else type_id


# --- The service's answer, as the engine stores it ---


@dataclass
class Flat:
    field: str
    value: object
    raw: str | None
    page: int | None
    bbox: list[float] | None
    method: str
    confidence: float | None
    components: dict[str, float]
    status: str
    missing_reason: str | None = None


@dataclass
class Unit:
    """One logical document as stored."""

    doc_key: str
    page_from: int
    page_to: int
    pages: list[PageInfo]
    classification: Classification
    instance_key: str | None = None
    identity: dict[str, str] = field(default_factory=dict)
    defects: list[dict] = field(default_factory=list)
    fields: list[Flat] = field(default_factory=list)


def document_grade(pages: list[PageInfo]) -> str:
    """F-07.3: the worst grade among non-blank pages (all blank: U)."""
    grades = [p.grade for p in pages if "blank" not in p.reasons]
    if not grades:
        return "U"
    return max(grades, key=lambda g: GRADE_ORDER[g])


def _reasons(pages: list[PageInfo], grades: tuple[str, ...]) -> list[str]:
    codes: list[str] = []
    for p in pages:
        if p.grade in grades:
            for r in p.reasons:
                if r not in codes:
                    codes.append(r)
    return codes


def _file_label(file_row: sqlite3.Row) -> str:
    return file_row["archive_path"] or file_row["original_name"]


def _norm_bbox(bbox: list[float] | None, dims: tuple[float, float] | None) -> list[float] | None:
    if not bbox or not dims or dims[0] <= 0 or dims[1] <= 0:
        return None
    w, h = dims
    x0, y0, x1, y1 = (min(max(v, 0.0), 1.0) for v in (bbox[0] / w, bbox[1] / h, bbox[2] / w, bbox[3] / h))
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def _flatten(doc: IngestDocument, dims: dict[int, tuple[float, float]]) -> list[Flat]:
    out: list[Flat] = []

    def field_row(name: str, f: IngestField) -> None:
        page = f.source.page if f.source else None
        bbox = _norm_bbox(f.source.bbox, dims.get(page)) if f.source and page else None
        if f.status == "missing" or f.value is None:
            out.append(Flat(name, None, f.raw_text, page, None, METHOD.get(f.method or "pattern", "deterministic"), None, {}, "missing", f.reason or "not_found"))
            return
        status = "in_review" if f.needs_review else "accepted"
        method = METHOD[f.method] if f.method else "deterministic"

        def add(fname: str, value: object, raw: str | None) -> None:
            out.append(Flat(fname, value, raw, page, bbox, method, f.confidence, dict(f.components), status))

        if isinstance(f.value, list):
            for i, el in enumerate(f.value):
                if isinstance(el, dict):
                    for k, v in el.items():
                        if v is not None:
                            add(f"{name}[{i}].{k}", v, str(v))
                else:
                    add(f"{name}[{i}]", el, str(el))
        else:
            add(name, f.value, f.raw_text)

    for name, f in doc.fields.items():
        field_row(name, f)
    for tname, t in doc.tables.items():
        if t.status != "found":
            out.append(Flat(tname, None, None, None, None, "deterministic", None, {}, "missing", t.reason or "table_not_found"))
            continue
        for i, row in enumerate(t.rows):
            page = row.source.get("page")
            bbox = _norm_bbox(row.source.get("bbox"), dims.get(page))
            for col, v in row.cells.items():
                if v is not None:
                    out.append(Flat(f"{tname}[{i}].{col}", v, row.raw.get(col), page, bbox, "deterministic", t.confidence, {}, "accepted"))
    return out


def _page_infos(fr: IngestFileResult, lo: int, hi: int) -> list[PageInfo]:
    return [PageInfo(n=p.page, route=ROUTE[p.source], grade=p.grade, reasons=list(p.reasons), ocr_confidence=p.ocr_conf)
            for p in fr.pages if lo <= p.page <= hi]


def _classification(fr: IngestFileResult) -> Classification:
    c = fr.classification
    if c is None:
        return Classification(types=[], confidence=0.0, exit_tier="none")
    sig = c.signals or {}
    return Classification(
        types=[c.type] if c.type else [],
        confidence=c.confidence,
        exit_tier=c.tier,
        signals=[*sig.get("required", []), *sig.get("supporting", [])],
        candidates=[Candidate(type_id=x.type, confidence=x.score) for x in c.candidates[:3]],
    )


def units_of(fr: IngestFileResult) -> list[Unit]:
    dims = {p.page: (p.width, p.height) for p in fr.pages}
    cls = _classification(fr)
    if fr.documents:
        units = []
        for d in fr.documents:
            key = hashlib.sha256(f"{fr.sha256}|{d.document_type}|{d.instance_no}|{d.page_from}-{d.page_to}".encode()).hexdigest()[:16]
            units.append(Unit(key, d.page_from, d.page_to, _page_infos(fr, d.page_from, d.page_to), cls, d.instance_key, dict(d.identity),
                              [x.model_dump() for x in d.defects], _flatten(d, dims)))
        return units
    if not fr.pages:
        return []
    last = max(p.page for p in fr.pages)
    key = hashlib.sha256(f"{fr.sha256}|-|1|1-{last}".encode()).hexdigest()[:16]
    return [Unit(key, 1, last, _page_infos(fr, 1, last), cls)]


# --- Storing one document ---


def _store_fields(conn: sqlite3.Connection, ctx: Context, case_id: str, doc_id: str, unit: Unit, types: list[str]) -> str:
    """Insert the document's field values; returns the document status
    (accepted, or in_review when a key field is below the threshold)."""
    in_review = False
    label = ", ".join(ctx.type_name(t) for t in types)
    for f in unit.fields:
        fv_id = stable_id("FV", doc_id, f.field)
        evidence = {"document_id": doc_id, "page": f.page, "bbox": f.bbox} if f.page and f.status != "missing" else None
        conn.execute(
            """INSERT INTO field_values (id, case_id, document_id, field, value, raw, evidence, method, confidence,
                   confidence_components, status, missing_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO NOTHING""",
            (fv_id, case_id, doc_id, f.field, json.dumps(f.value), f.raw, json.dumps(evidence) if evidence else None, f.method,
             f.confidence, json.dumps(f.components), f.status, f.missing_reason),
        )
        if f.status == "in_review":
            in_review = True
            shown = f.raw if f.raw is not None else f.value
            raise_item(
                conn, case_id=case_id, kind="field", ref=f"field:{fv_id}",
                summary=f"{label}: {f.field} = {shown} (confidence {f.confidence:.2f})",
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


def _timing(conn: sqlite3.Connection, case_id: str, subject: str, stage: str, started_at: str, ms: int) -> None:
    conn.execute(
        "INSERT INTO stage_timings (case_id, subject, stage, started_at, ms) VALUES (?, ?, ?, ?, ?)",
        (case_id, subject, stage, started_at, int(ms)),
    )


def _store_document(conn: sqlite3.Connection, ctx: Context, case_id: str, file_row: sqlite3.Row, unit: Unit) -> str | None:
    doc_id = stable_id("DOC", case_id, file_row["id"], unit.doc_key)
    if conn.execute("SELECT 1 FROM documents WHERE id = ?", (doc_id,)).fetchone():
        return None
    grade = document_grade(unit.pages)
    types = list(unit.classification.types)
    if grade == "U":
        status = "in_exception"
    elif not types:
        status = "unclassified"
    else:
        status = "extracted"
    conn.execute(
        """INSERT INTO documents (id, case_id, file_id, page_from, page_to, pages, grade, classification, status,
               instance_key, duplicate_of, config_version, doc_key, identity, defects, split_uncertain, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_id, case_id, file_row["id"], unit.page_from, unit.page_to, json.dumps([p.model_dump() for p in unit.pages]), grade,
         unit.classification.model_dump_json(), status, unit.instance_key, None, ctx.version, unit.doc_key, dumps(unit.identity),
         json.dumps(unit.defects), 0, now_iso()),
    )
    where = f"{_file_label(file_row)} p{unit.page_from}" + (f"-{unit.page_to}" if unit.page_to != unit.page_from else "")
    if status == "in_exception":
        codes = _reasons(unit.pages, ("U",)) or ["ocr_floor"]
        raise_item(conn, case_id=case_id, kind="quality", ref=f"document:{doc_id}", summary=f"{where} grade U: {', '.join(codes)}",
                   detail={"document_id": doc_id, "grade": "U", "reason_codes": codes})
    elif status == "unclassified":
        candidates = ", ".join(f"{ctx.type_name(c.type_id)} {c.confidence:.2f}" for c in unit.classification.candidates)
        raise_item(conn, case_id=case_id, kind="type", ref=f"document:{doc_id}",
                   summary=f"{where}: type not recognised" + (f" (candidates: {candidates})" if candidates else ""),
                   detail={"document_id": doc_id, "candidates": [c.model_dump() for c in unit.classification.candidates]})
    else:
        status = _store_fields(conn, ctx, case_id, doc_id, unit, types)
        conn.execute("UPDATE documents SET status = ? WHERE id = ?", (status, doc_id))
        _supersede(conn, case_id, doc_id, types, unit.instance_key)
    if grade == "C":
        codes = _reasons(unit.pages, ("C",)) or ["ocr_floor"]
        raise_item(conn, case_id=case_id, kind="quality", ref=f"document:{doc_id}",
                   summary=f"{where} grade C: {', '.join(codes)} (re-scan recommended)",
                   detail={"document_id": doc_id, "grade": "C", "reason_codes": codes})
    return doc_id


def _store_file_result(conn: sqlite3.Connection, ctx: Context, case_id: str, file_row: sqlite3.Row, result: IngestResult, started_at: str) -> None:
    t0 = time.perf_counter()
    with transaction(conn):
        fr = next((f for f in result.files if f.file_id == file_row["id"]), None)
        if fr is None:
            raise IngestError(f"the service returned nothing for file {file_row['original_name']}")
        if fr.status in ("rejected", "failed"):
            reason = (fr.reject.message if fr.reject else None) or (fr.error or {}).get("message") or "cannot be read"
            code = (fr.reject.code if fr.reject else "corrupt")
            conn.execute(
                "UPDATE files SET status = ?, reason = ?, reason_code = COALESCE(reason_code, ?) WHERE id = ?",
                ("exception" if fr.status == "failed" or code in ("corrupt", "encrypted", "empty") else "rejected", reason, code, file_row["id"]),
            )
            raise_item(conn, case_id=case_id, kind="quality", ref=f"file:{file_row['id']}", summary=f"{_file_label(file_row)}: {reason}",
                       detail={"file_id": file_row["id"], "reason_code": code, "rescan_request": fr.reject.rescan_request if fr.reject else None})
        else:
            for unit in units_of(fr):
                d0 = time.perf_counter()
                doc_id = _store_document(conn, ctx, case_id, file_row, unit)
                if doc_id:
                    _timing(conn, case_id, doc_id, "store", started_at, (time.perf_counter() - d0) * 1000)
        _timing(conn, case_id, file_row["id"], "store", started_at, (time.perf_counter() - t0) * 1000)
        conn.execute("UPDATE files SET processed_at = ? WHERE id = ?", (now_iso(), file_row["id"]))


def _ingest_file(r: sqlite3.Row, assigned_type: str | None = None) -> IngestFile:
    return IngestFile(file_id=r["id"], sha256=r["sha256"], original_name=r["original_name"], content_type=r["content_type"],
                      label_hint=r["label_hint"], assigned_type=assigned_type)


def _check_version(result: IngestResult, ctx: Context) -> None:
    if result.config.version != ctx.version:
        raise IngestError(f"the service used configuration {result.config.version}, expected {ctx.version}")


def process_files(conn: sqlite3.Connection, root: Path, job_id: str, case_id: str, file_ids: list[str], client) -> None:
    placeholders = ",".join("?" * len(file_ids)) or "''"
    rows = conn.execute(
        f"""SELECT * FROM files WHERE case_id = ? AND id IN ({placeholders})
            AND status = 'registered' AND processed_at IS NULL ORDER BY uploaded_at, rowid""",
        (case_id, *file_ids),
    ).fetchall()
    if rows:
        ctx = Context.load(root)
        request = IngestRequest(case_ref=case_id, config_version=ctx.version, files=[_ingest_file(r) for r in rows])
        payloads = {r["id"]: (case_files_dir(case_id, root) / r["stored_name"]).read_bytes() for r in rows}
        started_at = now_iso()
        t0 = time.perf_counter()
        result = client.process(request, payloads)
        ingest_ms = (time.perf_counter() - t0) * 1000
        _check_version(result, ctx)
        _timing(conn, case_id, case_id, "ingest", started_at, ingest_ms)
        for r in rows:
            _store_file_result(conn, ctx, case_id, r, result, started_at)
        log_decision(
            conn, at=now_iso(), actor="system", case_id=case_id, action="processing.run",
            detail=dumps({"job_id": job_id, "config_version": result.config.version, "config_hash": result.config.hash,
                          "engine_version": result.engine.version, "model": result.engine.model, "files": [r["id"] for r in rows]}),
        )
    refresh_case(conn, root, case_id, running_job=job_id)


def reextract_document(conn: sqlite3.Connection, root: Path, job_id: str, case_id: str, document_id: str, client) -> None:
    """After a person assigns a type (F-09.5): read the file again as that type. The document
    keeps its row; further instances the new type finds in the file become new rows."""
    doc = conn.execute("SELECT * FROM documents WHERE id = ? AND case_id = ?", (document_id, case_id)).fetchone()
    if doc is None or not doc["assigned_types"]:
        return
    file_row = conn.execute("SELECT * FROM files WHERE id = ?", (doc["file_id"],)).fetchone()
    ctx = Context.load(root)
    types = json.loads(doc["assigned_types"])
    request = IngestRequest(case_ref=case_id, config_version=ctx.version, files=[_ingest_file(file_row, assigned_type=types[0])])
    payloads = {file_row["id"]: (case_files_dir(case_id, root) / file_row["stored_name"]).read_bytes()}
    started_at = now_iso()
    t0 = time.perf_counter()
    result = client.process(request, payloads)
    ms = (time.perf_counter() - t0) * 1000
    _check_version(result, ctx)
    fr = result.files[0]
    units = units_of(fr) if fr.status == "processed" else []
    mine = next((u for u in units if (u.page_from, u.page_to) == (doc["page_from"], doc["page_to"])), None) or (units[0] if units else None)
    if mine is None:
        raise IngestError(f"the service returned no document for {file_row['original_name']} read as {types[0]}")
    with transaction(conn):
        conn.execute("DELETE FROM field_values WHERE document_id = ? AND method <> 'manual'", (document_id,))
        status = _store_fields(conn, ctx, case_id, document_id, mine, types)
        conn.execute(
            """UPDATE documents SET status = ?, identity = ?, defects = ?, config_version = ?, page_from = ?, page_to = ?, pages = ?,
                   instance_key = ?, grade = ? WHERE id = ?""",
            (status, dumps(mine.identity), json.dumps(mine.defects), ctx.version, mine.page_from, mine.page_to,
             json.dumps([p.model_dump() for p in mine.pages]), mine.instance_key, document_grade(mine.pages), document_id),
        )
        for extra in units:
            if extra is not mine:
                _store_document(conn, ctx, case_id, file_row, extra)
        _timing(conn, case_id, document_id, "extract", started_at, ms)
        log_decision(
            conn, at=now_iso(), actor="system", case_id=case_id, action="processing.reextract",
            detail=dumps({"job_id": job_id, "document_id": document_id, "type_id": types[0], "config_version": result.config.version}),
        )
    refresh_case(conn, root, case_id, running_job=job_id)


# --- Derived state ---


def refresh_case(conn: sqlite3.Connection, root: Path, case_id: str, *, running_job: str | None = None) -> None:
    from . import cases, crosschecks, parties, queries

    parties.refresh(conn, root, case_id)
    case = cases.get_case(conn, case_id)
    if case is not None:
        try:
            crosschecks.run(conn, root, case)
        except reader.NoPublishedConfig:
            # A configuration published before the cross-check sections
            # existed: the checks wait for the next publish.
            pass
    queries.refresh(conn, root, case_id)
    _update_stage(conn, root, case_id, running_job)


def _update_stage(conn: sqlite3.Connection, root: Path, case_id: str, running_job: str | None) -> None:
    """The case's stage is the first processing stage not yet done (FRD §7);
    a late document can move it back. Each change is logged."""
    from . import cases, progress

    case = cases.get_case(conn, case_id)
    if case is None:
        return
    stage = progress.compute(conn, root, case, running_job=running_job).stage
    if stage == case.stage:
        return
    with transaction(conn):
        conn.execute("UPDATE cases SET stage = ? WHERE id = ?", (stage, case_id))
        log_decision(
            conn, at=now_iso(), actor="system", case_id=case_id, action="case.stage",
            detail=dumps({"from": case.stage, "to": stage}),
        )
