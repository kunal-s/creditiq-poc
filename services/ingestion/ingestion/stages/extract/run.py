"""Stage 4: extract one instance (FRD F-15). Deterministic first, the model for what remains,
every value verified on its page, tables from word positions."""

from __future__ import annotations

import re

from ...config.models import FieldDef, FieldRule, IngestionConfig, ModelTable, PageScope
from ...contracts import CaseType
from ...llm.recorder import ModelClient
from ...pageindex import Page
from . import llm_extract, llm_tables
from . import kwtables, units
from .evidence import evidence_for_lines
from .fields import Found, extract_scalar
from .normalise import normalise, number_forms
from ...util import fold
from .tables import build_table


def _kind(f: FieldDef, rule: FieldRule) -> str:
    return rule.normaliser or {"date": "date", "number": "number", "boolean": "present"}.get(f.type, "text")


def _finish(f: FieldDef, rule: FieldRule, found: Found) -> dict:
    src = found.evidence.source()
    base = {"method": found.method, "source": src, "required": f.required, "key_field": bool(rule.key_field) or f.required}
    if f.type == "array":
        raw_list = found.raw if isinstance(found.raw, list) else [found.raw]
        if f.items and f.items.type == "object":
            keys = [s.name for s in f.items.fields]
            value = [e if isinstance(e, dict) else {keys[0]: e, **{k: None for k in keys[1:]}} for e in raw_list]
            value = [{k: e.get(k) for k in keys} for e in value]
            raw_text = "; ".join(str(e.get(keys[0])) for e in value)
        else:
            value, raw_text = list(raw_list), "; ".join(map(str, raw_list))
        return {**base, "status": "found", "reason": None, "value": value, "raw_text": raw_text}
    raw = str(found.raw)
    if found.corrected:
        # Read by undoing a scan's confusion, confirmed by a check (Story 2.6): the value read, the text as printed,
        # and a person confirms it.
        return {**base, "status": "found", "reason": None, "value": found.corrected, "raw_text": raw,
                "correction": f'printed "{raw}", read as {found.corrected} by a check on this document; please confirm'}
    value, why = normalise(raw, _kind(f, rule))
    if why:
        return {**base, "status": "missing", "reason": why, "value": None, "raw_text": raw}
    return {**base, "status": "found", "reason": None, "value": value, "raw_text": raw}


def _missing(f: FieldDef, rule: FieldRule, reason: str) -> dict:
    return {"status": "missing", "reason": reason, "value": None, "raw_text": None, "method": None, "source": None,
            "required": f.required, "key_field": bool(rule.key_field) or f.required}


def scoped_pages(scopes: list[PageScope], pages: list[Page]) -> list[Page]:
    """The pages the model reads: the first page, and each configured section (its first match and the pages after it)."""
    keep = {pages[0].no} if pages else set()
    for sc in scopes:
        rx = re.compile(sc.match, re.I)
        for i, p in enumerate(pages):
            if rx.search(p.text()):
                keep.update(q.no for q in pages[i:i + sc.span])
                break
    return [p for p in pages if p.no in keep]


def _extract_instance(cfg: IngestionConfig, doc_type: str, pages: list[Page], model: ModelClient | None,
                     prompt: str = "extract", subs: dict[str, str] | None = None) -> dict:
    td = cfg.document_types.by_id()[doc_type]
    rules = cfg.fields.types.get(doc_type)
    rules_f = rules.fields if rules else {}
    out_fields: dict[str, dict] = {}
    pending: list[FieldDef] = []
    model_first = bool(rules and rules.extraction == "model" and model is not None)
    for f in td.schema_.fields:
        rule = rules_f.get(f.name, FieldRule())
        if model_first and not rule.identifier and rule.llm is not False:
            out_fields[f.name] = _missing(f, rule, "not_found")
            pending.append(f)
            continue
        accept = None if f.type == "array" else (lambda c, k=_kind(f, rule): normalise(str(c.raw), k)[1] is None)
        found = (extract_scalar(rule, pages, accept, cfg.fields.identifier_reading)
                 if (rule.identifier or rule.aliases or rule.patterns) else None)
        if found:
            out_fields[f.name] = _finish(f, rule, found)
            if out_fields[f.name]["status"] == "found":
                continue
        else:
            out_fields[f.name] = _missing(f, rule, "not_found")
        allowed = rule.llm is True or (rule.llm is None and cfg.llm.fill == "missing")
        if allowed and model is not None and rule.llm is not False:
            pending.append(f)

    trace: list[dict] = []
    if pending and model is not None:
        hints = {f.name: rules_f.get(f.name, FieldRule()).llm_hint for f in pending}
        read = scoped_pages(rules.model_pages, pages) if model_first and rules.model_pages else pages
        found, reasons, trace = llm_extract.fill(cfg, td.display_name, pending, hints, read, model, prompt, subs)
        for f in pending:
            rule = rules_f.get(f.name, FieldRule())
            if f.name in found:
                out_fields[f.name] = _finish(f, rule, found[f.name])
            elif f.name in reasons:
                out_fields[f.name] = _missing(f, rule, reasons[f.name])
    elif pending and model is None:
        for f in pending:
            out_fields[f.name]["reason"] = "not_found"

    tables: dict[str, dict] = {}
    trules = rules.tables if rules else {}
    for t in td.schema_.tables:
        tr = trules.get(t.name) or []
        if not tr and not (rules and t.name in rules.table_keywords):
            tables[t.name] = {"status": "missing", "reason": "no_rule", "columns": [c.name for c in t.columns], "rows": [], "source": None, "repairs": [], "unparsed": 0, "method": "rules"}
            continue
        variants = tr if isinstance(tr, list) else [tr]
        kt = rules.table_keywords.get(t.name) if rules else None
        # By its headings first (any layout); the configured layouts stay as a fallback until they are retired.
        res = kwtables.read(cfg, kt, t.columns, pages, list(rules.table_keywords.values())) if kt else None
        if res is None:
            res = next((r for v in variants if (r := build_table(v, t.columns, pages, cfg.routing.reading))), None)
            if res is not None:
                res.method = "layout"
        spec = rules.model_tables.get(t.name) if rules else None
        shown = None
        if spec is None and kt is not None and kt.model:
            # No header found: the model maps the table from the pages the keyword scorer chooses for it.
            spec = ModelTable(label_column=kt.label, hints=kt.hints, max_pages=kt.model_pages)
            shown = kwtables.candidate_pages(cfg, kt, pages)
        if res is None and spec is not None and model is not None:
            # No header or layout found it: the model maps its rows, and code reads every value from the page (llm_tables).
            res, table_trace = llm_tables.map_table(cfg, td.display_name, t.name, t.description or t.name, t.columns, spec,
                                                    pages, model, dash_is_zero=any(v.dash_is_zero for v in variants)
                                                    or bool(kt and kt.dash_is_zero), shown=shown)
            trace += table_trace
        if res is None:
            tables[t.name] = {"status": "missing", "reason": "table_not_found", "columns": [c.name for c in t.columns], "rows": [], "source": None, "repairs": [], "unparsed": 0, "method": "rules"}
            continue
        src = {"sheet": res.sheet} if res.sheet else {"page_start": res.page_start, "page_end": res.page_end, "bbox": res.bbox}
        tables[t.name] = {"status": "found", "reason": None, "columns": res.columns, "rows": res.rows, "source": src, "repairs": res.repairs, "unparsed": res.unparsed, "method": res.method}
    _unit(cfg, td, rules, pages, out_fields, tables)
    return {"fields": out_fields, "tables": tables, "trace": trace}


def _unit(cfg: IngestionConfig, td, rules, pages: list[Page], out_fields: dict, tables: dict) -> None:
    """The unit the document's amounts are printed in (fields.yaml units): stated in a table's caption or a page's
    title lines. It fills `amount_unit` when the field's own rules found none, as the engine's name for it; a value
    they found is put in that name. A type that must state its unit and does not is marked so, never read as rupees."""
    names = {f.name for f in td.schema_.fields}
    if "amount_unit" not in names:
        return
    before: dict[int, int] = {}
    for t in tables.values():
        rows = t.get("rows") or []
        src = rows[0].get("source", {}) if rows else {}
        page = next((p for p in pages if p.no == src.get("page")), None)
        ids = src.get("line_ids") or []
        if page and ids:
            idx = next((i for i, l in enumerate(page.content_lines()) if l.id == ids[0]), None)
            if idx is not None:
                before[page.no] = max(before.get(page.no, -1), idx - 1)
    zones = {}
    if cfg.keywords:
        from .. import keywords as K
        zones = {p.no: [l for l, z in K.line_zones(cfg.keywords, p) if z in ("title", "footer")] for p in pages}
    f = out_fields.get("amount_unit") or {}
    if f.get("status") == "found":
        named = units.in_line(f"in {f.get('raw_text') or f.get('value')}", cfg.fields.units)
        if named:
            f["value"] = named
        return
    got = units.find(pages, cfg.fields.units, before, zones)
    if got is None:
        if td.document_type in cfg.fields.units.required:
            out_fields["amount_unit"] = {**f, "status": "missing", "reason": "unit_not_stated", "value": None}
        return
    page = next(p for p in pages if p.no == got.page)
    line = next(l for l in page.content_lines() if l.id == got.line_id)
    found = Found(got.text, "pattern", evidence_for_lines(page, [(line, 0, len(line.text))]))
    rule = (rules.fields.get("amount_unit") if rules else None) or FieldRule()
    fd = next(x for x in td.schema_.fields if x.name == "amount_unit")
    out_fields["amount_unit"] = {**_finish(fd, rule, found), "value": got.name}


def _extract_case_type(cfg: IngestionConfig, ct: CaseType, pages: list[Page], model: ModelClient | None) -> dict:
    """A document of a case document type (F-09.8, F-15.8): only the model reads it, since no rule in the
    published configuration knows the type. Named fields are read with the extraction prompt, each a key
    field; with none named, the model proposes the fields itself and every one is marked discovered."""
    out: dict[str, dict] = {}
    trace: list[dict] = []
    if ct.fields:
        defs = [FieldDef(name=f.name, type="string") for f in ct.fields]
        rule = FieldRule(key_field=True)
        for f in defs:
            out[f.name] = {**_missing(f, rule, "not_found" if model is not None else "no_model"), "origin": "named"}
        if model is not None:
            found, reasons, trace = llm_extract.fill(cfg, ct.name, defs, {f.name: f.hint for f in ct.fields}, pages, model)
            for f in defs:
                if f.name in found:
                    out[f.name] = {**_finish(f, rule, found[f.name]), "origin": "named"}
                elif f.name in reasons:
                    out[f.name] = {**_missing(f, rule, reasons[f.name]), "origin": "named"}
    elif model is not None:
        found, trace = llm_extract.discover(cfg, ct.name, ct.description, pages, model)
        rule = FieldRule()
        for name, (label, got) in found.items():
            out[name] = {**_finish(FieldDef(name=name, type="string"), rule, got), "origin": "discovered", "label": label}
    gaps = _gap_fields(cfg, ct, pages, model, taken=set(out), trace=trace)
    # A gap field the model also proposed under its own label is one fact: kept under the gap field's
    # name, which the checks read, with the document's label.
    for gname, g in gaps.items():
        same = [k for k, f in out.items() if f.get("origin") == "discovered" and f["status"] == "found"
                and fold(str(f["raw_text"])) == fold(str(g["raw_text"]))]
        if same:
            g["label"] = out[same[0]].get("label")
            for k in same:
                del out[k]
    out.update(gaps)
    return {"fields": out, "tables": {}, "trace": trace}


def _gap_fields(cfg: IngestionConfig, ct: CaseType, pages: list[Page], model: ModelClient | None, *,
                taken: set[str], trace: list[dict]) -> dict[str, dict]:
    """F-15.9: the published gap fields, read the same way from every such document: identifiers by
    pattern first, then the model with each field's hint. A field the person named, or the model
    proposed under the same name, is read once. Only values found are reported."""
    out: dict[str, dict] = {}
    pending: list[FieldDef] = []
    for name, rule in cfg.fields.gap_fields.items():
        if name in taken:
            continue
        f = FieldDef(name=name, type="string")
        found = extract_scalar(rule, pages, lambda c, k=_kind(f, rule): normalise(str(c.raw), k)[1] is None,
                               cfg.fields.identifier_reading) if (rule.identifier or rule.aliases or rule.patterns) else None
        done = _finish(f, rule, found) if found else None
        if done and done["status"] == "found":
            out[name] = {**done, "origin": "gap"}
        elif model is not None and rule.llm is not False:
            pending.append(f)
    if pending and model is not None:
        hints = {f.name: cfg.fields.gap_fields[f.name].llm_hint for f in pending}
        found, _, more = llm_extract.fill(cfg, ct.name, pending, hints, pages, model)
        trace.extend(more)
        for f in pending:
            if f.name in found:
                done = _finish(f, cfg.fields.gap_fields[f.name], found[f.name])
                if done["status"] == "found":
                    out[f.name] = {**done, "origin": "gap"}
    return out


def extract_instance(cfg: IngestionConfig, doc_type: str, pages: list[Page], model: ModelClient | None,
                     prompt: str = "extract", subs: dict[str, str] | None = None) -> dict:
    """One document's fields and tables, its amounts read in the configured number forms (fields.yaml numbers)."""
    with number_forms(cfg.fields.numbers):
        return _extract_instance(cfg, doc_type, pages, model, prompt, subs)


def extract_case_type(cfg: IngestionConfig, ct: CaseType, pages: list[Page], model: ModelClient | None) -> dict:
    with number_forms(cfg.fields.numbers):
        return _extract_case_type(cfg, ct, pages, model)
