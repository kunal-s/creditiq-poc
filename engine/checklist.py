"""Checklist derivation: which documents a case needs, from its constitution
and attributes (docs/functional-requirements.md F-12; tested for every
constitution and attribute combination).

Reads only the published config store — never `config/checklist_taxonomy.yaml`
directly (see .importlinter) — so a policy publish is the only way this
derivation changes.
"""

from __future__ import annotations

from pathlib import Path

from .configstore.reader import load_checklist_taxonomy
from .configstore.schema import ChecklistItemDef

Constitution = str  # "private_limited" | "proprietorship" | "partnership"


class CaseAttributes:
    """The boolean flags checklist items can require. Derived from a case
    descriptor, not typed by hand — see `from_request`."""

    def __init__(self, **flags: bool) -> None:
        self.flags = flags

    def has(self, name: str) -> bool:
        return bool(self.flags.get(name, False))

    @classmethod
    def from_request(
        cls,
        *,
        facility_types: list[str],
        collateral_present: bool,
        mpbf_applicable: bool,
        existing_facilities_declared: bool = False,
    ) -> "CaseAttributes":
        return cls(
            term_loan_requested="term_loan" in facility_types,
            cash_credit_requested="cash_credit" in facility_types,
            collateral_present=collateral_present,
            mpbf_applicable=mpbf_applicable,
            existing_facilities_declared=existing_facilities_declared,
        )

    @classmethod
    def from_case(
        cls,
        *,
        facilities: list[str],
        amount_inr: int,
        collateral_present: bool,
        facility_sets: dict[str, str | None],
        mpbf_above_limit_inr: int,
        existing_facilities_declared: bool = False,
    ) -> "CaseAttributes":
        """F-12.2: attributes from the case header. `facility_sets` maps each
        facility id to the attribute it sets (config/app.yaml); MPBF applies
        to working-capital requests above the policy limit."""
        flags = {name: True for fac in facilities if (name := facility_sets.get(fac))}
        working_capital = flags.get("cash_credit_requested", False)
        return cls(
            **flags,
            collateral_present=collateral_present,
            mpbf_applicable=working_capital and amount_inr > mpbf_above_limit_inr,
            existing_facilities_declared=existing_facilities_declared,
        )


def applies(item: ChecklistItemDef, constitution: Constitution, attrs: CaseAttributes) -> bool:
    if constitution not in item.constitutions:
        return False
    return all(attrs.has(flag) for flag in item.requires_attributes)


def derive_checklist(
    data_root: Path, constitution: Constitution, attrs: CaseAttributes
) -> list[ChecklistItemDef]:
    taxonomy = load_checklist_taxonomy(data_root)
    return [item for item in taxonomy.items if applies(item, constitution, attrs)]


def section_weights(items: list[ChecklistItemDef]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for item in items:
        totals[item.category] = totals.get(item.category, 0) + item.weight
    return totals
