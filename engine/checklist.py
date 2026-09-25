"""Checklist derivation: which documents a case needs, from its constitution
and attributes (plan.md section 7 Stage B: "tested for every constitution
and attribute combination").

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
    ) -> "CaseAttributes":
        return cls(
            term_loan_requested="term_loan" in facility_types,
            cash_credit_requested="cash_credit" in facility_types,
            collateral_present=collateral_present,
            mpbf_applicable=mpbf_applicable,
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
