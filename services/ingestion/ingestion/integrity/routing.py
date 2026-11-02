"""The recommendation: independent signals combined, never one alone.

A signal is a check that is a warning or needs review. Signals are counted by
family — metadata, font, layout, visual, history, identifier — because two
warnings from the same kind of evidence say the same thing twice. Context (how
the file was made, which tool wrote it) is never a signal.

Every threshold is in `config/ingestion/integrity.yaml` under `routing`.

Ported from RBL/fault_detection `backend/src/tamper/routing.py` (PROVENANCE.md).
The AI branch is not ported: no check here calls a model. The quality branch is
not ported either: `config/ingestion/quality.yaml` already grades a page and
asks for a clearer copy (FRD F-07.4).
"""

from __future__ import annotations

from typing import Any

from ..contracts import IntegrityFinding

__all__ = ["recommend", "LABELS"]

LABELS = {
    "no_notable_issue": "No notable issue detected",
    "needs_review": "Needs review",
    "needs_review_priority": "Needs review (priority)",
    "high_risk_indicators": "High-risk indicators found",
    "could_not_be_assessed": "Could not be assessed",
}
_RANK = {"low": 0, "medium": 1, "high": 2}


def recommend(found: list[IntegrityFinding], cfg: dict[str, Any]) -> dict[str, Any]:
    """One of five recommendations, with the families and signals behind it."""
    rules = cfg["routing"]
    strong = set(rules["strong_tiers"])

    def done(code: str, families=(), signals=(), why: str = "") -> dict[str, Any]:
        return {"code": code, "label": LABELS[code], "families": sorted(set(families)),
                "signals": [{"code": s.code, "family": s.family, "status": s.status,
                             "impact": s.impact, "tier": s.tier} for s in signals],
                "why": why, "policy_version": cfg["version"]}

    # Nothing can be judged when the file could not be opened at all.
    if found and all(r.status == "unable_to_determine" for r in found):
        return done("could_not_be_assessed", why="The file could not be read, so no check could be carried out.")

    signals = [r for r in found if r.status in ("warning", "review_required") and not r.context]
    if not signals:
        return done("no_notable_issue", why="No check that counts as a signal is a warning or needs review.")

    by_family: dict[str, list[IntegrityFinding]] = {}
    for s in signals:
        by_family.setdefault(s.family, []).append(s)
    # Each family weighs as its strongest signal.
    top = {f: max(ss, key=lambda s: (_RANK[s.impact], s.tier in strong)) for f, ss in by_family.items()}
    families = list(top)
    impacts = [_RANK[s.impact] for s in top.values()]
    min_rank = _RANK[rules["multi_family_min_impact"]]

    if len(families) >= 2:
        high = [f for f, s in top.items() if s.impact == "high"]
        if len(high) >= 2 and any(top[f].tier in strong for f in high):
            return done("high_risk_indicators", families, signals,
                        f"{len(families)} independent kinds of evidence, {len(high)} of them high impact.")
        if max(impacts) >= min_rank:
            return done("needs_review_priority", families, signals,
                        f"{len(families)} independent kinds of evidence point the same way.")
        return done("needs_review", families, signals, "Several low-impact observations.")
    only = top[families[0]]
    if only.impact == "high" and only.tier in strong:
        return done("needs_review_priority", families, signals,
                    f"One kind of evidence ({families[0]}), high impact, from the file itself.")
    return done("needs_review", families, signals, f"One kind of evidence ({families[0]}).")
