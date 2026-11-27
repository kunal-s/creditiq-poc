"""Sign-in, session and form metadata (FRD F-03, F-04)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SessionUser(BaseModel):
    id: str
    name: str
    role: str
    roleLabel: str
    email: str
    branch: str
    initials: str
    navGroups: list[str]
    permissions: list[str]


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: SessionUser


class Option(BaseModel):
    id: str
    label: str


class ProductMeta(Option):
    """A product a case can be opened under, with the lists a case of it may carry (config/app.yaml)."""

    prefix: str
    """The case number's prefix (BBG-2026-000001)."""
    case_types: list[Option]
    stages: list[Option]
    customer_types: list[Option]
    programs: list[Option]
    minimum: list[str]
    """Fields a case of the product needs before it can be created: borrower, facilities, amount_inr,
    applicants, customer_type, tenure_months, properties."""


ShowWhen = dict[str, list[str]]
"""Shown only when the form's value for each key (customer_type, case_type) is one of the listed ids."""


class IntakeField(BaseModel):
    """One field of the form (config/intake.yaml)."""

    id: str
    type: Literal[
        "text", "amount", "number", "months", "choice", "yes_no", "pan", "gstin", "cin_or_llpin", "udyam",
        "digits", "pincode", "date", "parties",
    ]
    required: bool = False
    options: list[Option] | None = None
    """The choices of a `choice` field, already resolved for the product."""
    length: int | None = None
    """Digits of a `digits` field."""
    holder: Literal["individual", "entity"] | None = None
    """Whose PAN: an individual's (fourth letter P) or an entity's."""
    unless: ShowWhen | None = None
    """The holder rule does not apply for these customer types."""
    alternative: str | None = None
    """A field that stands in for this one (PAN or Form 60)."""
    from_section: str | None = None
    """For a `parties` field: the section whose rows it chooses from."""
    show_when: ShowWhen | None = None


class IntakePeople(BaseModel):
    """A section whose rows are the case's parties."""

    default_role: str
    """The role a row that names none takes."""
    primary_role: str | None = None
    """The role of the row that is the borrower itself (a loan against property's primary applicant)."""


class IntakeSection(BaseModel):
    id: str
    repeat: dict[str, int] | None = None
    """{min, max} rows for a repeating section; None for a section of single values."""
    show_when: ShowWhen | None = None
    people: IntakePeople | None = None
    fields: list[IntakeField]


class IntakeIdentifier(BaseModel):
    """An identifier box on the start screen: always optional."""

    id: str
    type: Literal["pan", "gstin", "cin_or_llpin", "udyam", "text"]
    holder: Literal["individual", "entity"] | None = None
    unless: ShowWhen | None = None
    show_when: ShowWhen | None = None


class IntakeDocuments(BaseModel):
    required: bool
    min_files: int
    """Files the engine must have registered before it creates the case."""
    suggested: list[str] = Field(default_factory=list)
    """Ids of the documents to suggest starting with (worded by the terminology)."""


class IntakeStart(BaseModel):
    message_required: bool = False
    documents: IntakeDocuments
    identifiers: list[IntakeIdentifier]


class IntakeProduct(BaseModel):
    start: IntakeStart
    sections: list[IntakeSection]


class DisplayUnit(BaseModel):
    """The unit financial figures are written in, from the published configuration."""

    unit: Literal["rupee", "thousand", "lakh", "crore"]
    label: str
    """"Crore": named under a table's heading and in the Administration screen."""
    divisor: float
    decimals: int
    suffix: str
    """Written after a figure in a sentence: " cr"."""


class Features(BaseModel):
    """Features a deployment switches on or off (config/app.yaml `features:`)."""

    integrity_checks: bool = True
    """File integrity checks (F-07A) on screen."""
    model_usage: bool = True
    """The Administration's Model usage section."""


class Meta(BaseModel):
    """Choice lists the screens need, from config/app.yaml."""

    channels: list[Option]
    constitutions: list[Option]
    facilities: list[Option]
    products: list[ProductMeta]
    product_default: str | None = None
    customer_types: list[Option] = Field(default_factory=list)
    """Every customer type of every product (constitutions and the others)."""
    programs: list[Option] = Field(default_factory=list)
    intake: dict[str, IntakeProduct] = Field(default_factory=dict)
    """The New appraisal form per product id (config/intake.yaml)."""
    form_field_max_kb: int = 256
    """The largest `case` part POST /api/cases/intake accepts."""
    case_types: list[Option]
    branches: list[Option]
    bank_stages: list[Option]
    bank_stage_default: str | None = None
    """The stage a new case starts at (T2.1)."""
    case_create_minimum: list[str]
    """The business banking minimum, kept for callers that predate products; see `products[].minimum`."""
    features: Features = Field(default_factory=Features)
