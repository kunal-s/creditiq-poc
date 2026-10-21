"""Classified bank-statement transactions (the Banking view of the Financials section)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence

TxnStatus = Literal["matched", "ambiguous", "unmatched"]
TxnMethod = Literal["rule", "model", "manual"]
TxnDirection = Literal["credit", "debit"]


class TxnRow(BaseModel):
    """One statement transaction and how it was classified."""

    txn_id: str
    document_id: str
    account: str
    seq: int
    date: str | None = None
    narration: str
    debit: float
    credit: float
    category: str
    category_label: str
    direction: TxnDirection
    status: TxnStatus
    method: TxnMethod
    rule_id: str | None = None
    confidence: float
    channel: str | None = None
    counterparty: str | None = None
    candidates: list[str] = Field(default_factory=list)
    """For an ambiguous row, the categories the competing rules named."""
    flags: list[str] = Field(default_factory=list)
    paired_with: str | None = None
    needs_review: bool = False
    """Neither the rules nor a person settled it."""
    evidence: list[Evidence] = Field(default_factory=list)


class TxnPage(BaseModel):
    items: list[TxnRow]
    total: int
    limit: int
    offset: int


class TxnCategoryTotal(BaseModel):
    category: str
    label: str
    direction: TxnDirection
    count: int
    amount: float


class TxnMonthTotal(BaseModel):
    month: str
    """YYYY-MM."""
    credits: float
    debits: float
    by_category: dict[str, float]


class TxnSummary(BaseModel):
    case_id: str
    config_version: str | None = None
    total: int
    by_rule: int
    by_person: int
    unsettled: int
    """Rows nothing has settled yet: ambiguous or unmatched, with no person's decision."""
    categories: list[TxnCategoryTotal]
    months: list[TxnMonthTotal]
    accounts: list[str]


class TxnCategoryRequest(BaseModel):
    category: str
    reason: str = Field(min_length=3)
