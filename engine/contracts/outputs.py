"""Outputs: the spread, the draft CAM and the PD note (FRD F-22 to F-24)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence


class SpreadCell(BaseModel):
    value: float | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False


class SpreadColumn(BaseModel):
    """One year of one kind of statement."""

    key: str
    fy: str
    period_end: str
    basis: Literal["audited", "provisional", "projected"]


class SpreadRow(BaseModel):
    key: str
    label: str
    section: Literal["profit_and_loss", "balance_sheet", "ratios"]
    kind: Literal["line", "derived", "ratio"]
    unit: Literal["inr", "x", "%", "days"]
    formula: str | None = None
    """For derived lines and ratios: the working, in words (F-22.3)."""
    cells: list[SpreadCell]
    """One per column, in column order."""


class Working(BaseModel):
    """One step of the working-capital assessment (F-22.2)."""

    label: str
    value: float | None
    unit: Literal["inr", "%"] = "inr"
    basis: str | None = None
    """How the step is computed, in words."""
    evidence: list[Evidence] = Field(default_factory=list)


class WorkingCapitalAssessment(BaseModel):
    method: Literal["turnover", "mpbf", "not_applicable"]
    reason: str
    """Why this method (the configured limit) or why none applies."""
    column: str | None = None
    """The spread column the figures come from."""
    steps: list[Working] = Field(default_factory=list)
    eligible: float | None = None
    requested: float
    missing: list[str] = Field(default_factory=list)


class Spread(BaseModel):
    case_id: str
    interim: bool = True
    """Laid out before RBL's template arrived (decision C.4-8)."""
    columns: list[SpreadColumn]
    rows: list[SpreadRow]
    working_capital: WorkingCapitalAssessment
