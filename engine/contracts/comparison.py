"""RBL's reference record and the comparison against it (FRD F-25): the deviations and
approving-authority areas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .approval import ApprovingAuthority, AuthorityRef
from .policy import NormResult

ComparisonArea = Literal["deviations", "approving_authority"]
ComparisonStatus = Literal["agree", "differ", "new", "missed"]
Verdict = Literal["valid", "not_valid"]
NoteKind = Literal["value_differs", "category_differs", "pass", "cannot_evaluate", "not_applicable",
                   "no_norm", "lower", "higher", "not_in_matrix", "cannot_determine"]


class ReferenceDeviation(BaseModel):
    """One deviation as RBL's record states it."""

    row: int
    norm_id: str | None = None
    """The CreditIQ norm it corresponds to; None when no configured norm covers it."""
    description: str = Field(min_length=1)
    category: str | None = None
    recorded_value: str | None = None
    approved_by_text: str | None = None
    source_ref: str = Field(min_length=1)
    """Where in RBL's record (page, section)."""
    notes: str | None = None


class ReferenceApproval(BaseModel):
    """The approval as RBL's record states it: a role or committee, never a person."""

    authority_text: str = Field(min_length=2, max_length=120)
    authority_key: str | None = None
    """The matrix authority it corresponds to; None for "not_in_matrix"."""
    decision: Literal["approved", "declined", "referred"]
    decided_on: str | None = None
    source_ref: str = Field(min_length=1)
    notes: str | None = None


class ReferenceRecordImport(BaseModel):
    """The JSON form of the reference workbook."""

    case_id: str
    record_date: str | None = None
    deviations_recorded: bool
    deviations: list[ReferenceDeviation] = Field(default_factory=list)
    approval: ReferenceApproval | None = None


class ReferenceRecord(BaseModel):
    case_id: str
    workbook_name: str
    workbook_sha256: str
    record_date: str | None
    deviations_recorded: bool
    imported_by: str
    imported_at: str
    confirmed_by: str | None
    confirmed_by_name: str | None
    confirmed_at: str | None
    config_version: str | None
    deviations: list[ReferenceDeviation]
    approval: ReferenceApproval | None
    areas_not_compared: list[str]
    """F-25.1 areas the record may hold that are not compared yet."""


class ImportProblem(BaseModel):
    sheet: str
    row: int | None
    column: str | None
    message: str
    blocking: bool


class Adjudication(BaseModel):
    verdict: Verdict
    reason: str
    decided_by: str
    decided_by_name: str
    decided_at: str
    stale: bool = False
    """The item changed since the decision; it is not counted until decided again."""


class ComparisonItem(BaseModel):
    area: ComparisonArea
    key: str
    label: str
    status: ComparisonStatus
    creditiq_text: str | None
    record_text: str | None
    norm: NormResult | None = None
    """The CreditIQ side, with its inputs' evidence (F-25.3)."""
    record_deviation: ReferenceDeviation | None = None
    required: ApprovingAuthority | None = None
    record_approval: ReferenceApproval | None = None
    authority_on_record_deviations: AuthorityRef | None = None
    """The matrix applied to the record's own deviations: separates "the matrix was applied
    differently" from "different deviations were found"."""
    notes: list[NoteKind] = Field(default_factory=list)
    adjudicable: bool
    adjudication: Adjudication | None = None
    scored: bool


class ComparisonCounts(BaseModel):
    """agree, differ, new, missed and no_deviation_either_side count the deviations area;
    to_adjudicate counts every item in either area awaiting a current decision."""

    agree: int
    differ: int
    new: int
    missed: int
    to_adjudicate: int
    no_deviation_either_side: int


class AreaScore(BaseModel):
    """Inputs for the scorecard (F-26)."""

    area: ComparisonArea
    scored: bool
    found_in_record: int
    recorded_total: int
    valid: int
    flagged_total: int
    pending: int


class CaseComparison(BaseModel):
    case_id: str
    config_version: str | None
    record: ReferenceRecord | None
    provisional_norms: bool
    provisional_matrix: bool
    counts: ComparisonCounts
    items: list[ComparisonItem]
    scores: list[AreaScore]


class AdjudicationRequest(BaseModel):
    verdict: Verdict
    reason: str = Field(min_length=3)
