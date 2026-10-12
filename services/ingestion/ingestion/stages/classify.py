"""Stage 3: classification from content, against the closed list (FRD F-09).

Tier 1: configured signals (required, supporting, contrary, margin over the runner-up).
Tier 2: the model reads the opening text and chooses from the closed list or `none_of_these`.
The file name is never an input. Anything unplaced goes to review and is never extracted."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..config.models import IngestionConfig
from ..llm.provider import ModelError, ModelRequest
from ..llm.recorder import ModelClient
from ..llm.schema_gen import classify_schema
from ..pageindex import Page

FLAGS = re.I | re.M

_DASHES = {ord(c): "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"}
_INVISIBLE = {ord(c): None for c in "\u200b\u200c\u200d\u00ad\ufeff"}
_PAGE_BREAK = "\n\x00\n"  # \s never matches it, so a phrase cannot run across two pages


def normalise(text: str) -> str:
    """What a pattern is matched against: compatibility forms folded (ligatures, full-width), every
    dash a plain hyphen, invisible characters dropped, runs of spaces collapsed. Case is the pattern's job."""
    t = unicodedata.normalize("NFKC", text).translate(_DASHES).translate(_INVISIBLE)
    return re.sub(r"[ \t\xa0]+", " ", t)


@dataclass
class Evidence:
    """The text a type's signals are looked for in: `body` is every page read, `head` is only the
    opening lines of each page (where a document names itself)."""

    body: str
    head: str


def evidence(pages: list[Page], n: int, head_lines: int) -> Evidence:
    real = [p for p in pages if not p.blank][:n]
    body = _PAGE_BREAK.join(normalise(p.text()) for p in real)
    head = _PAGE_BREAK.join(normalise("\n".join(l.text for l in p.content_lines()[:head_lines])) for p in real)
    return Evidence(body, head)


def _search(rx: str, ev: Evidence, zone: str) -> bool:
    return re.search(rx, ev.head if zone == "head" else ev.body, FLAGS) is not None


def score_types(cfg: IngestionConfig, ev: Evidence) -> list[dict]:
    out = []
    for tid, ts in cfg.signals.types.items():
        met = [next((rx for rx in r.any if _search(rx, ev, r.zone)), None) for r in ts.required]
        sup = [x for x in ts.supporting if _search(x.rx, ev, "any")]
        con = [x.rx for x in ts.contrary if _search(x.rx, ev, x.zone)]
        req_frac = sum(m is not None for m in met) / len(met) if met else 1.0
        need = ts.corroboration or cfg.signals.corroboration
        sup_frac = min(1.0, sum(x.weight for x in sup) / need)  # saturates: listing more alternatives never lowers a score
        eligible = all(m is not None for m in met) and not con
        score = (0.5 + 0.5 * sup_frac) if eligible else max(0.0, 0.4 * req_frac + 0.2 * sup_frac - (0.3 if con else 0.0))
        out.append({"type": tid, "score": round(score, 4), "eligible": eligible,
                    "signals": {"required": [m for m in met if m is not None], "supporting": [x.rx for x in sup], "contrary": con}})
    out.sort(key=lambda c: (-c["score"], c["type"]))
    return out


def classify(cfg: IngestionConfig, pages: list[Page], model: ModelClient | None) -> dict:
    sig = cfg.signals
    ranked = score_types(cfg, evidence(pages, sig.signal_pages, sig.head_lines))
    candidates = [{"type": c["type"], "score": c["score"]} for c in ranked[:3]]
    top = ranked[0]
    others = [c["score"] for c in ranked[1:]]
    margin = top["score"] - (max(others) if others else 0.0)
    result = {"type": None, "confidence": 0.0, "tier": "none", "signals": {}, "candidates": candidates,
              "needs_review": True, "reason": None, "mixed_content": []}
    if top["eligible"] and top["score"] >= sig.classify_threshold and margin >= sig.tier1_margin:
        result.update(type=top["type"], confidence=top["score"], tier="signals", signals=top["signals"], needs_review=False,
                      reason=f"signals matched: {len(top['signals']['supporting'])} supporting, margin {margin:.2f}")
    else:
        why = "no type met the signal rules" if not top["eligible"] else f"margin {margin:.2f} below {sig.tier1_margin}"
        result["reason"] = why
        if model is None:
            result["reason"] = f"{why}; no model configured"
        else:
            tier2 = _tier2(cfg, pages, model)
            result.update({k: v for k, v in tier2.items() if k in ("type", "tier", "confidence", "needs_review", "reason", "model_error")})
            if tier2["type"]:
                entry = next(c for c in ranked if c["type"] == tier2["type"])
                blocked = _guard(cfg, tier2["type"], entry)
                if blocked:
                    suggestion = tier2["type"]
                    result.update(type=None, tier="none", confidence=0.0, needs_review=True,
                                  reason=f"the model suggested {suggestion}, but {blocked}")
                    others = [c for c in result["candidates"] if c["type"] != suggestion]
                    result["candidates"] = ([{"type": suggestion, "score": sig.tier2_confidence}] + others)[:3]
                else:
                    result["signals"] = entry["signals"]
    if result["type"] and sig.mixed_content_check:
        result["mixed_content"] = _mixed(cfg, pages, result["type"])
    return result


def _guard(cfg: IngestionConfig, type_id: str, entry: dict) -> str | None:
    """Why the document does not support the model's choice, or None."""
    g = cfg.signals.tier2_guard
    if g.block_on_contrary and entry["signals"]["contrary"]:
        return "the document carries a signal that rules that type out (" + entry["signals"]["contrary"][0] + ")"
    required = cfg.signals.types[type_id].required
    if required and len(entry["signals"]["required"]) / len(required) < g.min_required_fraction:
        return f"it has {len(entry['signals']['required'])} of the {len(required)} required signals of that type"
    return None


def _tier2(cfg: IngestionConfig, pages: list[Page], model: ModelClient) -> dict:
    ids = list(cfg.document_types.by_id())
    types = "\n".join(f"- {d.document_type}: {d.display_name} ({d.category})" for d in cfg.document_types.documents)
    lines, budget = [], cfg.llm.classify_chars
    for p in pages:
        for l in p.content_lines():
            row = f"{l.id}: {l.text}"
            if budget - len(row) < 0:
                break
            budget -= len(row) + 1
            lines.append(row)
    pr = cfg.llm.prompts["classify"]
    req = ModelRequest("classify", pr.system.strip(), pr.user.replace("{{types}}", types).replace("{{lines}}", "\n".join(lines)).strip(), classify_schema(ids))
    try:
        ans = model.call(req)
    except ModelError as e:
        return {"type": None, "tier": "none", "confidence": 0.0, "needs_review": True, "reason": f"model unavailable ({e.code}): {e}", "model_error": e.code}
    t = ans.get("type")
    if t in ids:
        return {"type": t, "tier": "model", "confidence": cfg.signals.tier2_confidence, "needs_review": False, "reason": str(ans.get("reason", ""))[:300]}
    return {"type": None, "tier": "none", "confidence": 0.0, "needs_review": True, "reason": "the model found none of the listed types: " + str(ans.get("reason", ""))[:300]}


def _mixed(cfg: IngestionConfig, pages: list[Page], doc_type: str) -> list[dict]:
    """Pages whose own content matches a different type outright (F-08 guard; no splitting)."""
    out = []
    for p in pages:
        if p.blank:
            continue
        ranked = score_types(cfg, evidence([p], 1, cfg.signals.head_lines))
        top = ranked[0]
        if top["eligible"] and top["type"] != doc_type and top["score"] >= cfg.signals.mixed_min_score:
            out.append({"page": p.no, "type": top["type"], "score": top["score"]})
    return out
