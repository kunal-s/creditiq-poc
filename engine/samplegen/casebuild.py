"""Ties a case descriptor to its computed financial model — the object the
document builders and manifest emitter consume, so they never recompute
figures themselves (single source of truth, per plan.md section 6)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .financials import CaseFinancials, build as build_financials
from .schema import CaseDescriptor

CASES_DIR = Path(__file__).resolve().parents[2] / "sample-data" / "cases"


def existing_term_debt(descriptor: CaseDescriptor) -> int:
    return sum(
        f.amount for f in descriptor.facilities_existing if f.type in ("term_loan", "vehicle_loan")
    )


def existing_cc_limit(descriptor: CaseDescriptor) -> int:
    for account in descriptor.accounts:
        if account.type == "cash_credit":
            return account.limit or 0
    return 0


@dataclass
class CompiledCase:
    descriptor: CaseDescriptor
    financials: CaseFinancials

    @property
    def latest_fy(self) -> int:
        return max(self.financials.years)


def load_descriptor(case_id: str) -> CaseDescriptor:
    path = CASES_DIR / case_id / "case.yaml"
    return CaseDescriptor.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def compile_case(case_id: str) -> CompiledCase:
    descriptor = load_descriptor(case_id)
    financials = build_financials(descriptor.financial_model, existing_term_debt_opening=existing_term_debt(descriptor))
    return CompiledCase(descriptor=descriptor, financials=financials)
