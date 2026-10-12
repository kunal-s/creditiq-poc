"""Cards for OB-01 to OB-03 (existing facilities and instalments).

Presentation only: built after the rule has decided its outcome (see engine/xv_cards/__init__.py).

OB-01's columns are the declaration of existing facilities (or the sourcing message), the sanction
letters and the commercial bureau report, with a row per facility each records. Its gap legs are
the lender problems the rule found, read from the finding's own line-by-line rows: a lender not
declared, a declared facility nothing else shows, and each pair of sources whose sanctioned
amounts differ. OB-02 and OB-03 hold the instalments inferred from the bank statements against the
declaration and against the books. A check short of documents asks for them in the words every
card uses (engine/xv_cards/__init__.py); OB-01 asks for any one of them.

The key figures: OB-01 a line per lender problem (the sanctioned amounts side by side and how far
apart; "not declared · INR 1.20 cr in the bureau report"; "declared, but no sanction letter or
bureau entry shows it"); OB-02 a line per lender paid by instalment and not declared; OB-03 the
difference in words; on a pass, what the rule confirmed.
"""

from __future__ import annotations

from datetime import date
from itertools import combinations
from typing import TYPE_CHECKING

from ..contracts import Finding, FindingDetailRow, FindingSide, GapLeg, SourceColumn, XvFact, XvHighlight
from ..crosschecks import BUREAU, CASE_RECORD, DECLARATION, NO, SANCTION, _variance
from ..util import display_date, parse_period, ranges_label
from . import (
    builds,
    column,
    column_from_side,
    document,
    documents,
    fact,
    highlight,
    inr,
    join,
    pair_leg,
    plural,
    row,
    sentence,
    wanted,
)
from .accounts import traced, waits_for_review

if TYPE_CHECKING:
    from ..configstore.schema import CrossCheckRule
    from ..crosschecks import Context

INSTALMENTS = "Instalments in bank statements"
"""The rules' side for the inferred obligations (engine/crosschecks.py _emis_declared, _borrowings_serviced)."""
AMOUNT_SOURCES = ("declared", "sanction letter", "bureau")
"""The sanctioned amounts in OB-01's rows, as the rule names them (engine/crosschecks.py _facilities_reconcile)."""
KEYS = {DECLARATION: "declaration", SANCTION: "sanction_letters", BUREAU: "bureau", CASE_RECORD: "sourcing_message"}
FACT_LABELS = {"declared": "declared", "sanction letter": "sanction letter", "bureau": "bureau report"}
"""OB-01's sanctioned amounts on the overview card, by source ("Sanction letter and bureau report")."""
SHOWN_IN = {"sanction letter": "the sanction letter", "bureau": "the bureau report"}


def _amount(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _source(side: FindingSide) -> str | None:
    return side.sources[0] if len(side.sources) == 1 else None


def _note_column(ctx: Context, side: FindingSide) -> SourceColumn:
    """The existing banking the RM declared in the sourcing message, as written. A note a person
    entered on the case has no place in the message, and says so."""
    return column(ctx, KEYS[CASE_RECORD], side.label, sources=side.sources, value=side.value,
                  coverage="In the sourcing message" if side.evidence else "Entered on the case", differs=side.differs,
                  manual=side.relies_on_manual, awaiting=side.awaiting_review, field_ids=side.field_ids,
                  evidence=side.evidence, row_columns=["Declared"], rows=[row([side.value], side.evidence)])


def _facilities_column(ctx: Context, side: FindingSide, layout: str) -> SourceColumn:
    """One source's facilities, a row each. `layout`: "sanction" (lender, facility, sanctioned, EMI),
    "emi" (lender, facility, EMI) or "bureau" (lender, facility, sanctioned, outstanding, overdue)."""
    source = _source(side)
    facilities = [f for f in ctx.facts.facilities if f.source == source]
    if layout == "bureau":
        heads = ["Lender", "Facility", "Sanctioned", "Outstanding", "Overdue"]
        rows = [row([f.lender, f.facility, f.amount, f.outstanding, f.overdue], f.evidence) for f in facilities]
    elif layout == "emi":
        heads = ["Lender", "Facility", "EMI"]
        rows = [row([f.lender, f.facility, f.emi], f.evidence) for f in facilities]
    else:
        heads = ["Lender", "Facility", "Sanctioned", "EMI"]
        rows = [row([f.lender, f.facility, f.amount, f.emi], f.evidence) for f in facilities]
    n = len(facilities)
    if source == DECLARATION:
        coverage = f"{plural(n, 'facility', 'facilities')} declared" if n else "Declares no existing facilities"
        if not rows:
            # A nil declaration is a statement too: its page is the evidence.
            rows = [row(["None declared"] + [None] * (len(heads) - 1), side.evidence)]
    elif source == SANCTION:
        letters = len({f.evidence[0].document_id for f in facilities if f.evidence})
        coverage = (f"{plural(n, 'facility', 'facilities')} in {plural(letters, 'letter')}" if n
                    else "No facility read from the sanction letters")
    else:
        owed = [f.outstanding for f in facilities if f.outstanding is not None]
        coverage = (f"{plural(n, 'facility', 'facilities')} reported" + (f" · {inr(sum(owed))} outstanding" if owed else "")
                    if n else "No facility reported")
    return column(ctx, KEYS[source], side.label, sources=side.sources, value=side.value, coverage=coverage,
                  differs=side.differs, manual=side.relies_on_manual, awaiting=side.awaiting_review,
                  field_ids=side.field_ids, evidence=traced(rows, side.evidence), row_columns=heads, rows=rows)


def _months(labels: list[str]) -> str:
    periods = [p for p in (parse_period(m) for m in labels) if p]
    return ranges_label(periods) if len(periods) == len(labels) else ", ".join(labels)


def _instalments_column(ctx: Context, side: FindingSide) -> SourceColumn:
    """The regular debits to lenders the bank statements show (F-18.4), a row each. With none, the
    statements searched are the evidence (an account with a statement starts with its page)."""
    obligations = ctx.facts.obligations
    rows = [row([o.lender, o.account, o.typical_amount, _months(o.months)], o.evidence) for o in obligations]
    lenders = len({o.lender for o in obligations})
    coverage = (f"{plural(lenders, 'lender')} · {inr(sum(o.typical_amount for o in obligations))} a month"
                if obligations else "No regular instalments found")
    searched = [a.evidence[0] for a in ctx.facts.accounts if a.has_statement and a.evidence]
    return column(ctx, "instalments", side.label, sources=side.sources, value=side.value, coverage=coverage,
                  differs=side.differs, manual=side.relies_on_manual, awaiting=side.awaiting_review,
                  field_ids=side.field_ids, evidence=traced(rows, side.evidence or searched),
                  row_columns=["Lender", "Account", "Monthly instalment", "Months"], rows=rows)


# --- OB-01 ---


def _lender_row(r: FindingDetailRow) -> tuple[object, object, object, dict[str, float]]:
    """One lender's row of the rule's own table: the lender, then the declared, sanction-letter and
    bureau cells (an amount, ✓ or — when the source does not show it) and the outstanding. Returns
    the three cells and the amounts among them, by source."""
    declared, letter, bureau = (list(r.cells) + [None, None, None])[:3]
    amounts = {k: a for k, a in zip(AMOUNT_SOURCES, map(_amount, (declared, letter, bureau))) if a is not None}
    return declared, letter, bureau, amounts


def _unsupported(ctx: Context) -> str:
    """A declared facility nothing else shows, in words."""
    return ("declared, but no sanction letter or bureau entry shows it" if BUREAU in ctx.on_file
            else "declared, but no sanction letter shows it")


def _lender_legs(ctx: Context, rule: CrossCheckRule, r: FindingDetailRow) -> list[GapLeg]:
    """The legs of one flagged lender, from the rule's own row. The pairs are compared exactly as the
    rule compares them."""
    lender = r.label
    declared, letter, bureau, amounts = _lender_row(r)
    legs = []
    if declared == NO:
        elsewhere = [amounts[k] for k in ("sanction letter", "bureau") if k in amounts]
        legs.append(GapLeg(label=f"{lender}: not declared", amount=max(elsewhere) if elsewhere else None,
                           legs=lender, breached=True))
    if letter == NO and bureau == NO:
        legs.append(GapLeg(label=f"{lender}: {_unsupported(ctx)}", amount=amounts.get("declared"), legs=lender,
                           breached=True))
    tol = ctx.tol(rule.tolerance, 5)
    if len(amounts) >= 2 and max(_variance(x, y) for x in amounts.values() for y in amounts.values()) > tol:
        for (ka, a), (kb, b) in combinations(amounts.items(), 2):
            if a != b:
                leg = pair_leg(ka, a, kb, b, tolerance_pct=tol, legs=f"{lender} {ka} against {kb}")
                leg.label = f"{lender}: {ka} against {kb}"
                legs.append(leg)
    return legs


def _lender_lines(ctx: Context, rule: CrossCheckRule, finding: Finding, r: FindingDetailRow) -> list[XvHighlight]:
    """The key-figure lines of one flagged lender, one per problem, as its legs show them (from the
    rule's own row, in the same order): not declared, with the largest amount shown elsewhere and
    where; declared, but shown nowhere else; the sanctioned amounts side by side when they differ."""
    lender = r.label
    declared, letter, bureau, amounts = _lender_row(r)
    lines = []
    if declared == NO:
        elsewhere = {k: amounts[k] for k in ("sanction letter", "bureau") if k in amounts}
        if elsewhere:
            top = max(elsewhere.values())
            note = f"not declared · {inr(top)} in {join(SHOWN_IN[k] for k, a in elsewhere.items() if a == top)}"
        else:
            # Shown without an amount that could be read.
            shown = join(SHOWN_IN[k] for k, cell in (("sanction letter", letter), ("bureau", bureau)) if cell != NO)
            note = f"not declared · in {shown}" if shown else "not declared"
        lines.append(highlight(finding, lender, note=note))
    if letter == NO and bureau == NO:
        lines.append(highlight(finding, lender, note=_unsupported(ctx)))
    tol = ctx.tol(rule.tolerance, 5)
    spread = max((_variance(x, y) for x in amounts.values() for y in amounts.values()), default=0.0)
    if len(amounts) >= 2 and spread > tol:
        tolerance = ctx.tol_text(rule.tolerance)
        note = f"{spread:.1f}% apart" + (f" · tolerance {tolerance}" if tolerance else "")
        lines.append(highlight(finding, lender, _amount_facts(amounts, tol), note))
    return lines


def _amount_facts(amounts: dict[str, float], tol: float) -> list[XvFact]:
    """One lender's sanctioned amounts side by side, each amount once (sources that agree to the
    rupee share it: "Sanction letter and bureau report"). Marked: the amounts outside the largest
    set of sources that agree within the tolerance; with no such set, the smallest, the amount the
    card's legs are measured against."""
    shared: dict[float, list[str]] = {}
    for source, a in amounts.items():
        shared.setdefault(a, []).append(source)
    groups: list[list[float]] = []
    for a in shared:
        found = next((g for g in groups if _variance(a, g[0]) <= tol), None)
        if found is not None:
            found.append(a)
        else:
            groups.append([a])

    def size(g: list[float]) -> int:
        return sum(len(shared[a]) for a in g)

    top = [g for g in groups if size(g) == max(map(size, groups))]
    if len(top) == 1 and len(groups) > 1:
        odd = {a for g in groups if g is not top[0] for a in g}
    else:
        odd = {min(shared)}
    return [fact(_capital(join(FACT_LABELS[s] for s in sources)), a, "inr", a in odd) for a, sources in shared.items()]


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _facility_lines(ctx: Context, rule: CrossCheckRule, finding: Finding) -> list[XvHighlight]:
    """OB-01's lines: one per lender problem the rule found; on a pass, how many facilities reconcile;
    for a check that could not run, what would complete it."""
    if finding.outcome == "fail" and finding.detail is not None:
        return [line for r in finding.detail.rows if r.flagged for line in _lender_lines(ctx, rule, finding, r)]
    if finding.outcome == "incomplete":
        return [highlight(finding, "Existing facilities", note=wanted(finding))]
    if finding.outcome != "pass":
        return []
    # A row per lender, each agreeing across the declaration, the sanction letters and the bureau.
    n = len(finding.detail.rows) if finding.detail else 0
    note = (f"{plural(n, 'facility', 'facilities')} {'reconciles' if n == 1 else 'reconcile'}" if n
            else "none declared, none reported")
    return [highlight(finding, "Existing facilities", note=note)]


@builds("facilities_reconcile")
def facilities_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    _facilities_card(ctx, rule, finding)
    finding.highlights = _facility_lines(ctx, rule, finding)


def _facilities_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    columns = []
    for i, side in enumerate(finding.sides):
        source = _source(side)
        if source == CASE_RECORD:
            columns.append(_note_column(ctx, side))
        elif source in (DECLARATION, SANCTION, BUREAU):
            columns.append(_facilities_column(ctx, side, "bureau" if source == BUREAU else "sanction"))
        else:
            columns.append(column_from_side(ctx, side, f"side-{i}"))
    finding.columns = columns
    if finding.outcome == "incomplete" and finding.missing:
        # Short of the declaration, or of anything to reconcile it with: any one of them completes it.
        finding.request = documents(finding.missing, "or")
    if finding.outcome not in ("pass", "fail") or finding.detail is None:
        return
    finding.gaps = [g for r in finding.detail.rows if r.flagged for g in _lender_legs(ctx, rule, r)]
    finding.gap_tolerance = ctx.tol_text(rule.tolerance)
    amounts = [g.amount for g in finding.gaps if g.amount is not None]
    finding.amount = max(amounts) if amounts else None


# --- OB-02 ---


@builds("emis_to_declared_lenders")
def instalments_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    _instalments_card(ctx, rule, finding)
    finding.highlights = _instalment_lines(ctx, finding)


def _instalment_lines(ctx: Context, finding: Finding) -> list[XvHighlight]:
    """A line per lender paid by instalment and not declared, as the rule's rows give it (the
    lender, then account, monthly instalment, months, declared); on a pass, what the rule confirmed."""
    if finding.outcome == "fail" and finding.detail is not None:
        lines = []
        for r in finding.detail.rows:
            if r.flagged:
                monthly = _amount(r.cells[1]) if len(r.cells) > 1 else None
                paid = f"{inr(monthly)} a month " if monthly is not None else ""
                lines.append(highlight(finding, r.label, note=f"{paid}in the bank statements, not declared"))
        return lines
    if finding.outcome == "incomplete":
        return [highlight(finding, "Instalments", note=wanted(finding))]
    if finding.outcome != "pass":
        return []
    found = ctx.facts.obligations
    return [highlight(finding, "Instalments", note="every lender paid by instalment is declared" if found
                      else "no regular instalments in the bank statements")]


def _instalments_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    columns = []
    for i, side in enumerate(finding.sides):
        source = _source(side)
        if side.label == INSTALMENTS:
            columns.append(_instalments_column(ctx, side))
        elif source == DECLARATION:
            columns.append(_facilities_column(ctx, side, "emi"))
        elif source == CASE_RECORD:
            columns.append(_note_column(ctx, side))
        else:
            columns.append(column_from_side(ctx, side, f"side-{i}"))
    finding.columns = columns
    if finding.outcome == "incomplete":
        lenders = [o.lender for o in ctx.facts.obligations]
        if not finding.missing and not waits_for_review(finding):
            # Nothing declares the existing facilities: the declaration, or a word on each lender, completes it.
            finding.request = (document(ctx.type_names[DECLARATION])
                               + (f" (or a written confirmation of the facility behind {join(lenders)})" if lenders else ""))
        return
    if finding.outcome != "fail" or finding.detail is None:
        return
    # The rule's rows: the lender, then account, monthly instalment, months, declared.
    flagged = [r for r in finding.detail.rows if r.flagged]
    legs = []
    for r in flagged:
        monthly = _amount(r.cells[1]) if len(r.cells) > 1 else None
        legs.append(GapLeg(label=f"Annual outflow to {r.label} ({inr(monthly)} a month), not declared",
                           amount=monthly * 12 if monthly is not None else None, legs=r.label, breached=True))
    finding.gaps = legs
    amounts = [g.amount for g in legs if g.amount is not None]
    finding.amount = sum(amounts) if amounts else None
    if flagged:
        finding.mismatch = sentence(f"Instalments to {join([r.label for r in flagged])} appear in the bank statements "
                                    "but no declaration names them")


# --- OB-03 ---


BORROWINGS = "Borrowings and instalments"
"""OB-03's line on the overview card."""


@builds("borrowings_serviced")
def borrowings_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    difference = _borrowings_card(ctx, rule, finding)
    finding.mismatch = sentence(difference) if difference else None
    finding.highlights = _borrowing_lines(ctx, finding, difference)


def _borrowing_lines(ctx: Context, finding: Finding, difference: str | None) -> list[XvHighlight]:
    """OB-03's line: the difference in the mismatch's words; on a pass, what the rule confirmed; for a
    check that could not run, what would complete it."""
    if finding.outcome == "fail":
        return [highlight(finding, BORROWINGS, note=difference)]
    if finding.outcome == "incomplete":
        return [highlight(finding, BORROWINGS, note=wanted(finding))]
    if finding.outcome != "pass":
        return []
    return [highlight(finding, BORROWINGS, note="serviced in the bank statements" if ctx.facts.obligations
                      else "no long-term borrowings and no instalments")]


def _borrowings_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> str | None:
    """The columns and the amount; returns the difference in words, for a discrepancy."""
    if len(finding.sides) < 2:
        return None
    books, emis = finding.sides[0], finding.sides[1]
    year = next((y for y in ctx.facts.financial_years if y.fy == finding.scope), None)
    line = year.current.get("long_term_borrowings") if year else None
    evidence = list(line.evidence) if line and line.evidence else list(books.evidence)
    finding.columns = [
        column(ctx, "borrowings", books.label, sources=books.sources, value=books.value, unit="inr",
               coverage=f"As at {display_date(date.fromisoformat(year.fy_end))} · audited" if year else None,
               differs=books.differs, manual=books.relies_on_manual, awaiting=books.awaiting_review,
               field_ids=books.field_ids, evidence=evidence, row_columns=["Line", "Year", "Amount"],
               rows=[row(["Long-term borrowings", finding.scope, books.value], evidence)]),
        _instalments_column(ctx, emis),
    ]
    if finding.outcome != "fail":
        return None
    if emis.differs:
        # Borrowings in the books, and no instalments in the bank.
        borrowings = _amount(books.value)
        finding.amount = borrowings
        return (f"Long-term borrowings of {inr(borrowings)} in the {finding.scope} balance sheet; "
                "no instalments in the bank statements")
    if books.differs:
        # Instalments in the bank, and no borrowings in the books: a year of them.
        monthly = sum(o.typical_amount for o in ctx.facts.obligations)
        finding.amount = monthly * 12
        return (f"Instalments of {inr(monthly)} a month in the bank statements; "
                f"no long-term borrowings in the {finding.scope} balance sheet")
    return None
