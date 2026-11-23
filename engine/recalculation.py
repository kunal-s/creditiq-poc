"""What an approved change to an extracted value did to the case: the recalculation record.

Once a case exists, a figure is changed in one place: the Extractions tab. The Credit Analyst changes the value
and the Credit Manager approves it (engine/figure_edits.py), or the Credit Manager corrects a value held for
review (engine/review.py). Everything worked from the figures then follows the value now in force: the statement
lines and the figures summed from them, the policy norms, the cross-checks, the document readiness and the
approving authority. The case is read before the change and again after its checks have re-run, and every
difference is written to the decision log with the change that caused it, so a reader sees what was, what is
now, and why. Nothing here changes a figure.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import approval, cases, completeness, policy
from .config import load_roles_config
from .configstore import reader
from .contracts import Recalculation, RecalculationChange, RecalculationTrigger
from .db import log_decision
from .figure_edits import shown
from .pipeline import effective_types
from .util import dumps, now_iso

ACTION = "case.recalculated"

# A cross-check run gives one finding per year or period it compares; the rule reads as its worst.
_WORST = ("fail", "incomplete", "pass", "not_applicable")
_CELL = re.compile(r"^(\w+)\[(\d+)\]\.(\w+)$")
_COLUMN_WORDS = {"current_period": "current year", "previous_period": "previous year"}


@dataclass
class Snapshot:
    """The case's worked results at one moment."""

    period: str | None = None
    figures: dict[str, tuple[str, float]] = field(default_factory=dict)
    norms: dict[str, tuple[str, str, str | None]] = field(default_factory=dict)
    """Norm id: (label, outcome, the figure as written)."""
    checks: dict[str, tuple[str, str]] = field(default_factory=dict)
    """Cross-check rule id: (title, outcome)."""
    readiness: float | None = None
    authority: str | None = None


def snapshot(conn: sqlite3.Connection, root: Path, case_id: str) -> Snapshot | None:
    """The case's figures and results as they read now; None when there is nothing to read them by (no case,
    or no published configuration)."""
    case = cases.get_case(conn, case_id)
    if case is None:
        return None
    try:
        inputs = policy.gather(conn, root, case)
        assessment = policy.assess(conn, root, case)
        readiness, _ = completeness.evaluate(conn, root, case)
        authority = approval.required(conn, root, case)
    except reader.NoPublishedConfig:
        return None
    snap = Snapshot(period=inputs.period, readiness=readiness.score_pct,
                    authority=authority.required.label if authority.required else None)
    for name in policy.FINANCIAL_INPUTS:
        v = inputs.values.get(name)
        if v is not None and v.value is not None:
            snap.figures[name] = (policy.INPUT_LABELS.get(name, name), float(v.value))
    for n in assessment.norms:
        snap.norms[n.id] = (n.label, n.outcome, n.actual_text)
    for row in conn.execute("SELECT rule_id, title, outcome FROM findings WHERE case_id = ? ORDER BY rule_id, id",
                            (case_id,)):
        title, worst = snap.checks.get(row["rule_id"], (row["title"], "not_applicable"))
        outcome = min(worst, row["outcome"], key=lambda o: _WORST.index(o) if o in _WORST else len(_WORST))
        snap.checks[row["rule_id"]] = (title, outcome)
    return snap


def changes(before: Snapshot, after: Snapshot) -> list[RecalculationChange]:
    """Every result that reads differently after the change, in the order a reader follows them: the figures,
    the norms, the cross-checks, then readiness and the authority."""
    out: list[RecalculationChange] = []
    period = f", {after.period or before.period}" if (after.period or before.period) else ""
    for key in [*before.figures, *[k for k in after.figures if k not in before.figures]]:
        was, now = before.figures.get(key), after.figures.get(key)
        a, b = (was[1] if was else None), (now[1] if now else None)
        if a is None and b is None or (a is not None and b is not None and abs(a - b) < 0.5):
            continue
        label = (now or was)[0]  # type: ignore[index]
        out.append(RecalculationChange(area="figure", key=key, label=f"{label}{period}", kind="amount", before=a, after=b))
    for key in [*before.norms, *[k for k in after.norms if k not in before.norms]]:
        was, now = before.norms.get(key), after.norms.get(key)
        if was and now and was[1:] == now[1:]:
            continue
        label = (now or was)[0]  # type: ignore[index]
        out.append(RecalculationChange(area="norm", key=key, label=f"{key} {label}", kind="outcome",
                                       before=was[1] if was else None, after=now[1] if now else None,
                                       detail_before=was[2] if was else None, detail_after=now[2] if now else None))
    for key in [*before.checks, *[k for k in after.checks if k not in before.checks]]:
        was, now = before.checks.get(key), after.checks.get(key)
        if was and now and was[1] == now[1]:
            continue
        label = (now or was)[0]  # type: ignore[index]
        out.append(RecalculationChange(area="check", key=key, label=f"{key} {label}", kind="outcome",
                                       before=was[1] if was else None, after=now[1] if now else None))
    if before.readiness != after.readiness:
        out.append(RecalculationChange(area="readiness", key="readiness", label="Document readiness", kind="percent",
                                       before=before.readiness, after=after.readiness))
    if before.authority != after.authority:
        out.append(RecalculationChange(area="authority", key="authority", label="Approving authority", kind="text",
                                       before=before.authority, after=after.authority))
    return out


def trigger(conn: sqlite3.Connection, root: Path, field_value_id: str, *, from_value: object, to_value: object,
            reason: str | None, changed_by: str | None) -> RecalculationTrigger | None:
    """The change as a reader names it: the value, its document and file, what it was and what it is now."""
    fv = conn.execute("SELECT * FROM field_values WHERE id = ?", (field_value_id,)).fetchone()
    if fv is None:
        return None
    doc = conn.execute(
        "SELECT d.*, f.original_name AS file_name FROM documents d LEFT JOIN files f ON f.id = d.file_id WHERE d.id = ?",
        (fv["document_id"],)).fetchone()
    names = {t.id: t.name for t in reader.load_document_types(root).types}
    types = effective_types(doc) if doc is not None else []
    label = fv["field"].replace("_", " ")
    m = _CELL.match(fv["field"])
    if m:
        row = conn.execute("SELECT value FROM field_values WHERE document_id = ? AND field IN (?, ?)",
                           (fv["document_id"], f"{m[1]}[{m[2]}].particulars", f"{m[1]}[{m[2]}].description")).fetchone()
        row_label = json.loads(row["value"]) if row is not None and row["value"] is not None else None
        column = _COLUMN_WORDS.get(m[3], m[3].replace("_", " "))
        label = f"{row_label}, {column}" if row_label else f"{m[1].replace('_', ' ')} row {int(m[2]) + 1}, {column}"
    return RecalculationTrigger(
        field_value_id=fv["id"], field=fv["field"], label=label[:1].upper() + label[1:], document_id=fv["document_id"],
        document=" + ".join(names.get(t, t.replace("_", " ")) for t in types) or "Document",
        file_name=doc["file_name"] if doc is not None else None,
        from_value=None if from_value is None else shown(from_value), to_value=None if to_value is None else shown(to_value),
        reason=reason, changed_by=changed_by)


def record(conn: sqlite3.Connection, case_id: str, *, approved_by: str, what: RecalculationTrigger,
           before: Snapshot, after: Snapshot) -> None:
    """Write the recalculation to the decision log (append-only), with every result that moved."""
    found = changes(before, after)
    log_decision(conn, at=now_iso(), actor=approved_by, case_id=case_id, action=ACTION,
                 detail=dumps({"trigger": what.model_dump(), "changes": [c.model_dump() for c in found]}))


def history(conn: sqlite3.Connection, case_id: str) -> list[Recalculation]:
    """The case's recalculations, the latest first."""
    names = {u["id"]: u["name"] for u in load_roles_config()["users"]}
    out: list[Recalculation] = []
    for row in conn.execute("SELECT seq, at, actor, detail FROM decision_log WHERE case_id = ? AND action = ? "
                            "ORDER BY seq DESC", (case_id, ACTION)):
        detail = json.loads(row["detail"] or "{}")
        out.append(Recalculation(id=f"RC-{row['seq']}", case_id=case_id, at=row["at"],
                                 approved_by=names.get(row["actor"], row["actor"]),
                                 trigger=RecalculationTrigger.model_validate(detail["trigger"]),
                                 changes=[RecalculationChange.model_validate(c) for c in detail.get("changes", [])]))
    return out
