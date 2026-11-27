"""Wave 1 intake contract: case proposals, uploads and parties
(docs/functional-requirements.md F-04, F-05, F-10)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .case import CaseDetail, CaseSummary, GroupRow
from .documents import FileRecord

ProposedStatus = Literal["found", "unclear", "not_found", "invalid"]


class Span(BaseModel):
    """Character offsets into the pasted message: [start, end)."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)


class ProposedCandidate(BaseModel):
    value: str
    span: Span


class ProposedField(BaseModel):
    """F-04.3: a value is proposed only with its span in the message."""

    value: str | None
    status: ProposedStatus
    span: Span | None = None
    candidates: list[ProposedCandidate] = Field(default_factory=list)
    note: str | None = None
    """Why a field is unclear or invalid, in plain language."""
    source: str | None = None
    """Where the value came from when it is not the message: "identifier" for a value typed in an
    identifier box on the start screen, "person" for one typed on the form. None for the message
    (its `span` says where)."""


class ProposalRequest(BaseModel):
    """What the start screen has so far. Every part is optional: with no text nothing is read, and
    the answer is only the duplicate check and what the product's minimum still lacks."""

    channel: str
    text: str | None = Field(default=None, min_length=1)
    """The pasted message, when there is one."""
    product: str | None = None
    """A product id; None takes the configured default."""
    fields: dict[str, Annotated[str | None, Field(max_length=500)]] = Field(default_factory=dict, max_length=100)
    """Values typed so far, by field id (borrower, pan, gstin, cin, udyam, application_id,
    customer_type, amount_inr, tenure_months, facilities as ids joined by ","). A typed value wins
    over what the message says."""
    groups: dict[str, Annotated[list[GroupRow], Field(max_length=50)]] = Field(default_factory=dict, max_length=20)
    """Rows typed so far (applicants, properties, ...), as in CaseCreate."""


class StrippedSpan(BaseModel):
    """Part of the message set aside before extraction but kept as
    provenance (F-04, normalisation): nothing is proposed from it."""

    kind: Literal["timestamp", "sender", "header", "quoted", "signature"]
    span: Span


class CaseElsewhere(BaseModel):
    """A matching case another RM holds, named without its details: the user may not read it (F-03)."""

    id: str
    rm: str


class CaseProposal(BaseModel):
    """What the pasted message proposes (F-04). Nothing is stored until the
    RM confirms and posts a CaseCreate (F-04.7)."""

    text_sha256: str | None = None
    """None when no message was given."""
    fields: dict[str, ProposedField]
    """borrower, constitution, facilities, amount_inr, pan, gstin, cin,
    udyam, promoters, declared_turnover_inr, existing_banking, contact.
    Multi-valued fields (facilities, promoters) list every value with its
    span in `candidates`; `value` joins them (facility ids with ",",
    names with "; ")."""
    stripped: list[StrippedSpan] = Field(default_factory=list)
    """Timestamps, senders, email headers, quoted replies and signatures."""
    duplicates: list[CaseSummary] = Field(default_factory=list)
    """Existing cases matching on PAN (the case's and every applicant's), GSTIN, application ID or
    normalised name (F-04.5) that the user may read."""
    duplicates_elsewhere: list[CaseElsewhere] = Field(default_factory=list)
    """Matching cases of other RMs, which this user may not read: their number and RM only."""
    missing_minimum: list[str] = Field(default_factory=list)
    """Fields of the product's minimum still to be supplied (F-04.6)."""


class UploadResult(BaseModel):
    """F-05.5: every file ends in a visible state; archives list their members."""

    files: list[FileRecord]
    job_id: str | None = None
    """The processing job for the registered files, if any were registered."""


class IntakeCreated(BaseModel):
    """POST /api/cases/intake: the case and its files, created together."""

    case: CaseDetail
    upload: UploadResult
    """Every file of the request in its visible state (F-05.5), and the processing job."""


IntakeRefusalCode = Literal[
    "bad_body", "case_part", "case_invalid", "minimum_missing", "identifier_invalid", "too_few_files",
]


class DuplicateConflict(BaseModel):
    """409 from a create: a matching case exists (F-04.5). Send `duplicate_override_reason` to create
    anyway; the reason covers the matches listed here."""

    message: str
    duplicates: list[CaseSummary]
    """The matching cases this user may read."""
    duplicates_elsewhere: list[CaseElsewhere] = Field(default_factory=list)
    """Matching cases of other RMs: their number and RM only."""


class DuplicateConflictResponse(BaseModel):
    """The body of a 409 from a create."""

    detail: DuplicateConflict


class IntakeRefusal(BaseModel):
    """Why POST /api/cases/intake created nothing (422): `code` says which rule, `message` says it in
    words. No case and no file is left behind."""

    code: IntakeRefusalCode
    message: str
    missing: list[str] = Field(default_factory=list)
    """minimum_missing: the fields of the product's minimum still to be supplied."""
    min_files: int | None = None
    """too_few_files: the documents the product needs before a case is created."""
    registered: int | None = None
    """too_few_files: the files received as new documents (junk, refused and repeated files do not count)."""


class IntakeRefusalResponse(BaseModel):
    """The body of a 422 from POST /api/cases/intake."""

    detail: IntakeRefusal


class Party(BaseModel):
    """A person or entity on the case: director, partner, proprietor,
    guarantor or the borrower itself (F-10.2)."""

    id: str
    case_id: str
    name: str
    role: Literal[
        "borrower", "director", "partner", "proprietor", "guarantor", "promoter", "applicant", "co_applicant"
    ]
    pan: str | None = None
    din: str | None = None
    source: str
    """Where the party came from: "document:<id>:p<n>", "message", "intake" (the form), or "person"."""
    kyc_document_ids: list[str] = Field(default_factory=list)


class ChecklistPreviewRequest(BaseModel):
    """The proposed application as it stands on the New appraisal screen, before
    any case exists: what the checklist would ask for (F-12, shown at intake)."""

    constitution: str = "unknown"
    facilities: list[str] = Field(default_factory=list)
    amount_inr: int = 0
    collateral_present: bool = False
    product: str | None = None
    case_type: str | None = None
    customer_type: str | None = None
    """A loan against property's customer type (salaried, self-employed, ...); until it is given the
    preview is provisional."""
    fields: dict[str, Annotated[str | None, Field(max_length=500)]] = Field(default_factory=dict, max_length=100)
    """Single values typed on the form so far, by field id, as in ProposalRequest (gstin,
    declared_rental_income_inr, ...): an item that applies only when a value is declared reads them.
    A value no item reads changes nothing."""
    groups: dict[str, Annotated[list[GroupRow], Field(max_length=50)]] = Field(default_factory=dict, max_length=20)
    """Rows typed so far, by section id, as in CaseCreate: an item that applies only when a section has
    rows (existing_loans) reads them."""


class ChecklistPreviewItem(BaseModel):
    id: str
    name: str
    category: str
    why: str
    blocking: bool
    request: str | None = None
    document_types: list[str] = Field(default_factory=list)
    """Names of the document types that can satisfy the item."""


class ChecklistPreview(BaseModel):
    provisional: bool
    """The constitution (or, for a loan against property, the customer type) is not confirmed yet:
    only the items every one needs."""
    sections: list[str]
    items: list[ChecklistPreviewItem]
