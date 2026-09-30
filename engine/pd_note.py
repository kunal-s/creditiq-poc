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
                rule=f.rule_id, title=f.title, evidence=evidence,
                text=rule.pd_question.format_map(_Fmt(explanation=f.explanation)).strip()))
        elif f.outcome == "incomplete":
            questions.append(PdQuestion(
                id=stable_id("PDQ", case.id, f.id), severity="mild", source="gap", ref=f.id, rule=f.rule_id,
                title=f.title, evidence=evidence,
                text=checks.pd_incomplete.format_map(_Fmt(title=f.title, explanation=f.explanation)).strip()))

    assessment = policy_module.assess(conn, root, case)
    for n in assessment.norms:
        evidence = [e for i in n.inputs for e in i.evidence[:1]]
        norm_config = next((c for c in policy_config.norms if c.id == n.id), None)
        values = _Fmt(label=n.label, required=n.required, period=assessment.period or "the latest year",
                      missing=", ".join(n.missing),
                      actual=policy_module.unit_text(n.actual, n.unit) if n.actual is not None else "")
        if n.outcome == "deviation":
            template = (norm_config.pd_question if norm_config else None) or policy_config.pd_questions.get(n.family)
            if template:
                questions.append(PdQuestion(
                    id=stable_id("PDQ", case.id, n.id), severity="moderate", source="deviation", ref=n.id,
                    rule=n.id, title=n.label, evidence=evidence, text=template.format_map(values).strip()))
        elif n.outcome == "cannot_evaluate" and policy_config.pd_questions.get("cannot_evaluate"):
            questions.append(PdQuestion(
                id=stable_id("PDQ", case.id, n.id), severity="mild", source="gap", ref=n.id, rule=n.id,
                title=n.label, evidence=evidence,
                text=policy_config.pd_questions["cannot_evaluate"].format_map(values).strip()))

    questions.sort(key=lambda q: (SEVERITY[q.severity], SOURCE[q.source]))
    return PdNote(case_id=case.id, questions=questions)
