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


CheckArea = Literal["identity", "authority", "turnover", "tax", "financials", "accounts", "obligations"]
Provenance = Literal["declared", "borrower_supplied", "independent"]
"""Where a document comes from (config/document_types.yaml): declared by the RM or the
borrower, supplied by the borrower, or obtained independently (bureau, partner reports)."""


class FindingSide(BaseModel):
    label: str
    value: str | float | None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False
    awaiting_review: bool = False
    """The value is still waiting for a person's review (F-17.2): the check
    is incomplete until it is confirmed or corrected."""
    differs: bool = False
    """This side disagrees with the rest (the minority value of a failed check)."""
    field_ids: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    """The document types the value comes from (the RM's sourcing message is application_message)."""


class EvidenceRow(BaseModel):
    """One extracted row behind a headline value, with the page it was read from."""

    cells: list[str | float | None]
    evidence: list[Evidence] = Field(default_factory=list)
    kind: Literal["row", "total", "excluded"] = "row"
    """`excluded`: a line removed to reach the headline (a loan disbursal, an own-account
    transfer, a reversal); `total`: the aggregate the headline is."""


class SourceColumn(BaseModel):
    """One source a finding compared, as a column of its card (F-19.3)."""

    key: str
    label: str
    sources: list[str] = Field(default_factory=list)
    """Document type ids behind the value."""
    provenance: list[Provenance] = Field(default_factory=list)
    value: str | float | None = None
    unit: Literal["inr", "text", "count", "date"] = "text"
    """How the value is written: rupees in Indian units, text as given, a count, a date."""
    coverage: str | None = None
    """What the value covers: a period, "12 of 12 returns filed", the accounts."""
    differs: bool = False
    relies_on_manual: bool = False
    awaiting_review: bool = False
    field_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    """Where the value can be traced; the first is the page "Trace to the source" opens."""
    row_columns: list[str] = Field(default_factory=list)
    """Headings of `rows`."""
    rows: list[EvidenceRow] = Field(default_factory=list)
    """The extracted rows behind the value, and the lines excluded to reach it."""


class GapLeg(BaseModel):
    """How far one source is from another: one leg of a comparison."""

    label: str
    """"Gap against bank credits", or the line compared."""
    amount: float | None = None
    """The difference in rupees."""
    pct: float | None = None
    """The difference as a percentage of `base`."""
    base: str | None = None
    """What the percentage is of, as written after "of": "audited", "declared"."""
    legs: str
    """The two sources compared, for "breached on ...": "audited against bank credits"."""
    breached: bool = False
    """Beyond the rule's tolerance."""


class FindingDetailRow(BaseModel):
    label: str
    cells: list[str | float | None]
    flagged: bool = False
    """The row is one of the reasons the check failed."""
    flagged_cells: list[int] = []
    """Which of the row's cells (by position) are the reason, where the row says more than one thing
    (a name's middle name missing, its first and last names the same)."""


class FindingDetail(BaseModel):
    """The line-by-line comparison behind a finding: months, people, years."""

    columns: list[str]
    """Headings of the cells; the row label has none."""
    rows: list[FindingDetailRow]


class XvFact(BaseModel):
    """One figure on an area's overview card: a short source label and its value."""

    label: str
    value: str | float | None = None
    unit: Literal["inr", "text", "count", "date"] = "text"
    differs: bool = False


class XvHighlight(BaseModel):
    """A key-figure line on an area's overview card, from one finding: what it compares, the
    figures side by side, and a short note ("25.0% apart · tolerance 10%", "declared, no statement")."""

    finding_id: str
    rule_id: str
    outcome: Outcome
    label: str
    facts: list[XvFact] = Field(default_factory=list)
    note: str | None = None


class Finding(BaseModel):
    """A cross-check or policy outcome (F-19, F-20)."""

    id: str
    case_id: str
    rule_id: str
    title: str
    area: CheckArea = "identity"
    scope: str | None = None
    """What one run of the rule covers: a financial year, a window of months."""
    outcome: Outcome
    severity: Severity
    blocking: bool
    explanation: str
    sides: list[FindingSide]
    detail: FindingDetail | None = None
    missing: list[str] = Field(default_factory=list)
    """Documents the check needs that are not on file (F-19.3, incomplete)."""
    tolerance: str | None = None
    config_version: str | None = None
    run_id: str | None = None
    query: str | None = None
    """What to ask the customer about a failure (F-19.5), if the rule says."""
    # The card (the cross-verification board): presentation of the outcome above, never an input to it.
    ref: str | None = None
    """XV-<case number>-<sequence>: given when the rule first fails on the case, kept across re-runs."""
    finding_title: str | None = None
    """The plain-English title of the finding (config: finding_title)."""
    compares: str | None = None
    """What the rule compares, in words (the rule's title)."""
    policy_ref: str | None = None
    columns: list[SourceColumn] = Field(default_factory=list)
    """Each source compared, side by side (2 to 4)."""
    gaps: list[GapLeg] = Field(default_factory=list)
    gap_tolerance: str | None = None
    """The configured tolerance the gaps are measured against, as written ("10%", "5%")."""
    mismatch: str | None = None
    """For a check without an amount: the difference in words."""
    reference: str | None = None
    """For an identifier check: the value most sources give; differing characters are marked against it."""
    amount: float | None = None
    """The size of the gap in rupees, for ranking; None when the check has no amount."""
    request: str | None = None
    """For an incomplete check: what would complete it (a document, months of returns)."""
    highlights: list[XvHighlight] = Field(default_factory=list)
    """Its key-figure lines for the area's overview card (none, one, or one per lender or account)."""


XvDecisionKind = Literal["accept", "dismiss", "escalate"]


class XvDecision(BaseModel):
    """A person's decision on a discrepancy, with the comment every decision needs."""

    decision: XvDecisionKind
    comment: str
    by: str
    by_name: str
    at: str


class XvItem(BaseModel):
    """One finding of the latest run, with its review state, as the board shows it."""

    finding: Finding
    rank: int | None = None
    """Discrepancies only: the rank within its area, 1 being the greatest credit impact."""
    review_item_id: str | None = None
    decision: XvDecision | None = None
    """The decision that closed it: accept (a valid finding) or dismiss (not valid)."""
    escalation: XvDecision | None = None
    """The latest escalation; the finding stays open until accepted or dismissed."""
    adjudicated: bool = False
    in_query_list: bool = False
    """Incomplete checks: whether its request has been added to the query list."""


class XvRun(BaseModel):
    id: str
    at: str
    rules: int
    sources: int
    """Distinct source document types the rules compared."""


class XvCounts(BaseModel):
    serious: int
    moderate: int
    mild: int
    """Discrepancies of each severity not yet adjudicated."""
    adjudicated: int
    total: int
    """Discrepancies accepted or dismissed, out of all discrepancies."""
    blocking_open: int


XvAreaStatus = Literal["open", "decided", "incomplete", "clear"]


class XvArea(BaseModel):
    """One area of the board (identity, turnover, bank accounts, existing obligations) as its
    overview card shows it, counted from the area's findings of the latest run."""

    area: CheckArea
    rules: int
    """Enabled rules in the area."""
    discrepancies: int
    open: int
    """Discrepancies not yet accepted or dismissed."""
    serious: int
    moderate: int
    mild: int
    """Open discrepancies of each severity."""
    blocking_open: int
    adjudicated: int
    incomplete: int
    passed: int
    not_applicable: int
    top_finding_id: str | None = None
    """The open discrepancy with the greatest credit impact; if every one is decided, the greatest of them."""
    highlights: list[XvHighlight] = Field(default_factory=list)
    """Up to three key-figure lines: from open discrepancies in rank order, then decided ones, then
    checks that could not run, then passed checks."""
    status: XvAreaStatus
    """open: a discrepancy is open; decided: every discrepancy is decided; incomplete: none, but a
    check could not run; clear: every check passed or did not apply."""


class CrossVerificationView(BaseModel):
    """The cross-verification board for one case (F-19): every finding of the latest run by area,
    discrepancies ranked by credit impact within each area, and whether submission is blocked."""

    case_id: str
    run: XvRun | None
    areas: list[XvArea] = Field(default_factory=list)
    """The board's areas in order, each with its overview counts."""
    items: list[XvItem]
    """By area, in the areas' order; within an area: discrepancies by credit impact, then the checks
    that could not run, the passed ones and those that did not apply, in configured order."""
    counts: XvCounts
    blocked: bool
    """A blocking discrepancy is not yet accepted or dismissed."""
    first_blocking: str | None = None
    """The open blocking discrepancy with the greatest credit impact: what the banner points to."""
    top_finding_id: str | None = None
    """The card expanded when the board opens: the first card on the board, the greatest discrepancy
    of the first area with an open one (else of the first area with any)."""


class XvDecisionRequest(BaseModel):
    decision: XvDecisionKind
    comment: str = Field(min_length=3)


class XvQueryRequest(BaseModel):
    ref: str
    """The finding's id (incomplete checks have no XV reference)."""


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
    escalated: bool = False
    """A finding escalated to the Credit Manager from the cross-verification board."""


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
