"""Files, logical documents and extracted values (FRD F-02, F-05, F-07 to F-09, F-15)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence, Grade
from .ingest import IngestIntegrityFacts, IngestIntegrityFinding

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

ExitTier = Literal["signals", "layout", "model", "person", "sibling", "none"]
"""sibling: found inside a file another type was read as, on its own pages (F-08.1)."""


IntegrityState = Literal["passed", "review_recommended", "suspicious", "suspicious_high", "incomplete",
                         "failed", "not_checked", "not_applicable"]


class IntegrityStatus(BaseModel):
    """F-07A: what a file's integrity checks come to, said once (engine.integrity_status)."""

    state: IntegrityState
    suspicious: list[str] = Field(default_factory=list)
    """Checks that stand out and count: evidence from the file itself."""
    informational: list[str] = Field(default_factory=list)
    """Listed-only observations, such as the program that made the file."""
    pending: list[str] = Field(default_factory=list)
    """Checks that have not run on this file."""
    unconfigured: list[str] = Field(default_factory=list)
    """Of those, the ones the configuration the file ran under did not name: publishing the
    configuration comes before running them."""
    failed: list[str] = Field(default_factory=list)
    """Checks that could not run."""
    stopped: bool = False
    """Processing of the file stopped before it finished."""
    passed: int = 0
    not_applicable: int = 0
    score: int | None = None
    """Evidence strength, 0 to the configured cap (never 100): how strongly the file
    contradicts itself. Uncalibrated, and not the chance a document was altered.
    None when the published configuration sets no scoring."""
    band: Literal["none", "weak", "moderate", "strong"] | None = None
    score_parts: list[ScorePart] = Field(default_factory=list)


class ScorePart(BaseModel):
    """One suspicious indicator's share of the evidence strength."""

    code: str
    family: str
    points: float
    """Its impact times its tier, before it is combined."""
    adds: float
    """What it adds to the strength once combined with the others."""


IntegrityDecision = Literal["genuine", "altered", "unclear", "not_completed"]


class IntegrityReview(BaseModel):
    """F-07A: a person's conclusion on a file, after looking at its evidence. Never set by
    the checks; the latest recorded is shown, every one is kept."""

    decision: IntegrityDecision
    reason: str
    decided_by: str
    decided_at: str


class IntegrityReviewRequest(BaseModel):
    decision: IntegrityDecision
    reason: str = ""


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
    integrity: list[IngestIntegrityFinding] = Field(default_factory=list)
    """F-07A: what the file's own bytes said about its history, checked before
    anything was read from it. Empty until the file has been processed."""
    integrity_recommendation: str | None = None
    integrity_facts: IngestIntegrityFacts | None = None
    """What the file says about itself: the records its integrity checks read."""
    integrity_status: IntegrityStatus | None = None
    """What its integrity checks come to, against the published configuration."""
    integrity_review: IntegrityReview | None = None
    """A person's latest conclusion on the file, if any."""


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
    why_unclassified: Literal["model_unavailable", "no_model", "model_found_none", "model_blocked",
                              "signals_weak"] | None = None
    """Why no type was decided, so a reader is told rather than left to guess:
    the classifier's model gave no answer, none is set up, it found none of the
    listed types, it suggested one the document lacks the marks of, or the
    document's own words matched no type well enough. None once classified."""


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


class RejectionItem(BaseModel):
    """A file or document that did not pass intake, with the reason and the rule that raised it (read-only)."""

    kind: Literal["file", "document"]
    id: str
    document: str
    """The file name, with the page range for a document inside a file."""
    document_type: str | None = None
    status: str
    reason: str
    """What is wrong, in plain language."""
    request: str | None = None
    """What to ask for, when the reason code has a configured re-scan request."""
    rule: str | None = None
    """The reason code, or the review kind that raised it."""


class MessageRequest(BaseModel):
    """A customer message the case assistant asks the host to record for sending."""

    to: str
    subject: str
    body: str
    idempotency_key: str
    """The same key sent again returns the message already recorded; nothing is recorded twice."""


class OutboxMessage(BaseModel):
    """A customer message recorded for sending. Nothing leaves the bank until a delivery step is configured."""

    id: int
    case_id: str
    to: str
    subject: str
    status: Literal["recorded"]
    created_at: str
    created_by: str
