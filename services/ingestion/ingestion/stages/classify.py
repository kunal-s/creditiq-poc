"""Stage 3: classification from content, against the closed list (FRD F-09).

Tier 1: configured signals (required, supporting, contrary, margin over the runner-up).
Tier 2: the model reads the opening text and chooses from the closed list or `none_of_these`.
The file name is never an input. Anything unplaced goes to review and is never extracted."""

from __future__ import annotations

import re

from ..config.models import IngestionConfig
from ..llm.provider import ModelError, ModelRequest
from ..llm.recorder import ModelClient
from ..llm.schema_gen import classify_schema
from ..pageindex import Page

FLAGS = re.I | re.M


def signal_text(pages: list[Page], n: int) -> str:
    real = [p for p in pages if not p.blank]
    return "\n".join(p.text() for p in real[:n])


def score_types(cfg: IngestionConfig, text: str) -> list[dict]:
    out = []
    for tid, ts in cfg.signals.types.items():
        req = [bool(re.search(rx, text, FLAGS)) for rx in ts.required]
        sup = [rx for rx in ts.supporting if re.search(rx, text, FLAGS)]
        con = [rx for rx in ts.contrary if re.search(rx, text, FLAGS)]
        req_frac = sum(req) / len(req) if req else 1.0
        sup_frac = len(sup) / len(ts.supporting) if ts.supporting else 1.0
        eligible = all(req) and not con
        score = (0.5 + 0.5 * sup_frac) if eligible else max(0.0, 0.4 * req_frac + 0.2 * sup_frac - (0.3 if con else 0.0))
        out.append({"type": tid, "score": round(score, 4), "eligible": eligible,
                    "signals": {"required": [r for r, ok in zip(ts.required, req) if ok], "supporting": sup, "contrary": con}})
    out.sort(key=lambda c: (-c["score"], c["type"]))
    return out


def classify(cfg: IngestionConfig, pages: list[Page], model: ModelClient | None) -> dict:
    sig = cfg.signals
    text = signal_text(pages, sig.signal_pages)
    ranked = score_types(cfg, text)
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
        ranked = score_types(cfg, p.text())
        top = ranked[0]
        if top["eligible"] and top["type"] != doc_type and top["score"] >= cfg.signals.mixed_min_score:
            out.append({"page": p.no, "type": top["type"], "score": top["score"]})
    return out
