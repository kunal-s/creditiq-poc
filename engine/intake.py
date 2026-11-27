"""The product-first intake form: what it asks, and what a case needs before it exists.

The form per product is in config/intake.yaml (read directly, like config/app.yaml); the products and
their lists are in config/app.yaml. This module reads them and answers what the engine asks at intake:

- the form's schema, with its option lists resolved, for `GET /api/meta`, and its limits;
- what `show_when` shows for a case, the people sections and their roles, the primary applicant;
- whether the product's minimum is met (`missing_minimum`);
- where a value came from (`source_kind`, `CREATE_SOURCES`) and what the case's own declaration is
  called where it is cited (`declared_label`).

What each value may be is checked by engine/intake_rules.py. It imports no configuration writer and
nothing that runs a case (CLAUDE.md rule 4): it only reads.
"""

from __future__ import annotations

import re
from typing import get_args

from .config import (
    ConfigError,
    ProductConfig,
    customer_type_options,
    load_app_config,
    load_intake_config,
    option_list,
)
from .config import products as product_configs
from .contracts import Party

#: The roles a party may have (engine/contracts Party): a people section's roles must be among them.
PARTY_ROLES = frozenset(get_args(Party.model_fields["role"].annotation))

FIELD_TYPES = (
    "text", "amount", "number", "months", "choice", "yes_no", "pan", "gstin", "cin_or_llpin", "udyam", "digits",
    "pincode", "date", "parties",
)
IDENTIFIER_TYPES = ("pan", "gstin", "cin_or_llpin", "udyam", "text")
#: The sections a minimum field is counted from (the rows of a repeating section).
MINIMUM_SECTIONS = {"applicants": "applicants", "properties": "properties", "facilities": "facilities"}
#: The limits a value is held to when config/intake.yaml `limits` leaves one out.
DEFAULT_LIMITS = {"text_max": 500, "short_text_max": 100, "months_max": 600}

#: Single values of the form that the case holds in its own columns (CaseCreate), not in the header.
CASE_COLUMNS = frozenset({
    "borrower", "constitution", "facilities", "amount_inr", "channel", "pan", "gstin", "cin", "udyam",
    "collateral_present", "product", "case_type", "customer_type", "program", "tenure_months",
    "application_id", "customer_id", "branch", "bank_stage",
})


def limits() -> dict[str, int]:
    """The lengths and ranges a value may have (config/intake.yaml `limits`)."""
    return {**DEFAULT_LIMITS, **{k: int(v) for k, v in (load_intake_config().get("limits") or {}).items()}}


def shown(rule: dict | None, context: dict) -> bool:
    """Whether a `show_when` rule shows its section, field or box for the case: every key's value (the
    customer type, the case type) is one of the ids the rule lists. No rule shows it always."""
    return all(context.get(key) in (values or []) for key, values in (rule or {}).items())


# --- The form's schema ---


def _option(raw: dict) -> dict:
    return {"id": raw["id"], "label": raw["label"]}


def _options_for(name: str, product: ProductConfig, lists: dict) -> list[dict]:
    """The choices a field's `options` name: a list of config/intake.yaml, or a list of app.yaml
    narrowed to what the product uses."""
    if name in lists:
        return [_option(o) for o in lists[name]]
    if name == "case_types":
        return [_option(o) for o in option_list("case_types") if o["id"] in product.case_types or o["id"] == "unknown"]
    if name == "programs":
        return [_option(o) for o in load_app_config().get("programs", []) if o["id"] in product.programs]
    if name == "customer_types":
        return [_option(o) for o in customer_type_options() if o["id"] in product.customer_types]
    if name == "stages":
        return [_option(o) for o in option_list("bank_stages") if o["id"] in product.stages]
    if name in ("facilities", "constitutions", "channels", "branches"):
        return [_option(o) for o in option_list(name)]
    raise ConfigError(f"config/intake.yaml: unknown option list {name!r}")


def _field(raw: dict, product: ProductConfig, lists: dict, where: str) -> dict:
    if raw.get("type") not in FIELD_TYPES:
        raise ConfigError(f"config/intake.yaml {where}.{raw.get('id')}: unknown field type {raw.get('type')!r}")
    if raw["type"] == "digits" and not raw.get("length"):
        raise ConfigError(f"config/intake.yaml {where}.{raw['id']}: a digits field needs a length")
    out = {
        "id": raw["id"], "type": raw["type"], "required": bool(raw.get("required", False)),
        "options": _options_for(raw["options"], product, lists) if raw["type"] == "choice" else None,
        "length": raw.get("length"), "holder": raw.get("holder"), "unless": raw.get("unless"),
        "alternative": raw.get("alternative"), "from_section": raw.get("from"), "show_when": raw.get("show_when"),
    }
    if raw["type"] == "choice" and not out["options"]:
        raise ConfigError(f"config/intake.yaml {where}.{raw['id']}: a choice field with no options")
    return out


def _start(raw: dict, where: str) -> dict:
    documents = raw.get("documents") or {}
    if documents.get("required") and int(documents.get("min_files", 0)) < 1:
        raise ConfigError(f"config/intake.yaml {where}.start.documents: required needs min_files of at least 1")
    ids = []
    for ident in raw.get("identifiers") or []:
        if ident.get("type") not in IDENTIFIER_TYPES:
            raise ConfigError(f"config/intake.yaml {where}.start.identifiers.{ident.get('id')}: unknown type")
        ids.append({"id": ident["id"], "type": ident["type"], "holder": ident.get("holder"),
                    "unless": ident.get("unless"), "show_when": ident.get("show_when")})
    if len({i["id"] for i in ids}) != len(ids):
        raise ConfigError(f"config/intake.yaml {where}.start.identifiers: duplicate ids")
    return {
        "message_required": bool((raw.get("message") or {}).get("required", False)),
        "documents": {"required": bool(documents.get("required", False)),
                      "min_files": int(documents.get("min_files", 0)),
                      "suggested": list(documents.get("suggested") or [])},
        "identifiers": ids,
    }


def _people(raw: dict | None, fields: list[dict], repeat: dict | None, where: str) -> dict | None:
    """A people section's roles: the role a row without one takes, and the borrower's own role. Both must
    be choices of the section's `role` field."""
    if raw is None:
        return None
    role = next((f for f in fields if f["id"] == "role" and f["type"] == "choice"), None)
    if repeat is None or role is None or not any(f["id"] == "name" for f in fields):
        raise ConfigError(f"config/intake.yaml {where}: a people section repeats and has name and role fields")
    roles = [o["id"] for o in role["options"]]
    not_parties = [r for r in roles if r not in PARTY_ROLES]
    if not_parties:
        raise ConfigError(f"config/intake.yaml {where}: roles {not_parties} are not party roles {sorted(PARTY_ROLES)}")
    out = {"default_role": raw.get("default_role"), "primary_role": raw.get("primary_role")}
    bad = [r for r in out.values() if r is not None and r not in roles]
    if bad or out["default_role"] is None:
        raise ConfigError(f"config/intake.yaml {where}.people: default_role (and primary_role) must be roles {roles}")
    return out


def product_schema(product: ProductConfig) -> dict:
    """One product's form, as `GET /api/meta` serves it: start rules and sections, each field with its
    options resolved. Raises ConfigError when config/intake.yaml is not well formed."""
    cfg = load_intake_config()
    raw = cfg[product.id]
    lists = cfg.get("option_lists") or {}
    sections = []
    for sec in raw.get("sections") or []:
        where = f"{product.id}.{sec['id']}"
        repeat = sec.get("repeat")
        if repeat is not None and not (0 <= int(repeat["min"]) <= int(repeat["max"]) and int(repeat["max"]) >= 1):
            raise ConfigError(f"config/intake.yaml {where}: repeat needs 0 <= min <= max")
        fields = [_field(f, product, lists, where) for f in sec.get("fields") or []]
        sections.append({
            "id": sec["id"],
            "repeat": {"min": int(repeat["min"]), "max": int(repeat["max"])} if repeat else None,
            "show_when": sec.get("show_when"),
            "people": _people(sec.get("people"), fields, repeat, where),
            "fields": fields,
        })
    ids = [s["id"] for s in sections]
    if len(ids) != len(set(ids)):
        raise ConfigError(f"config/intake.yaml {product.id}: duplicate section ids")
    repeating = {s["id"] for s in sections if s["repeat"] is not None}
    for sec in sections:
        for f in sec["fields"]:
            if f["type"] == "parties" and f["from_section"] not in repeating:
                raise ConfigError(f"config/intake.yaml {product.id}.{sec['id']}.{f['id']}: `from` names no repeating section")
    for name in product.minimum:
        section = MINIMUM_SECTIONS.get(name)
        if section is not None and section not in ids:
            raise ConfigError(f"config/intake.yaml {product.id}: the minimum names {name!r} but has no {section!r} section")
    return {"start": _start(raw.get("start") or {}, product.id), "sections": sections}


def schema() -> dict[str, dict]:
    """The form of every product, by product id."""
    return {p.id: product_schema(p) for p in product_configs()}


def checklist_terms() -> dict[str, dict[str, set[str]]]:
    """What a checklist item of each product may name in its applicability (engine/configstore/schema.py
    `cross_check`), by product id: its customer and case types (config/app.yaml), the single values its
    form declares (`declared`: the fields of sections that do not repeat, and the start screen's
    identifiers), its repeating sections (`rows`) and their `parties` fields (`named_in`, as
    `<section>.<field>`)."""
    out: dict[str, dict[str, set[str]]] = {}
    for product in product_configs():
        form = product_schema(product)
        single = [s for s in form["sections"] if s["repeat"] is None]
        repeating = [s for s in form["sections"] if s["repeat"] is not None]
        out[product.id] = {
            "customer_types": set(product.customer_types),
            "case_types": set(product.case_types),
            "declared": {f["id"] for s in single for f in s["fields"]} | {i["id"] for i in form["start"]["identifiers"]},
            "rows": {s["id"] for s in repeating},
            "named_in": {f"{s['id']}.{f['id']}" for s in repeating for f in s["fields"] if f["type"] == "parties"},
        }
    return out


# --- Values ---


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def row_value(row: dict, name: str) -> str | None:
    """A row's value for a field, whether the row holds the field's provenance or the bare value."""
    cell = row.get(name)
    if cell is None:
        return None
    return _clean(cell.get("value") if isinstance(cell, dict) else getattr(cell, "value", cell))


def _cell_source(cell: object) -> str | None:
    return cell.get("source") if isinstance(cell, dict) else getattr(cell, "source", None)


# --- The people of the form ---


def people_sections(product: ProductConfig) -> list[dict]:
    """The sections whose rows are the case's parties, in the form's order: {id, default_role,
    primary_role, roles} (config/intake.yaml `people`)."""
    out = []
    for s in product_schema(product)["sections"]:
        if s.get("people"):
            role = next(f for f in s["fields"] if f["id"] == "role")
            out.append({"id": s["id"], **s["people"], "roles": [o["id"] for o in role["options"]]})
    return out


def primary_row(product: ProductConfig, groups: dict[str, list]) -> dict | None:
    """The row that is the borrower itself (a loan against property's primary applicant): in the first
    people section with a primary role, the first named row with that role, else its first named row."""
    for section in people_sections(product):
        if section["primary_role"] is None:
            continue
        rows = [r for r in groups.get(section["id"]) or [] if row_value(r, "name")]
        if rows:
            return next((r for r in rows if row_value(r, "role") == section["primary_role"]), rows[0])
    return None


def primary_applicant(product: ProductConfig, groups: dict[str, list]) -> tuple[str, str | None] | None:
    """The primary applicant as (name, the source its name came from), or None."""
    row = primary_row(product, groups)
    return (row_value(row, "name") or "", _cell_source(row.get("name"))) if row else None


def people_pans(product: ProductConfig, groups: dict[str, list]) -> list[str]:
    """Every PAN the people sections give (applicants, co-applicants, guarantors, a business's people)."""
    return [pan.upper() for s in people_sections(product) for r in groups.get(s["id"]) or []
            if (pan := row_value(r, "pan"))]


# --- The minimum ---


def missing_minimum(
    product: ProductConfig,
    *,
    borrower: str | None,
    facilities: list[str],
    amount_inr: int | None,
    customer_type: str | None,
    tenure_months: int | None,
    groups: dict[str, list[dict]],
) -> list[str]:
    """The fields of the product's minimum still missing, in the minimum's order."""
    def rows(section: str, field: str) -> bool:
        return any(row_value(r, field) for r in groups.get(section) or [])

    present = {
        "borrower": bool((borrower or "").strip()),
        "facilities": bool(facilities) or rows("facilities", "facility"),
        "amount_inr": bool(amount_inr and amount_inr > 0),
        "applicants": rows("applicants", "name"),
        "customer_type": customer_type in product.customer_types,
        "tenure_months": bool(tenure_months and tenure_months > 0),
        "properties": rows("properties", "property_type"),
    }
    # Every name config.products() accepts in a minimum (MINIMUM_FIELDS) has its test here.
    return [name for name in product.minimum if not present[name]]


def from_facility_lines(groups: dict[str, list], *, facilities: list[str], amount_inr: int) -> tuple[list[str], int]:
    """A business's facilities and requested amount, as its facility lines give them when the case leaves
    them out: the facilities named on the lines, and the sum of their amounts. Never overrides a value
    given."""
    lines = groups.get("facilities") or []
    if not facilities:
        facilities = list(dict.fromkeys(f for r in lines if (f := row_value(r, "facility"))))
    if not amount_inr:
        amount_inr = sum(int(a.replace(",", "")) for r in lines if (a := row_value(r, "amount_inr")))
    return facilities, amount_inr


# --- Provenance ---


def source_kind(source: str | None) -> str:
    """The kind of source a header value or row field names: message, identifier, document, default,
    intake or person (none given is a person's)."""
    if not source:
        return "person"
    head = source.split(":", 1)[0]
    return head if head in ("message", "identifier", "document", "default", "intake") else "person"


#: The sources a create accepts for a header value or a row field: a person, an identifier box, the form, a
#: configured default or the RM's own branch; a span of the message is checked against the message.
CREATE_SOURCES = frozenset({"person", "identifier", "intake", "default:config", "default:rm"})
_MESSAGE_SPAN = re.compile(r"message:([0-9]+)-([0-9]+)")


def create_source_problem(source: str | None, message: str | None) -> str | None:
    """Why a create may not record this source, or None: a document's page, say, is the engine's to cite,
    never a client's to claim."""
    if source is None or source in CREATE_SOURCES:
        return None
    span = _MESSAGE_SPAN.fullmatch(source)
    if span is None:
        return f"source {source!r} is not one a create may record"
    start, end = int(span[1]), int(span[2])
    if message is None or not 0 <= start < end <= len(message):
        return f"source {source!r} does not point into the message"
    return None


def counts_by_source(header: dict, groups: dict[str, list[dict]]) -> dict[str, int]:
    """How many filled fields of the header and of the rows came from each kind of source."""
    counts: dict[str, int] = {}

    def add(cell: object) -> None:
        value = cell.get("value") if isinstance(cell, dict) else getattr(cell, "value", None)
        source = cell.get("source") if isinstance(cell, dict) else getattr(cell, "source", None)
        if _clean(value) is None:
            return
        kind = source_kind(source)
        counts[kind] = counts.get(kind, 0) + 1

    for cell in header.values():
        add(cell)
    for rows in groups.values():
        for row in rows:
            for cell in row.values():
                add(cell)
    return counts


# --- What a header value is called where it is cited ---


def _declared(kind: str) -> dict:
    return load_app_config()["declared_sources"][kind]


def declared_label(has_message: bool) -> str:
    """What a value taken from the case header is called where it is cited: "Sourcing message" when the
    case has one, "Declared at intake" when it was entered on the form (config/app.yaml declared_sources)."""
    return _declared("message" if has_message else "intake")["label"]


def declared_side(has_message: bool) -> str:
    """The same, as a title for the side of a cross-check ("Declared in the sourcing message")."""
    return _declared("message" if has_message else "intake")["side"]


def declared_phrase(has_message: bool) -> str:
    """The same, inside a sentence ("is not named in the sourcing message", "... in the intake form")."""
    return _declared("message" if has_message else "intake")["phrase"]


def declared_sides() -> list[str]:
    """Every title a side of the case's own declaration may carry, however the case came about."""
    return [_declared(k)["side"] for k in ("message", "intake")]


def is_declared_label(label: str | None) -> bool:
    """Whether a source label is the name of the case's own declaration, however the case came about."""
    return label in {_declared(k)["label"] for k in ("message", "intake")}


__all__ = [
    "CASE_COLUMNS", "CREATE_SOURCES", "counts_by_source", "create_source_problem", "declared_label",
    "declared_phrase", "declared_side", "declared_sides", "from_facility_lines", "is_declared_label", "limits",
    "missing_minimum", "people_pans", "people_sections", "primary_applicant", "primary_row", "product_schema",
    "row_value", "schema", "shown", "source_kind",
]
