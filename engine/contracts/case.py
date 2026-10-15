"""Cases (FRD F-01, F-04)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Stage


class HeaderField(BaseModel):
    """One case-header field with both values kept (F-01.2): what the system
    proposed and where from, and what a person confirmed."""

    value: str | None
    proposed: str | None = None
    source: str | None = None
    """"message:<start>-<end>" (a span in the pasted message),
    "document:<document_id>:p<page>", or "person"."""


class CaseCreate(BaseModel):
    """Create a case after the RM confirms (F-04.7). The proposal flow
    (F-04) fills `header` with sources; a direct create leaves it empty."""

    borrower: str = Field(min_length=1)
    constitution: str = "unknown"
    facilities: list[str] = Field(min_length=1)
    amount_inr: int = Field(gt=0)
    channel: str
    pan: str | None = None
    gstin: str | None = None
    cin: str | None = None
    udyam: str | None = None
    collateral_present: bool = False
    header: dict[str, HeaderField] = Field(default_factory=dict)
    duplicate_override_reason: str | None = None
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
    rm: str
    created_at: str
    open_review_items: int


class CaseDetail(CaseSummary):
    pan: str | None
    gstin: str | None
    cin: str | None
    udyam: str | None
    collateral_present: bool
    channel: str
    as_of: str
    """Fixed at creation; every age and window rule uses it (FRD principle 8)."""
    created_by: str
    config_version: str | None
    header: dict[str, HeaderField]
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
    `review_gate`, `blocking_items`, `open_exceptions`."""
    score_pct: float = 0
    gate_pct: float = 0
    blocking_open: int = 0
    open_exceptions: int = 0


class CaseProgress(BaseModel):
    case_id: str
    stage: Stage
    stages: list[StageProgress]
    gate: AssessmentGate | None = None
    """None only for a progress computed before the gate existed."""
