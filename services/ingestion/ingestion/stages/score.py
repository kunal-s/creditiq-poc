"""Stage 6: confidence and decision (FRD F-17).

field confidence = min(applicable caps) x sum(weight_i x component_i). Components: classification,
page grade, reading trust, validation, agreement. A model's own confidence is never a component.
The decision feeds the review queue; it is not a credit decision."""

from __future__ import annotations

from ..config.models import IngestionConfig
from ..pageindex import Page
from .read import GRADE_ORDER

AGREEMENT_MODEL = 0.6  # a value read only by the model (then verified on the page) agrees less than a pattern read


def _val_component(checks: list[dict]) -> float:
    if not checks:
        return 1.0
    if any(c["outcome"] == "fail" for c in checks):
        return 0.0
    if any(c["outcome"] == "warn" for c in checks):
        return 0.5
    return 1.0


def score_field(cfg: IngestionConfig, name: str, f: dict, cls_conf: float, pages: dict[int, Page], checks: list[dict]) -> dict:
    cc = cfg.confidence
    if f["status"] != "found":
        return {**f, "confidence": 0.0, "components": {}, "needs_review": False}
    src = f.get("source") or {}
    page = pages.get(src.get("page", -1))
    grade = page.grade if page else "A"
    mine = [c for c in checks if name in c["fields"]]
    comps = {
        "classification": round(cls_conf, 4),
        "page_grade": cc.grade_scores[grade],
        "reading_trust": round(page.reading_trust if page else 1.0, 4),
        "validation": _val_component(mine),
        "agreement": AGREEMENT_MODEL if f["method"] == "model" else cc.single_read,
    }
    base = sum(cc.weights[k] * comps[k] for k in cc.weights)
    caps = [1.0]
    if any(c.get("kind") == "checksum" and c["outcome"] == "fail" for c in mine):
        caps.append(cc.caps["checksum_fail"])
    if grade == "C":
        caps.append(cc.caps["grade_c_page"])
    conf = round(min(caps) * base, 4)
    return {**f, "confidence": conf, "components": comps, "needs_review": bool(f["key_field"] and conf < cc.key_field_review_threshold)}


def score_table(cfg: IngestionConfig, name: str, t: dict, pages: dict[int, Page], checks: list[dict]) -> dict:
    if t["status"] != "found":
        return {**t, "confidence": 0.0}
    src = t["source"] or {}
    nos = range(src.get("page_start", 1), src.get("page_end", 1) + 1) if "page_start" in src else [p for p in pages]
    grades = [pages[n].grade for n in nos if n in pages] or ["A"]
    g = cfg.confidence.grade_scores[max(grades, key=lambda x: GRADE_ORDER[x])]
    mine = [c for c in checks if name in c["tables"]]
    parsed = 1.0 - min(0.5, t["unparsed"] / max(len(t["rows"]), 1))
    return {**t, "confidence": round(g * _val_component(mine) * parsed, 4)}


def decide(cfg: IngestionConfig, doc_grade: str, cls: dict, fields: dict, checks: list[dict], tables: dict) -> dict:
    dc = cfg.decision
    key = {n: f for n, f in fields.items() if f["key_field"]}
    confs = [f["confidence"] if f["status"] == "found" else 0.0 for f in key.values()]
    doc_conf = round(sum(confs) / len(confs), 4) if confs else 0.0
    reasons: list[dict] = []
    if cls["type"] is None:
        reasons.append({"kind": "type_unassigned", "detail": cls.get("reason")})
    if cls.get("mixed_content"):
        reasons.append({"kind": "mixed_content", "pages": [m["page"] for m in cls["mixed_content"]]})
    for n, f in key.items():
        if f["status"] != "found":
            if f["required"] and dc.review_on_missing_required:
                reasons.append({"kind": "missing_required", "field": n, "reason": f["reason"]})
        elif f["confidence"] < cfg.confidence.key_field_review_threshold:
            reasons.append({"kind": "field_review", "field": n, "confidence": f["confidence"]})
    if dc.review_on_failed_check:
        for c in checks:
            if c["outcome"] == "fail":
                reasons.append({"kind": "failed_check", "check": c["id"], "detail": c["detail"]})
    for n, t in tables.items():
        if t["status"] == "missing" and t["reason"] == "table_not_found":
            reasons.append({"kind": "table_missing", "table": n})
    if doc_grade in dc.reject_grades:
        decision = "reject"
    elif reasons:
        decision = "human_review"
    elif doc_conf >= dc.accept_min_document_confidence:
        decision = "auto_accept"
    elif doc_conf >= dc.review_min_document_confidence:
        decision = "human_review"
    else:
        decision = "reject"
    return {"document": doc_conf, "decision": decision, "reasons": reasons,
            "composition": {"key_fields": len(key), "found": sum(1 for f in key.values() if f["status"] == "found"), "document_grade": doc_grade,
                            "failed_checks": sum(1 for c in checks if c["outcome"] == "fail"), "warnings": sum(1 for c in checks if c["outcome"] == "warn")}}
