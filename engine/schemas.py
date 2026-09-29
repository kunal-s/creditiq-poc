"""API schemas. Mirrored by hand in src/api/types.ts (zod) until the TS
client is generated from this service's OpenAPI schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Case stages (docs/functional-requirements.md §7).
Stage = Literal["Intake", "Readiness", "Appraisal", "Outputs", "Completed"]


class Case(BaseModel):
    """Workbench view of a case (FRD F-01.4)."""

    id: str
    borrower: str
    constitution: str
    product: str
    amount: str
    stage: Stage
    rm: str
    created: str
    openReviewItems: int


class SessionUser(BaseModel):
    id: str
    name: str
    role: str
    roleLabel: str
    email: str
    branch: str
    initials: str
    navGroups: list[str]


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: SessionUser
