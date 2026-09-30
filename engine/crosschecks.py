"""Cross-checks: identity, turnover, bank accounts, obligations (FRD F-19).

Each configured rule (config/crosschecks.yaml) compares one aligned fact
(engine/facts.py) across its sources. The outcome is pass, fail,
incomplete (with the missing coverage named) or not applicable (F-19.3). A
failure keeps both sides' values with their evidence, the tolerance and the
explanation; it says when it relies on a person's entry (F-19.4). Findings
are replaced on every run, so changing one tolerance changes exactly the
findings that use it (F-19.6).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from . import facts as facts_module
from .configstore import reader
from .configstore.schema import CrossCheckRule
from .contracts import CaseDetail, CaseFacts, Evidence, Finding, FindingSide, FactValue, TurnoverFigure
from .db import transaction
from .names import similarity
from .review_items import raise_item
from .util import dumps, stable_id

TURNOVER_PAIRS = {
    "turnover_audited_vs_gst": ("financials", "gst"),
    "turnover_gst_vs_bank": ("gst", "bank"),
    "turnover_audited_vs_bank": ("financials", "bank"),
    "turnover_declared_vs_evidenced": ("declared", "financials"),
}


class _Fmt(dict):
    def __missing__(self, key: str) -> str:
        return ""


class Context:
    def __init__(self, root: Path, case: CaseDetail, facts: CaseFacts) -> None:
        self.case = case
        self.facts = facts
        self.tolerances = {t.key: t for t in reader.load_tolerances(root).tolerances}
        self.noise = [w.lower() for w in reader.load_alignment(root).name_noise_words]
        self.version = reader.published_version(root)["version"]

    def tol(self, key: str | None, default: float) -> float:
        return self.tolerances[key].value if key and key in self.tolerances else default

    def tol_text(self, key: str | None) -> str | None:
        if not key or key not in self.tolerances:
            return None
        t = self.tolerances[key]
        return f"{t.value:g}%" if t.unit == "%" else f"{t.value:g}"


def _finding(ctx: Context, rule: CrossCheckRule, outcome: str, sides: list[FindingSide], scope: str = "",
             **fmt: str) -> Finding:
    values = _Fmt(fmt)
    values.setdefault("tolerance", ctx.tol_text(rule.tolerance) or "")
    explanation = rule.explanation.format_map(values) if outcome == "fail" else fmt.get("note", "")
    title = f"{rule.title} · {scope}" if scope else rule.title
    return Finding(
        id=stable_id("FND", ctx.case.id, rule.id, scope),
        case_id=ctx.case.id,
        rule_id=rule.id,
        title=title,
        outcome=outcome,  # type: ignore[arg-type]
        severity=rule.severity,
        blocking=rule.blocking,
        explanation=explanation,
        sides=sides,
        # Shown only where it is the comparison's allowance; a name-matching
        # threshold is how sources are matched, not a finding's tolerance.
        tolerance=ctx.tol_text(rule.tolerance) if rule.comparison == "tolerance" else None,
        config_version=ctx.version,
        query=rule.query.format_map(values) if outcome == "fail" and rule.query else None,
    )


def _side(label: str, value: str | float | None, evidence: list[Evidence], manual: bool = False) -> FindingSide:
    return FindingSide(label=label, value=value, evidence=evidence, relies_on_manual=manual)


# --- Identity (ID-01 to ID-03): one value across sources ---


def _groups(values: list[FactValue], same) -> list[list[FactValue]]:
    groups: list[list[FactValue]] = []
    for v in values:
        for g in groups:
            if same(v.value, g[0].value):
                g.append(v)
                break
        else:
            groups.append([v])
    return groups


def _exact(ctx: Context, rule: CrossCheckRule, values: list[FactValue]) -> Finding:
    values = [v for v in values if v.source in rule.sources or v.source == "application_message"]
    if len({(v.source, v.label, str(v.value)) for v in values}) < 2:
        return _finding(ctx, rule, "not_applicable", [], note="Fewer than two sources state this.")
    if rule.variable == "legal_name":
        threshold = ctx.tol(rule.tolerance, 0.85)
        groups = _groups(values, lambda a, b: similarity(str(a), str(b)) >= threshold)
    else:
        groups = _groups(values, lambda a, b: str(a) == str(b))
    sides = [
        _side(
            ", ".join(dict.fromkeys(v.label for v in g)),
            g[0].value,
            [e for v in g for e in v.evidence[:1]],
            any(v.relies_on_manual for v in g),
        )
        for g in groups
    ]
    if len(groups) == 1:
        return _finding(ctx, rule, "pass", sides, note=f"Consistent across {len(values)} sources.")
    items = " · ".join(f"{s.value} ({s.label})" for s in sides)
    return _finding(ctx, rule, "fail", sides, items=items)


# --- Promoter set (ID-04) ---


def _persons(ctx: Context, rule: CrossCheckRule) -> Finding:
    sets = [p for p in ctx.facts.persons if p.source in rule.sources]
    if len(sets) < 2:
        return _finding(ctx, rule, "not_applicable", [], note="Fewer than two sources name the promoters.")
    threshold = ctx.tol(rule.tolerance, 0.85)
    people: list[str] = []
    for p in sets:
        for name in p.names:
            if not any(similarity(name, q) >= threshold for q in people):
                people.append(name)
    gaps = []
    for person in people:
        absent = [p.label for p in sets if not any(similarity(person, n) >= threshold for n in p.names)]
        if absent:
            gaps.append(f"{person} is not in {', '.join(absent)}")
    sides = [_side(p.label, "; ".join(p.names), p.evidence[:1], p.relies_on_manual) for p in sets]
    if not gaps:
        return _finding(ctx, rule, "pass", sides, note=f"The same {len(people)} person(s) in {len(sets)} sources.")
    return _finding(ctx, rule, "fail", sides, items="; ".join(gaps))


# --- Turnover (TO-01 to TO-04): per financial year ---


def _figure_side(f: TurnoverFigure) -> FindingSide:
    return _side(f.label, f.value, f.evidence[:12], f.relies_on_manual)


def _turnover(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    left_key, right_key = TURNOVER_PAIRS[rule.variable]
    years = []
    for y in ctx.facts.turnover:
        by = {f.source: f for f in y.figures}
        right = by.get(right_key)
        if rule.variable == "turnover_declared_vs_evidenced" and right is None:
            gst = by.get("gst")
            right = gst if gst and gst.months_covered == 12 else None
        years.append((y, by.get(left_key), right))
    if left_key == "declared" and not any(lf for _, lf, _ in years):
        # Nothing was declared: there is nothing to hold the evidence against.
        return [_finding(ctx, rule, "not_applicable", [], note="No turnover was declared in the sourcing message.")]
    both = [(y, lf, rf) for y, lf, rf in years if lf and rf]
    if not both:
        present = [(y, lf, rf) for y, lf, rf in years if lf or rf]
        if not present:
            return [_finding(ctx, rule, "not_applicable", [], note="Neither source is on file.")]
        y, lf, rf = present[0]
        have = lf or rf
        missing = _label(right_key) if lf else _label(left_key)
        return [_finding(ctx, rule, "incomplete", [_figure_side(have)], y.fy,
                         note=f"{missing} for {y.fy} is not on file.")]
    out = []
    tol = ctx.tol(rule.tolerance, 10)
    for y, lf, rf in both:
        gaps = [f"{f.label} covers {f.months_covered} of 12 months ({', '.join(f.months_missing[:3])}"
                f"{'…' if len(f.months_missing) > 3 else ''} absent)"
                for f in (lf, rf) if f.months_covered is not None and f.months_covered < 12]
        sides = [_figure_side(lf), _figure_side(rf)]
        if gaps:
            out.append(_finding(ctx, rule, "incomplete", sides, y.fy, note="; ".join(gaps) + "."))
            continue
        a, b = float(lf.value or 0), float(rf.value or 0)
        variance = abs(a - b) / max(a, b) * 100 if max(a, b) else 0.0
        fmt = dict(period=y.fy, left=facts_module.inr(a), right=facts_module.inr(b), left_label=lf.label,
                   right_label=rf.label, variance=f"{variance:.1f}%")
        if variance <= tol:
            out.append(_finding(ctx, rule, "pass", sides, y.fy,
                                note=f"Variance {variance:.1f}% within {ctx.tol_text(rule.tolerance)}.", **fmt))
        else:
            out.append(_finding(ctx, rule, "fail", sides, y.fy, **fmt))
    return out


def _label(source: str) -> str:
    return {
        "financials": "Audited turnover",
        "gst": "GST outward supplies",
        "bank": "Bank statements",
        "declared": "Declared turnover",
    }[source]


# --- Bank accounts (BA-01, BA-02) ---


def _accounts(ctx: Context, rule: CrossCheckRule) -> Finding:
    accounts = ctx.facts.accounts
    if not ctx.facts.declaration_received and not any(a.declared for a in accounts):
        if not accounts:
            return _finding(ctx, rule, "not_applicable", [], note="No bank account is on file.")
        return _finding(ctx, rule, "incomplete", [],
                        note="No declaration of existing banking is on file to compare with.")
    if rule.variable == "declared_accounts_with_statements":
        subject = [a for a in accounts if a.declared]
        missing = [a for a in subject if not a.has_statement]
        left, right = "Declared accounts", "Accounts with statements"
        right_set = [a for a in accounts if a.has_statement]
    else:
        subject = [a for a in accounts if a.has_statement or any(not _is_declaration(s) for s in a.sources)]
        missing = [a for a in subject if not a.declared]
        left, right = "Accounts evidenced", "Declared accounts"
        right_set = [a for a in accounts if a.declared]
    sides = [
        _side(left, ", ".join(a.label for a in subject) or "none", [e for a in subject for e in a.evidence[:1]]),
        _side(right, ", ".join(a.label for a in right_set) or "none", [e for a in right_set for e in a.evidence[:1]]),
    ]
    if not missing:
        return _finding(ctx, rule, "pass", sides, note=f"{len(subject)} account(s) reconcile.")
    names = ", ".join(f"{a.label} ({', '.join(a.sources)})" for a in missing)
    return _finding(ctx, rule, "fail", sides, missing=names)


def _is_declaration(source: str) -> bool:
    low = source.lower()
    return "declaration" in low or "sourcing message" in low


# --- Obligations (OB-01, OB-02) ---


def _facilities(ctx: Context, rule: CrossCheckRule) -> Finding:
    groups: dict[str, list] = defaultdict(list)
    for f in ctx.facts.facilities:
        if f.source in rule.sources:
            groups[f.label].append(f)
    declared_label = next((f.label for f in ctx.facts.facilities if f.source == "existing_facilities_declaration"),
                          "Declaration of existing facilities")
    if ctx.facts.declaration_received and declared_label not in groups:
        groups[declared_label] = []  # a nil declaration still states a set: none
    if len(groups) < 2:
        return _finding(ctx, rule, "not_applicable", [], note="Fewer than two sources record existing facilities.")
    threshold = ctx.tol("name_match", 0.85)
    lenders: list[str] = []
    for fs in groups.values():
        for f in fs:
            if not any(facts_module.same_entity(f.lender, q, ctx.noise, threshold) for q in lenders):
                lenders.append(f.lender)
    gaps = []
    for lender in lenders:
        absent = [label for label, fs in groups.items()
                  if not any(facts_module.same_entity(lender, f.lender, ctx.noise, threshold) for f in fs)]
        if absent:
            gaps.append(f"{lender} is not in {', '.join(absent)}")
    sides = [
        _side(label, ", ".join(dict.fromkeys(f.lender for f in fs)) or "none",
              [e for f in fs for e in f.evidence[:1]], any(f.relies_on_manual for f in fs))
        for label, fs in groups.items()
    ]
    if not gaps:
        return _finding(ctx, rule, "pass", sides, note=f"{len(lenders)} lender(s) agree across {len(groups)} sources.")
    return _finding(ctx, rule, "fail", sides, items="; ".join(gaps))


def _emis(ctx: Context, rule: CrossCheckRule) -> Finding:
    if not ctx.facts.credits and not ctx.facts.obligations and not any(a.has_statement for a in ctx.facts.accounts):
        return _finding(ctx, rule, "not_applicable", [], note="No bank statement is on file.")
    if not ctx.facts.declaration_received:
        return _finding(ctx, rule, "incomplete", [],
                        note="No declaration of existing facilities is on file to compare with.")
    threshold = ctx.tol("name_match", 0.85)
    declared = [f for f in ctx.facts.facilities if f.source == "existing_facilities_declaration"]
    undeclared = [o for o in ctx.facts.obligations
                  if not any(facts_module.same_entity(o.lender, f.lender, ctx.noise, threshold) for f in declared)]
    sides = [
        _side("Instalments in bank statements",
              ", ".join(f"{o.lender} ({facts_module.inr(o.typical_amount)} × {len(o.months)})"
                        for o in ctx.facts.obligations) or "none",
              [e for o in ctx.facts.obligations for e in o.evidence[:2]]),
        _side("Declared facilities", ", ".join(f.lender for f in declared) or "none",
              [e for f in declared for e in f.evidence[:1]], any(f.relies_on_manual for f in declared)),
    ]
    if not undeclared:
        return _finding(ctx, rule, "pass", sides,
                        note=f"{len(ctx.facts.obligations)} recurring instalment(s), all to declared lenders.")
    missing = ", ".join(
        f"{o.lender} ({facts_module.inr(o.typical_amount)} a month in {len(o.months)} months, {o.account})"
        for o in undeclared
    )
    return _finding(ctx, rule, "fail", sides, missing=missing)


def evaluate(root: Path, case: CaseDetail, facts: CaseFacts) -> list[Finding]:
    ctx = Context(root, case, facts)
    out: list[Finding] = []
    for rule in reader.load_crosschecks(root).rules:
        v = rule.variable
        if v in ("entity_pan", "gstin", "legal_name"):
            out.append(_exact(ctx, rule, getattr(facts.identities, v)))
        elif v == "promoter_set":
            out.append(_persons(ctx, rule))
        elif v in TURNOVER_PAIRS:
            out.extend(_turnover(ctx, rule))
        elif v in ("declared_accounts_with_statements", "evidenced_accounts_declared"):
            out.append(_accounts(ctx, rule))
        elif v == "facilities_reconcile":
            out.append(_facilities(ctx, rule))
        elif v == "emis_to_declared_lenders":
            out.append(_emis(ctx, rule))
    return out


def run(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> list[Finding]:
    """Evaluate every rule and replace the case's findings. A failure raises
    a finding review item (F-17.4); an open item whose finding no longer
    fails is withdrawn. Decided items stay, as the record of the decision."""
    found = evaluate(root, case, facts_module.compute(conn, root, case))
    failing = {f"finding:{f.id}" for f in found if f.outcome == "fail"}
    with transaction(conn):
        conn.execute("DELETE FROM findings WHERE case_id = ?", (case.id,))
        for f in found:
            conn.execute(
                """INSERT INTO findings (id, case_id, rule_id, title, outcome, severity, blocking, explanation, sides,
                   tolerance, config_version, run_id, query) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f.id, case.id, f.rule_id, f.title, f.outcome, f.severity, int(f.blocking), f.explanation,
                 dumps([s.model_dump() for s in f.sides]), f.tolerance, f.config_version, f.run_id, f.query),
            )
            if f.outcome == "fail":
                raise_item(conn, case_id=case.id, kind="finding", ref=f"finding:{f.id}",
                           summary=f"{f.rule_id} {f.title}: {f.explanation}",
                           detail={"finding_id": f.id, "rule_id": f.rule_id})
        for row in conn.execute(
            "SELECT id, ref FROM review_items WHERE case_id = ? AND kind = 'finding' AND status = 'open'", (case.id,)
        ).fetchall():
            if row["ref"] not in failing:
                conn.execute("DELETE FROM review_items WHERE id = ?", (row["id"],))
    return found
