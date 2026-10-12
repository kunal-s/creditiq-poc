"""Cards for TO-01 to TO-05, TX-01, TX-02, FS-01 and FS-02 (turnover, tax, statements).

Presentation only: built after the rule has decided its outcome (see engine/xv_cards/__init__.py).

Each figure the rule compared is a column with the rows behind it, so the headline can be
reconciled line by line: a GST figure with its returns month by month; a bank figure with each
account's credits by month, the credits excluded and each exclusion (the figure is the credits
less the excluded credits over the months it counts, and only those months are shown); a
statement figure with its printed line. Gaps are measured as the rule measures them, against the
rule's own tolerance.

A check of a financial year that has not ended by the appraisal date asks for nothing: no return,
statement or audit the customer could send now would complete it (its explanation still names the
months it lacks). Only months that ended before the appraisal date are called missing.

The key figures of a turnover check: the two figures side by side, the smaller marked on a
discrepancy, and how far apart they are against the tolerance ("25.0% apart · tolerance 10%");
for a check that could not run, what would complete it.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import TYPE_CHECKING

from ..contracts import (
    Evidence,
    EvidenceRow,
    FactValue,
    Finding,
    FindingSide,
    FinancialYear,
    GapLeg,
    MonthFigure,
    SourceColumn,
    TurnoverFigure,
    TurnoverYear,
    XvHighlight,
)
from ..crosschecks import CASE_RECORD, FIGURE_SOURCES, LINE_LABELS, TURNOVER_PAIRS, _previous_year
from ..facts import fy_months, fy_of
from ..util import display_date, month_label, parse_date, ranges_label
from . import builds, column, documents, fact, highlight, join, pair_leg, row, wanted

if TYPE_CHECKING:
    from ..configstore.schema import CrossCheckRule
    from ..crosschecks import Context

AUDITED, GSTR, BANK, ITR = "audited_financial_statements", "gstr_3b", "bank_statement", "income_tax_return"
SHORT = {"financials": "audited", "gst": "GST outward supplies", "bank": "bank credits", "declared": "declared",
         "itr": "tax return"}
"""How each turnover figure is named in a gap leg: "Gap against bank credits", "of audited"."""
NAMES = {"financials": "audited", "gst": "GST", "bank": "bank credits", "declared": "declared", "itr": "tax return"}
"""How a turnover check is named on the overview card: "GST against bank credits · FY 2025-26"."""
FIGURES = {"financials": "Audited", "gst": "GST outward supplies", "bank": "Bank credits", "declared": "Declared",
           "itr": "Tax return"}
"""Each figure's label beside its value on the overview card."""
TAX_RETURN = "tax return"
# What would complete a check, read after "Please provide": the months a figure lacks, or a figure
# missing for a year (by its source). A document not on file is asked for in the words every card
# uses (engine/xv_cards/__init__.py).
FIGURE_WANTED = {"financials": "audited financial statements for {fy}", "gst": "GSTR-3B returns for {fy}",
                 "bank": "bank statements for {fy}", "declared": "the turnover declared for {fy}",
                 "itr": "the income tax return for {fy}"}
GST_ROWS = ["Period", "Filed", "3.1(a)+(b)+(c) outward supplies"]
"""A month's GST figure is the sum of the rows of table 3.1 that config/statements.yaml names
(gst_outward): (a) taxable, (b) zero rated, (c) nil rated and exempted outward supplies."""
BANK_ROWS = ["Month", "Account", "Credits", "Excluded credits"]
LINE_ROWS = ["Line", "Year", "Amount"]


# --- TO-01 to TO-04: two turnover figures for one financial year ---


@builds(*TURNOVER_PAIRS)
def _turnover(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    year = next((y for y in ctx.facts.turnover if y.fy == finding.scope), None)
    _turnover_card(ctx, rule, finding, year)
    finding.highlights = _turnover_lines(ctx, rule, finding, year)


def _turnover_card(ctx: Context, rule: CrossCheckRule, finding: Finding, year: TurnoverYear | None) -> None:
    if year is None or finding.outcome == "not_applicable":
        return
    left, right = _figures(rule, year)
    finding.columns = [_figure_column(ctx, year, f, finding) for f in (left, right) if f is not None]
    if finding.outcome in ("pass", "fail") and left is not None and right is not None:
        leg = _leg(SHORT[left.source], float(left.value or 0), SHORT[right.source], float(right.value or 0),
                   ctx.tol(rule.tolerance, 10), finding)
        _measured(ctx, rule, finding, [leg], leg.amount)
    elif finding.outcome == "incomplete" and not finding.missing:
        finding.request = _turnover_wanted(ctx, rule, year, left, right)


def _turnover_lines(ctx: Context, rule: CrossCheckRule, finding: Finding,
                    year: TurnoverYear | None) -> list[XvHighlight]:
    """The overview card's line: the two figures the rule compared for the year, and how far apart;
    for a check that could not run, what would complete it (a year not yet ended: when it ends)."""
    if finding.outcome == "not_applicable":
        return []
    left_key, right_key = TURNOVER_PAIRS[rule.variable]
    left, right = _figures(rule, year) if year is not None else (None, None)
    name = _name(left.source if left else left_key, right.source if right else right_key)
    label = f"{name} · {finding.scope}" if finding.scope else name
    if finding.outcome == "incomplete":
        ends = None if year is None or _ended(ctx, year) else f"the year ends on {_day(year.fy_end)}"
        return [highlight(finding, label, note=wanted(finding) or ends)]
    if left is None or right is None:
        return []
    return [_compared(finding, label, [(left.source, left.value), (right.source, right.value)])]


def _ended(ctx: Context, year: TurnoverYear) -> bool:
    """Whether the financial year ended before the appraisal date (a year whose end cannot be read
    is taken to have ended)."""
    end = parse_date(year.fy_end)
    return end is None or end < ctx.as_of


def _over(month: tuple[int, int], as_of: date) -> bool:
    """Whether a month ended before the appraisal date: any month before the appraisal date's own."""
    return month < (as_of.year, as_of.month)


def _figures(rule: CrossCheckRule, year: TurnoverYear) -> tuple[TurnoverFigure | None, TurnoverFigure | None]:
    """The two figures the rule compares for the year, picked as the rule picks them (TO-04: the
    audited figure, or a full year of GST returns when there is none)."""
    left_key, right_key = TURNOVER_PAIRS[rule.variable]
    by = {f.source: f for f in year.figures}
    right = by.get(right_key)
    if rule.variable == "turnover_declared_vs_evidenced" and right is None:
        gst = by.get("gst")
        right = gst if gst and gst.months_covered == 12 else None
    return by.get(left_key), right


def _turnover_wanted(ctx: Context, rule: CrossCheckRule, year: TurnoverYear, left: TurnoverFigure | None,
                     right: TurnoverFigure | None) -> str | None:
    """What would complete the comparison: the months a figure lacks, or the figure not on file.
    None while a figure waits for a person's review: the review completes it. None for a year that
    has not ended by the appraisal date: its returns, statements and audit cannot all exist yet."""
    figures = [f for f in (left, right) if f is not None]
    if not figures or any(f.awaiting_review for f in figures) or not _ended(ctx, year):
        return None
    if left is None or right is None:
        left_key, right_key = TURNOVER_PAIRS[rule.variable]
        return FIGURE_WANTED[right_key if left is not None else left_key].format(fy=year.fy)
    months = [m for m in _year_months(ctx, year) if _over(m, ctx.as_of)]
    asked = []
    for f in figures:
        if f.months_covered is None or f.months_covered >= 12:
            continue
        absent = set(f.months_missing)
        span = ranges_label([m for m in months if month_label(m) in absent])
        if span and f.source == "gst":
            asked.append(f"GSTR-3B returns for {span}")
        elif span and f.source == "bank":
            asked.append(f"bank statements for every account covering {span}")
    return " and ".join(asked) or None


def _figure_column(ctx: Context, year: TurnoverYear, f: TurnoverFigure, finding: Finding) -> SourceColumn:
    side = _side(finding, FIGURE_SOURCES[f.source])
    flags = dict(differs=bool(side and side.differs), manual=f.relies_on_manual, awaiting=f.awaiting_review,
                 field_ids=f.field_ids, evidence=f.evidence)
    months = _year_months(ctx, year)
    if f.source == "gst":
        in_year = set(months)
        shown = [m for m in ctx.facts.months if m.gst is not None and _ym(m.month) in in_year]
        present = [_ym(m.month) for m in shown]
        filed = f.months_covered if f.months_covered is not None else len(present)
        coverage = _line(_period(present), f"{filed} of {len(months)} returns filed")
        # A month that has not ended by the appraisal date is not missing: it has not happened yet.
        missing = [m for m in months if m not in set(present) and _over(m, ctx.as_of)]
        if missing:
            coverage += f"; {ranges_label(missing)} missing"
        return _gst_column(ctx, shown, f.value, total=f"Aggregate {year.fy}", coverage=coverage, **flags)
    if f.source == "bank":
        # The months the figure counts: those every account's statements cover.
        absent = set(f.months_missing)
        covered = [m for m in months if month_label(m) not in absent]
        return _bank_column(ctx, covered, f.value, total=f"Total {year.fy}", **flags)
    if f.source == "financials":
        return _line_column(ctx, "audited", "Audited financial statements", [AUDITED], "Revenue from operations",
                            year.fy, f.value, coverage=f"Year ended {_day(year.fy_end)} · audited", **flags)
    if f.source == "itr":
        tax = {t.fy: t for t in ctx.facts.tax_years}.get(year.fy)
        ay = f"AY {tax.assessment_year}" if tax else year.fy
        return _line_column(ctx, "itr", "Income tax return", [ITR], "Turnover as per the return", ay, f.value,
                            coverage=f"{ay} · for {year.fy}", **flags)
    return _line_column(ctx, "declared", "Turnover declared in the sourcing message", [CASE_RECORD],
                        "Declared turnover", year.fy, f.value, coverage=f"Declared for {year.fy}", **flags)


# --- TO-05: GST against bank credits over the months both cover ---


@builds("turnover_gst_vs_bank_window")
def _turnover_window(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    _window_card(ctx, rule, finding)
    finding.highlights = _window_lines(finding)


def _window_lines(finding: Finding) -> list[XvHighlight]:
    """The overview card's line: GST and bank credits over the months both cover, and how far apart;
    for a check that could not run, what would complete it."""
    if finding.outcome == "not_applicable":
        return []
    label = f"{_name('gst', 'bank')} · {finding.scope or 'months both cover'}"
    if finding.outcome == "incomplete":
        return [highlight(finding, label, note=wanted(finding))]
    shown = {c.key: c.value for c in finding.columns}
    if "gst" not in shown or "bank" not in shown:
        return []
    return [_compared(finding, label, [("gst", shown["gst"]), ("bank", shown["bank"])])]


def _window_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    if finding.outcome == "not_applicable":
        return
    months = ctx.facts.months
    if finding.scope:
        # The window the rule compared (or would have, but for a value waiting for review).
        both = [m for m in months if m.gst is not None and m.bank is not None]
        g_total, b_total = sum(m.gst or 0 for m in both), sum(m.bank or 0 for m in both)
        finding.columns = [
            _gst_column(ctx, both, g_total, total=f"Aggregate {finding.scope}",
                        coverage=_line(finding.scope, _count(len(both), "return")),
                        **_side_flags(_side(finding, GSTR))),
            _bank_column(ctx, [_ym(m.month) for m in both], b_total, total=f"Total {finding.scope}",
                         **_side_flags(_side(finding, BANK))),
        ]
        if finding.outcome in ("pass", "fail"):
            leg = _leg(SHORT["gst"], g_total, SHORT["bank"], b_total, ctx.tol(rule.tolerance, 10), finding)
            _measured(ctx, rule, finding, [leg], leg.amount)
        return
    # Not compared: what each source covers on its own.
    gst = [m for m in months if m.gst is not None]
    bank = [_ym(m.month) for m in months if m.bank is not None]
    columns = []
    if gst:
        span = ranges_label([_ym(m.month) for m in gst])
        columns.append(_gst_column(ctx, gst, sum(m.gst or 0 for m in gst), total=f"Aggregate {span}",
                                   coverage=_line(span, _count(len(gst), "return"))))
    if bank:
        columns.append(_bank_column(ctx, bank, sum(m.bank or 0 for m in months if m.bank is not None),
                                    total=f"Total {ranges_label(bank)}"))
    finding.columns = columns
    if gst and bank and not finding.missing:
        need = int(ctx.tol("turnover_window_min_months", 3))
        finding.request = f"GSTR-3B returns and bank statements covering the same months (at least {need})"


# --- The columns of a turnover card ---


def _gst_column(ctx: Context, months: list[MonthFigure], value: float | None, *, total: str, coverage: str,
                differs: bool = False, manual: bool = False, awaiting: bool = False, field_ids: Iterable[str] = (),
                evidence: Iterable[Evidence] = ()) -> SourceColumn:
    """The returns month by month (period, filing date, outward supplies) and their aggregate, the figure."""
    rows = [row([m.label, m.gst_filed, m.gst], m.gst_evidence) for m in months]
    rows.append(row([total, "", value], kind="total"))
    return column(ctx, "gst", "GST outward supplies (GSTR-3B)", sources=[GSTR], value=value, unit="inr",
                  coverage=coverage, differs=differs, manual=manual, awaiting=awaiting, field_ids=field_ids,
                  evidence=_pages(evidence, rows), row_columns=GST_ROWS, rows=rows)


def _bank_column(ctx: Context, months: list[tuple[int, int]], value: float | None, *, total: str,
                 differs: bool = False, manual: bool = False, awaiting: bool = False, field_ids: Iterable[str] = (),
                 evidence: Iterable[Evidence] = ()) -> SourceColumn:
    """Each account's credits month by month over `months` (the months the figure counts), their total,
    then every credit excluded in those months: the credits less the excluded credits are the figure."""
    credits = ctx.facts.credits
    counted = {f"{y}-{m:02d}" for y, m in months}
    lines = sorted(((m.month, i, m, c.account) for i, c in enumerate(credits) for m in c.by_month if m.month in counted),
                   key=lambda t: t[:2])
    rows = [row([m.label, account, m.gross, m.excluded], m.evidence) for _, _, m, account in lines]
    rows.append(row([total, "", sum(t[2].gross for t in lines), sum(t[2].excluded for t in lines)], kind="total"))
    order = {c.account: i for i, c in enumerate(credits)}
    removed = sorted((e for c in credits for e in c.exclusions if e.date and e.date[:7] in counted),
                     key=lambda e: (e.date, order.get(e.account, len(order))))
    rows += [row([_day(e.date), e.account, f"{e.label}: {e.narration}", e.amount], _distinct(e.evidence), "excluded")
             for e in removed]
    accounts = _accounts(ctx)
    coverage = _line(ranges_label(months),
                     f"{_count(len(accounts), 'account')}: {', '.join(accounts)}" if accounts else "")
    statements = [e for a in ctx.facts.accounts if a.has_statement for e in a.evidence[:1]]
    return column(ctx, "bank", "Business credits in bank statements", sources=[BANK], value=value, unit="inr",
                  coverage=coverage, differs=differs, manual=manual, awaiting=awaiting, field_ids=field_ids,
                  evidence=_pages(evidence, rows) or statements, row_columns=BANK_ROWS, rows=rows)


def _accounts(ctx: Context) -> list[str]:
    """The accounts behind a bank figure: every account with a statement (a month counts only when
    all of them cover it), named as their credits are."""
    labels = [c.account for c in ctx.facts.credits]
    named = {label.rsplit("·", 1)[1] if "·" in label else None for label in labels}
    labels += [a.label for a in ctx.facts.accounts if a.has_statement and a.last4 not in named]
    return list(dict.fromkeys(labels))


def _line_column(ctx: Context, key: str, label: str, sources: list[str], line: str, year: str,
                 value: str | float | None, *, coverage: str, differs: bool = False, manual: bool = False,
                 awaiting: bool = False, field_ids: Iterable[str] = (),
                 evidence: Iterable[Evidence] = ()) -> SourceColumn:
    """A figure printed on one line of one document: the audited revenue, a profit, a balance."""
    evidence = list(evidence)
    return column(ctx, key, label, sources=sources, value=value, unit="inr", coverage=coverage, differs=differs,
                  manual=manual, awaiting=awaiting, field_ids=field_ids, evidence=evidence, row_columns=LINE_ROWS,
                  rows=[row([line, year, value], evidence)])


# --- TX-01, TX-02: the income tax return against the books ---


@builds("itr_years")
def _itr_years(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    if finding.outcome == "not_applicable":
        return
    years, returns = ctx.facts.financial_years, ctx.facts.tax_years
    books, filed = _side(finding, AUDITED), _side(finding, ITR)
    columns = []
    if years:
        columns.append(column(
            ctx, "audited", "Audited statements", sources=[AUDITED], value=", ".join(y.fy for y in years),
            coverage=f"{_count(len(years), 'year')} audited", differs=bool(books and books.differs),
            evidence=[e for y in years for e in _year_evidence(y)], row_columns=["Year", "Statements"],
            rows=[row([y.fy, "Audited"], _year_evidence(y)) for y in years]))
    if returns:
        columns.append(column(
            ctx, "itr", "Income tax returns", sources=[ITR],
            value=", ".join(f"AY {t.assessment_year}" for t in returns),
            coverage=f"{_count(len(returns), 'return')} on file", differs=bool(filed and filed.differs),
            evidence=[e for t in returns for e in t.evidence[:1]], row_columns=["Assessment year", "Financial year"],
            rows=[row([f"AY {t.assessment_year}", t.fy], t.evidence) for t in returns]))
    finding.columns = columns
    if finding.outcome == "fail":
        unfiled = [r.label for r in finding.detail.rows if r.flagged] if finding.detail else []
        finding.mismatch = f"No income tax return for {join(unfiled)}, though due." if unfiled else None
        finding.highlights = [highlight(finding, "Income tax returns", note=finding.mismatch)]
    elif finding.outcome == "pass":
        finding.highlights = [highlight(finding, "Income tax returns",
                                        note=f"{_count(len(returns), 'return')} on file, one for each year due")]


@builds("itr_profit")
def _itr_profit(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    if finding.outcome == "incomplete" and finding.missing:
        return  # nothing to show; the documents are asked for as every card asks for them
    year = next((y for y in ctx.facts.financial_years if y.fy == finding.scope), None)
    tax = {t.fy: t for t in ctx.facts.tax_years}.get(finding.scope or "")
    if finding.outcome == "not_applicable" or year is None or tax is None:
        return
    book, filed = year.current.get("profit_before_tax"), tax.lines.get("profit_before_tax")
    if not book or not filed:
        return
    ay = f"AY {tax.assessment_year}"
    finding.columns = [
        _line_column(ctx, "audited", "Audited financial statements", [AUDITED], "Profit before tax", year.fy,
                     book.value, coverage=f"Year ended {_day(year.fy_end)} · audited",
                     **_fact_flags(book, finding, 0)),
        _line_column(ctx, "itr", "Income tax return", [ITR], "Profit as per the computation", ay, filed.value,
                     coverage=f"{ay} · computation of income", **_fact_flags(filed, finding, 1)),
    ]
    if finding.outcome in ("pass", "fail"):
        leg = _leg(SHORT["financials"], float(book.value or 0), TAX_RETURN, float(filed.value or 0),
                   ctx.tol(rule.tolerance, 10), finding)
        _measured(ctx, rule, finding, [leg], leg.amount)
        finding.highlights = [_compared(finding, f"Profit: audited against tax return · {finding.scope}",
                                        [("financials", book.value), ("itr", filed.value)])]
    elif finding.outcome == "incomplete":
        finding.highlights = [highlight(finding, f"Profit: audited against tax return · {finding.scope}",
                                        note=wanted(finding))]


# --- FS-01, FS-02: the statements against each other and the bank ---


@builds("comparatives")
def _comparatives(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    if finding.outcome == "incomplete" and finding.missing:
        finding.request = f"{documents(finding.missing)} for two consecutive years"
        return
    years = ctx.facts.financial_years
    year = next((y for y in years if y.fy == finding.scope), None)
    prev = _previous_year(years, year) if year else None
    if finding.outcome == "not_applicable" or year is None or prev is None:
        return
    lines = [(label, year.previous[key], prev.current[key]) for key, label in LINE_LABELS.items()
             if year.previous.get(key) and prev.current.get(key)]
    if not lines:
        return
    # The headline is the line the rule's sides show: the first restated line, else the first compared.
    flagged = [r.label for r in finding.detail.rows if r.flagged] if finding.detail else []
    head = next((ln for ln in lines if ln[0] in flagged[:1]), lines[0])
    sides = finding.sides
    finding.columns = [
        _lines_column(ctx, "restated", f"{prev.fy} column of the {year.fy} statements", lines, head, 1,
                      sides[0] if sides else None),
        _lines_column(ctx, "audited", f"{prev.fy} audited statements", lines, head, 2,
                      sides[1] if len(sides) > 1 else None),
    ]
    if finding.outcome in ("pass", "fail"):
        tol = ctx.tol(rule.tolerance, 1)
        legs = []
        for label, shown, filed in lines:
            leg = pair_leg("as restated", float(shown.value or 0), "as audited", float(filed.value or 0),
                           tolerance_pct=tol, legs=label)
            leg.label = label
            legs.append(leg)
        breached = [leg.amount for leg in legs if leg.breached]
        amount = max(breached) if finding.outcome == "fail" and breached else max(leg.amount for leg in legs)
        _measured(ctx, rule, finding, legs, amount)


def _lines_column(ctx: Context, key: str, label: str, lines: list[tuple[str, FactValue, FactValue]],
                  head: tuple[str, FactValue, FactValue], index: int, side: FindingSide | None) -> SourceColumn:
    """One year's figures for the compared lines, as one statement prints them (index 1: the later
    statements' comparative column; 2: that year's own statements)."""
    values = [ln[index] for ln in lines]
    return column(ctx, key, label, sources=[AUDITED], value=head[index].value, unit="inr",
                  coverage=_line(head[0], f"{_count(len(lines), 'line')} compared"),
                  differs=bool(side and side.differs), manual=bool(side and side.relies_on_manual),
                  awaiting=bool(side and side.awaiting_review), field_ids=[i for v in values for i in v.field_ids],
                  evidence=_distinct(head[index].evidence[:1] + [e for v in values for e in v.evidence[:1]]),
                  row_columns=["Line", "Amount"],
                  rows=[row([ln[0], ln[index].value], _distinct(ln[index].evidence)) for ln in lines])


@builds("year_end_balance")
def _year_end_balance(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    if finding.outcome == "incomplete" and finding.missing:
        return  # nothing to show; the documents are asked for as every card asks for them
    years = ctx.facts.financial_years
    if finding.outcome == "not_applicable" or not years:
        return
    latest = years[0]
    balances = [b for b in ctx.facts.balances if b.date == latest.fy_end]
    audited = latest.current.get("cash_and_bank_balances")
    if not balances or audited is None:
        return
    end = _day(latest.fy_end)
    total = sum(b.balance for b in balances)
    side = finding.sides[0] if finding.sides else None
    finding.columns = [
        column(ctx, "bank", "Year-end bank balances", sources=[BANK], value=total, unit="inr",
               coverage=f"On {end} · {_count(len(balances), 'account')}", differs=bool(side and side.differs),
               evidence=[e for b in balances for e in b.evidence[:1]], row_columns=["Account", "Date", "Balance"],
               rows=[row([b.account, end, b.balance], b.evidence) for b in balances]),
        _line_column(ctx, "audited", "Audited cash and bank balance", [AUDITED], "Cash and bank balances", latest.fy,
                     audited.value, coverage=f"Balance sheet as at {end}", **_fact_flags(audited, finding, 1)),
    ]
    if finding.outcome in ("pass", "fail"):
        base = float(audited.value or 0)
        excess = total - base
        # How far the balances are above the audited figure (below it, on a pass that has room).
        leg = GapLeg(label=f"{'Above' if excess >= 0 else 'Below'} the audited cash and bank balance",
                     amount=abs(excess), pct=round(abs(excess) / abs(base) * 100, 1) if base else None,
                     base="audited", legs="bank balances against audited", breached=finding.outcome == "fail")
        _measured(ctx, rule, finding, [leg], excess if excess > 0 else None)


# --- Helpers ---


def _name(left: str, right: str) -> str:
    """A turnover check as the overview card names it: "GST against bank credits"."""
    first = NAMES[left]
    return f"{first[:1].upper()}{first[1:]} against {NAMES[right]}"


def _compared(finding: Finding, label: str, figures: list[tuple[str, str | float | None]]) -> XvHighlight:
    """The line of a comparison the rule made: the two figures as the card shows them, the smaller
    marked on a discrepancy (the one the gap is measured against), and how far apart they are, from
    the card's own leg, against the tolerance."""
    sizes = [abs(v) if isinstance(v, (int, float)) else 0.0 for _, v in figures]
    low = sizes.index(min(sizes))
    facts = [fact(FIGURES[source], value, "inr", differs=finding.outcome == "fail" and i == low)
             for i, (source, value) in enumerate(figures)]
    leg = finding.gaps[0] if finding.gaps else None
    note = None
    if leg is not None and leg.pct is not None:
        note = f"{leg.pct:.1f}% apart"
        if finding.gap_tolerance:
            note += f" · {'tolerance' if finding.outcome == 'fail' else 'within'} {finding.gap_tolerance}"
    return highlight(finding, label, facts, note)


def _measured(ctx: Context, rule: CrossCheckRule, finding: Finding, legs: list[GapLeg], amount: float | None) -> None:
    """The gaps of a comparison the rule made, with its tolerance as written and the amount it ranks by."""
    finding.gaps = legs
    finding.gap_tolerance = ctx.tol_text(rule.tolerance)
    finding.amount = amount


def _leg(left: str, a: float, right: str, b: float, tolerance: float, finding: Finding) -> GapLeg:
    """The one leg of a two-figure comparison, measured as the rule measures it. It is the whole
    comparison, so it is breached exactly when the rule failed."""
    leg = pair_leg(left, a, right, b, tolerance_pct=tolerance, legs=f"{left} against {right}")
    leg.breached = finding.outcome == "fail"
    return leg


def _side(finding: Finding, source: str) -> FindingSide | None:
    """The rule's side for a source document type."""
    return next((s for s in finding.sides if source in s.sources), None)


def _side_flags(side: FindingSide | None) -> dict:
    if side is None:
        return {}
    return dict(differs=side.differs, manual=side.relies_on_manual, awaiting=side.awaiting_review,
                field_ids=side.field_ids, evidence=side.evidence)


def _fact_flags(value: FactValue, finding: Finding, index: int) -> dict:
    """A column's flags for a fact: whether it differs from the rule's side at `index`, the rest from the fact."""
    side = finding.sides[index] if len(finding.sides) > index else None
    return dict(differs=bool(side and side.differs), manual=value.relies_on_manual, awaiting=value.awaiting_review,
                field_ids=value.field_ids, evidence=value.evidence)


def _year_evidence(year: FinancialYear) -> list[Evidence]:
    """A page of the year's audited statements: the first printed line's."""
    return next((v.evidence[:1] for v in year.current.values() if v.evidence), [])


def _year_months(ctx: Context, year: TurnoverYear) -> list[tuple[int, int]]:
    end = parse_date(year.fy_end)
    return fy_months(fy_of(end.year, end.month, ctx.fy_start), ctx.fy_start) if end else []


def _ym(month: str) -> tuple[int, int]:
    return int(month[:4]), int(month[5:7])


def _period(months: list[tuple[int, int]]) -> str:
    """The first month to the last: "Aug 2025 to Mar 2026"."""
    if not months:
        return ""
    return month_label(months[0]) if len(months) == 1 else f"{month_label(months[0])} to {month_label(months[-1])}"


def _line(*parts: str) -> str:
    return " · ".join(p for p in parts if p)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _day(value: str | None) -> str | None:
    """A date as the card writes it: 10 Jun 2025."""
    when = parse_date(value)
    return display_date(when) if when else value


def _pages(evidence: Iterable[Evidence], rows: list[EvidenceRow]) -> list[Evidence]:
    """Where a column's value can be traced: the figure's own pages (its first is the primary page),
    then the pages behind its rows, once each."""
    return _distinct([*evidence, *(e for r in rows for e in r.evidence[:1])])


def _distinct(evidence: Iterable[Evidence]) -> list[Evidence]:
    out, seen = [], set()
    for e in evidence:
        key = (e.document_id, e.page, e.bbox)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
