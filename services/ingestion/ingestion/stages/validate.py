"""Stage 5: validation (FRD F-15, F-17). Format and checksum checks per field, then the named
cross-field and table rules from validators.yaml. A validator reports; it never edits a value."""

from __future__ import annotations

import re
from typing import Callable

from ..config.models import IngestionConfig, ValidatorRule
from ..pageindex import Page
from .extract import identifiers


def _val(fields: dict, name: str):
    f = fields.get(name)
    return f["value"] if f and f["status"] == "found" else None


def _check(rule_id: str, label: str, outcome: str, detail: str, severity: str, fields=(), tables=(), kind: str = "rule") -> dict:
    return {"id": rule_id, "label": label, "outcome": outcome, "detail": detail, "severity": severity,
            "fields": list(fields), "tables": list(tables), "kind": kind}


def _fail(sev: str) -> str:
    return "fail" if sev == "fail" else "warn"


# --- rule kinds --------------------------------------------------------------------------------

def k_required(r: ValidatorRule, td, fields, tables, pages):
    missing = [f.name for f in td.schema_.fields if f.required and (fields.get(f.name, {}).get("status") != "found")]
    if missing:
        return _check(r.id, r.label or r.id, _fail(r.severity), "Required fields missing: " + ", ".join(missing), r.severity, missing)
    return _check(r.id, r.label or r.id, "pass", "All required fields were found.", r.severity)


def k_cin_year(r, td, fields, tables, pages):
    cin, date = _val(fields, r.params["cin"]), _val(fields, r.params["date"])
    if not cin or not date:
        return None
    ok = len(cin) >= 12 and cin[8:12] == str(date)[:4]
    return _check(r.id, r.label or r.id, "pass" if ok else _fail(r.severity),
                  f"The year in the CIN ({cin[8:12]}) {'matches' if ok else 'does not match'} the date of incorporation ({str(date)[:4]}).",
                  r.severity, [r.params["cin"], r.params["date"]])


def k_pan_char(r, td, fields, tables, pages):
    pan = _val(fields, r.params["pan"])
    if not pan or len(pan) < 4:
        return None
    ok = pan[3] == r.params["expect"]
    return _check(r.id, r.label or r.id, "pass" if ok else _fail(r.severity),
                  f"The fourth character of the PAN is {pan[3]}; {r.params['expect']} is expected.", r.severity, [r.params["pan"]])


def k_date_order(r, td, fields, tables, pages):
    a, b = _val(fields, r.params["first"]), _val(fields, r.params["second"])
    if not a or not b:
        return None
    ok = str(a) <= str(b)
    return _check(r.id, r.label or r.id, "pass" if ok else _fail(r.severity), f"{a} is {'not after' if ok else 'after'} {b}.", r.severity, [r.params["first"], r.params["second"]])


def k_balance(r, td, fields, tables, pages):
    p = r.params
    t = tables.get(p["table"])
    if not t or t["status"] != "found":
        return None
    num = lambda row, k: row["cells"].get(k) if isinstance(row["cells"].get(k), (int, float)) else None  # noqa: E731
    rows = [x for x in t["rows"] if num(x, p["balance"]) is not None]
    bad = 0
    for prev, cur in zip(rows, rows[1:]):
        exp = num(prev, p["balance"]) + (num(cur, p["credit"]) or 0) - (num(cur, p["debit"]) or 0)
        bad += abs(exp - num(cur, p["balance"])) > 0.005
    notes = [f"{bad} of {max(len(rows) - 1, 0)} rows break the running balance"]
    closing, opening = _val(fields, p.get("closing", "")), _val(fields, p.get("opening", ""))
    ok = bad == 0
    if rows and closing is not None:
        same = abs(num(rows[-1], p["balance"]) - closing) < 0.005
        ok &= same
        notes.append(f"the last balance {'agrees' if same else 'does not agree'} with the closing balance")
    if rows and opening is not None:
        first = rows[0]
        implied = num(first, p["balance"]) - (num(first, p["credit"]) or 0) + (num(first, p["debit"]) or 0)
        same = abs(implied - opening) < 0.005
        ok &= same
        notes.append(f"the opening row {'agrees' if same else 'does not agree'} with the opening balance")
    if t.get("repairs"):
        notes.append(f"{len(t['repairs'])} cell(s) repaired arithmetically")
    return _check(r.id, r.label or r.id, "pass" if ok else _fail(r.severity), "; ".join(notes) + ".", r.severity,
                  [x for x in (p.get("opening"), p.get("closing")) if x], [p["table"]])


def k_rows_equal(r, td, fields, tables, pages):
    p = r.params
    t = tables.get(p["table"])
    if not t or t["status"] != "found":
        return None
    rx = re.compile(p["pattern"], re.I)
    vals = [x["cells"].get(p["column"]) for x in t["rows"] if rx.search(str(x["cells"].get(p["label_column"]) or ""))]
    i, j = p["compare"]
    if len(vals) <= max(i, j) or vals[i] is None or vals[j] is None:
        return None
    ok = abs(vals[i] - vals[j]) < 0.005
    return _check(r.id, r.label or r.id, "pass" if ok else _fail(r.severity), f"{vals[i]:,} and {vals[j]:,} {'agree' if ok else 'differ'}.", r.severity, [], [p["table"]])


def k_blank_after_label(r, td, fields, tables, pages):
    blanks = []
    for label in r.params["labels"]:
        rx = re.compile(re.escape(label), re.I)
        for pg in pages:
            for l in pg.content_lines():
                if rx.search(l.text) and not rx.sub("", l.text).strip():
                    blanks.append(label)
                    break
    if blanks:
        return _check(r.id, r.label or r.id, _fail(r.severity), "Left blank: " + ", ".join(sorted(set(blanks))) + ".", r.severity)
    return _check(r.id, r.label or r.id, "pass", "No blank signature block found.", r.severity)


KINDS: dict[str, Callable] = {
    "required": k_required, "cin_year_matches_date": k_cin_year, "pan_entity_char": k_pan_char,
    "date_order": k_date_order, "balance_continuity": k_balance, "rows_equal": k_rows_equal,
    "blank_after_label": k_blank_after_label,
}


def validate_instance(cfg: IngestionConfig, doc_type: str, pages: list[Page], fields: dict, tables: dict) -> list[dict]:
    td = cfg.document_types.by_id()[doc_type]
    checks: list[dict] = []
    rules = cfg.fields.types.get(doc_type)
    for name, rule in (rules.fields if rules else {}).items():
        f = fields.get(name)
        if not f or f["status"] != "found":
            continue
        for v in rule.validators:
            kind, _, arg = v.partition(":")
            if kind != "format":
                continue
            ok, detail = identifiers.check(arg, str(f["raw_text"]))
            checks.append(_check(f"format:{name}", f"{name} format", "pass" if ok else "fail", detail, "fail",
                                 [name], kind="checksum" if (not ok and "check digit" in detail) else "format"))
    for r in cfg.validators.rules:
        if doc_type not in r.types:
            continue
        fn = KINDS.get(r.kind)
        if fn is None:
            checks.append(_check(r.id, r.label or r.id, "warn", f"Unknown validator kind {r.kind}.", r.severity))
            continue
        c = fn(r, td, fields, tables, pages)
        if c:
            checks.append(c)
    return checks
