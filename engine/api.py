"""The engine service behind the screens (docs/functional-requirements.md).

Every data endpoint needs a session and a permission (F-03.1). Response
models come from engine/contracts (AD-4), so the OpenAPI schema, and the
TypeScript types generated from it, match exactly. This app must never
import the configuration writer (CLAUDE.md rule 4; enforced by .importlinter).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from python_multipart.exceptions import MultipartParseError

from . import auth, cases, db, jobs, pages, parties, pipeline, proposal, queries, reads, review, uploads
from .config import load_app_config, option_ids
from .configstore import reader as configstore_reader
from .configstore.schema import ChecklistTaxonomySection, DocumentTypesSection, PolicySection
from .contracts import (
    CaseCreate,
    CaseDeleteRequest,
    CaseDetail,
    CaseProposal,
    CaseSummary,
    Party,
    ProposalRequest,
    ReviewDecisionRequest,
    UploadResult,
    FieldValue,
    FileRecord,
    Finding,
    LoginRequest,
    LoginResponse,
    LogicalDocument,
    Meta,
    QueryItem,
    Readiness,
    ReviewItem,
    SessionUser,
)
from .deps import bearer_token, current_user, get_conn, require
from .store import data_root

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """The processing worker runs beside the API (F-02.3); CREDITIQ_WORKER=0
    leaves jobs to `creditiq jobs run`."""
    worker = None
    if os.environ.get("CREDITIQ_WORKER", "1") != "0":
        worker = jobs.Worker(data_root)
        worker.start()
    try:
        yield
    finally:
        if worker is not None:
            worker.stop()


app = FastAPI(title="CreditIQ engine (RBL Bank instance)", version="0.1.0", lifespan=lifespan)

# The frontend dev server and this API run as separate local processes.
# Browsers treat localhost and 127.0.0.1 as distinct origins, so both are
# listed for whichever host the frontend happens to be opened on.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _published_version() -> str | None:
    try:
        return configstore_reader.published_version(data_root())["version"]
    except configstore_reader.NoPublishedConfig:
        return None


def _case_for(conn: sqlite3.Connection, case_id: str, user: dict) -> CaseDetail:
    """The case, if it exists and this user may see it (an RM sees only
    cases they created). Otherwise 404, so existence is not disclosed."""
    case = cases.get_case(conn, case_id)
    if case is None or ("case.read.all" not in user["permissions"] and case.created_by != user["id"]):
        raise HTTPException(status_code=404, detail=f"no case {case_id!r}")
    return case


# --- Service ---


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "config_version": _published_version()}


# --- Session (F-03) ---


@app.post("/api/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    result = auth.login(conn, body.email, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return result


@app.get("/api/auth/session", response_model=SessionUser)
def session(user: dict = Depends(current_user)) -> dict:
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(token: str = Depends(bearer_token), conn: sqlite3.Connection = Depends(get_conn)) -> None:
    auth.logout(conn, token)


@app.get("/api/meta", response_model=Meta)
def meta(_: dict = Depends(current_user)) -> dict:
    cfg = load_app_config()
    return {
        "channels": [{"id": c["id"], "label": c["label"]} for c in cfg["channels"]],
        "constitutions": [{"id": c["id"], "label": c["label"]} for c in cfg["constitutions"]],
        "facilities": [{"id": f["id"], "label": f["label"]} for f in cfg["facilities"]],
        "case_create_minimum": cfg["case_create_minimum"],
    }


# --- Cases (F-01) ---


@app.get("/api/cases", response_model=list[CaseSummary])
def list_cases(user: dict = Depends(require("case.read")), conn: sqlite3.Connection = Depends(get_conn)):
    only = None if "case.read.all" in user["permissions"] else user["id"]
    return cases.list_cases(conn, only_created_by=only)


@app.post("/api/cases", response_model=CaseDetail, status_code=201)
def create_case(
    body: CaseCreate, user: dict = Depends(require("case.create")), conn: sqlite3.Connection = Depends(get_conn)
):
    root = data_root()
    try:
        created = cases.create_case(
            conn,
            body,
            created_by=user["id"],
            config_version=_published_version(),
            root=root,
            name_threshold=parties.name_tolerance(root),
        )
    except cases.DuplicateCase as e:
        # F-04.5: offer "Open it" or "Create anyway" (with a reason).
        raise HTTPException(
            status_code=409,
            detail={"message": str(e), "duplicates": [d.model_dump() for d in e.duplicates]},
        ) from e
    except cases.CaseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    try:
        pipeline.refresh_case(conn, root, created.id)
    except configstore_reader.NoPublishedConfig:
        pass  # derived state is built once configuration is published
    return created


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, user: dict = Depends(require("case.read")), conn: sqlite3.Connection = Depends(get_conn)):
    return _case_for(conn, case_id, user)


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(
    case_id: str,
    body: CaseDeleteRequest,
    user: dict = Depends(require("case.delete")),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """F-01.5: delete a case and everything it owns, so testing can start
    again. An RM may delete only their own cases. The decision log keeps a
    record of the deletion; the case ID is not reused."""
    _case_for(conn, case_id, user)
    try:
        cases.delete_case(conn, case_id, actor=user["id"], reason=body.reason.strip(), root=data_root())
    except cases.CaseBusy as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except cases.CaseError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- Documents and data (F-05, F-07 to F-09, F-15) ---


@app.get("/api/cases/{case_id}/files", response_model=list[FileRecord])
def case_files(case_id: str, user: dict = Depends(require("case.read")), conn: sqlite3.Connection = Depends(get_conn)):
    _case_for(conn, case_id, user)
    return reads.files(conn, case_id)


@app.get("/api/cases/{case_id}/documents", response_model=list[LogicalDocument])
def case_documents(
    case_id: str, user: dict = Depends(require("case.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    _case_for(conn, case_id, user)
    return reads.documents(conn, case_id)


@app.get("/api/cases/{case_id}/fields", response_model=list[FieldValue])
def case_fields(
    case_id: str,
    document_id: str | None = None,
    user: dict = Depends(require("data.read")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    _case_for(conn, case_id, user)
    return reads.field_values(conn, case_id, document_id)


# --- Completeness (F-12 to F-14) ---


@app.get("/api/cases/{case_id}/checklist", response_model=Readiness)
def case_checklist(
    case_id: str, user: dict = Depends(require("checklist.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    case = _case_for(conn, case_id, user)
    try:
        return reads.readiness(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/cases/{case_id}/queries", response_model=list[QueryItem])
def case_queries(
    case_id: str, user: dict = Depends(require("query.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    _case_for(conn, case_id, user)
    try:
        queries.refresh(conn, data_root(), case_id)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return reads.query_items(conn, case_id)


# --- Cross-checks (F-19) and review (F-17) ---


@app.get("/api/cases/{case_id}/findings", response_model=list[Finding])
def case_findings(
    case_id: str, user: dict = Depends(require("finding.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    _case_for(conn, case_id, user)
    return reads.findings(conn, case_id)


@app.get("/api/review", response_model=list[ReviewItem])
def review_queue(
    case_id: str | None = None,
    include_decided: bool = False,
    _: dict = Depends(require("review.read")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return reads.review_items(conn, case_id=case_id, open_only=not include_decided)


# --- Wave 1 contract: declared here so screens and engine build against one
# OpenAPI; each returns 501 until its feature lands (stream B). ---


@app.post("/api/cases/proposals", response_model=CaseProposal)
def propose_case(
    body: ProposalRequest, _: dict = Depends(require("case.create")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-04: parse a pasted message into a proposed case. Stores nothing."""
    if body.channel not in option_ids("channels"):
        raise HTTPException(status_code=422, detail=f"unknown channel {body.channel!r}")
    try:
        return proposal.propose(conn, data_root(), body.text)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


_UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["files"],
                    "properties": {
                        "files": {"type": "array", "items": {"type": "string", "format": "binary"}},
                        "channel": {"type": "string"},
                    },
                }
            }
        },
    }
}


@app.post(
    "/api/cases/{case_id}/files", response_model=UploadResult, status_code=202, openapi_extra=_UPLOAD_BODY
)
async def upload_files(case_id: str, request: Request, user: dict = Depends(require("document.upload"))):
    """F-05: multipart upload, field name "files" (repeatable): single files,
    several files or ZIP archives. Registers every file and queues processing.
    The body is parsed as it streams, so size limits apply before a file is
    held in full."""
    root = data_root()

    def check_case() -> None:
        conn = db.connect(root)
        try:
            _case_for(conn, case_id, user)
        finally:
            conn.close()

    await run_in_threadpool(check_case)
    try:
        receiver = uploads.MultipartReceiver(
            request.headers.get("content-type", ""), uploads.spool_dir(root, case_id), uploads.limits()
        )
        async for chunk in request.stream():
            await run_in_threadpool(receiver.write, chunk)
        receiver.finish()
    except (uploads.UploadError, MultipartParseError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not receiver.parts:
        raise HTTPException(status_code=422, detail="no files in the upload (multipart field 'files')")
    channel = (receiver.fields.get("channel") or "upload").strip()[:40] or "upload"

    def register() -> UploadResult:
        conn = db.connect(root)
        try:
            result = uploads.register_parts(
                conn, root, case_id=case_id, user_id=user["id"], channel=channel, parts=receiver.parts
            )
            pipeline.refresh_case(conn, root, case_id)
            return result
        finally:
            conn.close()

    return await run_in_threadpool(register)


@app.get("/api/cases/{case_id}/documents/{document_id}/pages/{page}", response_class=Response)
def document_page(
    case_id: str,
    document_id: str,
    page: int,
    user: dict = Depends(require("case.read")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """F-05.6, F-16: the rendered page image (PNG) of a document's source
    file; `page` is the absolute page in the file, as in Evidence."""
    _case_for(conn, case_id, user)
    try:
        data, media_type = pages.page_image(conn, data_root(), case_id, document_id, page)
    except pages.PageError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(content=data, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/cases/{case_id}/parties", response_model=list[Party])
def case_parties(case_id: str, user: dict = Depends(require("case.read")), conn: sqlite3.Connection = Depends(get_conn)):
    """F-10.2: the case's party set with sources and attributed KYC."""
    _case_for(conn, case_id, user)
    if not conn.execute("SELECT 1 FROM parties WHERE case_id = ? LIMIT 1", (case_id,)).fetchone():
        try:
            parties.refresh(conn, data_root(), case_id)
        except configstore_reader.NoPublishedConfig as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
    return parties.list_parties(conn, case_id)


@app.post("/api/review/{item_id}/decision", response_model=ReviewItem)
def decide_review(
    item_id: str,
    body: ReviewDecisionRequest,
    user: dict = Depends(require("review.decide")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """F-17.5: confirm, correct, waive or assign, with a reason. Recorded as
    an overlay; never changes configuration."""
    row = conn.execute("SELECT case_id FROM review_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"no review item {item_id!r}")
    _case_for(conn, row["case_id"], user)
    try:
        return review.decide(conn, data_root(), item_id, body, user)
    except review.ReviewError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e


# --- Published configuration (F-00) ---


def _config(loader):
    try:
        return loader(data_root())
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/config/version")
def config_version(_: dict = Depends(current_user)) -> dict:
    return _config(configstore_reader.published_version)


@app.get("/api/config/policy", response_model=PolicySection)
def config_policy(_: dict = Depends(current_user)):
    return _config(configstore_reader.load_policy)


@app.get("/api/config/checklist-taxonomy", response_model=ChecklistTaxonomySection)
def config_checklist_taxonomy(_: dict = Depends(current_user)):
    return _config(configstore_reader.load_checklist_taxonomy)


@app.get("/api/config/document-types", response_model=DocumentTypesSection)
def config_document_types(_: dict = Depends(current_user)):
    return _config(configstore_reader.load_document_types)
