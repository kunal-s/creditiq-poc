"""Result contract v2 (FRD AD-4). Built around the supplied `output_contract`: every field has a
value, a confidence and a source {page, text, bbox}; every table has columns, rows and a source.
Additions required by the FRD: status and reason (F-15.1), raw_text, method and the confidence
components (F-17.1). Timings are not part of the contract, so a replay is byte-identical."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class C(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(C):
    kind: Literal["page", "cell"]
    page: int | None = None
    text: str | None = None
    bbox: list[float] | None = None
    sheet: str | None = None
    range: str | None = None


class FieldResult(C):
    status: Literal["found", "missing"]
    reason: str | None = None
    value: Any = None
    raw_text: str | None = None
    method: Literal["identifier", "alias", "pattern", "model"] | None = None
    confidence: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    source: Source | None = None
    required: bool = False
    key_field: bool = False
    needs_review: bool = False
    """A key field below the review threshold (F-17.2): it goes to the review queue before use."""


class TableRow(C):
    cells: dict[str, Any]
    raw: dict[str, str]
    source: dict[str, Any]


class TableResult(C):
    status: Literal["found", "missing"]
    reason: str | None = None
    columns: list[str]
    rows: list[TableRow] = Field(default_factory=list)
    source: dict[str, Any] | None = None
    repairs: list[dict[str, Any]] = Field(default_factory=list)
    unparsed: int = 0
    confidence: float = 0.0


class Check(C):
    id: str
    label: str
    outcome: Literal["pass", "warn", "fail"]
    detail: str
    severity: Literal["warn", "fail"]
    fields: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    kind: str = "rule"


class Candidate(C):
    type: str
    score: float


class Classification(C):
    type: str | None
    confidence: float
    tier: Literal["signals", "model", "person", "none"]
    signals: dict[str, Any] = Field(default_factory=dict)
    candidates: list[Candidate] = Field(default_factory=list)
    needs_review: bool
    reason: str | None = None
    mixed_content: list[dict[str, Any]] = Field(default_factory=list)
    model_error: str | None = None


class Confidence(C):
    document: float
    decision: Literal["auto_accept", "human_review", "reject"]
    reasons: list[dict[str, Any]] = Field(default_factory=list)
    composition: dict[str, Any] = Field(default_factory=dict)


class TraceEntry(C):
    stage: str
    input_hash: str
    output_hash: str


class PageInfo(C):
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


class Defect(C):
    """A defect of the document, not of the extraction (F-13.3)."""

    code: Literal["pages_absent", "period_gap", "unsigned", "unstamped", "plain_paper", "pagination_break"]
    detail: str
    pages: list[int] = Field(default_factory=list)


class Document(C):
    instance_no: int
    instance_key: str | None = None
    page_from: int
    page_to: int
    document_type: str
    fields: dict[str, FieldResult]
    tables: dict[str, TableResult]
    validation: list[Check]
    confidence: Confidence
    identity: dict[str, str] = Field(default_factory=dict)
    """name, pan, din, dob, gstin, cin as read, for party attribution (F-10)."""
    defects: list[Defect] = Field(default_factory=list)


class Reject(C):
    code: str
    message: str
    rescan_request: str | None = None


class FileResult(C):
    file_id: str
    sha256: str
    name: str
    status: Literal["processed", "rejected", "failed"]
    reject: Reject | None = None
    error: dict[str, str] | None = None
    run_id: str | None = None
    source: dict[str, Any] = Field(default_factory=dict)
    grade: str | None = None
    route: dict[str, Any] = Field(default_factory=dict)
    pages: list[PageInfo] = Field(default_factory=list)
    front_matter_pages: list[int] = Field(default_factory=list)
    classification: Classification | None = None
    documents: list[Document] = Field(default_factory=list)
    decision: Literal["auto_accept", "human_review", "reject"] | None = None
    review_reasons: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[TraceEntry] = Field(default_factory=list)


class ConfigRef(C):
    version: str
    hash: str


class EngineRef(C):
    version: str
    ocr: str
    model: str


class IngestResult(C):
    contract_version: str
    case_ref: str
    config: ConfigRef
    engine: EngineRef
    files: list[FileResult]


class FileSpec(C):
    file_id: str
    sha256: str
    original_name: str
    content_type: str = "application/octet-stream"
    label_hint: str | None = None
    """Never used to classify (F-09.1)."""
    assigned_type: str | None = None
    """A person's type assignment (F-09.5): classification is skipped, the file is read as this type."""


class IngestRequest(C):
    case_ref: str
    config_version: str
    files: list[FileSpec]
