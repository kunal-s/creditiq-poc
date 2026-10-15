"""Policy norms and deviations (FRD F-20)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence


class NormComponent(BaseModel):
    """One line a derived figure was summed from, with the sign it carried (F-20.2).

    `net worth = share capital + reserves and surplus` shows as two components, each with the
    figure read from the statement and the page it was read from."""

    label: str
    sign: int
    """+1 added, -1 subtracted."""
    value: float
    evidence: list[Evidence] = Field(default_factory=list)


class NormInput(BaseModel):
    """One source figure a norm used, with where it came from (F-20.2)."""

    name: str
    label: str
    value: float | None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False
    awaiting_review: bool = False
    """A figure it rests on is still waiting for a person's review (F-17.2)."""
    basis: Literal["document", "case", "checklist", "statements_coverage", "not_requested"] = "document"
    """Where a figure without a document page comes from: the case header, the checklist,
    statements that show no instalments, or no term loan requested."""
    refs: list[str] = Field(default_factory=list)
    """basis checklist: the open blocking checklist item ids."""
    components: list[NormComponent] = Field(default_factory=list)
    """For a figure derived by summing statement lines, the lines it came from. Empty for a
    figure the statement prints itself."""


NormOutcome = Literal["pass", "deviation", "cannot_evaluate", "not_applicable"]


class NormResult(BaseModel):
    id: str
    family: Literal["eligibility", "ratios", "security_cover", "documentation"]
    label: str
    formula: str
    """The expression as configured, in words where the ratio gives them."""
    required: str
    """e.g. "at least 1.20x"."""
    comparator: Literal["min", "max"] = "min"
    """Which way the threshold runs, so the screens can write the test as a comparison:
    min reads "actual >= threshold", max reads "actual <= threshold"."""
    threshold_text: str | None = None
    """The threshold on its own, formatted as the screens write a value ("1.20x")."""
    actual: float | None = None
    unit: str | None = None
    outcome: NormOutcome
    category: str
    category_label: str
    inputs: list[NormInput] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    """For cannot evaluate: the inputs not on file (F-20.3)."""
    reason: Literal["zero_denominator", "denominator_not_positive", "awaiting_review"] | None = None
    """Why a norm with every input on file has no ordinary result."""
    reason_inputs: list[str] = Field(default_factory=list)
    """The input labels the reason names."""
    actual_text: str | None = None
    """The actual value as the screens, the CAM and the PD note write it."""
    definition: str | None = None
    """The conventional definition of a ratio norm; `formula` is the expression evaluated."""
    source: str | None = None
    """The norm's provenance tag (provisional, rbl_supplied, ...)."""
    note: str | None = None
    provisional: bool = False


NormFamily = Literal["eligibility", "ratios", "security_cover", "documentation"]


class PolicyCounts(BaseModel):
    """Norms by outcome."""

    deviations: int = 0
    cannot_evaluate: int = 0
    passed: int = 0
    not_applicable: int = 0


class PolicyGroup(BaseModel):
    """One family of norms as the Policy page's overview shows it (F-20)."""

    family: NormFamily
    norms: int
    """Configured norms in the family (none for security cover until a valuation document is in scope)."""
    counts: PolicyCounts
    status: Literal["deviation", "cannot_evaluate", "clear", "no_norms"]
    """deviation: a norm deviates; cannot_evaluate: none deviates but one cannot be evaluated; clear:
    every norm passed or did not apply; no_norms: the family has no norm."""
    highlights: list[str] = Field(default_factory=list)
    """Up to three norm ids for the overview: deviations, then norms that cannot be evaluated, then passed ones."""


class PolicyAssessment(BaseModel):
    case_id: str
    period: str | None
    """The financial year the financial inputs come from."""
    norms: list[NormResult]
    config_version: str | None = None
    counts: PolicyCounts = Field(default_factory=PolicyCounts)
    groups: list[PolicyGroup] = Field(default_factory=list)
    """The families in the order the page shows them: eligibility, ratios, documentation, security cover."""
