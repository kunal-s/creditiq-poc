"""Policy norms and deviations (FRD F-20).

Every norm in config/policy.yaml is evaluated for the case: its expression
over the inputs below, against its threshold. The result shows the norm,
the required value, the actual value, the source figures with evidence,
pass or deviation, and the deviation category (F-20.2). A norm whose inputs
are not on file is "cannot evaluate", naming them, and never a pass
(F-20.3). Financial inputs come from the latest audited statements.
"""

from __future__ import annotations

import ast
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import completeness, facts as facts_module
from .configstore import reader
from .configstore.schema import PolicyNorm, PolicyRatio
from .contracts import CaseDetail, Evidence, NormInput, NormResult, PolicyAssessment
from .util import parse_date

WORKING_CAPITAL = {"cash_credit", "overdraft", "wcdl", "packing_credit", "post_shipment"}
TERM = {"term_loan"}

FINANCIAL_INPUTS = [
    "revenue_from_operations", "other_income", "ebitda", "depreciation", "finance_costs", "profit_before_tax",
    "profit_after_tax", "share_capital", "reserves_and_surplus", "net_worth", "long_term_borrowings",
    "short_term_borrowings", "total_borrowings", "inventories", "trade_receivables", "trade_payables",
    "current_assets", "current_liabilities",
]

INPUT_LABELS = {
    "revenue_from_operations": "Revenue from operations",
    "other_income": "Other income",
    "ebitda": "EBITDA",
    "depreciation": "Depreciation",
    "finance_costs": "Finance costs",
    "profit_before_tax": "Profit before tax",
    "profit_after_tax": "Profit after tax",
    "share_capital": "Share capital",
    "reserves_and_surplus": "Reserves and surplus",
    "net_worth": "Net worth",
    "long_term_borrowings": "Long-term borrowings",
    "short_term_borrowings": "Short-term borrowings",
    "total_borrowings": "Total borrowings",
    "inventories": "Inventories",
    "trade_receivables": "Trade receivables",
    "trade_payables": "Trade payables",
    "current_assets": "Current assets",
    "current_liabilities": "Current liabilities",
    "amount_requested": "Amount requested",
    "vintage_years": "Years in business",
    "bureau_rank": "Commercial bureau rank",
    "market_value": "Collateral market value",
    "realisable_value": "Collateral realisable value",
    "annual_instalments": "Annual instalments on existing and inferred facilities",
    "blocking_items_open": "Blocking checklist items open",
    "audited_years": "Years of audited statements",
}


@dataclass
class Inputs:
    values: dict[str, NormInput] = field(default_factory=dict)
    period: str | None = None

    def put(self, name: str, value: float | None, evidence: list[Evidence] | None = None, manual: bool = False) -> None:
        if value is None:
            return
        self.values[name] = NormInput(name=name, label=INPUT_LABELS[name], value=float(value),
                                      evidence=evidence or [], relies_on_manual=manual)


def _number(v: facts_module.Value | None) -> float | None:
    if v is None or v.value in (None, ""):
        return None
    try:
        return float(str(v.value).replace(",", ""))
    except ValueError:
        return None


def gather(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> Inputs:
    docs = facts_module.load_documents(conn, root, case.id)
    by_type = lambda *ids: [d for d in docs if any(t in d.types for t in ids)]  # noqa: E731
    start = reader.load_alignment(root).financial_year_start_month
    inputs = Inputs()
    as_of = date.fromisoformat(case.as_of)

    # The latest audited statements, and how many years are on file.
    audited = []
    for d in by_type("audited_financial_statements"):
        end = parse_date(d.get("period_end").value) if d.get("period_end") else None
        if end:
            audited.append((end, d))
    audited.sort(key=lambda pair: pair[0])
    years = {facts_module.fy_of(end.year, end.month, start) for end, _ in audited}
    inputs.put("audited_years", len(years), [e for _, d in audited for e in d.evidence(d.get("period_end"))[:1]])
    if audited:
        end, latest = audited[-1]
        inputs.period = facts_module.fy_name(facts_module.fy_of(end.year, end.month, start), start)
        for name in FINANCIAL_INPUTS:
            v = latest.get(name)
            inputs.put(name, _number(v), latest.evidence(v) if v else None, bool(v and v.manual))

    # The case: the amount asked for.
    inputs.put("amount_requested", case.amount_inr)

    # Years in business: incorporation, else registration.
    for type_id, field_name in (("certificate_of_incorporation", "incorporation_date"),
                                ("udyam_certificate", "registration_date"),
                                ("gst_registration_certificate", "registration_date")):
        found = next(((d, d.get(field_name)) for d in by_type(type_id) if d.get(field_name)), None)
        if found and (since := parse_date(found[1].value)):
            inputs.put("vintage_years", round((as_of - since).days / 365.25, 1), found[0].evidence(found[1]),
                       found[1].manual)
            break

    # Commercial bureau rank: the number in "Rank 3", "CMR-3".
    for d in by_type("bureau_commercial"):
        score = d.get("score", "rank", "cmr_rank")
        m = re.search(r"\d+", str(score.value)) if score else None
        if m:
            inputs.put("bureau_rank", int(m[0]), d.evidence(score), score.manual)
            break

    # Collateral values, summed over valuation reports.
    for name in ("market_value", "realisable_value"):
        values = [(d, d.get(name)) for d in by_type("valuation_report") if d.get(name)]
        numbers = [(d, v, _number(v)) for d, v in values if _number(v) is not None]
        if numbers:
            inputs.put(name, sum(n for _, _, n in numbers), [e for d, v, _ in numbers for e in d.evidence(v)[:1]],
                       any(v.manual for _, v, _ in numbers))

    # Annual instalments: declared EMIs, plus inferred ones to other lenders.
    facts = facts_module.compute(conn, root, case)
    noise = [w.lower() for w in reader.load_alignment(root).name_noise_words]
    threshold = {t.key: t.value for t in reader.load_tolerances(root).tolerances}.get("name_match", 0.85)
    declared = [f for f in facts.facilities if f.source == "existing_facilities_declaration"]
    monthly = sum(f.emi or 0 for f in declared)
    evidence = [e for f in declared if f.emi for e in f.evidence[:1]]
    for o in facts.obligations:
        if not any(facts_module.same_entity(o.lender, f.lender, noise, threshold) for f in declared if f.emi):
            monthly += o.typical_amount
            evidence += o.evidence[:1]
    if facts.declaration_received or facts.obligations or any(a.has_statement for a in facts.accounts):
        inputs.put("annual_instalments", monthly * 12, evidence)

    # Blocking checklist items still open (F-13).
    readiness, _ = completeness.evaluate(conn, root, case)
    inputs.put("blocking_items_open", readiness.blocking_open)
    return inputs


# --- Expressions ---


class _Missing(Exception):
    pass


def _eval(node: ast.AST, values: dict[str, float], missing: list[str]) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body, values, missing)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in values:
            missing.append(INPUT_LABELS.get(node.id, node.id))
            return 0.0
        return values[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, values, missing)
    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left, values, missing), _eval(node.right, values, missing)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0 and not missing:
                raise ZeroDivisionError(ast.unparse(node.right))
            return left / right if right else 0.0
    raise _Missing(f"unsupported expression {ast.unparse(node)!r}")


def words(expression: str) -> str:
    """The expression with its inputs named: "Current assets ÷ Current liabilities"."""
    text = re.sub(r"[a-z_]+", lambda m: INPUT_LABELS.get(m[0], m[0]), expression)
    return text.replace("/", "÷").replace("*", "×")


# --- Norms ---


def _unit_text(value: float, unit: str | None) -> str:
    if unit == "x":
        return f"{value:.2f}x"
    if unit == "%":
        return f"{value:.1f}%" if value % 1 else f"{value:.0f}%"
    if unit == "days":
        return f"{value:.0f} days"
    if unit == "years":
        return f"{value:g} years"
    if unit == "inr":
        return facts_module.inr(value)
    if unit == "rank":
        return f"rank {value:g}"
    return f"{value:g}"


def _applies(norm: PolicyNorm, case: CaseDetail, inputs: Inputs) -> bool:
    if norm.applies_when == "working_capital":
        return bool(set(case.facilities) & WORKING_CAPITAL)
    if norm.applies_when == "term_debt":
        instalments = inputs.values.get("annual_instalments")
        return bool(set(case.facilities) & TERM) or bool(instalments and instalments.value)
    if norm.applies_when == "collateral":
        return bool(case.collateral_present)
    return True


def evaluate(norm: PolicyNorm, ratio: PolicyRatio | None, case: CaseDetail, inputs: Inputs,
             categories: dict[str, str]) -> NormResult:
    label = norm.label or (ratio.label if ratio else norm.id)
    unit = norm.unit or (ratio.unit if ratio else None)
    kind = norm.kind or (ratio.kind if ratio else "min")
    threshold = norm.threshold if norm.threshold is not None else (ratio.acceptable if ratio else 0.0)
    required = f"{'at least' if kind == 'min' else 'at most'} {_unit_text(threshold, unit)}"
    status = norm.status or (ratio.status if ratio else None)
    result = NormResult(
        id=norm.id, family=norm.family, label=label,
        formula=ratio.formula if ratio else words(norm.expression),
        required=required, unit=unit, outcome="not_applicable", category=norm.category,
        category_label=categories.get(norm.category, norm.category), note=norm.note or (ratio.note if ratio else None),
        provisional=status == "provisional",
    )
    if not _applies(norm, case, inputs):
        return result
    tree = ast.parse(norm.expression, mode="eval")
    names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
    result.inputs = [inputs.values[n] for n in dict.fromkeys(names) if n in inputs.values]
    missing: list[str] = []
    try:
        actual = _eval(tree, {k: v.value for k, v in inputs.values.items() if v.value is not None}, missing)
    except ZeroDivisionError as zero:
        result.outcome = "cannot_evaluate"
        result.missing = [f"{words(str(zero))} is zero"]
        return result
    if missing:
        result.outcome = "cannot_evaluate"
        result.missing = list(dict.fromkeys(missing))
        return result
    result.actual = round(actual, 4)
    ok = actual >= threshold if kind == "min" else actual <= threshold
    result.outcome = "pass" if ok else "deviation"
    return result


def assess(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> PolicyAssessment:
    policy = reader.load_policy(root)
    ratios = {r.key: r for r in policy.ratios}
    categories = {c.key: c.label for c in policy.deviation_categories}
    inputs = gather(conn, root, case)
    return PolicyAssessment(
        case_id=case.id,
        period=inputs.period,
        norms=[evaluate(n, ratios.get(n.ratio or ""), case, inputs, categories) for n in policy.norms],
    )
