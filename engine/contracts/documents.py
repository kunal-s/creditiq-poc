"""Files, logical documents and extracted values (FRD F-02, F-05, F-07 to F-09, F-15)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence, Grade

FileStatus = Literal["registered", "duplicate", "ignored", "rejected", "exception"]

DocStatus = Literal[
    "received",
    "graded",
    "split",
    "classified",
    "unclassified",
    "extracted",
    "accepted",
    "in_review",
    "in_exception",
    "superseded",
    "duplicate",
]

ExitTier = Literal["signals", "layout", "model", "person", "none"]


class FileRecord(BaseModel):
    """Bytes as received (F-05). Every file ends in a visible state (F-05.5)."""

    id: str
    case_id: str
    sha256: str
    original_name: str
    archive_path: str | None = None
    content_type: str
    size_bytes: int
    channel: str
    uploaded_by: str
    uploaded_at: str
    status: FileStatus
    reason: str | None = None
    duplicate_of: str | None = None
    label_hint: str | None = None


class PageInfo(BaseModel):
    n: int = Field(ge=1)
    route: Literal["text", "ocr", "sheet"]
    grade: Grade
    reasons: list[str] = Field(default_factory=list)
    """Reason codes for grades C and U (F-07.4)."""
    ocr_confidence: float | None = None


class Candidate(BaseModel):
    type_id: str
    confidence: float


class Classification(BaseModel):
    """F-09.4: what was found, how it exited, and the runners-up."""

    types: list[str]
    """Empty means unclassified (goes to review, F-09.5). Several means the
    document satisfies several requirements (F-09.2)."""
    confidence: float
    exit_tier: ExitTier
    signals: list[str] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list, max_length=3)


class LogicalDocument(BaseModel):
    """One logical document: a file and a page range (F-08)."""

    id: str
    case_id: str
    file_id: str
    page_from: int
    page_to: int
    pages: list[PageInfo]
    grade: Grade
    classification: Classification | None
    status: DocStatus
    instance_key: str | None = None
    party_id: str | None = None
    version_of: str | None = None
    duplicate_of: str | None = None
    label_mismatch: bool = False
    config_version: str | None = None


FieldMethod = Literal["deterministic", "model", "manual", "person"]
FieldStatus = Literal["accepted", "in_review", "corrected", "missing", "rejected"]
Scalar = str | float | int | bool | None


class FieldValue(BaseModel):
    """One extracted value with its evidence and confidence (F-15, F-17)."""

    id: str
    case_id: str
    document_id: str
    field: str
    """Dictionary field name; table cells use "<table>[<row>].<column>"."""
    value: Scalar
    raw: str | None = None
    evidence: Evidence | None = None
    method: FieldMethod
    confidence: float | None = None
    confidence_components: dict[str, float] = Field(default_factory=dict)
    status: FieldStatus
    missing_reason: str | None = None
    corrected_value: Scalar = None
