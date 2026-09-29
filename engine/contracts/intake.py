"""Wave 1 intake contract: case proposals, uploads and parties
(docs/functional-requirements.md F-04, F-05, F-10)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .case import CaseSummary
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


class ProposalRequest(BaseModel):
    channel: str
    text: str = Field(min_length=1)


class StrippedSpan(BaseModel):
    """Part of the message set aside before extraction but kept as
    provenance (F-04, normalisation): nothing is proposed from it."""

    kind: Literal["timestamp", "sender", "header", "quoted", "signature"]
    span: Span


class CaseProposal(BaseModel):
    """What the pasted message proposes (F-04). Nothing is stored until the
    RM confirms and posts a CaseCreate (F-04.7)."""

    text_sha256: str
    fields: dict[str, ProposedField]
    """borrower, constitution, facilities, amount_inr, pan, gstin, cin,
    udyam, promoters, declared_turnover_inr, existing_banking, contact.
    Multi-valued fields (facilities, promoters) list every value with its
    span in `candidates`; `value` joins them (facility ids with ",",
    names with "; ")."""
    stripped: list[StrippedSpan] = Field(default_factory=list)
    """Timestamps, senders, email headers, quoted replies and signatures."""
    duplicates: list[CaseSummary] = Field(default_factory=list)
    """Existing cases matching on PAN, GSTIN or normalised name (F-04.5)."""
    missing_minimum: list[str] = Field(default_factory=list)
    """Fields from case_create_minimum still to be supplied (F-04.6)."""


class UploadResult(BaseModel):
    """F-05.5: every file ends in a visible state; archives list their members."""

    files: list[FileRecord]
    job_id: str | None = None
    """The processing job for the registered files, if any were registered."""


class Party(BaseModel):
    """A person or entity on the case: director, partner, proprietor,
    guarantor or the borrower itself (F-10.2)."""

    id: str
    case_id: str
    name: str
    role: Literal["borrower", "director", "partner", "proprietor", "guarantor", "promoter"]
    pan: str | None = None
    din: str | None = None
    source: str
    """Where the party came from: "document:<id>:p<n>", "message", or "person"."""
    kyc_document_ids: list[str] = Field(default_factory=list)
