"""The second pass (FRD F-08.1, F-08.2): the other documents of the same category inside one file.

A file is classified as one type, but a bundle may hold several documents of one category: a
certificate of incorporation, the company's PAN letter and its memorandum, scanned together. This
pass looks for the other types of the classified type's category (document_types.json `category`).

1. Page by page, each type's own signals are scored on that page alone (classify.score_types). A
   page where a type of the group is eligible opens a part of that type; the pages after it that
   carry no signals of their own stay with it. A page eligible for the file's own type closes it.
2. Each part is split into instances by the type's own rule and read like any document: rules,
   then the model with the `sibling` prompt, every value verified on its page.
3. A part counts only when at least `min_key_fields` of its key fields (required, or named in the
   type's identity) were found. A part that does not is dropped and its pages stay with the file's
   own document; so is a part that would take every page of the file, since the classification
   of the file then stands.

Signals decide where a part may be, and verified values decide whether it is there: a certificate
that prints the company's PAN does not create a PAN letter, because no page of it is headed as one.
Each part is read on its own pages only (principle 7), never against the file's other documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config.models import IngestionConfig
from ..llm.recorder import ModelClient
from ..pageindex import Page
from .classify import evidence, score_types
from .extract.run import extract_instance
from .instances import split_instances
from .validate import validate_instance


@dataclass
class Part:
    """One document of another type found in the file, read and validated."""

    type: str
    pages: list[Page]
    extracted: dict
    checks: list[dict]
    classification: dict


@dataclass
class Result:
    parts: list[Part] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)

    @property
    def taken(self) -> set[int]:
        """The page numbers the parts found here hold; they are no longer the file's own document's."""
        return {p.no for part in self.parts for p in part.pages}

    def to_json(self) -> list[dict]:
        return self.trace


def group_of(cfg: IngestionConfig, doc_type: str) -> list[str]:
    """The other types of `doc_type`'s category, in configuration order."""
    by_id = cfg.document_types.by_id()
    cat = by_id[doc_type].category
    return [t for t in by_id if t != doc_type and by_id[t].category == cat]


def _page_signals(cfg: IngestionConfig, page: Page, types: set[str]) -> list[dict]:
    """The types among `types` whose signals are met on this page alone, best first."""
    ranked = score_types(cfg, evidence([page], 1, cfg.signals.head_lines))
    floor = cfg.llm.siblings.page_min_score
    return [r for r in ranked if r["type"] in types and r["eligible"] and r["score"] >= floor]


def runs(cfg: IngestionConfig, doc_type: str, pages: list[Page]) -> list[tuple[str, list[Page], dict]]:
    """Consecutive pages that belong to another type of the group: (type, pages, signals of its opening page)."""
    group = group_of(cfg, doc_type)
    if not group:
        return []
    watch = {doc_type, *group}
    out: list[tuple[str, list[Page], dict]] = []
    cur: tuple[str, list[Page], dict] | None = None
    for p in pages:
        if p.blank:
            continue
        hits = _page_signals(cfg, p, watch)
        if hits:
            top = hits[0]
            if any(h["type"] == doc_type for h in hits):
                cur = None                      # the file's own type: the part above ends here
                continue
            if cur is None or cur[0] != top["type"]:
                cur = (top["type"], [], top)
                out.append(cur)
            cur[1].append(p)
        elif cur is not None:
            cur[1].append(p)                    # a page with no signals of its own continues the part above
    return out


def _key_fields(cfg: IngestionConfig, doc_type: str) -> set[str]:
    td = cfg.document_types.by_id()[doc_type]
    tf = cfg.fields.types.get(doc_type)
    return {f.name for f in td.schema_.fields if f.required} | set(tf.identity.values() if tf else ())


def find(cfg: IngestionConfig, doc_type: str, pages: list[Page], model: ModelClient | None) -> Result:
    res = Result()
    sc = cfg.llm.siblings
    if not sc.enabled or not doc_type:
        return res
    by_id = cfg.document_types.by_id()
    real = [p for p in pages if not p.blank]
    subs = {"primary_name": by_id[doc_type].display_name}
    for tid, run_pages, opening in runs(cfg, doc_type, pages):
        nos = [p.no for p in run_pages]
        if len(run_pages) == len(real):
            res.trace.append({"type": tid, "pages": nos, "outcome": "dropped", "reason": "whole_file"})
            continue
        keys = _key_fields(cfg, tid)
        _front, groups = split_instances(cfg, tid, run_pages)
        for ipages in groups:
            e = extract_instance(cfg, tid, ipages, model, prompt="sibling", subs=subs)
            found = sorted(k for k in keys if e["fields"].get(k, {}).get("status") == "found")
            entry = {"type": tid, "pages": [p.no for p in ipages], "key_fields_found": found}
            if len(found) < sc.min_key_fields:
                why = next((f["reason"] for f in e["fields"].values() if str(f.get("reason") or "").startswith("model_unavailable")), None)
                res.trace.append({**entry, "outcome": "dropped", "reason": why or "key_fields_not_found"})
                continue
            checks = validate_instance(cfg, tid, ipages, e["fields"], e["tables"])
            cls = {"type": tid, "confidence": opening["score"], "tier": "sibling", "signals": opening["signals"],
                   "candidates": [{"type": tid, "score": opening["score"]}], "needs_review": True,
                   "reason": f"found inside a file read as {by_id[doc_type].display_name}", "mixed_content": []}
            res.parts.append(Part(tid, ipages, e, checks, cls))
            res.trace.append({**entry, "outcome": "found", "score": opening["score"], "model_trace": e["trace"]})
    if res.parts and {p.no for p in real} <= res.taken:
        # Together the parts would leave the file's own type no page: its classification stands, and they are dropped.
        for t in res.trace:
            if t["outcome"] == "found":
                t.update(outcome="dropped", reason="whole_file")
        res.parts = []
    return res
