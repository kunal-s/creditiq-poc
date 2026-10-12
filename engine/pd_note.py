"""The PD question note (FRD F-24).

Questions for the personal discussion with the promoter, generated from the
failed cross-checks nobody has found not valid, the policy deviations, and
the gaps still open (checks left incomplete, norms that could not be
evaluated). Ranked by severity, each tied to its finding or norm and its
evidence (F-24.1, F-24.2). The wording is configuration.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import policy as policy_module
from . import reads
from .configstore import reader
from .contracts import CaseDetail, PdNote, PdQuestion
from .util import stable_id

SEVERITY = {"serious": 0, "moderate": 1, "mild": 2}
SOURCE = {"finding": 0, "deviation": 1, "gap": 2}


class _Fmt(dict):
    def __missing__(self, key: str) -> str:
        return ""


def question_template(norm_config, policy_config, result) -> str | None:
    """What to ask the promoter about a norm, or None: the norm's own question, then its family's for a
    deviation; for a norm that could not be evaluated, the question for its reason. A figure awaiting
    review is an internal step, and a norm marked pd_gap skip rests on an input the bank obtains."""
    if result.outcome == "deviation":
        return (norm_config.pd_question if norm_config else None) or policy_config.pd_questions.get(result.family)
    if result.outcome != "cannot_evaluate" or result.reason == "awaiting_review":
        return None
    if norm_config is not None and norm_config.pd_gap == "skip":
        return None
    if result.reason in ("zero_denominator", "denominator_not_positive"):
        return policy_config.pd_questions.get(result.reason)
    return policy_config.pd_questions.get("cannot_evaluate")


def build(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> PdNote:
    checks = reader.load_crosschecks(root)
    rules = {r.id: r for r in checks.rules}
    policy_config = reader.load_policy(root)
    waived = {
        r["ref"]
        for r in conn.execute(
            "SELECT ref FROM review_items WHERE case_id = ? AND kind = 'finding' AND decision = 'waive'", (case.id,)
        )
    }
    questions: list[PdQuestion] = []

    for f in reads.findings(conn, case.id):
        rule = rules.get(f.rule_id)
        evidence = [e for s in f.sides for e in s.evidence[:1]]
        if f.outcome == "fail" and f"finding:{f.id}" not in waived and rule and rule.pd_question:
            questions.append(PdQuestion(
                id=stable_id("PDQ", case.id, f.id), severity=f.severity, source="finding", ref=f.id,
                rule=f.rule_id, title=f.title, evidence=evidence, target="cross_verification",
                text=rule.pd_question.format_map(_Fmt(explanation=f.explanation)).strip()))
        elif f.outcome == "incomplete":
            questions.append(PdQuestion(
                id=stable_id("PDQ", case.id, f.id), severity="mild", source="gap", ref=f.id, rule=f.rule_id,
                title=f.title, evidence=evidence, target="cross_verification",
                text=checks.pd_incomplete.format_map(_Fmt(title=f.title, explanation=f.explanation)).strip()))

    assessment = policy_module.assess(conn, root, case)
    for n in assessment.norms:
        evidence = [e for i in n.inputs for e in i.evidence[:1]]
        norm_config = next((c for c in policy_config.norms if c.id == n.id), None)
        values = _Fmt(label=n.label, required=n.required, period=assessment.period or "the latest year",
                      missing=", ".join(n.missing), inputs=", ".join(n.reason_inputs), actual=n.actual_text or "")
        template = question_template(norm_config, policy_config, n)
        if template is None:
            continue
        questions.append(PdQuestion(
            id=stable_id("PDQ", case.id, n.id), severity="moderate" if n.outcome == "deviation" else "mild",
            source="deviation" if n.outcome == "deviation" else "gap", ref=n.id, rule=n.id, title=n.label,
            evidence=evidence, target="policy", text=template.format_map(values).strip()))

    questions.sort(key=lambda q: (SEVERITY[q.severity], SOURCE[q.source]))
    return PdNote(case_id=case.id, questions=questions)
