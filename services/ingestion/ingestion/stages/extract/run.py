"""Stage 4: extract one instance (FRD F-15). Deterministic first, the model for what remains,
every value verified on its page, tables from word positions."""

from __future__ import annotations

from ...config.models import FieldDef, FieldRule, IngestionConfig
from ...llm.recorder import ModelClient
from ...pageindex import Page
from . import llm_extract
from .fields import Found, extract_scalar
from .normalise import normalise
from .tables import build_table


def _kind(f: FieldDef, rule: FieldRule) -> str:
    return rule.normaliser or {"date": "date", "number": "number"}.get(f.type, "text")


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
    value, why = normalise(raw, _kind(f, rule))
    if why:
        return {**base, "status": "missing", "reason": why, "value": None, "raw_text": raw}
    return {**base, "status": "found", "reason": None, "value": value, "raw_text": raw}


def _missing(f: FieldDef, rule: FieldRule, reason: str) -> dict:
    return {"status": "missing", "reason": reason, "value": None, "raw_text": None, "method": None, "source": None,
            "required": f.required, "key_field": bool(rule.key_field) or f.required}


def extract_instance(cfg: IngestionConfig, doc_type: str, pages: list[Page], model: ModelClient | None) -> dict:
    td = cfg.document_types.by_id()[doc_type]
    rules = cfg.fields.types.get(doc_type)
    rules_f = rules.fields if rules else {}
    out_fields: dict[str, dict] = {}
    pending: list[FieldDef] = []
    for f in td.schema_.fields:
        rule = rules_f.get(f.name, FieldRule())
        accept = None if f.type == "array" else (lambda c, k=_kind(f, rule): normalise(str(c.raw), k)[1] is None)
        found = extract_scalar(rule, pages, accept) if (rule.identifier or rule.aliases or rule.patterns) else None
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
        found, reasons, trace = llm_extract.fill(cfg, td.display_name, pending, hints, pages, model)
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
        tr = trules.get(t.name)
        if tr is None:
            tables[t.name] = {"status": "missing", "reason": "no_rule", "columns": [c.name for c in t.columns], "rows": [], "source": None, "repairs": [], "unparsed": 0}
            continue
        res = build_table(tr, t.columns, pages, cfg.routing.reading)
        if res is None:
            tables[t.name] = {"status": "missing", "reason": "table_not_found", "columns": [c.name for c in t.columns], "rows": [], "source": None, "repairs": [], "unparsed": 0}
            continue
        src = {"sheet": res.sheet} if res.sheet else {"page_start": res.page_start, "page_end": res.page_end, "bbox": res.bbox}
        tables[t.name] = {"status": "found", "reason": None, "columns": res.columns, "rows": res.rows, "source": src, "repairs": res.repairs, "unparsed": res.unparsed}
    return {"fields": out_fields, "tables": tables, "trace": trace}
