"""A file's integrity status, said once (F-07A).

The document service answers each check; this says what they come to for a
reader, so every screen shows the same thing and none works it out itself:

  passed              every configured check ran; nothing stands out
  review_recommended  one low-impact indicator, or an observation a person should check
                      (a context check configured with prompts_review, e.g. a design tool)
  suspicious          the routing's priority: independent evidence from the file itself
  suspicious_high     the routing's high-risk indicators
  incomplete          configured checks that have not run on this file, or checks the
                      document service has that the configuration it ran under did not name
  failed              checks that could not run (the file or its pages could not be read,
                      or processing stopped)
  not_checked         a PDF not yet read
  not_applicable      not a PDF

What is incomplete is never shown as passed, an observation is never a signal,
and nothing here is a decision: a person records that separately.

"Configured" is the published configuration, as everywhere: a check added to the
files but not yet published is not one the file is expected to have run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .configstore import reader
from .contracts.documents import IntegrityStatus, ScorePart
from .contracts.ingest import IngestIntegrityFinding

__all__ = ["configured_checks", "score_settings", "assess", "strength"]

PDF = "application/pdf"
_STANDS_OUT = ("warning", "review_required")


def configured_checks(root: Path) -> dict[str, dict[str, Any]]:
    """The integrity checks the published configuration names, with their settings."""
    try:
        return dict((reader.published_ingestion_sections(root).get("integrity") or {}).get("checks") or {})
    except reader.NoPublishedConfig:
        return {}


def score_settings(root: Path) -> dict[str, Any] | None:
    """The published evidence-strength settings, or None when the version sets none."""
    try:
        return (reader.published_ingestion_sections(root).get("integrity") or {}).get("score")
    except reader.NoPublishedConfig:
        return None


def strength(found: list[IngestIntegrityFinding], score: dict[str, Any] | None
             ) -> tuple[int | None, str | None, list[ScorePart]]:
    """Evidence strength: each suspicious indicator scores its impact times its tier; a
    family scores its strongest plus a share of the rest; each further independent
    family adds a share of its own. Capped below certainty. Observations score nothing."""
    if not score:
        return None, None, []
    signals = [f for f in found if f.status in _STANDS_OUT and not f.context]
    if not signals:
        return 0, "none", []
    points = {f.code: score["impact_points"].get(f.impact, 0) * score["tier_factor"].get(f.tier, 1.0)
              for f in signals}
    families: dict[str, list[IngestIntegrityFinding]] = {}
    for f in sorted(signals, key=lambda f: -points[f.code]):
        families.setdefault(f.family, []).append(f)
    totals = {fam: sum(points[f.code] * (1 if i == 0 else score["same_family_share"]) for i, f in enumerate(fs))
              for fam, fs in families.items()}
    parts: list[ScorePart] = []
    for rank, fam in enumerate(sorted(totals, key=lambda k: -totals[k])):
        across = 1 if rank == 0 else score["other_family_share"]
        for i, f in enumerate(families[fam]):
            within = 1 if i == 0 else score["same_family_share"]
            parts.append(ScorePart(code=f.code, family=fam, points=round(points[f.code], 1),
                                   adds=round(points[f.code] * within * across, 1)))
    total = min(score["cap"], round(sum(p.adds for p in parts)))
    bands = score["bands"]
    band = "strong" if total >= bands["strong"] else "moderate" if total >= bands["moderate"] else "weak"
    return total, band, parts


def assess(row: sqlite3.Row | dict, found: list[IngestIntegrityFinding],
           checks: dict[str, dict[str, Any]], score: dict[str, Any] | None = None) -> IntegrityStatus:
    """The status of one file, from its stored integrity results and the configured checks."""
    status, reason_code = row["status"], row["reason_code"]
    recommendation = row["integrity_recommendation"]
    pdf = row["content_type"] == PDF
    present = {f.code for f in found}
    suspicious = [f.code for f in found if f.status in _STANDS_OUT and not f.context]
    informational = [f.code for f in found if f.status in _STANDS_OUT and f.context]
    failed = [f.code for f in found if f.method.get("execution_failed") == "true"]
    # Checks the document service has but the configuration it ran under did not name.
    unconfigured = [f.code for f in found if f.method.get("not_configured") == "true"]
    stopped = status == "exception" and reason_code == "processing_failed"
    pending = ([c for c in checks if c not in present] + unconfigured) if pdf and (found or stopped) else []
    counts = {"passed": sum(f.status == "pass" for f in found),
              "not_applicable": sum(f.status in ("not_applicable", "unable_to_determine")
                                    and f.code not in failed and f.code not in unconfigured for f in found)}

    total, band, parts = strength(found, score)

    def said(state: str) -> IntegrityStatus:
        return IntegrityStatus(state=state, suspicious=suspicious, informational=informational,
                               pending=pending, unconfigured=unconfigured, failed=failed, stopped=stopped,
                               score=total, band=band, score_parts=parts, **counts)

    if not pdf and not found:
        return said("not_applicable")
    if not found and not stopped:
        return said("failed" if status == "exception" else "not_checked")
    if recommendation == "high_risk_indicators":
        return said("suspicious_high")
    if recommendation == "needs_review_priority":
        return said("suspicious")
    if failed or stopped or recommendation == "could_not_be_assessed":
        return said("failed")
    if pending:
        return said("incomplete")
    if recommendation == "needs_review" or any((checks.get(c) or {}).get("prompts_review") for c in informational):
        return said("review_recommended")
    return said("passed")
