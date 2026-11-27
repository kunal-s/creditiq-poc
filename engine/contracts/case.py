"""Cases (FRD F-01, F-04)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Stage


class IdentifierRecord(BaseModel):
    """A borrower identifier taken from the documents onto the case (F-10): the value the documents
    agree on, which the engine checks against its own cross-check before recording it."""

    value: str


class HeaderField(BaseModel):
    """One case-header field with both values kept (F-01.2): what the system
    proposed and where from, and what a person confirmed."""

    value: str | None
    proposed: str | None = None
    source: str | None = None
    """"message:<start>-<end>" (a span in the pasted message),
    "document:<document_id>:p<page>", "person", "identifier" (typed in an
    identifier box on the start screen), or a default the system filled:
    "default:config" (the configured default) or "default:rm" (the RM's own
    branch)."""


GroupRow = dict[str, HeaderField]
"""One row of a repeating section of the intake form (an applicant, a property, a facility line):
each field of the row with its own provenance (F-01.2)."""


#: Storage bounds of a case's figures (an integer column holds 18 digits); the form's own limits are
#: config/intake.yaml `limits`.
MAX_AMOUNT_INR = 999_999_999_999_999
MAX_TENURE_MONTHS = 9_999


class CaseCreate(BaseModel):
    """Create a case after the RM confirms (F-04.7). The proposal flow
    (F-04) fills `header` with sources; a direct create leaves it empty."""

    borrower: str = Field(default="", max_length=500)
    """Required for a product whose minimum names it (business banking); a loan against property takes
    the primary applicant's name when it is left empty."""
    constitution: str = "unknown"
    facilities: list[str] = Field(default_factory=list)
    """Required for a product whose minimum names it (business banking)."""
    amount_inr: int = Field(default=0, ge=0, le=MAX_AMOUNT_INR)
    """Required (above zero) by every product's minimum; whole rupees, at most 15 digits."""
    channel: str
    pan: str | None = Field(default=None, max_length=50)
    gstin: str | None = Field(default=None, max_length=50)
    cin: str | None = Field(default=None, max_length=50)
    udyam: str | None = Field(default=None, max_length=50)
    collateral_present: bool = False
    product: str | None = None
    """A product id from config/app.yaml; None takes the configured default."""
    case_type: str = "unknown"
    """One of the product's case types; "unknown" until confirmed."""
    customer_type: str | None = None
    """One of the product's customer types (a constitution, or salaried, self-employed and so on)."""
    program: str | None = None
    """One of the product's credit programs."""
    tenure_months: int | None = Field(default=None, ge=1, le=MAX_TENURE_MONTHS)
    """Months; the form's own limit (config/intake.yaml limits.months_max) is checked too."""
    groups: dict[str, list[GroupRow]] = Field(default_factory=dict)
    """The rows of the intake form's repeating sections, by section id (applicants, properties,
    facilities, people, existing_loans, banking). Kept apart from `header`, which holds single
    values; checked against the product's form in config/intake.yaml."""
    application_id: str | None = Field(default=None, max_length=100)
    """The application's identifier in the loan origination system."""
    customer_id: str | None = Field(default=None, max_length=100)
    """The customer's identifier in the bank's systems."""
    branch: str | None = None
    """A branch id from config/app.yaml; None takes the RM's branch."""
    bank_stage: str | None = None
    """A bank stage id from config/app.yaml; None takes the configured default."""
    header: dict[str, HeaderField] = Field(default_factory=dict)
    duplicate_override_reason: str | None = Field(default=None, max_length=1000)
    """Required when the duplicate-case check matched and the RM creates anyway (F-04.5)."""
    message_text: str | None = None
    """The pasted message, unchanged, when the case comes from a proposal
    (F-04.8): stored as the case's first document; header sources
    "message:<start>-<end>" point into it."""


class CaseDeleteRequest(BaseModel):
    """F-01.5: why the case is being deleted; kept in the decision log."""

    reason: str = Field(min_length=3)


class CaseSummary(BaseModel):
    """Workbench row (F-01.4)."""

    id: str
    borrower: str
    constitution: str
    facilities: list[str]
    amount_inr: int
    stage: Stage
    product: str | None = None
    case_type: str | None = None
    """None for a case created before case types were recorded."""
    customer_type: str | None = None
    program: str | None = None
    bank_stage: str | None = None
    rm: str
    created_at: str
    open_review_items: int
    files_attention: int = 0
    """Files that need a person: unread or refused, checks that found something, a document waiting."""
    files_altered: int = 0
    """Of those, files whose checks found signs of an edit."""


class CaseDetail(CaseSummary):
    pan: str | None
    gstin: str | None
    cin: str | None
    udyam: str | None
    collateral_present: bool
    channel: str
    application_id: str | None = None
    customer_id: str | None = None
    branch: str | None = None
    as_of: str
    """Fixed at creation; every age and window rule uses it (FRD principle 8)."""
    created_by: str
    config_version: str | None
    header: dict[str, HeaderField]
    tenure_months: int | None = None
    groups: dict[str, list[GroupRow]] = Field(default_factory=dict)
    """The intake form's repeating rows, by section id, each field with its provenance."""
    assessment_opened_at: str | None = None
    """When the case was created, opening cross-verification, policy and outputs (F-13 gate).
    None while the appraisal is still in intake."""
    assessment_opened_by: str | None = None


StageKey = Literal["documents", "extraction", "completeness", "cross_verification", "policy", "outputs"]
StageStatus = Literal["not_started", "in_progress", "needs_attention", "done"]


class StageProgress(BaseModel):
    """One processing stage of FRD §5, as the case workspace shows it (§6).
    Counts only, never extracted values, so every role may read it."""

    key: StageKey
    status: StageStatus
    done: int = 0
    """Units finished: documents classified, documents extracted, checklist items satisfied."""
    total: int = 0
    attention: int = 0
    """Units waiting for a person or blocking the stage."""


class CreateCaseRequest(BaseModel):
    """Creating the case with its checks not passed (F-04.10): the reason is recorded in the decision log."""

    reason: str = Field(min_length=1, max_length=2000)


class RequiredFieldGap(BaseModel):
    """A required field no document received supplies (F-13.6), and what cannot be worked out without it."""

    field: str
    label: str
    stops: list[str] = Field(default_factory=list)


class AssessmentGate(BaseModel):
    """The F-13 gate between intake and assessment: cross-verification, policy checks and the
    outputs open only once completeness is satisfied and a person creates the case."""

    open: bool
    """The case has been created; the assessment stages are open."""
    can_open: bool
    """Completeness is satisfied, so the case may be created now."""
    opened_at: str | None = None
    opened_by: str | None = None
    blockers: list[str] = Field(default_factory=list)
    """Why it cannot be created yet, keyed for the screens:
    `review_gate`, `blocking_items`, `open_exceptions`, `required_fields`."""
    score_pct: float = 0
    gate_pct: float = 0
    blocking_open: int = 0
    open_exceptions: int = 0
    required_fields: list[RequiredFieldGap] = Field(default_factory=list)
    """The required-field check (F-13.6): each gap among the documents received."""
    opened_anyway: str | None = None
    """The reason recorded when a person created the case with the checks not passed (F-04.10)."""


class CaseProgress(BaseModel):
    case_id: str
    stage: Stage
    stages: list[StageProgress]
    gate: AssessmentGate | None = None
    """None only for a progress computed before the gate existed."""
