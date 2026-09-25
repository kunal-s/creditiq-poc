"""Case descriptor schema (plan.md / reference/05-sample-generator-design.md
section A), as pydantic models for consistency with the rest of engine/.

Identifiers are pinned literals here — the generator never invents them at
build time. `engine.identifiers` checks the ones with a real algorithm
(GSTIN); the rest are format-checked only, and existence is the human
verification step (plan.md C11) this module cannot perform.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .. import identifiers as ids

Constitution = Literal["private_limited", "proprietorship", "partnership"]
FacilityType = Literal["cash_credit", "term_loan"]


class Timeline(BaseModel):
    as_of: date
    application_received: date
    window_start: date
    window_end: date
    audited_fys: list[int]
    provisional_fy: int
    provisional_months: int
    provisional_signed_on: date


class Address(BaseModel):
    line1: str
    city: str
    state: str
    gst_state_code: str
    pin: str


class Entity(BaseModel):
    legal_name: str
    constitution: Constitution
    activity: str
    sector: str
    formed_on: date
    employees: int
    msme_class: Literal["micro", "small", "medium"]
    address: Address


class Identifiers(BaseModel):
    pan: str
    gstin: str
    cin: str | None = None
    udyam: str
    tan: str | None = None

    @field_validator("pan")
    @classmethod
    def _pan_format(cls, v: str) -> str:
        if not ids.validate_pan_format(v):
            raise ValueError(f"{v!r} is not a validly formatted PAN")
        return v

    @field_validator("gstin")
    @classmethod
    def _gstin_checksum(cls, v: str) -> str:
        if not ids.validate_gstin(v):
            raise ValueError(f"{v!r} fails the GSTIN checksum")
        return v

    @field_validator("udyam")
    @classmethod
    def _udyam_format(cls, v: str) -> str:
        if not ids.validate_udyam(v):
            raise ValueError(f"{v!r} is not a validly formatted Udyam number")
        return v

    @model_validator(mode="after")
    def _gstin_embeds_pan(self) -> "Identifiers":
        if self.gstin[2:12] != self.pan:
            raise ValueError(f"GSTIN {self.gstin!r} does not embed PAN {self.pan!r}")
        return self


class Person(BaseModel):
    id: str
    name: str
    role: str
    din: str | None = None
    pan: str
    share_pct: float | None = None


class Bank(BaseModel):
    id: str
    name: str
    fictional: bool = True
    ifsc_prefix: str


class Lender(BaseModel):
    id: str
    name: str
    kind: Literal["nbfc", "bank"]
    fictional: bool = True


class Account(BaseModel):
    id: str
    bank: str
    type: Literal["cash_credit", "current"]
    number: str
    limit: int | None = None
    declared: bool
    statement_provided: bool = True


class ExistingFacility(BaseModel):
    id: str
    lender: str
    type: Literal["cash_credit", "term_loan", "vehicle_loan"]
    amount: int
    account: str | None = None
    declared: bool


class RequestedFacility(BaseModel):
    type: FacilityType
    nature: Literal["enhancement", "renewal", "fresh"]
    amount: int
    tenor_months: int | None = None
    purpose: str | None = None


class Request(BaseModel):
    facilities: list[RequestedFacility]
    collateral_present: bool
    assessment_method_expected: Literal["turnover_method", "mpbf"]

    @property
    def total(self) -> int:
        return sum(f.amount for f in self.facilities)

    @property
    def facility_types(self) -> list[FacilityType]:
        return [f.type for f in self.facilities]


class FinancialModel(BaseModel):
    """Annual figures by fiscal year (ending March), in rupees."""

    revenue: dict[int, int]
    cost_ratios: dict[str, float] = Field(description="materials, employee, power, other as share of revenue")
    tax_rate: float
    net_worth_opening: int
    working_capital_days: dict[str, int] = Field(description="inventory_days, debtor_days, creditor_days")
    gst_rate: float


class Plant(BaseModel):
    id: str
    kind: str
    detail: dict = Field(default_factory=dict)


class Baseline(BaseModel):
    caught: list[str] = Field(default_factory=list)
    missed: list[str] = Field(default_factory=list)


class CaseDescriptor(BaseModel):
    schema_: Literal["creditiq.samplecase/1"] = Field(alias="schema")
    case_id: str
    seed: int
    timeline: Timeline
    entity: Entity
    identifiers: Identifiers
    people: list[Person]
    banks: list[Bank] = Field(default_factory=list)
    lenders: list[Lender] = Field(default_factory=list)
    accounts: list[Account] = Field(default_factory=list)
    facilities_existing: list[ExistingFacility] = Field(default_factory=list)
    request: Request
    financial_model: FinancialModel
    plants: list[Plant] = Field(default_factory=list)
    baseline: Baseline = Field(default_factory=Baseline)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _identifiers_match_constitution(self) -> "CaseDescriptor":
        has_cin = self.identifiers.cin is not None
        if self.entity.constitution == "private_limited" and not has_cin:
            raise ValueError("private_limited entities must have a CIN")
        if self.entity.constitution != "private_limited" and has_cin:
            raise ValueError(f"{self.entity.constitution} entities must not have a CIN")
        return self

    @model_validator(mode="after")
    def _pan_fourth_char_matches_constitution(self) -> "CaseDescriptor":
        holder_type = {"private_limited": "company", "partnership": "firm"}.get(
            self.entity.constitution, "individual"
        )
        if not ids.validate_pan(self.identifiers.pan, holder_type=holder_type):
            raise ValueError(
                f"PAN {self.identifiers.pan!r} 4th character does not match "
                f"constitution {self.entity.constitution!r} (expected holder type {holder_type!r})"
            )
        return self

    @model_validator(mode="after")
    def _cin_year_and_roc(self) -> "CaseDescriptor":
        if self.identifiers.cin is not None:
            if not ids.validate_cin(self.identifiers.cin, formed_year=self.entity.formed_on.year):
                raise ValueError(
                    f"CIN {self.identifiers.cin!r} does not match incorporation year {self.entity.formed_on.year}"
                )
        return self
