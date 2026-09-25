"""Minimal service behind the frontend seam (plan.md section 7, Stage A).

Only cases and auth exist here. The processing pipeline (intake through
assemble), the config-store writer and the rule engine are later stages —
this app must never import them (CLAUDE.md rule 4).
"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import auth, store
from .config import load_roles_config, role_label
from .configstore import reader as configstore_reader
from .configstore.schema import ChecklistTaxonomySection, DictionarySection, PolicySection
from .schemas import Case, DirectoryUser, LoginRequest, LoginResponse, Role, SessionUser

app = FastAPI(title="CreditIQ engine (RBL Bank instance)")

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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/roles", response_model=list[Role])
def list_roles() -> list[dict]:
    return load_roles_config()["roles"]


@app.get("/api/users", response_model=list[DirectoryUser])
def list_users() -> list[dict]:
    return [
        {**user, "roleLabel": role_label(user["role"])} for user in load_roles_config()["users"]
    ]


@app.get("/api/cases", response_model=list[Case])
def list_cases() -> list[dict]:
    return store.list_cases()


@app.get("/api/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> dict:
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"no case {case_id!r}")
    return case


@app.get("/api/config/version")
def config_version() -> dict:
    try:
        return configstore_reader.published_version(store.data_root())
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/config/policy", response_model=PolicySection)
def config_policy() -> PolicySection:
    try:
        return configstore_reader.load_policy(store.data_root())
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/config/checklist-taxonomy", response_model=ChecklistTaxonomySection)
def config_checklist_taxonomy() -> ChecklistTaxonomySection:
    try:
        return configstore_reader.load_checklist_taxonomy(store.data_root())
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/config/dictionaries/{case_id}", response_model=DictionarySection)
def config_dictionary(case_id: str) -> DictionarySection:
    try:
        return configstore_reader.load_dictionary(store.data_root(), case_id)
    except configstore_reader.NoPublishedConfig as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/api/auth/login", response_model=LoginResponse)
def login(body: LoginRequest) -> dict:
    result = auth.login(body.email, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return result


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return authorization.split(" ", 1)[1]


@app.get("/api/auth/session", response_model=SessionUser)
def session(authorization: str | None = Header(default=None)) -> dict:
    user = auth.session_user(_bearer_token(authorization))
    if user is None:
        raise HTTPException(status_code=401, detail="no active session")
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(authorization: str | None = Header(default=None)) -> None:
    auth.logout(_bearer_token(authorization))
