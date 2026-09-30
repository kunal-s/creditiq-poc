"""Aligned facts, the input to the cross-checks (FRD F-18)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence


class FactValue(BaseModel):
    """One source's value for a fact, with where it came from (F-18.6)."""

    source: str
    """The document type it came from, or application_message."""
    label: str
    """How the source is named on screen, e.g. "GST registration certificate"."""
    value: str | float | None
    evidence: list[Evidence] = Field(default_factory=list)
    field_ids: list[str] = Field(default_factory=list)
    relies_on_manual: bool = False
    """The value was entered or corrected by a person (F-19.4)."""


class IdentityFacts(BaseModel):
    entity_pan: list[FactValue] = Field(default_factory=list)
    gstin: list[FactValue] = Field(default_factory=list)
    legal_name: list[FactValue] = Field(default_factory=list)


class PersonSet(BaseModel):
    """The promoters one source names (F-18.3: variants resolved later)."""

    source: str
    label: str
    names: list[str]
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False


TurnoverSource = Literal["financials", "gst", "bank", "declared"]


class TurnoverFigure(BaseModel):
    """One source's turnover for one financial year (F-18.1)."""

    source: TurnoverSource
    label: str
    value: float | None
    months_covered: int | None = None
    """For monthly sources: months of the year present. Annual figures: None."""
    months_missing: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    field_ids: list[str] = Field(default_factory=list)
    relies_on_manual: bool = False


class TurnoverYear(BaseModel):
    fy: str
    """e.g. "FY 2024-25"."""
    fy_end: str
    figures: list[TurnoverFigure]


class Exclusion(BaseModel):
    """A credit removed before counting business inflow (F-18.2)."""

    rule: str
    label: str
    account: str
    date: str | None
    narration: str
    amount: float
    evidence: list[Evidence] = Field(default_factory=list)


class AccountCredits(BaseModel):
    """One account's credits, before and after cleansing (F-18.2)."""

    account: str
    gross: float
    excluded: float
    net: float
    months: list[str]
    exclusions: list[Exclusion]


class Obligation(BaseModel):
    """A recurring debit that looks like a loan instalment (F-18.4)."""

    lender: str
    variants: list[str]
    account: str
    months: list[str]
    typical_amount: float
    debits: int
    evidence: list[Evidence] = Field(default_factory=list)


class AccountFact(BaseModel):
    """One bank account and where it is evidenced (F-18.5)."""

    bank: str
    last4: str | None
    label: str
    sources: list[str]
    declared: bool
    has_statement: bool
    evidence: list[Evidence] = Field(default_factory=list)


class FacilityFact(BaseModel):
    """An existing facility as one source records it (F-19 OB-01)."""

    source: str
    label: str
    lender: str
    facility: str | None = None
    amount: float | None = None
    emi: float | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False


class CaseFacts(BaseModel):
    case_id: str
    identities: IdentityFacts
    persons: list[PersonSet]
    turnover: list[TurnoverYear]
    credits: list[AccountCredits]
    obligations: list[Obligation]
    accounts: list[AccountFact]
    facilities: list[FacilityFact]
    declaration_received: bool
    """A declaration of existing banking and facilities is on file."""
