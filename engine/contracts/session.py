"""Sign-in, session and form metadata (FRD F-03, F-04)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SessionUser(BaseModel):
    id: str
    name: str
    role: str
    roleLabel: str
    email: str
    branch: str
    initials: str
    navGroups: list[str]
    permissions: list[str]


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: SessionUser


class Option(BaseModel):
    id: str
    label: str


class DisplayUnit(BaseModel):
    """The unit financial figures are written in, from the published configuration."""

    unit: Literal["rupee", "thousand", "lakh", "crore"]
    label: str
    """"Crore": named under a table's heading and in the Administration screen."""
    divisor: float
    decimals: int
    suffix: str
    """Written after a figure in a sentence: " cr"."""


class Meta(BaseModel):
    """Choice lists the screens need, from config/app.yaml."""

    channels: list[Option]
    constitutions: list[Option]
    facilities: list[Option]
    case_create_minimum: list[str]
