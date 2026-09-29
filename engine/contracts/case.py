"""Cases (FRD F-01, F-04)."""

from __future__ import annotations

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
