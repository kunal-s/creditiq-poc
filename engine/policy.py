"""Policy norms and deviations (FRD F-20).

Every norm in config/policy.yaml is evaluated for the case: its expression
over the inputs below, against its threshold. The result shows the norm,
the required value, the actual value, the source figures with evidence,
pass or deviation, and the deviation category (F-20.2). A norm whose inputs
are not on file is "cannot evaluate", naming them, and never a pass
(F-20.3); so is a norm resting on a figure still waiting for review
(F-17.2), and one whose divisor is zero. A leverage norm on a net worth of
zero or less is a deviation, never a pass. Financial inputs come from the
latest audited statements.
"""

from __future__ import annotations

import ast
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import completeness, facts as facts_module, statements
from .configstore import reader
from .configstore.schema import PolicyNorm, PolicyRatio, unsupported_nodes
from .contracts import (CaseDetail, Evidence, FacilityFact, NormComponent, NormInput, NormResult, Obligation, PolicyAssessment,
                        PolicyCounts, PolicyGroup)
from .util import parse_date

WORKING_CAPITAL = {"cash_credit", "overdraft", "wcdl", "packing_credit", "post_shipment"}
TERM = {"term_loan"}
KNOWN_CONSTITUTIONS = {"private_limited", "proprietorship", "partnership"}

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
    # Lines that appear only inside a derived figure's breakdown (F-20.2).
    "cash_and_bank_balances": "Cash and bank balances",
    "short_term_loans_and_advances": "Short-term loans and advances",
    "other_current_liabilities": "Other current liabilities",
    "short_term_provisions": "Short-term provisions",
    "current_assets": "Current assets",
    "current_liabilities": "Current liabilities",
    "amount_requested": "Amount requested",
    "vintage_years": "Years in business",
    "bureau_rank": "Commercial bureau rank",
    "market_value": "Collateral market value",
    "realisable_value": "Collateral realisable value",
    "annual_instalments": "Annual instalments on existing facilities",
    "proposed_instalments": "Annual instalments on the proposed term loan",
    "blocking_items_open": "Blocking checklist items open",
    "audited_years": "Years of audited statements",
}


@dataclass
class Inputs:
    values: dict[str, NormInput] = field(default_factory=dict)
    period: str | None = None

    def put(self, name: str, value: float | None, evidence: list[Evidence] | None = None, manual: bool = False,
            pending: bool = False, basis: str = "document", refs: list[str] | None = None,
            components: list[NormComponent] | None = None) -> None:
        if value is None:
            return
        self.values[name] = NormInput(name=name, label=INPUT_LABELS[name], value=float(value), evidence=evidence or [],
                                      relies_on_manual=manual, awaiting_review=pending, basis=basis,  # type: ignore[arg-type]
                                      refs=refs or [], components=components or [])


def number(v: facts_module.Value | None) -> float | None:
    if v is None or v.value in (None, ""):
        return None
    try:
        return float(str(v.value).replace(",", ""))
    except ValueError:
        return None


def completed_months(since: date, as_of: date) -> int:
    """Whole months from `since` to `as_of`; a month counts once its day is reached (29 February to 28 February is short)."""
    months = (as_of.year - since.year) * 12 + (as_of.month - since.month)
    if as_of.day < since.day:
        months -= 1
    return max(months, 0)


def _near(a: float, b: float, pct: float) -> bool:
    return abs(a - b) <= pct / 100 * max(abs(a), abs(b))


def _document(f: FacilityFact) -> str | None:
    return f.evidence[0].document_id if f.evidence else None


def counted_facilities(facilities: list[FacilityFact], noise: list[str], threshold: float, emi_pct: float
                       ) -> tuple[list[FacilityFact], list[FacilityFact]]:
    """The declared and sanctioned facilities with an instalment, each counted once (FR-03).

    A lender matches on its resolved name only (same_entity): "Indian Bank" and "Indian Overseas
    Bank" are two lenders. A second document restating a facility already counted from the same
    source (a re-signed declaration, a renewed sanction letter: the same lender, facility and
    instalment) is not counted again; separate rows of one document are separate facilities. A
    sanction letter from a lender the declaration already lists with an instalment is that
    declared facility."""
    entity = lambda a, b: facts_module.same_entity(a, b, noise, threshold)  # noqa: E731

    def restates(kept: FacilityFact, f: FacilityFact) -> bool:
        return (_document(kept) != _document(f) and entity(kept.lender, f.lender)
                and (kept.facility or "") == (f.facility or "") and _near(kept.emi or 0, f.emi or 0, emi_pct))

    declared: list[FacilityFact] = []
    for f in facilities:
        if f.source == facts_module.DECLARATION and f.emi and not any(restates(d, f) for d in declared):
            declared.append(f)
    sanctioned: list[FacilityFact] = []
    for f in facilities:
        if (f.source == facts_module.SANCTION and f.emi and not any(entity(f.lender, d.lender) for d in declared)
                and not any(restates(s, f) for s in sanctioned)):
            sanctioned.append(f)
    return declared, sanctioned


def _pays(o: Obligation, f: FacilityFact, noise: list[str], threshold: float, emi_pct: float) -> bool:
    """A recurring bank debit pays facility f: the same lender by name, or a narration that
    abbreviates the lender ("TIDEWATER FIN") debiting the facility's instalment."""
    if facts_module.same_entity(o.lender, f.lender, noise, threshold):
        return True
    return facts_module.same_lender(o.lender, f.lender, noise, threshold) and _near(o.typical_amount, f.emi or 0, emi_pct)


def gather(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> Inputs:
    facts = facts_module.compute(conn, root, case)
    docs = facts_module.load_documents(conn, root, case.id)
    by_type = lambda *ids: [d for d in docs if any(t in d.types for t in ids)]  # noqa: E731
    alignment = reader.load_alignment(root)
    tolerances = {t.key: t.value for t in reader.load_tolerances(root).tolerances}
    start = alignment.financial_year_start_month
    noise = [w.lower() for w in alignment.name_noise_words]
    threshold = tolerances.get("name_match", 0.85)
    inputs = Inputs()
    as_of = date.fromisoformat(case.as_of)

    # The latest audited statements, and how many years are on file.
    cfg = reader.load_statements(root)
    audited = []
    for d in by_type("audited_financial_statements"):
        end = statements.period_end(d)
        if end:
            audited.append((end, d))
    audited.sort(key=lambda pair: pair[0])
    years = {facts_module.fy_of(end.year, end.month, start) for end, _ in audited}
    labels = [d.get("financial_year") for _, d in audited]
    inputs.put("audited_years", len(years), [e for _, d in audited for e in d.evidence(d.get("financial_year"))[:1]],
               pending=any(v is not None and v.pending for v in labels))
    if audited:
        end = audited[-1][0]
        inputs.period = facts_module.fy_name(facts_module.fy_of(end.year, end.month, start), start)
        # More than one copy of the latest year's statements: each figure from the first copy that has it.
        copies = [statements.lines(d, cfg) for e, d in audited if e == end]
        for name in FINANCIAL_INPUTS:
            line = next((c[name] for c in copies if name in c), None)
            if line:
                # A derived figure (net worth, current assets) carries the lines it was summed
                # from, so the screen can show the arithmetic rather than only the total.
                inputs.put(name, line.value, line.evidence, line.manual, pending=line.pending,
                           components=[
                               NormComponent(label=INPUT_LABELS.get(part.name, part.name), sign=part.sign,
                                             value=part.value, evidence=part.evidence)
                               for part in line.parts
                           ])

    # The amount asked for: the case record, citing the sourcing message where it came from.
    requested = facts.requested_amount
    if requested is not None:
        inputs.put("amount_requested", float(requested.value), requested.evidence, requested.relies_on_manual,
                   basis="document" if requested.evidence else "case")

    # Years in business: completed months since incorporation, never rounded up to a threshold.
    found = next(((d, d.get("date_of_incorporation")) for d in by_type("certificate_of_incorporation")
                  if d.get("date_of_incorporation")), None)
    if found and (since := parse_date(found[1].value)):
        inputs.put("vintage_years", round(completed_months(since, as_of) / 12, 4), found[0].evidence(found[1]),
                   found[1].manual, pending=found[1].pending)

    # Commercial bureau rank: the latest report by its date (undated or tied: the last filed).
    reports = [(parse_date(d.get("report_date").value) if d.get("report_date") else None, i, d)
               for i, d in enumerate(by_type("commercial_bureau_report"))]
    if reports:
        _, _, latest = max(reports, key=lambda r: (r[0] or date.min, r[1]))
        rank = latest.get("credit_rank")
        digits = re.search(r"\d+", str(rank.value)) if rank else None
        if rank and digits:
            inputs.put("bureau_rank", int(digits[0]), latest.evidence(rank), rank.manual, pending=rank.pending)

    # Annual instalments on existing facilities: declared, then sanctioned, then inferred from the
    # bank statements, each facility counted once.
    emi_pct = tolerances.get("emi_amount_match", 5)
    declared, sanctioned = counted_facilities(facts.facilities, noise, threshold, emi_pct)
    inferred = [o for o in facts.obligations
                if not any(_pays(o, f, noise, threshold, emi_pct) for f in declared + sanctioned)]
    if declared or sanctioned or inferred:
        monthly = sum(f.emi or 0 for f in declared + sanctioned) + sum(o.typical_amount for o in inferred)
        inputs.put("annual_instalments", monthly * 12,
                   [e for f in declared + sanctioned for e in f.evidence[:1]] + [e for o in inferred for e in o.evidence[:1]],
                   any(f.relies_on_manual for f in declared + sanctioned),
                   pending=any(f.awaiting_review for f in declared + sanctioned))
    elif sum(1 for m in facts.months if m.bank is not None) >= int(tolerances.get("emi_min_occurrences", 3)):
        # Enough months of statements and no instalment in them: none on existing facilities.
        inputs.put("annual_instalments", 0, [e for a in facts.accounts if a.has_statement for e in a.evidence[:1]],
                   basis="statements_coverage")

    # Annual instalments on the proposed term loan, from the monthly instalment the RM entered.
    if set(case.facilities) & TERM:
        emi = facts.proposed_emi
        if emi is not None:
            inputs.put("proposed_instalments", float(emi.value) * 12, emi.evidence, emi.relies_on_manual,
                       basis="document" if emi.evidence else "case")
    else:
        inputs.put("proposed_instalments", 0, basis="not_requested")

    # Blocking checklist items still open (F-13), and which.
    readiness, _ = completeness.evaluate(conn, root, case)
    open_items = [s.item_id for s in readiness.items if s.blocking and s.status not in ("satisfied", "waived")]
    inputs.put("blocking_items_open", readiness.blocking_open, basis="checklist", refs=open_items)
    return inputs


# --- Expressions ---


class _Unsupported(Exception):
    pass


def evaluate_expression(node: ast.AST, values: dict[str, float], missing: list[str],
                        divisors: list[tuple[str, float]] | None = None) -> float:
    """The expression's value; missing inputs are named, and every divisor is recorded with its value.
    A zero divisor gives 0.0: the caller decides what it means."""
    divisors = divisors if divisors is not None else []
    if isinstance(node, ast.Expression):
        return evaluate_expression(node.body, values, missing, divisors)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in values:
            missing.append(INPUT_LABELS.get(node.id, node.id))
            return 0.0
        return values[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -evaluate_expression(node.operand, values, missing, divisors)
    if isinstance(node, ast.BinOp):
        left = evaluate_expression(node.left, values, missing, divisors)
        right = evaluate_expression(node.right, values, missing, divisors)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            divisors.append((words(ast.unparse(node.right)), right))
            return left / right if right else 0.0
    raise _Unsupported(f"unsupported expression {ast.unparse(node)!r}")


def words(expression: str) -> str:
    """The expression with its inputs named: "Current assets ÷ Current liabilities"."""
    text = re.sub(r"[a-z_]+", lambda m: INPUT_LABELS.get(m[0], m[0]), expression)
    return text.replace("/", "÷").replace("*", "×")


# --- Norms ---


def _fixed(value: float, decimals: int) -> str:
    """The value to so many decimals, never "-0" for a value that rounds to zero."""
    text = f"{value:.{decimals}f}"
    return text[1:] if text.startswith("-") and float(text) == 0 else text


def _counted(text: str, word: str) -> str:
    """The count with its word, singular only for exactly one: 1 year, 2 years, 0.5 years."""
    return f"{text} {word}" if text.lstrip("-") == "1" else f"{text} {word}s"


def unit_text(value: float, unit: str | None, extra: int = 0) -> str:
    if unit == "x":
        return f"{_fixed(value, 2 + extra)}x"
    if unit == "%":
        return f"{_fixed(value, 1 + extra)}%" if value % 1 or extra else f"{value:.0f}%"
    if unit == "days":
        return _counted(_fixed(value, extra), "day")
    if unit == "years":
        # Years and completed months, as the memo states the time in business; never rounded up to a
        # threshold: 2.99 years is "2 years 11 months". A value is a count of months over 12 to four
        # places, so a whole month is never lost to the rounding.
        years, months = divmod(math.floor(value * 12 + 1e-3), 12)
        parts = ([_counted(str(years), "year")] if years else []) + ([_counted(str(months), "month")] if months else [])
        return " ".join(parts) or "0 years"
    if unit == "inr":
        return facts_module.inr(value)
    if unit == "rank":
        return f"rank {value:g}"
    return f"{value:g}"


_DECIMALS = {"x": 2, "%": 1, "days": 0}


def actual_text(value: float, unit: str | None, threshold: float, outcome: str) -> str:
    """The actual as written; a deviation never reads the same as its norm (20.04% against at
    most 20%, never 20.0%): decimals are added while the two still round to the same number."""
    if outcome != "deviation" or unit not in _DECIMALS:
        return unit_text(value, unit)
    base, extra = _DECIMALS[unit], 0
    # Up to the 9 decimals the outcome is decided at, so even the smallest deviation shows.
    while base + extra < 9 and round(value, base + extra) == round(threshold, base + extra):
        extra += 1
    return unit_text(value, unit, extra)


def required_text(kind: str, threshold: float, unit: str | None) -> str:
    """The norm as written: "at least 1.20x". A rupee figure that must be positive, a profit that must
    not be a loss and a count that must be nil read in words, never "at least INR 1" or "at most 0"."""
    if unit == "inr" and kind == "min" and threshold in (0, 1):
        return "positive" if threshold == 1 else "no loss"
    if unit == "count" and kind == "max" and threshold == 0:
        return "none"
    return f"{'at least' if kind == 'min' else 'at most'} {unit_text(threshold, unit)}"


def _applies(norm: PolicyNorm, case: CaseDetail, inputs: Inputs, wc_limit: float) -> bool:
    if norm.constitutions and case.constitution in KNOWN_CONSTITUTIONS and case.constitution not in norm.constitutions:
        return False
    if norm.applies_when == "working_capital":
        return bool(set(case.facilities) & WORKING_CAPITAL)
    if norm.applies_when == "turnover_method":
        return bool(set(case.facilities) & WORKING_CAPITAL) and case.amount_inr <= wc_limit
    if norm.applies_when == "term_debt":
        instalments = inputs.values.get("annual_instalments")
        return bool(set(case.facilities) & TERM) or bool(instalments and instalments.value)
    if norm.applies_when == "collateral":
        return bool(case.collateral_present)
    return True


def evaluate(norm: PolicyNorm, ratio: PolicyRatio | None, case: CaseDetail, inputs: Inputs,
             categories: dict[str, str], wc_limit: float = float("inf")) -> NormResult:
    label = norm.label or (ratio.label if ratio else norm.id)
    unit = norm.unit or (ratio.unit if ratio else None)
    kind = norm.kind or (ratio.kind if ratio else "min")
    threshold = norm.threshold if norm.threshold is not None else (ratio.acceptable if ratio else 0.0)
    required = required_text(kind, threshold, unit)
    status = norm.status or (ratio.status if ratio else None)
    result = NormResult(
        id=norm.id, family=norm.family, label=label, formula=words(norm.expression),
        definition=ratio.formula if ratio else None, source=norm.source or (ratio.source if ratio else None),
        required=required, comparator=kind, threshold_text=unit_text(threshold, unit),
        unit=unit, outcome="not_applicable", category=norm.category,
        category_label=categories.get(norm.category, norm.category), note=norm.note or (ratio.note if ratio else None),
        provisional=status == "provisional",
    )
    if not _applies(norm, case, inputs, wc_limit):
        return result
    tree = ast.parse(norm.expression, mode="eval")
    if unsupported_nodes(tree):
        result.outcome = "cannot_evaluate"
        result.missing = ["a supported expression"]
        return result
    names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
    result.inputs = [inputs.values[n] for n in dict.fromkeys(names) if n in inputs.values]
    missing: list[str] = []
    divisors: list[tuple[str, float]] = []
    try:
        actual = evaluate_expression(tree, {k: v.value for k, v in inputs.values.items() if v.value is not None},
                                     missing, divisors)
    except _Unsupported:
        result.outcome = "cannot_evaluate"
        result.missing = ["a supported expression"]
        return result
    if missing:
        result.outcome = "cannot_evaluate"
        result.missing = list(dict.fromkeys(missing))
        return result
    waiting = [i.label for i in result.inputs if i.awaiting_review]
    if waiting:
        # F-17.2: a figure below its confidence threshold is reviewed before a norm relies on it.
        result.outcome, result.reason, result.reason_inputs = "cannot_evaluate", "awaiting_review", waiting
        return result
    bad = [(text, value) for text, value in divisors if value <= 0]
    if bad:
        labels = list(dict.fromkeys(text for text, _ in bad))
        result.reason_inputs = labels
        if norm.non_positive_denominator == "deviation":
            result.outcome, result.reason = "deviation", "denominator_not_positive"
            result.actual_text = f"unbounded ({', '.join(labels)} zero or negative)"
        else:
            result.outcome = "cannot_evaluate"
            result.reason = "zero_denominator" if all(value == 0 for _, value in bad) else "denominator_not_positive"
        return result
    result.actual = round(actual, 4)
    # Inclusive, and compared at 9 decimals so a value equal to the threshold is never lost to floating point.
    value = round(actual, 9)
    ok = value >= threshold if kind == "min" else value <= threshold
    result.outcome = "pass" if ok else "deviation"
    result.actual_text = actual_text(actual, unit, threshold, result.outcome)
    return result


FAMILIES = ("eligibility", "ratios", "documentation", "security_cover")
"""The families in the order the Policy page shows them."""
HIGHLIGHTS = 3


def assess(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> PolicyAssessment:
    policy = reader.load_policy(root)
    ratios = {r.key: r for r in policy.ratios}
    categories = {c.key: c.label for c in policy.deviation_categories}
    inputs = gather(conn, root, case)
    wc_limit = policy.working_capital.mpbf_above_limit_inr
    norms = [evaluate(n, ratios.get(n.ratio or ""), case, inputs, categories, wc_limit) for n in policy.norms]
    return PolicyAssessment(
        case_id=case.id,
        period=inputs.period,
        norms=norms,
        config_version=reader.published_version(root)["version"],
        counts=_counts(norms),
        groups=[_group(family, [n for n in norms if n.family == family]) for family in FAMILIES],
    )


def _counts(norms: list[NormResult]) -> PolicyCounts:
    outcomes = [n.outcome for n in norms]
    return PolicyCounts(deviations=outcomes.count("deviation"), cannot_evaluate=outcomes.count("cannot_evaluate"),
                        passed=outcomes.count("pass"), not_applicable=outcomes.count("not_applicable"))


def _group(family: str, norms: list[NormResult]) -> PolicyGroup:
    """A family's overview card: its counts, where it stands, and the norms to show first."""
    counts = _counts(norms)
    status = ("no_norms" if not norms else "deviation" if counts.deviations
              else "cannot_evaluate" if counts.cannot_evaluate else "clear")
    picks = [n.id for outcome in ("deviation", "cannot_evaluate", "pass") for n in norms if n.outcome == outcome]
    return PolicyGroup(family=family, norms=len(norms), counts=counts, status=status,  # type: ignore[arg-type]
                       highlights=picks[:HIGHLIGHTS])
