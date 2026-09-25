"""API schemas. Mirrored by hand in src/api/types.ts (zod), kept in step
manually until Stage C generates the TS client from this service's OpenAPI
schema (plan.md section 3: "types generated from the service's OpenAPI")."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

Stage = Literal[
    "Identity",
    "Data",
    "Spread",
    "Cross-Verification",
    "Draft",
    "Submission",
    "Completed",
]


class Case(BaseModel):
    id: str
    borrower: str
    sector: str
    pan: str
    gstin: str
    proposal: str
    facilities: str
    exposure: str
    stage: Stage
    analyst: str
    rm: str
    started: str
    completed: Optional[str] = None
    rating: str
    ratingLabel: str
    discrepancies: int
    reviewDue: Optional[str] = None
    branch: str


class Role(BaseModel):
    id: str
    label: str


class DirectoryUser(BaseModel):
    id: str
    name: str
    role: str
    roleLabel: str
    email: str
    branch: str


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
