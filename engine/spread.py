"""The spread, interim layout (FRD F-22; decision C.4-8).

Financial-statement lines by year for audited, provisional and projected
statements (F-22.1); derived lines and ratios with their workings, the
ratios using the same configured formulas as the policy norms, so the two
never disagree; and the working-capital assessment by the turnover method or
MPBF as configured for the limit (F-22.2). Every figure carries its source
page; a derived figure names its inputs (F-22.3). The layout is re-mapped to
RBL's rows when its template arrives.
"""

from __future__ import annotations

import ast
import sqlite3
from datetime import date
from pathlib import Path

from . import facts as facts_module
from . import policy as policy_module
from .configstore import reader
from .contracts import (
    CaseDetail,
    Evidence,
    Spread,
    SpreadCell,
    SpreadColumn,
    SpreadRow,
    Working,
    WorkingCapitalAssessment,
)
from .util import parse_date

BASIS = {
    "audited_financial_statements": "audited",
    "provisional_financial_statements": "provisional",
    "projected_financial_statements": "projected",
}

PROFIT_AND_LOSS = [
    "revenue_from_operations", "other_income", "ebitda", "depreciation", "finance_costs", "profit_before_tax",
    "profit_after_tax",
]
BALANCE_SHEET = [
    "share_capital", "reserves_and_surplus", "net_worth", "long_term_borrowings", "short_term_borrowings",
    "total_borrowings", "trade_payables", "current_liabilities", "inventories", "trade_receivables",
    "current_assets",
]

# Derived lines: key, label, section, unit, expression over the lines above.
DERIVED = [
    ("total_income", "Total income", "profit_and_loss", "inr", "revenue_from_operations + other_income"),
    ("ebitda_margin", "EBITDA margin", "profit_and_loss", "%", "ebitda / revenue_from_operations * 100"),
    ("pat_margin", "Net profit margin", "profit_and_loss", "%", "profit_after_tax / revenue_from_operations * 100"),
    ("net_working_capital", "Net working capital", "balance_sheet", "inr", "current_assets - current_liabilities"),
    ("tol", "Total outside liabilities", "balance_sheet", "inr", "long_term_borrowings + current_liabilities"),
]
BASIS_ORDER = {"audited": 0, "provisional": 1, "projected": 2}


def _columns(conn: sqlite3.Connection, root: Path, case: CaseDetail):
    """Columns in order (audited by year, then provisional, then projected),
    each with its documents; several copies of one year merge line by line."""
    start = reader.load_alignment(root).financial_year_start_month
    groups: dict[tuple[str, int], list[facts_module.Doc]] = {}
    ends: dict[tuple[str, int], date] = {}
    for d in facts_module.load_documents(conn, root, case.id):
        basis = next((BASIS[t] for t in d.types if t in BASIS), None)
        end = parse_date(d.get("period_end").value) if basis and d.get("period_end") else None
        if not (basis and end):
            continue
        fy = facts_module.fy_of(end.year, end.month, start)
        groups.setdefault((basis, fy), []).append(d)
        ends[(basis, fy)] = max(end, ends.get((basis, fy), end))
    keys = sorted(groups, key=lambda k: (BASIS_ORDER[k[0]], k[1]))
    columns = [
        SpreadColumn(key=f"{basis}-{fy}", fy=facts_module.fy_name(fy, start), period_end=ends[(basis, fy)].isoformat(),
                     basis=basis)  # type: ignore[arg-type]
        for basis, fy in keys
    ]
    return columns, [groups[k] for k in keys]


def _line(docs: list[facts_module.Doc], name: str) -> SpreadCell:
    for d in docs:
        v = d.get(name)
        number = policy_module.number(v)
        if number is not None:
            return SpreadCell(value=number, evidence=d.evidence(v), relies_on_manual=v.manual)
    return SpreadCell()


def _derived(expression: str, lines: dict[str, SpreadCell]) -> SpreadCell:
    tree = ast.parse(expression, mode="eval")
    names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]
    values = {k: c.value for k, c in lines.items() if c.value is not None}
    missing: list[str] = []
    try:
        value = policy_module.evaluate_expression(tree, values, missing)
    except ZeroDivisionError:
        return SpreadCell()
    if missing:
        return SpreadCell()
    evidence: list[Evidence] = []
    for n in dict.fromkeys(names):
        evidence += lines[n].evidence[:1] if n in lines else []
    return SpreadCell(value=round(value, 4), evidence=evidence,
                      relies_on_manual=any(lines[n].relies_on_manual for n in names if n in lines))


def _working_capital(root: Path, case: CaseDetail, columns: list[SpreadColumn],
                     lines_by_column: list[dict[str, SpreadCell]]) -> WorkingCapitalAssessment:
    wc = reader.load_policy(root).working_capital
    requested = float(case.amount_inr)
    if not set(case.facilities) & policy_module.WORKING_CAPITAL:
        return WorkingCapitalAssessment(method="not_applicable", requested=requested,
                                        reason="No working-capital facility is requested.")
    limit = facts_module.inr(wc.mpbf_above_limit_inr)
    # Projected figures first, then provisional, then the latest audited.
    order = sorted(range(len(columns)), key=lambda i: (BASIS_ORDER[columns[i].basis], columns[i].period_end))[::-1]

    if requested <= wc.mpbf_above_limit_inr:
        pick = next((i for i in order if lines_by_column[i]["revenue_from_operations"].value), None)
        result = WorkingCapitalAssessment(
            method="turnover", requested=requested,
            reason=f"The request is within {limit}, so the turnover method applies.")
        if pick is None:
            result.missing = ["Revenue from operations (projected, provisional or audited)"]
            return result
        turnover = lines_by_column[pick]["revenue_from_operations"]
        col = columns[pick]
        result.column = f"{col.fy} ({col.basis})"
        requirement = turnover.value * wc.turnover_requirement_pct / 100
        margin = turnover.value * wc.turnover_margin_pct / 100
        eligible = requirement - margin
        result.steps = [
            Working(label="Turnover", value=turnover.value, basis=f"Revenue from operations, {result.column}",
                    evidence=turnover.evidence),
            Working(label="Working-capital requirement", value=requirement,
                    basis=f"{wc.turnover_requirement_pct:g}% of turnover"),
            Working(label="Minimum margin from the borrower", value=margin,
                    basis=f"{wc.turnover_margin_pct:g}% of turnover"),
            Working(label="Eligible bank finance", value=eligible, basis="Requirement less the margin"),
        ]
        result.eligible = eligible
        return result

    pick = next((i for i in order if lines_by_column[i]["current_assets"].value is not None
                 and lines_by_column[i]["current_liabilities"].value is not None), None)
    result = WorkingCapitalAssessment(
        method="mpbf", requested=requested,
        reason=f"The request is above {limit}, so the MPBF method (second method) applies.")
    if pick is None:
        result.missing = ["Current assets", "Current liabilities"]
        return result
    lines = lines_by_column[pick]
    col = columns[pick]
    result.column = f"{col.fy} ({col.basis})"
    ca, cl = lines["current_assets"], lines["current_liabilities"]
    bank = lines["short_term_borrowings"].value or 0.0
    other_cl = cl.value - bank
    gap = ca.value - other_cl
    margin = ca.value * wc.mpbf_margin_pct / 100
    mpbf = gap - margin
    result.steps = [
        Working(label="Current assets", value=ca.value, basis=result.column, evidence=ca.evidence),
        Working(label="Current liabilities other than bank borrowings", value=other_cl,
                basis="Current liabilities less short-term borrowings",
                evidence=cl.evidence + lines["short_term_borrowings"].evidence[:1]),
        Working(label="Working-capital gap", value=gap, basis="Current assets less other current liabilities"),
        Working(label="Minimum margin from the borrower", value=margin,
                basis=f"{wc.mpbf_margin_pct:g}% of current assets"),
        Working(label="Maximum permissible bank finance", value=mpbf, basis="Gap less the margin"),
    ]
    result.eligible = mpbf
    return result


def build(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> Spread:
    policy = reader.load_policy(root)
    ratios = {r.key: r for r in policy.ratios}
    columns, groups = _columns(conn, root, case)
    lines_by_column = [{name: _line(docs, name) for name in PROFIT_AND_LOSS + BALANCE_SHEET} for docs in groups]
    rows: list[SpreadRow] = []
    for section, names in (("profit_and_loss", PROFIT_AND_LOSS), ("balance_sheet", BALANCE_SHEET)):
        for name in names:
            rows.append(SpreadRow(key=name, label=policy_module.INPUT_LABELS[name], section=section, kind="line",
                                  unit="inr", cells=[lines[name] for lines in lines_by_column]))
        for key, label, sec, unit, expression in DERIVED:
            if sec == section:
                rows.append(SpreadRow(key=key, label=label, section=sec, kind="derived", unit=unit,
                                      formula=policy_module.words(expression),
                                      cells=[_derived(expression, lines) for lines in lines_by_column]))
    # Ratios: the policy's ratio norms, per year, where every input is a statement line.
    statement_lines = set(PROFIT_AND_LOSS + BALANCE_SHEET)
    for norm in policy.norms:
        ratio = ratios.get(norm.ratio or "")
        if norm.family != "ratios" or ratio is None:
            continue
        names = {n.id for n in ast.walk(ast.parse(norm.expression, mode="eval")) if isinstance(n, ast.Name)}
        if not names <= statement_lines:
            continue
        rows.append(SpreadRow(key=ratio.key, label=ratio.label, section="ratios", kind="ratio",
                              unit=ratio.unit, formula=ratio.formula,
                              cells=[_derived(norm.expression, lines) for lines in lines_by_column]))
    return Spread(case_id=case.id, columns=columns, rows=rows,
                  working_capital=_working_capital(root, case, columns, lines_by_column))
