"""The document-processing sidecar contract (FRD AD-2, F-07 to F-09, F-11, F-15).

The engine sends `POST {ingest_url}/v1/process` as multipart/form-data:
- a part `request` holding IngestRequest as JSON;
- one part per file, named by its `file_id`.

The sidecar answers with IngestResult. The JSON schema of IngestResult is
exported to contracts/ingest-result.schema.json (`npm run gen:api`); the
sidecar validates its output against that file in its tests.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .documents import Classification, PageInfo


class IngestFile(BaseModel):
    file_id: str
    sha256: str
    original_name: str
    content_type: str
    label_hint: str | None = None
    """Never used to classify (F-09.1); echoed for the label check (F-10.1)."""


class IngestRequest(BaseModel):
    case_ref: str
    config_version: str
    """The published CreditIQ configuration version to use; the sidecar
    refuses an unknown version and echoes the one it used (F-00.3)."""
    files: list[IngestFile]


class ExtractedField(BaseModel):
    field: str
    """Dictionary field; table cells as "<table>[<row>].<column>"."""
    value: str | float | int | bool | None
    raw: str | None
    """The text as printed on the page."""
    page: int | None = Field(default=None, ge=1)
    """Absolute page in the source file. None only when the value is missing."""
    bbox: tuple[float, float, float, float] | None = None
    method: Literal["deterministic", "model"]
    confidence_components: dict[str, float] = Field(default_factory=dict)
    missing_reason: str | None = None


class DocumentDefect(BaseModel):
    """A defect of the document, not of the extraction (F-13.3)."""

    code: Literal["pages_absent", "period_gap", "unsigned", "unstamped", "plain_paper", "pagination_break"]
    detail: str
    pages: list[int] = Field(default_factory=list)


class IngestDocument(BaseModel):
    doc_key: str
    """Content-derived and stable across re-runs (order independence)."""
    file_id: str
    page_from: int
    page_to: int
    pages: list[PageInfo]
    classification: Classification
    instance_key: str | None = None
    fields: list[ExtractedField] = Field(default_factory=list)
    identity: dict[str, str] = Field(default_factory=dict)
    """Identity fields for party attribution (F-10): name, pan, din, dob, gstin, cin."""
    defects: list[DocumentDefect] = Field(default_factory=list)
    duplicate_of_key: str | None = None
    split_uncertain: bool = False


class IngestFileOutcome(BaseModel):
    file_id: str
    status: Literal["processed", "exception", "rejected"]
    reason: str | None = None


class StageTiming(BaseModel):
    stage: Literal["read", "grade", "split", "classify", "extract", "validate"]
    file_id: str
    ms: int


class IngestResult(BaseModel):
    case_ref: str
    config_version: str
    engine_version: str
    model_provider: str
    """"anthropic", "gemini" or "stub"; recorded per run (AD-5)."""
    files: list[IngestFileOutcome]
    documents: list[IngestDocument]
    timings: list[StageTiming] = Field(default_factory=list)
