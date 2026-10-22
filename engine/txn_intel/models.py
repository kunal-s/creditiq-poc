"""The inputs and outputs of the deterministic pass."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Status = Literal["matched", "ambiguous", "unmatched"]


@dataclass(frozen=True)
class Txn:
    """One statement row. `id` is the caller's own key for it (a field-value id, say)."""

    id: str
    account: str
    """The account's label, so rows of one statement are told from another's."""
    date: date | None
    narration: str
    debit: float = 0.0
    credit: float = 0.0
    account_last4: str | None = None


@dataclass(frozen=True)
class Context:
    """What the case knows that a narration may mention (all optional)."""

    borrower_name: str = ""
    own_account_last4: frozenset[str] = frozenset()
    """The last digits of every account in the account set (F-18.5)."""
    lender_names: tuple[str, ...] = ()
    director_names: tuple[str, ...] = ()
    emi_min_months: int = 3
    emi_tolerance_pct: float = 5.0
    """A recurring debit: the same party in this many months, amounts within this percentage."""


@dataclass
class Label:
    txn_id: str
    category: str
    status: Status
    rule_id: str | None
    confidence: float
    channel: str | None = None
    counterparty: str | None = None
    counterparty_key: str | None = None
    candidates: list[str] = field(default_factory=list)
    """For an ambiguous row, the categories the competing rules named."""
    flags: list[str] = field(default_factory=list)
    paired_with: str | None = None
    method: Literal["rule", "model"] = "rule"

    needs_model: bool = False
