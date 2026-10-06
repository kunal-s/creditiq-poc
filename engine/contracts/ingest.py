"""The document-processing service contract, version 2 (FRD AD-2a, AD-4; F-07 to F-09, F-11, F-15).

The engine sends `POST {ingest_url}/v1/ingest` as multipart/form-data:
- a part `request` holding IngestRequest as JSON;
- one part per file, named by its `file_id`.

The service answers with IngestResult. These models mirror services/ingestion/ingestion/contracts.py
and forbid unknown keys, so a field added on one side fails the contract test on the other
(tests/test_ingest_contract.py validates the real service output for every fixture document).
Timings are not part of the result, so a replay is byte-identical (principle 6).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _C(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestFile(_C):
    file_id: str
    sha256: str
    original_name: str
    content_type: str = "application/octet-stream"
    label_hint: str | None = None
    """Never used to classify (F-09.1)."""
    assigned_type: str | None = None
    """A person's type assignment (F-09.5): classification is skipped and the file is read as this type."""


class IngestRequest(_C):
    case_ref: str
    config_version: str
    """The published CreditIQ configuration version; the service refuses an unknown one (409) and echoes
    the one it used (F-00.3)."""
    files: list[IngestFile]


class IngestSource(_C):
    kind: Literal["page", "cell"]
    page: int | None = None
    text: str | None = None
    bbox: list[float] | None = None
    sheet: str | None = None
    range: str | None = None


class IngestField(_C):
    status: Literal["found", "missing"]
    reason: str | None = None
    value: Any = None
    raw_text: str | None = None
    method: Literal["identifier", "alias", "pattern", "model"] | None = None
    confidence: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    source: IngestSource | None = None
    required: bool = False
    key_field: bool = False
    needs_review: bool = False


class IngestTableRow(_C):
    cells: dict[str, Any]
    raw: dict[str, str]
    source: dict[str, Any]


class IngestTable(_C):
    status: Literal["found", "missing"]
    reason: str | None = None
    columns: list[str]
    rows: list[IngestTableRow] = Field(default_factory=list)
    source: dict[str, Any] | None = None
    repairs: list[dict[str, Any]] = Field(default_factory=list)
    unparsed: int = 0
    confidence: float = 0.0


class IngestCheck(_C):
    id: str
    label: str
    outcome: Literal["pass", "warn", "fail"]
    detail: str
    severity: Literal["warn", "fail"]
    fields: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    kind: str = "rule"


class IngestCandidate(_C):
    type: str
    score: float


class IngestClassification(_C):
    type: str | None
    confidence: float
    tier: Literal["signals", "model", "person", "none"]
    signals: dict[str, Any] = Field(default_factory=dict)
    candidates: list[IngestCandidate] = Field(default_factory=list)
    needs_review: bool
    reason: str | None = None
    mixed_content: list[dict[str, Any]] = Field(default_factory=list)
    model_error: str | None = None


class IngestConfidence(_C):
    document: float
    decision: Literal["auto_accept", "human_review", "reject"]
    reasons: list[dict[str, Any]] = Field(default_factory=list)
    composition: dict[str, Any] = Field(default_factory=dict)


class IngestTrace(_C):
    stage: str
    input_hash: str
    output_hash: str


class IngestPage(_C):
    page: int
    source: Literal["text_layer", "ocr", "sheet"]
    width: float = 0.0
    height: float = 0.0
    """Page size in points; boxes are in points, origin top left. Zero for a spreadsheet."""
    grade: Literal["A", "B", "C", "U"]
    reasons: list[str] = Field(default_factory=list)
    reading_trust: float
    ocr_conf: float | None = None
    sheet: str | None = None
    blank: bool = False
    words: int = 0


class DocumentDefect(_C):
    """A defect of the document, not of the extraction (F-13.3)."""

    code: Literal["pages_absent", "period_gap", "unsigned", "unstamped", "plain_paper", "pagination_break"]
    detail: str
    pages: list[int] = Field(default_factory=list)


class IngestDocument(_C):
    instance_no: int
    instance_key: str | None = None
    page_from: int
    page_to: int
    document_type: str
    fields: dict[str, IngestField]
    tables: dict[str, IngestTable]
    validation: list[IngestCheck]
    confidence: IngestConfidence
    identity: dict[str, str] = Field(default_factory=dict)
    """name, pan, din, dob, gstin, cin as read, for party attribution (F-10)."""
    defects: list[DocumentDefect] = Field(default_factory=list)


class IngestReject(_C):
    code: str
    message: str
    rescan_request: str | None = None


class IngestFileResult(_C):
    file_id: str
    sha256: str
    name: str
    status: Literal["processed", "rejected", "failed"]
    reject: IngestReject | None = None
    error: dict[str, str] | None = None
    run_id: str | None = None
    source: dict[str, Any] = Field(default_factory=dict)
    grade: str | None = None
    route: dict[str, Any] = Field(default_factory=dict)
    pages: list[IngestPage] = Field(default_factory=list)
    front_matter_pages: list[int] = Field(default_factory=list)
    classification: IngestClassification | None = None
    documents: list[IngestDocument] = Field(default_factory=list)
    decision: Literal["auto_accept", "human_review", "reject"] | None = None
    review_reasons: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[IngestTrace] = Field(default_factory=list)


class IngestConfigRef(_C):
    version: str
    hash: str


class IngestEngineRef(_C):
    version: str
    ocr: str
    model: str


class IngestResult(_C):
    contract_version: str
    case_ref: str
    config: IngestConfigRef
    engine: IngestEngineRef
    files: list[IngestFileResult]
