"""What the start screen has so far, proposed as a case (F-04): the message read by the rules
(engine/proposal.py), the values typed over it, the duplicate check (F-04.5) and what the product's minimum
still lacks (F-04.6). Stores nothing.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from . import intake, intake_rules
from .cases import find_duplicates
from .config import ProductConfig
from .config import product as product_config
from .contracts import CaseProposal, ProposedField
from .parties import name_tolerance
from .proposal import parse


#: The case's identifiers, checked when typed even where the product offers no box for them.
TYPED_IDENTIFIERS = ("pan", "gstin", "cin", "udyam")


def _typed_field(product: ProductConfig, name: str, value: str, context: dict) -> ProposedField:
    """A value the RM typed (an identifier box on the start screen, or the form): found as typed, or
    invalid with why; never corrected (F-04.4). An identifier is judged as the create will judge it, for
    the constitution, customer type and case type the start screen has so far (`context`)."""
    box = intake_rules.identifier_spec(product, name)
    source = "identifier" if box else "person"
    problem = None
    if box or name in TYPED_IDENTIFIERS:
        if (box["type"] if box else "pan") != "text":
            value = value.upper()
        problem = intake_rules.check_identifier(product, name, value, **context)
    choices = {"customer_type": product.customer_types, "case_type": (*product.case_types, "unknown"),
               "program": product.programs, "bank_stage": product.stages}
    if name in choices and value not in choices[name]:
        problem = f"{value!r} is not one of the choices for {product.label}."
    if name in ("amount_inr", "tenure_months") and intake_rules.whole_number(value) is None:
        problem = "Whole numbers only."
    return ProposedField(value=value, status="invalid" if problem else "found", note=problem, source=source)


def _value(fields: dict[str, ProposedField], name: str, *, found_only: bool = False) -> str | None:
    """The field's value: a proposed value counts toward the minimum even while unclear (the RM confirms
    it); the duplicate check takes only a value found outright."""
    f = fields.get(name)
    if not f or not f.value or f.status in ("not_found", "invalid"):
        return None
    return f.value if f.status == "found" or not found_only else None


def _minimum(product: ProductConfig, fields: dict[str, ProposedField], groups: dict) -> list[str]:
    """F-04.6: the fields of the product's minimum the message, the typed values and the rows still lack."""
    applicant = intake.primary_applicant(product, groups)
    return intake.missing_minimum(
        product,
        borrower=_value(fields, "borrower") or (applicant[0] if applicant else None),
        facilities=[f for f in (_value(fields, "facilities") or "").split(",") if f],
        amount_inr=intake_rules.whole_number(_value(fields, "amount_inr")),
        customer_type=_value(fields, "customer_type"),
        tenure_months=intake_rules.whole_number(_value(fields, "tenure_months")),
        groups=groups,
    )


def _typed(product: ProductConfig, fields: dict[str, ProposedField], typed: dict[str, str | None]) -> None:
    """The typed values over what the message says. Identifiers are judged with the constitution typed on
    the form, else the one the message gives."""
    given = {k: v.strip() for k, v in typed.items() if v is not None and v.strip()}
    context = {
        "constitution": given.get("constitution") or _value(fields, "constitution", found_only=True),
        "customer_type": given.get("customer_type"),
        "case_type": given.get("case_type") or _value(fields, "case_type", found_only=True),
    }
    for name, value in given.items():
        fields[name] = _typed_field(product, name, value, context)


def _duplicates(conn: sqlite3.Connection, root: Path, product: ProductConfig, fields: dict[str, ProposedField],
                groups: dict) -> list:
    """F-04.5: cases matching any name proposed (the borrower, its candidates, the primary applicant), the
    PAN and every PAN the rows give, the GSTIN or the application ID."""
    names = [fields["borrower"].value] if fields.get("borrower") and fields["borrower"].value else []
    names += [c.value for c in fields["borrower"].candidates] if "borrower" in fields else []
    applicant = intake.primary_applicant(product, groups)
    if applicant and applicant[0] not in names:
        names.append(applicant[0])
    threshold = name_tolerance(root)
    seen: dict[str, object] = {}
    for name in names or [None]:
        for dup in find_duplicates(conn, pan=_value(fields, "pan", found_only=True),
                                   gstin=_value(fields, "gstin", found_only=True), borrower=name,
                                   name_threshold=threshold,
                                   application_id=_value(fields, "application_id", found_only=True),
                                   pans=intake.people_pans(product, groups)):
            seen.setdefault(dup.id, dup)
    return list(seen.values())


def propose(
    conn: sqlite3.Connection,
    root: Path,
    text: str | None,
    *,
    product: str | None = None,
    typed: dict[str, str | None] | None = None,
    groups: dict | None = None,
) -> CaseProposal:
    """F-04: what the start screen has so far, proposed as a case. A pasted message is read (only the
    product's case types are matched); values typed win over what it says; with no message nothing is
    read, and the answer is the duplicate check (PAN, GSTIN, application ID, names) and what the product's
    minimum still lacks. Raises KeyError for an unknown product. Stores nothing."""
    chosen = product_config(product)
    groups = groups or {}
    fields, stripped = parse(text, product=chosen.id) if text else ({}, [])
    _typed(chosen, fields, typed or {})
    return CaseProposal(
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
        fields=fields,
        duplicates=_duplicates(conn, root, chosen, fields, groups),
        missing_minimum=_minimum(chosen, fields, groups),
        stripped=stripped,
    )
