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
    """Neither the rules, the model nor a person settled it."""
    reason: str | None = None
    """What the model relied on, when it read this row."""
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
    by_model: int = 0
    by_person: int
    unsettled: int
    """Rows nothing has settled yet: ambiguous or unmatched, with no person's decision."""
    categories: list[TxnCategoryTotal]
    months: list[TxnMonthTotal]
    accounts: list[str]
    model_error: str | None = None
    """Why the last attempt to ask the model failed, if it did."""


class TxnCategoryRequest(BaseModel):
    category: str
    reason: str = Field(min_length=3)


# ---- Conduct of the accounts (read from the classified transactions) ----

FlagSeverity = Literal["info", "watch", "concern"]
FlagKind = Literal[
    "cash", "returns", "concentration", "round_trip", "balance_spike", "statutory_late", "statutory_gap",
    "promoter", "unusual", "weekend", "period_gap", "balance_break", "duplicate", "duplicate_reference", "unsettled",
]


class ConductFlag(BaseModel):
    """Something in the accounts for a person to look at. A question, never a decision."""

    kind: FlagKind
    severity: FlagSeverity
    message: str
    month: str | None = None
    account: str | None = None
    amount: float | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class MonthConduct(BaseModel):
    month: str
    """YYYY-MM, all accounts together."""
    credits: float
    business_credits: float
    """Credits less the categories removed from business inflow."""
    customer_receipts: float
    cash_deposits: float
    cash_share_pct: float
    returns_count: int
    returns_amount: float
    failed_debits_reversed: float
    salary: float
    salary_day: int | None = None
    statutory: dict[str, int] = Field(default_factory=dict)
    """Category -> the day of the month it was last paid."""
    promoter_in: float
    promoter_out: float


class PartyShare(BaseModel):
    party: str
    amount: float
    count: int
    share_pct: float


class RoundTrip(BaseModel):
    party: str
    out_date: str
    out_amount: float
    in_date: str
    in_amount: float
    evidence: list[Evidence] = Field(default_factory=list)


class BalanceMonth(BaseModel):
    month: str
    average: float
    minimum: float
    month_end: float | None = None
    spike: bool = False


class AccountBalances(BaseModel):
    account: str
    months: list[BalanceMonth]


class BankConduct(BaseModel):
    case_id: str
    accounts: list[str]
    months: list[MonthConduct]
    customers: list[PartyShare]
    customer_top1_pct: float | None = None
    customer_top5_pct: float | None = None
    suppliers: list[PartyShare]
    round_trips: list[RoundTrip]
    balances: list[AccountBalances]
    promoter_in: float
    promoter_out: float
    flags: list[ConductFlag]
    unsettled_count: int
    """Transactions nothing has filed under a category yet."""
