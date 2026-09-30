"""Policy norms and deviations (FRD F-20)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence


class NormInput(BaseModel):
    """One source figure a norm used, with where it came from (F-20.2)."""

    name: str
    label: str
    value: float | None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False


NormOutcome = Literal["pass", "deviation", "cannot_evaluate", "not_applicable"]


class NormResult(BaseModel):
    id: str
    family: Literal["eligibility", "ratios", "security_cover", "documentation"]
    label: str
    formula: str
    """The expression as configured, in words where the ratio gives them."""
    required: str
    """e.g. "at least 1.20x"."""
    actual: float | None = None
    unit: str | None = None
    outcome: NormOutcome
    category: str
    category_label: str
    inputs: list[NormInput] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    """For cannot evaluate: the inputs not on file (F-20.3)."""
    note: str | None = None
    provisional: bool = False


class PolicyAssessment(BaseModel):
    case_id: str
    period: str | None
    """The financial year the financial inputs come from."""
    norms: list[NormResult]
