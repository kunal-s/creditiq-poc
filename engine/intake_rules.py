"""What the intake form accepts: each value against its field's type, rows against their sections, what
`show_when` hides, a section's least rows and a shown field's `required` (config/intake.yaml).

Values are flagged, never corrected (F-04.4). Every rule raises IntakeError naming the section, row and
field; an identifier that is not valid for its box raises IdentifierProblem. It only reads the
configuration (CLAUDE.md rule 4).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from . import identifiers
from .config import ProductConfig
from .intake import CASE_COLUMNS, limits, product_schema, row_value, shown
from .names import normalise_name

IDENTIFIER_KINDS = ("pan", "gstin", "cin_or_llpin", "udyam")
_DIGITS = re.compile(r"[0-9]+")


class IntakeError(ValueError):
    """The intake values are not valid for the product."""


class IdentifierProblem(IntakeError):
    """An identifier is not valid for its box or field."""


# --- Identifiers ---


def has_controls(value: str, *, lines: bool = False) -> bool:
    """Control characters in a value; `lines` allows a tab and line breaks (a text field)."""
    allowed = "\t\n\r" if lines else ""
    return any(unicodedata.category(c) == "Cc" and c not in allowed for c in value)


def identifier_error(
    kind: str,
    value: str,
    *,
    holder: str | None = None,
    constitution: str | None = None,
    holder_rule_lifted: bool = False,
) -> str | None:
    """Why an identifier is not valid, or None. Never corrects it (F-04.4).

    A PAN's `holder` is `individual` (the fourth letter must be P) or `entity`: a P-type PAN is refused
    for an entity only when the constitution is known and is not a proprietorship, whose PAN is the
    proprietor's own. `holder_rule_lifted` drops the individual rule (a non-individual customer)."""
    value = value.strip().upper()
    if kind == "pan":
        if not identifiers.validate_pan_format(value):
            return "Not a valid PAN (five letters, four digits, one letter)."
        if holder == "individual" and not holder_rule_lifted and value[3] != "P":
            return "An individual's PAN has P as its fourth letter."
        if holder == "entity" and value[3] == "P" and constitution not in (None, "unknown", "proprietorship"):
            return "An individual's PAN (fourth letter P) cannot be the PAN of this constitution."
        return None
    if kind == "gstin":
        return None if identifiers.validate_gstin(value) else "Not a valid GSTIN (format or check character)."
    if kind == "cin_or_llpin":
        if identifiers.validate_cin(value) or identifiers.validate_llpin(value):
            return None
        return "Not a valid CIN (21 characters) or LLPIN (AAA-1234)."
    if kind == "udyam":
        return None if identifiers.validate_udyam(value) else "Not a valid Udyam number (UDYAM-XX-00-0000000)."
    if kind == "text":
        most = limits()["short_text_max"]
        if len(value) > most or has_controls(value):
            return f"Too long, or has control characters (at most {most} characters)."
        return None
    return f"Unknown identifier type {kind!r}."


def identifier_spec(product: ProductConfig, ident_id: str) -> dict | None:
    return next((i for i in product_schema(product)["start"]["identifiers"] if i["id"] == ident_id), None)


def _lifted(spec: dict, customer_type: str | None) -> bool:
    return customer_type in ((spec.get("unless") or {}).get("customer_type") or [])


def check_identifier(product: ProductConfig, ident_id: str, value: str, *, constitution: str | None,
                     customer_type: str | None, case_type: str | None = None) -> str | None:
    """The error for an identifier typed at the start (or held on the case) under the product's own rules
    for that box, or None. A box the product does not offer is judged as plain text; a box `show_when`
    hides for this case takes no value."""
    spec = identifier_spec(product, ident_id)
    if spec is None:
        return identifier_error("text", value)
    if not shown(spec.get("show_when"), {"customer_type": customer_type, "case_type": case_type}):
        return "Not asked for this customer or case type."
    return identifier_error(spec["type"], value, holder=spec.get("holder"),
                            constitution=constitution or customer_type, holder_rule_lifted=_lifted(spec, customer_type))


# --- One value ---


def _number_rule(kind: str, field: dict, value: str) -> str | None:
    """Why a number-like value does not fit its field, or None. Digits are 0 to 9 only."""
    plain = value.replace(",", "")
    if kind == "amount":
        return None if re.fullmatch(r"[0-9]{1,15}", plain) else "an amount is whole rupees, digits only"
    if kind == "number":
        return None if re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,4})?", value.replace(",", "")) else \
            "a number, digits and a decimal point only"
    if kind == "months":
        most = limits()["months_max"]
        ok = bool(re.fullmatch(r"[0-9]{1,4}", value)) and 1 <= int(value) <= most
        return None if ok else f"months from 1 to {most}"
    if kind == "digits":
        return None if re.fullmatch(rf"[0-9]{{{field['length']}}}", value) else f"exactly {field['length']} digits"
    if kind == "pincode":
        return None if re.fullmatch(r"[1-9][0-9]{5}", value) else "a 6-digit PIN code"
    return None


def _other_rule(kind: str, field: dict, value: str) -> str | None:
    if kind == "yes_no":
        return None if value in ("yes", "no") else "yes or no"
    if kind == "date":
        try:
            date.fromisoformat(value)
        except ValueError:
            return "a date as YYYY-MM-DD"
        return None
    if kind == "choice":
        return None if value in {o["id"] for o in field["options"]} else f"{value!r} is not one of the choices"
    return None


def check_value(field: dict, value: str, where: str, context: dict) -> None:
    """One value against its field's type (IntakeError); an identifier against its holder rule
    (IdentifierProblem)."""
    kind = field["type"]
    caps = limits()
    if kind in ("text", "parties"):
        if len(value) > caps["text_max"]:
            raise IntakeError(f"{where}: longer than {caps['text_max']} characters")
        if has_controls(value, lines=True):
            raise IntakeError(f"{where}: has control characters")
        return
    if len(value) > caps["short_text_max"]:
        raise IntakeError(f"{where}: too long")
    if kind in IDENTIFIER_KINDS:
        problem = identifier_error(kind, value, holder=field.get("holder"),
                                   constitution=context.get("constitution") or context.get("customer_type"),
                                   holder_rule_lifted=_lifted(field, context.get("customer_type")))
        if problem:
            raise IdentifierProblem(f"{where}: {problem}")
        return
    problem = _number_rule(kind, field, value) or _other_rule(kind, field, value)
    if problem:
        raise IntakeError(f"{where}: {problem}")


def whole_number(value: str | None) -> int | None:
    """A value of digits 0 to 9 (commas allowed) as a number, else None."""
    plain = (value or "").replace(",", "").strip()
    return int(plain) if _DIGITS.fullmatch(plain) else None


# --- Rows ---


def _names(rows: list[dict]) -> set[str]:
    return {normalise_name(n) for r in rows if (n := row_value(r, "name"))}


def _check_section_parties(section: dict, groups: dict[str, list[dict]]) -> None:
    """Each `parties` value of the section's rows names rows of its `from` section (names joined by "; ")."""
    for field in (f for f in section["fields"] if f["type"] == "parties"):
        known = _names(groups.get(field.get("from_section") or "", []))
        for number, row in enumerate(groups.get(section["id"]) or [], start=1):
            value = row_value(row, field["id"]) or ""
            unknown = [n.strip() for n in value.split(";") if n.strip() and normalise_name(n) not in known]
            if unknown:
                raise IntakeError(f"{section['id']} row {number} {field['id']}: {', '.join(unknown)} "
                                  f"not named in {field.get('from_section')}")


def _check_row(section: dict, row: dict, number: int, context: dict) -> None:
    """One row's values checked (a `parties` value names rows of another section: check_form_rules)."""
    fields = {f["id"]: f for f in section["fields"]}
    name = section["id"]
    unknown = sorted(set(row) - set(fields))
    if unknown:
        raise IntakeError(f"{name} row {number}: unknown fields {unknown}")
    for fid, field in fields.items():
        where = f"{name} row {number} {fid}"
        value = row_value(row, fid)
        if value is not None and not shown(field.get("show_when"), context):
            raise IntakeError(f"{where}: not asked for this customer or case type")
        if value is None:
            if field["required"] and shown(field.get("show_when"), context):
                raise IntakeError(f"{where}: required")
            continue
        check_value(field, value, where, context)


def validate_groups(product: ProductConfig, groups: dict[str, list[dict]], context: dict) -> dict[str, list[dict]]:
    """The rows of the repeating sections, checked against the product's form: only its repeating sections
    and only those `show_when` shows for the case, no more rows than the section allows, only its fields,
    every value valid for its field's type and shown, required fields present. Rows with no value at all are
    dropped; returns the rows kept. `context` holds the case's customer_type, case_type and constitution."""
    sections = {s["id"]: s for s in product_schema(product)["sections"] if s["repeat"] is not None}
    kept: dict[str, list[dict]] = {}
    for name, rows in groups.items():
        section = sections.get(name)
        if section is None:
            raise IntakeError(f"{name!r} is not a repeating section of {product.id}")
        nonempty = [r for r in rows if any(row_value(r, k) is not None for k in r)]
        if nonempty and not shown(section.get("show_when"), context):
            raise IntakeError(f"{name}: not asked for this customer or case type")
        if len(nonempty) > section["repeat"]["max"]:
            raise IntakeError(f"{name}: at most {section['repeat']['max']} rows")
        for number, row in enumerate(nonempty, start=1):
            _check_row(section, row, number, context)
        if nonempty:
            kept[name] = nonempty
    return kept


# --- Single values: the header and the case's own columns ---


def _single_fields(product: ProductConfig) -> dict[str, tuple[dict, dict]]:
    """Each field of a section of single values, with its section: {field id: (section, field)}."""
    return {f["id"]: (s, f) for s in product_schema(product)["sections"] if s["repeat"] is None for f in s["fields"]}


def _is_shown(section: dict, field: dict, context: dict) -> bool:
    return shown(section.get("show_when"), context) and shown(field.get("show_when"), context)


def validate_header(product: ProductConfig, header: dict, context: dict) -> None:
    """The header's single values of the product's form (a business's GSTIN, a declared income, the existing
    lender of a balance transfer), each checked against its field's type and refused where `show_when`
    hides it. The values the case holds in its own columns (check_case_columns), and header entries the form
    does not name (what a message proposes), are left alone."""
    fields = _single_fields(product)
    for name, cell in header.items():
        if name in CASE_COLUMNS or name not in fields:
            continue
        section, field = fields[name]
        value = row_value({name: cell}, name)
        if value is None:
            continue
        if not _is_shown(section, field, context):
            raise IntakeError(f"{name}: not asked for this customer or case type")
        check_value(field, value, name, context)


def check_case_columns(product: ProductConfig, values: dict[str, str | None], context: dict) -> None:
    """The case's own columns that the product's form asks (borrower, identifiers, amount, tenure, IDs),
    each against its field's type, and none given where `show_when` hides it. Choices are checked against
    the product's lists by the caller."""
    fields = _single_fields(product)
    for name, value in values.items():
        if value is None or name not in fields:
            continue
        section, field = fields[name]
        if not _is_shown(section, field, context):
            raise IntakeError(f"{name}: not asked for this customer or case type")
        if field["type"] != "choice":
            check_value(field, value, name, context)


def check_form_rules(product: ProductConfig, values: dict[str, str | None], header: dict,
                     groups: dict[str, list[dict]], context: dict) -> None:
    """What the form requires beyond the product's minimum (checked first): each shown repeating section
    has at least its `min` rows, each `parties` value names rows of its section, and each shown required
    single value is given (a case column in `values`, else the header)."""
    for section in product_schema(product)["sections"]:
        if not shown(section.get("show_when"), context):
            continue
        if section["repeat"] is not None:
            least = section["repeat"]["min"]
            if len(groups.get(section["id"]) or []) < least:
                raise IntakeError(f"{section['id']}: at least {least} row{'s' if least != 1 else ''}")
            _check_section_parties(section, groups)
            continue
        for field in section["fields"]:
            if not field["required"] or not shown(field.get("show_when"), context):
                continue
            given = values.get(field["id"]) if field["id"] in CASE_COLUMNS else row_value(header, field["id"])
            if not given:
                raise IntakeError(f"{field['id']}: required")


__all__ = [
    "IdentifierProblem", "IntakeError", "check_case_columns", "check_form_rules", "check_identifier",
    "check_value", "has_controls", "identifier_error", "identifier_spec", "validate_groups", "validate_header", "whole_number",
]
