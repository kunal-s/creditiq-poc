"""Read-only administration and audit views (FRD §6)."""

from __future__ import annotations

from pydantic import BaseModel


class ConfigVersion(BaseModel):
    version: str
    author: str
    note: str
    published_at: str
    prior_version: str | None
    sections_changed: list[str]
    """Sections whose content differs from the prior version; every section for the first."""
    current: bool


class DirectoryUser(BaseModel):
    id: str
    name: str
    role: str
    roleLabel: str
    email: str
    branch: str
    permissions: list[str]


class AuditEntry(BaseModel):
    seq: int
    at: str
    actor: str
    actor_name: str
    case_id: str | None
    action: str
    detail: dict


class AuditPage(BaseModel):
    entries: list[AuditEntry]
    next_before: int | None
    """Pass as `before` to read the next, older page; null at the end."""
    actors: list[str]
    actions: list[str]
