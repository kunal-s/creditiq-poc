"""Checklist derivation: which documents a case needs, from its constitution
and attributes (docs/functional-requirements.md F-12; tested for every
constitution and attribute combination), and for a product keyed by its own
customer types (a loan against property), from its customer type, its case
type and what its intake form declares (plan 2026-11-27 section 7.3).

Reads only the published config store — never `config/checklist_taxonomy.yaml`
directly (see .importlinter) — so a policy publish is the only way this
derivation changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from .config import option_default
from .config import product as product_config
from .configstore.reader import load_checklist_taxonomy
from .configstore.schema import ChecklistCondition, ChecklistItemDef

Constitution = str  # "private_limited" | "proprietorship" | "partnership"

#: A value the intake form holds that declares nothing: a yes/no field answered no, a choice not yet confirmed.
_NOT_DECLARED = frozenset({"no", "false", "unknown"})


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
        product: str | None = None,
        case_type: str | None = None,
        customer_type: str | None = None,
        declared: Iterable[str] = (),
        rows: Iterable[str] = (),
    ) -> "CaseAttributes":
        """F-12.2: attributes from the case header. `facility_sets` maps each
        facility id to the attribute it sets (config/app.yaml); MPBF applies
        to working-capital requests above the policy limit. The product and a
        confirmed case type set `product_<id>` and `case_type_<id>` (T2.1), a
        known customer type `customer_type_<id>`, each value the intake form
        declares `declared_<field>` (`declared_names`) and each repeating section
        with rows `rows_<section>` (`row_sections`): an item's customer_types,
        case_types and when_any read them (`applies`)."""
        flags = {name: True for fac in facilities if (name := facility_sets.get(fac))}
        if product:
            flags[f"product_{product}"] = True
        if case_type and case_type != "unknown":
            flags[f"case_type_{case_type}"] = True
        if customer_type and customer_type != "unknown":
            flags[f"customer_type_{customer_type}"] = True
        flags.update({f"declared_{name}": True for name in declared})
        flags.update({f"rows_{section}": True for section in rows})
        working_capital = flags.get("cash_credit_requested", False)
        return cls(
            **flags,
            collateral_present=collateral_present,
            mpbf_applicable=working_capital and amount_inr > mpbf_above_limit_inr,
            existing_facilities_declared=existing_facilities_declared,
        )


def for_product(item: ChecklistItemDef, product: str | None) -> bool:
    """The item is asked of cases of this product: it names it. An item that names no product (a checklist
    published before products were named) is the default product's only, so no other product inherits a
    business's items; a case with no product (one created before products were recorded) is of the
    default product."""
    default = option_default("products")
    return (product or default) in (item.products or [default])


def _met(condition: ChecklistCondition, attrs: CaseAttributes) -> bool:
    """Any one part of an item's `when_any` holds of the case."""
    return (any(attrs.has(f"case_type_{c}") for c in condition.case_types)
            or any(attrs.has(f"declared_{v}") for v in condition.declared)
            or any(attrs.has(f"rows_{s}") for s in condition.rows))


def applies(
    item: ChecklistItemDef, constitution: Constitution, attrs: CaseAttributes, product: str | None = None
) -> bool:
    """The item is asked of the case: of its product, of its constitution where the product's customers are
    businesses (a loan against property is keyed by its customer type, not a constitution), of its customer
    type and case type when it names them, when one part of its `when_any` holds, and every attribute it
    requires is set. A customer or case type not yet known meets no item that names them."""
    if not for_product(item, product):
        return False
    if product_config(product).constitution_based and constitution not in item.constitutions:
        return False
    if item.customer_types and not any(attrs.has(f"customer_type_{c}") for c in item.customer_types):
        return False
    if item.case_types and not any(attrs.has(f"case_type_{c}") for c in item.case_types):
        return False
    if item.when_any is not None and not _met(item.when_any, attrs):
        return False
    return all(attrs.has(flag) for flag in item.requires_attributes)


def is_declared(value: object) -> bool:
    """A value the intake form holds says something: not empty, not a zero amount, not a "no" (nor a
    choice still "unknown"); a list says something when one of its values does."""
    if isinstance(value, (list, tuple, set)):
        return any(is_declared(v) for v in value)
    text = str(value).strip() if value is not None else ""
    if not text or text.lower() in _NOT_DECLARED:
        return False
    try:
        return float(text.replace(",", "")) != 0
    except ValueError:
        return True


def _cell_value(cell: object) -> object:
    """A form value, whether it is held with its provenance (a header field, a row's cell) or bare."""
    if isinstance(cell, Mapping):
        return cell.get("value")
    return getattr(cell, "value", cell)


def declared_names(values: Mapping[str, object]) -> set[str]:
    """The fields the intake form declares a value for, from its single values by field id (the case's
    header and identifier columns, or the preview's fields)."""
    return {name for name, cell in values.items() if is_declared(_cell_value(cell))}


def _filled(cell: object) -> bool:
    value = _cell_value(cell)
    return value is not None and str(value).strip() != ""


def row_sections(groups: Mapping[str, Iterable[Mapping[str, object]]]) -> set[str]:
    """The repeating sections of the intake form with at least one row that holds a value."""
    return {section for section, rows in groups.items()
            if any(any(_filled(cell) for cell in row.values()) for row in rows or [])}


def derive_checklist(
    data_root: Path, constitution: Constitution, attrs: CaseAttributes, product: str | None = None
) -> list[ChecklistItemDef]:
    taxonomy = load_checklist_taxonomy(data_root)
    return [item for item in taxonomy.items if applies(item, constitution, attrs, product)]


def section_weights(items: list[ChecklistItemDef]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for item in items:
        totals[item.category] = totals.get(item.category, 0) + item.weight
    return totals
