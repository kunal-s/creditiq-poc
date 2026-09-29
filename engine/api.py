"""The engine service behind the screens (docs/functional-requirements.md).

Every data endpoint needs a session and a permission (F-03.1). Response
models come from engine/contracts (AD-4), so the OpenAPI schema, and the
TypeScript types generated from it, match exactly. This app must never
import the configuration writer (CLAUDE.md rule 4; enforced by .importlinter).
"""

from __future__ import annotations

import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from . import auth, cases, reads
from .config import load_app_config
from .configstore import reader as configstore_reader
from .configstore.schema import ChecklistTaxonomySection, DocumentTypesSection, PolicySection
from .contracts import (
    CaseCreate,
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

app = FastAPI(title="CreditIQ engine (RBL Bank instance)", version="0.1.0")

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
    try:
        return cases.create_case(conn, body, created_by=user["id"], config_version=_published_version())
    except cases.CaseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, user: dict = Depends(require("case.read")), conn: sqlite3.Connection = Depends(get_conn)):
    return _case_for(conn, case_id, user)


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


def _not_yet(feature: str):
    raise HTTPException(status_code=501, detail=f"{feature} is not implemented yet")


@app.post("/api/cases/proposals", response_model=CaseProposal)
def propose_case(body: ProposalRequest, _: dict = Depends(require("case.create"))):
    """F-04: parse a pasted message into a proposed case. Stores nothing."""
    _not_yet("F-04 case proposal")


@app.post("/api/cases/{case_id}/files", response_model=UploadResult, status_code=202)
def upload_files(case_id: str, _: dict = Depends(require("document.upload"))):
    """F-05: multipart upload, field name "files" (repeatable): single files,
    several files or ZIP archives. Registers every file and queues processing."""
    _not_yet("F-05 upload")


@app.get("/api/cases/{case_id}/documents/{document_id}/pages/{page}", response_class=Response)
def document_page(case_id: str, document_id: str, page: int, _: dict = Depends(require("case.read"))):
    """F-05.6, F-16: the rendered page image (PNG) of a document's source
    file; `page` is the absolute page in the file, as in Evidence."""
    _not_yet("F-16 page images")


@app.get("/api/cases/{case_id}/parties", response_model=list[Party])
def case_parties(case_id: str, _: dict = Depends(require("case.read"))):
    """F-10.2: the case's party set with sources and attributed KYC."""
    _not_yet("F-10 parties")


@app.post("/api/review/{item_id}/decision", response_model=ReviewItem)
def decide_review(item_id: str, body: ReviewDecisionRequest, _: dict = Depends(require("review.decide"))):
    """F-17.5: confirm, correct, waive or assign, with a reason. Recorded as
    an overlay; never changes configuration."""
    _not_yet("F-17 review decisions")


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
