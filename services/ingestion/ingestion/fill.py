"""Filling a case's pending fields (Epic 6): a required field its own documents left empty is read from other pages
of the case's files, the leftovers first (Story 6.2) and then, for a field that may be swept, the pages of other
document types (Story 6.8). The engine names the file, the pages and the fields; this reads them the way every field is
read: an identifier by its form and check first, then the model on the pages that score highest for the fields
(Story 6.7), each value checked on its page (Story 6.6). A value is never adjusted toward another document's."""

from __future__ import annotations

from datetime import date

from .config.models import FieldDef, IngestionConfig, RequiredField
from .contracts import FillRequest, FillResult, FillValue
from .llm.recorder import ModelClient
from .pageindex import Page
from .stages.extract import llm_extract
from .stages.extract.fields import extract_scalar
from .stages.extract.normalise import normalise, number_forms
from .stages.extract.run import _finish, _kind, cue_pages, cue_scores

_TYPES = {"amount": "number", "date": "date"}


def _key(name: str, period_end: str | None) -> str:
    return f"{name}__{period_end.replace('-', '')}" if period_end else name


def _hint(rule: RequiredField, period_end: str | None) -> str | None:
    if not period_end:
        return rule.llm_hint
    d = date.fromisoformat(period_end)
    return f"{rule.llm_hint or ''}; for the financial year ended {d.day} {d:%B} {d.year} only".strip("; ")


def fill(cfg: IngestionConfig, req: FillRequest, pages: list[Page], model: ModelClient | None) -> FillResult:
    with number_forms(cfg.fields.numbers):
        return _fill(cfg, req, pages, model)


def _fill(cfg: IngestionConfig, req: FillRequest, pages: list[Page], model: ModelClient | None) -> FillResult:
    rules = cfg.fields.required_fields
    asked = [f for f in req.fields if f.name in rules and rules[f.name].kind in ("text", "identifier", "date", "amount")]
    allowed = [p for p in pages if p.no in set(req.pages)]
    out = FillResult()
    if not asked or not allowed:
        return out
    pending = {}
    for f in asked:
        rule = rules[f.name]
        fdef = FieldDef(name=_key(f.name, f.period_end), type=_TYPES.get(rule.kind, "string"))
        if rule.identifier and not f.period_end:
            found = extract_scalar(rule, allowed, lambda c, k=_kind(fdef, rule): normalise(str(c.raw), k)[1] is None,
                                   cfg.fields.identifier_reading)
            done = _finish(fdef, rule, found) if found else None
            if done and done["status"] == "found":
                out.found.append(_value(f.name, f.period_end, done, "rules"))
                continue
        if rule.llm is not False:
            pending[fdef.name] = (f, fdef, rule)
    by_key = {k: r for k, (_, _, r) in pending.items()}
    if pending and req.select and not any(cue_scores(by_key, list(pending), allowed)):
        out.trace.append({"call": "fill", "skipped": "no page has a cue for the fields"})
        return out          # the sweep: pages of another type that never name the field are not read
    if pending and model is not None:
        read = cue_pages(by_key, list(pending), allowed, cfg.llm.fill_pages) if req.select else allowed
        out.pages_read = [p.no for p in read]
        hints = {k: _hint(r, f.period_end) for k, (f, _, r) in pending.items()}
        found, _, trace = llm_extract.fill(cfg, "case document", [d for _, d, _ in pending.values()], hints, read, model,
                                           "fill")
        out.trace += trace
        for k, got in found.items():
            f, fdef, rule = pending[k]
            done = _finish(fdef, rule, got)
            if done["status"] == "found":
                out.found.append(_value(f.name, f.period_end, done, "model"))
    return out


def _value(name: str, period_end: str | None, done: dict, method: str) -> FillValue:
    src = done.get("source") or {}
    return FillValue(field=name, period_end=period_end, value=done["value"], raw_text=str(done["raw_text"]), method=method,
                     page=int(src.get("page") or 0), bbox=src.get("bbox"), line=src.get("line"))
