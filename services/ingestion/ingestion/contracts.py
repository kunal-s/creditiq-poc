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
    tier: Literal["signals", "model", "person", "sibling", "none"]
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
    origin: Literal["classified", "sibling"] = "classified"
    """classified: the file's own type. sibling: another document of the same category found inside the
    file by the second pass (F-08.1), read on its own pages."""
    pages: list[int] = Field(default_factory=list)
    """The pages this document was read from. A document found by the second pass need not be contiguous."""
    classification: Classification | None = None
    """How a document found by the second pass was recognised; absent for the file's own type."""


class IntegrityEvidence(C):
    """Where a finding is, and what it was measured against."""

    page: int
    """1-based page of the file."""
    rect: tuple[float, float, float, float] | None = None
    """left, top, right, bottom as fractions of the rendered page."""
    observed: str
    threshold: str
    locate: str | None = None
    """Text printed on the page that this evidence points at. The pipeline places
    it (page and rect) once the pages have been read; until then, or when it is
    not found, the evidence is about the file and has no place on a page."""
    object: int | None = None
    """An object of the file this evidence points at. Placed on the page that
    draws it once the pages have been read: an image where it is drawn, a page
    or its content as the whole page."""


class IntegrityFinding(C):
    """One integrity check's result (F-07A).

    An indicator for a person to look at, never a verdict. Every finding says
    what was measured, what it was compared with, and the limit it crossed.
    """

    code: str
    family: Literal["metadata", "font", "layout", "visual", "history", "identifier", "arithmetic", "signature"]
    status: Literal["pass", "warning", "review_required", "not_applicable", "unable_to_determine"]
    finding: str
    """One sentence, in plain words."""
    evidence: list[IntegrityEvidence] = Field(default_factory=list)
    tier: Literal["T0", "T1", "T2", "T3"]
    """T0 arithmetic · T1 the file contradicts itself · T2 image · T3 provenance."""
    impact: Literal["low", "medium", "high"]
    context: bool = False
    """Listed for a reader, never counted as a signal."""
    method: dict[str, str] = Field(default_factory=dict)
    skipped_for_type: str | None = None
    reads: list[str] = Field(default_factory=list)
    """The file facts this check read (keys of IntegrityFacts, e.g. "info.Producer",
    "revisions"), so a reader can see where in the file its answer came from."""


class IntegrityFigure(C):
    """A figure a page prints, where and how: so a reader can see every figure
    the page checks read, and how each is set beside its column."""

    page: int
    rect: tuple[float, float, float, float]
    """left, top, right, bottom as fractions of the rendered page."""
    text: str
    font: str
    size: float
    """Points, as a reader sees it."""
    right: float = 0.0
    """Its right edge in points, which places it in a column."""
    column: int | None = None
    """Which column of amounts on its page it is set in; None for a value that is not an amount."""


class IntegrityObject(C):
    """An object a later save wrote: its number and what it is."""

    number: int
    kind: str
    """page, image, form, font, annotation, signature, info, metadata, stream, …"""


class IntegrityRevision(C):
    """One saved state of the file, as byte offsets."""

    index: int
    start: int
    end: int
    length: int
    replaced: list[IntegrityObject] = Field(default_factory=list)
    """Objects this save defined again (later saves only)."""
    added: list[IntegrityObject] = Field(default_factory=list)
    """Objects this save defined for the first time (later saves only)."""
    replaced_count: int = 0
    added_count: int = 0


class IntegrityRecovered(C):
    """A figure an earlier revision printed where the current one differs."""

    object_number: int
    was: str
    now: str


class IntegrityMadeAs(C):
    """How the file was made, from its pages: text of its own, pictures of pages,
    and how those pictures measure as made (F-07A)."""

    kind: Literal["digital", "mixed", "scanned", "design_tool", "computer_drawn", "screenshot"]
    text_pages: int = 0
    picture_pages: int = 0
    writer: str | None = None
    """The design or editing tool the file names as its writer, if any."""


class IntegrityFacts(C):
    """What the file says about itself, as read by the integrity stage (F-07A):
    the records every check's answer comes from, kept so a reader can see them."""

    size_bytes: int
    pdf_version: str | None = None
    header_offset: int = 0
    """Bytes before %PDF-: a portal wrapper when above zero."""
    pages: int | None = None
    page_sizes: list[tuple[float, float]] = Field(default_factory=list)
    """Each distinct page size in points, width by height."""
    info: dict[str, str] = Field(default_factory=dict)
    """The information dictionary as the file stores it."""
    info_dates: dict[str, str] = Field(default_factory=dict)
    """Its dates as ISO-8601, where they parse."""
    has_xmp: bool = False
    xmp: dict[str, str] = Field(default_factory=dict)
    id_original: str | None = None
    id_current: str | None = None
    revisions: list[IntegrityRevision] = Field(default_factory=list)
    signatures: int = 0
    superseded_objects: int = 0
    recovered: list[IntegrityRecovered] = Field(default_factory=list)
    fonts: list[str] = Field(default_factory=list)
    made_as: IntegrityMadeAs | None = None


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
    integrity: list[IntegrityFinding] = Field(default_factory=list)
    """F-07A: what the file says about its own history, before anything is extracted."""
    integrity_recommendation: str | None = None
    """no_notable_issue | needs_review | needs_review_priority | high_risk_indicators | could_not_be_assessed"""
    integrity_facts: IntegrityFacts | None = None
    """What the file says about itself: the records the integrity checks read."""
    integrity_figures: list[IntegrityFigure] = Field(default_factory=list)
    """Every figure the page checks read, with its place, font and size."""
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
