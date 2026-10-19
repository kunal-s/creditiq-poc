"""The engine service behind the screens (docs/functional-requirements.md).

Every data endpoint needs a session and a permission (F-03.1). Response
models come from engine/contracts (AD-4), so the OpenAPI schema, and the
TypeScript types generated from it, match exactly. The configuration writer is
reached only through engine.admin_config, for an Administrator's publish from
the Administration screen (F-00.6); nothing that runs on a case may import it
(CLAUDE.md rule 4; enforced by .importlinter).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from python_multipart.exceptions import MultipartParseError

from . import (
    admin_config,
    approval,
    auth,
    cam,
    cam_copilot,
    cam_review,
    keys,
    cases,
    comparison,
    db,
    exports,
    facts,
    jobs,
    pages,
    parties,
    pd_note,
    pipeline,
    policy,
    progress,
    proposal,
    queries,
    reads,
    reference,
    review,
    spread,
    uploads,
    xv,
)
from .config import load_app_config, load_roles_config, option_ids, role_label, find_user_by_id
from .configstore import reader as configstore_reader
from .configstore.schema import ApprovalMatrixSection, ChecklistTaxonomySection, DocumentTypesSection, PolicySection
from .contracts import (
    CrossVerificationView,
    XvDecisionRequest,
    XvItem,
    AdjudicationRequest,
    ApprovingAuthority,
    CaseComparison,
    ComparisonArea,
    ComparisonItem,
    ReferenceRecord,
    AuditPage,
    ConfigVersion,
    DirectoryUser,
    EditableSettings,
    SettingsChanges,
    SettingsPreview,
    SettingsPublished,
    SettingsPublishRequest,
    CaseCreate,
    CaseDeleteRequest,
    Cam,
    CaseDetail,
    CaseFacts,
    CaseProgress,
    CaseProposal,
    PdNote,
    PolicyAssessment,
    Spread,
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
    CamDataRequest,
    CamOverrideRequest,
    CamRegenerateRequest,
    CamRegenerateResult,
    CamWordsRequest,
)
from .deps import bearer_token, current_user, get_conn, require
from .store import data_root
from .util import now_iso

# Keys from git-ignored files (workflow/private/), where the environment does not carry them.
keys.load()


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
        # Other frontend origins, comma separated (for a non-default dev port).
        *[o.strip() for o in os.environ.get("CREDITIQ_FRONTEND_ORIGINS", "").split(",") if o.strip()],
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


def _assessed_case(conn: sqlite3.Connection, case_id: str, user: dict) -> CaseDetail:
    """The case, refused with 409 while the assessment gate is shut (F-13). The screens
    lock these tabs; this is the same rule on the server, so the data is not reachable
    by asking for it directly."""
    case = _case_for(conn, case_id, user)
    if not case.assessment_opened_at:
        raise HTTPException(status_code=409, detail="assessment_not_open")
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


@app.get("/api/cases/{case_id}/progress", response_model=CaseProgress)
def case_progress(
    case_id: str, user: dict = Depends(require("case.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    """FRD §6: each processing stage's status and counts, for the stage
    progress in the case workspace. Counts only, so every role may read it."""
    case = _case_for(conn, case_id, user)
    try:
        return progress.compute(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.post("/api/cases/{case_id}/assessment", response_model=CaseDetail)
def open_assessment(
    case_id: str,
    user: dict = Depends(require("review.decide")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """F-13: create the case, opening cross-verification, policy checks and the outputs.

    `review.decide`, because it is the decision that intake is complete: the analyst and the
    credit manager hold it, the RM does not.

    Refused with 409 while completeness is not satisfied; the body names the blockers so the
    screen can say which one. Pressing it twice is harmless: the case is returned unchanged.
    """
    case = _case_for(conn, case_id, user)
    try:
        return cases.open_assessment(conn, data_root(), case, user["id"])
    except cases.GateNotMet as e:
        raise HTTPException(status_code=409, detail={"error": "assessment_not_open", "blockers": e.blockers}) from e
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


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


@app.get("/api/cases/{case_id}/facts", response_model=CaseFacts)
def case_facts(
    case_id: str, user: dict = Depends(require("data.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-18: the aligned facts the cross-checks compare, each with its evidence."""
    case = _case_for(conn, case_id, user)
    try:
        return facts.compute(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/cases/{case_id}/policy", response_model=PolicyAssessment)
def case_policy(
    case_id: str, user: dict = Depends(require("finding.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-20: every norm with its required and actual value, source figures and outcome."""
    case = _assessed_case(conn, case_id, user)
    try:
        return policy.assess(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/cases/{case_id}/cross-verification", response_model=CrossVerificationView)
def case_cross_verification(
    case_id: str, user: dict = Depends(require("finding.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-19: the cross-verification board: every finding of the latest run, the discrepancies ranked
    by credit impact with their sources side by side, and whether submission is blocked."""
    case = _assessed_case(conn, case_id, user)
    try:
        return xv.view(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.post("/api/cases/{case_id}/cross-verification/findings/{finding_id}/decision", response_model=XvItem)
def decide_cross_verification(
    case_id: str,
    finding_id: str,
    body: XvDecisionRequest,
    user: dict = Depends(require("review.decide")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """F-19, F-17.4: accept, dismiss or escalate a discrepancy, with a comment."""
    case = _case_for(conn, case_id, user)
    try:
        return xv.decide(conn, data_root(), case, finding_id, body, user)
    except xv.XvError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.post("/api/cases/{case_id}/cross-verification/findings/{finding_id}/query", response_model=XvItem)
def query_cross_verification(
    case_id: str,
    finding_id: str,
    user: dict = Depends(require("review.decide")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """F-14: put what would complete a check that could not run on the pre-login query list."""
    case = _case_for(conn, case_id, user)
    try:
        return xv.add_query(conn, data_root(), case, finding_id, user)
    except xv.XvError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/cases/{case_id}/approving-authority", response_model=ApprovingAuthority)
def case_approving_authority(
    case_id: str, user: dict = Depends(require("finding.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-21: the authority the case needs under the published matrix, and the rules that set it."""
    case = _case_for(conn, case_id, user)
    try:
        return approval.required(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail="approval matrix not published") from e


@app.get("/api/cases/{case_id}/comparison", response_model=CaseComparison)
def case_comparison(
    case_id: str, user: dict = Depends(require("comparison.adjudicate")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-25: CreditIQ against RBL's confirmed reference record, deviations and approving authority."""
    case = _case_for(conn, case_id, user)
    try:
        return comparison.compare(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.post("/api/cases/{case_id}/reference/confirm", response_model=ReferenceRecord)
def confirm_reference(
    case_id: str, user: dict = Depends(require("comparison.adjudicate")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-25.1: the RBL reviewer confirms the imported record (never the person who imported it)."""
    _case_for(conn, case_id, user)
    try:
        return reference.confirm(conn, case_id, user)
    except reference.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except reference.Conflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@app.put("/api/cases/{case_id}/comparison/{area}/{key}/adjudication", response_model=ComparisonItem)
def adjudicate_comparison_item(
    case_id: str,
    area: ComparisonArea,
    key: str,
    body: AdjudicationRequest,
    user: dict = Depends(require("comparison.adjudicate")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """F-25.4: the reviewer's verdict on a difference or a new deviation, with a reason."""
    case = _case_for(conn, case_id, user)
    try:
        return comparison.adjudicate(conn, data_root(), case, area, key, body, user)
    except comparison.Invalid as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except comparison.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except comparison.Conflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/cases/{case_id}/spread", response_model=Spread)
def case_spread(
    case_id: str, user: dict = Depends(require("output.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-22: the spread (interim layout) with ratios and the working-capital assessment."""
    case = _assessed_case(conn, case_id, user)
    try:
        return spread.build(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/cases/{case_id}/pd-note", response_model=PdNote)
def case_pd_note(
    case_id: str, user: dict = Depends(require("output.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-24: questions for the personal discussion, ranked, each tied to its source."""
    case = _assessed_case(conn, case_id, user)
    try:
        return pd_note.build(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/cases/{case_id}/cam", response_model=Cam)
def case_cam(
    case_id: str, user: dict = Depends(require("output.read")), conn: sqlite3.Connection = Depends(get_conn)
):
    """F-23: the draft CAM, every figure cited, ending in the structured summary."""
    case = _assessed_case(conn, case_id, user)
    try:
        return cam.build(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


# --- The draft CAM's review (F-23): a section in a person's words, a copilot redraft, a figure
# overridden, data asked for. Each answers the memo as it now reads.


def _review_cam(conn: sqlite3.Connection, case_id: str, user: dict) -> Cam:
    case = _assessed_case(conn, case_id, user)
    try:
        return cam.build(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


def _reviewed(conn: sqlite3.Connection, case_id: str, user: dict, change) -> Cam:
    memo = _review_cam(conn, case_id, user)
    try:
        change(memo)
    except cam_review.ReviewError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return _review_cam(conn, case_id, user)


@app.put("/api/cases/{case_id}/cam/sections/{section_id}/words", response_model=Cam)
def cam_words(case_id: str, section_id: str, body: CamWordsRequest, user: dict = Depends(require("review.decide")),
              conn: sqlite3.Connection = Depends(get_conn)):
    """A section in a person's words, or a copilot redraft a person keeps."""
    state = "regenerated" if body.source == "copilot" else "edited"
    return _reviewed(conn, case_id, user, lambda memo: cam_review.save_words(
        conn, memo, section_id, body.paragraphs, user, state=state, model=body.model if state == "regenerated" else None))


@app.delete("/api/cases/{case_id}/cam/sections/{section_id}/words", response_model=Cam)
def cam_restore(case_id: str, section_id: str, user: dict = Depends(require("review.decide")),
                conn: sqlite3.Connection = Depends(get_conn)):
    """Back to the engine's draft of the section."""
    return _reviewed(conn, case_id, user, lambda memo: cam_review.restore(conn, memo, section_id, user))


@app.post("/api/cases/{case_id}/cam/sections/{section_id}/regenerate", response_model=CamRegenerateResult)
def cam_regenerate(case_id: str, section_id: str, body: CamRegenerateRequest,
                   user: dict = Depends(require("review.decide")), conn: sqlite3.Connection = Depends(get_conn)):
    """The copilot's redraft of a section, for a person to keep or discard; nothing is kept yet."""
    memo = _review_cam(conn, case_id, user)
    cfg = configstore_reader.load_cam(data_root()).copilot
    try:
        paragraphs, recorded = cam_copilot.regenerate(conn, memo, section_id, body.instruction, cfg)
    except cam_review.ReviewError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return CamRegenerateResult(paragraphs=paragraphs, model=cfg.model, recorded=recorded)


@app.post("/api/cases/{case_id}/cam/sections/{section_id}/overrides", response_model=Cam)
def cam_override(case_id: str, section_id: str, body: CamOverrideRequest,
                 user: dict = Depends(require("review.decide")), conn: sqlite3.Connection = Depends(get_conn)):
    """A figure overridden, with the value drafted and the reason, kept with who and when."""
    return _reviewed(conn, case_id, user, lambda memo: cam_review.add_override(
        conn, memo, section_id, body.figure, body.original, body.value, body.reason, user))


@app.post("/api/cases/{case_id}/cam/sections/{section_id}/requests", response_model=Cam)
def cam_request(case_id: str, section_id: str, body: CamDataRequest,
                user: dict = Depends(require("review.decide")), conn: sqlite3.Connection = Depends(get_conn)):
    """More data asked for from a section; it goes on the query list."""
    def change(memo: Cam) -> None:
        cam_review.add_request(conn, memo, section_id, body.text, user)
        queries.refresh(conn, data_root(), case_id)
    return _reviewed(conn, case_id, user, change)


_DOWNLOAD = {200: {"description": "The file, as an attachment.",
                   "content": {media: {"schema": {"type": "string", "format": "binary"}}
                               for media in exports.MEDIA_TYPES.values()}}}
_OUTPUTS = {"cam": "draft CAM", "pd_note": "PD note"}
_FORMATS = {"docx": "Word", "pdf": "PDF"}
_log = logging.getLogger("creditiq.api")


def _download(conn: sqlite3.Connection, user: dict, case: CaseDetail, output: str, fmt: str,
              draft: Cam | PdNote) -> Response:
    """The file as an attachment; the decision log records the download. A file that cannot be written
    is a 500 with its reason in words, which reaches the screens as any error does."""
    try:
        document = exports.cam_document(draft) if output == "cam" else exports.pd_note_document(draft)
        content = exports.render(document, fmt)
    except Exception as e:  # any writer's fault: logged, and answered rather than left to the server
        _log.exception("%s %s file for %s failed", output, fmt, case.id)
        raise HTTPException(status_code=500, detail=f"The {_OUTPUTS[output]} could not be written as a "
                                                    f"{_FORMATS[fmt]} file ({type(e).__name__}).") from e
    db.log_decision(conn, at=now_iso(), actor=user["id"], case_id=case.id, action="output.downloaded",
                    detail=json.dumps({"output": output, "format": fmt}))
    return Response(content=content, media_type=exports.MEDIA_TYPES[fmt], headers={
        "Content-Disposition": f'attachment; filename="{exports.file_name(output, case.id, fmt)}"',
        # The screens call from another origin and name the saved file from this header.
        "Access-Control-Expose-Headers": "Content-Disposition",
        "Cache-Control": "no-store",
    })


@app.get("/api/cases/{case_id}/pd-note/download", response_class=Response, responses=_DOWNLOAD)
def case_pd_note_download(
    case_id: str,
    fmt: Literal["docx", "pdf"] = Query(alias="format"),
    user: dict = Depends(require("output.read")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """F-24.3: the PD question note as a Word or PDF file, the same content as the screen, with room
    under each question for the response and the follow-up."""
    case = _case_for(conn, case_id, user)
    try:
        note = pd_note.build(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return _download(conn, user, case, "pd_note", fmt, note)


@app.get("/api/cases/{case_id}/cam/download", response_class=Response, responses=_DOWNLOAD)
def case_cam_download(
    case_id: str,
    fmt: Literal["docx", "pdf"] = Query(alias="format"),
    user: dict = Depends(require("output.read")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """F-23.5: the draft CAM as a Word or PDF file, the same content as the screen, with numbered
    citations and the sources; the recommendation is left blank for credit."""
    case = _case_for(conn, case_id, user)
    try:
        draft = cam.build(conn, data_root(), case)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return _download(conn, user, case, "cam", fmt, draft)


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


@app.get("/api/config/versions", response_model=list[ConfigVersion])
def config_versions(_: dict = Depends(require("config.read"))):
    return _config(configstore_reader.publish_history)


@app.get("/api/users", response_model=list[DirectoryUser])
def user_directory(_: dict = Depends(require("config.read"))):
    roles = load_roles_config()
    return [
        {
            "id": u["id"],
            "name": u["name"],
            "role": u["role"],
            "roleLabel": role_label(u["role"]),
            "email": u["email"],
            "branch": u["branch"],
            "permissions": list(roles.get("permissions", {}).get(u["role"], [])),
        }
        for u in roles["users"]
    ]


@app.get("/api/audit", response_model=AuditPage)
def audit_trail(
    case_id: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    before: int | None = None,
    limit: int = 100,
    user: dict = Depends(require("audit.read")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """The append-only decision log, newest first, filtered and paged. RBL's reference record
    and the reviewer's decisions on it are for the reviewer only (F-25): anyone else sees that
    the import, confirmation or decision happened, never what it said."""
    limit = max(1, min(limit, 500))
    where, args = [], []
    for column, value in (("case_id", case_id), ("actor", actor), ("action", action)):
        if value:
            where.append(f"{column} = ?")
            args.append(value)
    if before is not None:
        where.append("seq < ?")
        args.append(before)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        f"SELECT seq, at, actor, case_id, action, detail FROM decision_log {clause} ORDER BY seq DESC LIMIT ?",
        (*args, limit + 1),
    ).fetchall()
    page = rows[:limit]

    def name(actor_id: str) -> str:
        user = find_user_by_id(actor_id)
        return user["name"] if user else actor_id

    reviewer = "comparison.adjudicate" in user["permissions"]

    def detail(raw: str, action: str) -> dict:
        if not reviewer and action.startswith(("reference.", "comparison.")):
            return {}
        try:
            value = json.loads(raw)
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    return {
        "entries": [
            {
                "seq": r["seq"],
                "at": r["at"],
                "actor": r["actor"],
                "actor_name": name(r["actor"]),
                "case_id": r["case_id"],
                "action": r["action"],
                "detail": detail(r["detail"], r["action"]),
            }
            for r in page
        ],
        "next_before": page[-1]["seq"] if len(rows) > limit and page else None,
        "actors": [r[0] for r in conn.execute("SELECT DISTINCT actor FROM decision_log ORDER BY actor")],
        "actions": [r[0] for r in conn.execute("SELECT DISTINCT action FROM decision_log ORDER BY action")],
    }


@app.get("/api/admin/settings", response_model=EditableSettings)
def admin_settings(_: dict = Depends(require("config.read"))):
    """The tolerances, norm thresholds, cross-check rules and approval matrix an Administrator
    edits (F-00.6), as the version now published has them."""
    return _config(admin_config.editable)


@app.post("/api/admin/settings/preview", response_model=SettingsPreview)
def admin_settings_preview(body: SettingsChanges, _: dict = Depends(require("config.publish"))):
    """What the changes would change and why they could not be published; nothing is published."""
    return _config(lambda root: admin_config.preview(root, body))


@app.post("/api/admin/settings/publish", response_model=SettingsPublished)
def admin_settings_publish(
    body: SettingsPublishRequest,
    user: dict = Depends(require("config.publish")),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Publish the changes as a new configuration version, with the Administrator's note, and
    re-run every case's checks (F-00.6). 422 with the problems when they cannot be published."""
    try:
        return admin_config.publish(conn, data_root(), user, body.note, body.changes)
    except admin_config.SettingsInvalid as e:
        raise HTTPException(status_code=422, detail={"problems": e.problems}) from e
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/config/policy", response_model=PolicySection)
def config_policy(_: dict = Depends(current_user)):
    return _config(configstore_reader.load_policy)


@app.get("/api/config/approval-matrix", response_model=ApprovalMatrixSection)
def config_approval_matrix(_: dict = Depends(require("config.read"))):
    return _config(configstore_reader.load_approval_matrix)


@app.get("/api/config/checklist-taxonomy", response_model=ChecklistTaxonomySection)
def config_checklist_taxonomy(_: dict = Depends(current_user)):
    return _config(configstore_reader.load_checklist_taxonomy)


@app.get("/api/config/document-types", response_model=DocumentTypesSection)
def config_document_types(_: dict = Depends(current_user)):
    return _config(configstore_reader.load_document_types)
