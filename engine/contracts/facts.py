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
    awaiting_review: bool = False
    """The value is below its confidence threshold and not yet reviewed (F-17.2)."""


class IdentityFacts(BaseModel):
    entity_pan: list[FactValue] = Field(default_factory=list)
    gstin: list[FactValue] = Field(default_factory=list)
    legal_name: list[FactValue] = Field(default_factory=list)
    cin: list[FactValue] = Field(default_factory=list)


class PersonEntry(BaseModel):
    """One person as one source names them, with the identifiers printed there."""

    name: str
    din: str | None = None
    pan: str | None = None
    role: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False
    awaiting_review: bool = False


class PersonSet(BaseModel):
    """The promoters one source names (F-18.3: variants resolved later)."""

    source: str
    label: str
    names: list[str]
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False
    entries: list[PersonEntry] = Field(default_factory=list)


class IncorporationFact(BaseModel):
    """The company's incorporation as the certificate of incorporation records it."""

    date_of_incorporation: FactValue | None = None
    company_type: FactValue | None = None


class AuthorityFact(BaseModel):
    """What one board resolution for borrowing authorises (BR-01 to BR-04)."""

    document_id: str
    label: str
    borrowing_limit: FactValue | None = None
    lender: FactValue | None = None
    resolution_date: FactValue | None = None
    signatories: list[PersonEntry] = Field(default_factory=list)


class TaxYear(BaseModel):
    """One income tax return, by the financial year it covers."""

    assessment_year: str
    fy: str
    fy_end: str
    lines: dict[str, FactValue] = Field(default_factory=dict)
    """Computation lines configured in statements.itr_lines."""
    evidence: list[Evidence] = Field(default_factory=list)


class FinancialYear(BaseModel):
    """One year's audited statements: their own year and the comparative column."""

    fy: str
    fy_end: str
    label: str
    current: dict[str, FactValue] = Field(default_factory=dict)
    previous: dict[str, FactValue] = Field(default_factory=dict)


class MonthFigure(BaseModel):
    """GST outward supplies and cleansed bank credits for one month (TO-05)."""

    month: str
    """"2025-09"."""
    label: str
    """"Sep 2025"."""
    gst: float | None = None
    bank: float | None = None
    gst_evidence: list[Evidence] = Field(default_factory=list)
    bank_evidence: list[Evidence] = Field(default_factory=list)
    awaiting_review: bool = False


class BalanceFact(BaseModel):
    """One account's balance on a financial-year end, from its statement (FS-02)."""

    account: str
    date: str
    balance: float
    evidence: list[Evidence] = Field(default_factory=list)


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
    awaiting_review: bool = False


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
    """An existing facility as one source records it (F-19 OB-01): the declaration of existing
    facilities, a sanction letter or the commercial bureau report."""

    source: str
    label: str
    lender: str
    facility: str | None = None
    amount: float | None = None
    """The sanctioned amount or limit."""
    emi: float | None = None
    outstanding: float | None = None
    overdue: float | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False
    awaiting_review: bool = False


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
    declared_banking: FactValue | None = None
    """The existing banking the RM declared in the sourcing message."""
    declaration: FactValue | None = None
    """The declaration of existing facilities, when one is on file: the lenders it declares, or "None declared"."""
    requested_amount: FactValue | None = None
    """The amount the case requests (BR-01)."""
    incorporation: IncorporationFact = Field(default_factory=IncorporationFact)
    authority: list[AuthorityFact] = Field(default_factory=list)
    tax_years: list[TaxYear] = Field(default_factory=list)
    financial_years: list[FinancialYear] = Field(default_factory=list)
    months: list[MonthFigure] = Field(default_factory=list)
    balances: list[BalanceFact] = Field(default_factory=list)
    types_on_file: list[str] = Field(default_factory=list)
    """The document types the case has a usable document of."""
