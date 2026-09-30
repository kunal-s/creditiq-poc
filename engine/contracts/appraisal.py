"""Checklist, queries, findings and review (FRD F-12 to F-14, F-17, F-19)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence

ChecklistStatus = Literal["satisfied", "insufficient", "missing", "in_review", "waived"]


class ChecklistItemState(BaseModel):
    item_id: str
    name: str
    section: str
    blocking: bool
    weight: int
    status: ChecklistStatus
    deficiency: str | None = None
    """Stated for insufficient and missing items (F-13.1)."""
    document_ids: list[str] = Field(default_factory=list)
    why: str
    basis: str


class Readiness(BaseModel):
    """F-13.4: weighted proportion satisfied, against the configured gate."""

    score_pct: float
    gate_pct: int
    gate_met: bool
    blocking_open: int
    provisional: bool
    """True while constitution or product is unconfirmed (F-12.3)."""
    items: list[ChecklistItemState]
    ready_for_credit: bool = False
    """F-13.5: every item satisfied or waived, on a confirmed checklist."""


class QueryItem(BaseModel):
    """One line of the pre-login query list (F-14)."""

    id: str
    case_id: str
    group: Literal["documents_needed", "documents_to_redo", "clarifications"]
    text: str
    source_kind: Literal["checklist", "quality", "label", "party", "finding"]
    source_ref: str
    evidence: list[Evidence] = Field(default_factory=list)
    resolved: bool = False


Outcome = Literal["pass", "fail", "incomplete", "not_applicable"]
Severity = Literal["serious", "moderate", "mild"]


class FindingSide(BaseModel):
    label: str
    value: str | float | None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False


class Finding(BaseModel):
    """A cross-check or policy outcome (F-19, F-20)."""

    id: str
    case_id: str
    rule_id: str
    title: str
    outcome: Outcome
    severity: Severity
    blocking: bool
    explanation: str
    sides: list[FindingSide]
    tolerance: str | None = None
    config_version: str | None = None
    run_id: str | None = None
    query: str | None = None
    """What to ask the customer about a failure (F-19.5), if the rule says."""


ReviewKind = Literal["type", "field", "quality", "party", "split", "manual_entry", "finding"]
ReviewDecision = Literal["confirm", "correct", "waive", "assign"]


class ReviewItem(BaseModel):
    """Something waiting for a person (F-17.4)."""

    id: str
    case_id: str
    kind: ReviewKind
    ref: str
    summary: str
    created_at: str
    status: Literal["open", "decided"]
    decision: ReviewDecision | None = None
    reason: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    maker: str | None = None
    """For manual entry: the maker, who may not be the checker (F-03.4)."""


class ReviewDecisionRequest(BaseModel):
    decision: ReviewDecision
    reason: str | None = None
    value: str | float | int | bool | None = None
    """The corrected value, the assigned type id, or (party items) the
    party id the document belongs to."""
    values: dict[str, str | float | int | bool | None] | None = None
    """Manual entry (F-07.5): the maker's values for an unreadable
    document, by dictionary field, posted as "correct" on its quality item.
    A different person with the checker permission confirms them."""
