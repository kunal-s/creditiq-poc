"""Cards for BR-01 to BR-04 (the board resolution).

Presentation only: built after the rule has decided its outcome (see engine/xv_cards/__init__.py).

The columns are the rule's sides: the resolution's borrowing limit against the amount requested
(BR-01, with the shortfall as its gap leg), its signatories against the directors on file (BR-02),
the lender it names against this bank (BR-03), and its date against the incorporation and the
appraisal date (BR-04). The checks without an amount state the difference in words. A check short
of documents asks for them in the words every card uses (engine/xv_cards/__init__.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts import AuthorityFact, Evidence, Finding, FindingSide, GapLeg, SourceColumn
from ..crosschecks import CASE_RECORD, _resolution
from ..names import normalise_name
from ..util import display_date, parse_date
from . import builds, column, column_from_side, document, join, plural, row, sentence
from .accounts import page_line, traced, waits_for_review

if TYPE_CHECKING:
    from ..configstore.schema import CrossCheckRule
    from ..crosschecks import Context

RESOLUTION = "board_resolution_borrowing"
DIRECTOR_SOURCES = ("director_kyc", "memorandum_articles_of_association", CASE_RECORD)
"""Where BR-02 finds the directors on file (engine/crosschecks.py _signatories)."""
NAME_COLUMNS = ["Name", "Source document"]


def _dated(a: AuthorityFact | None) -> str | None:
    when = parse_date(a.resolution_date.value) if a and a.resolution_date else None
    return f"Resolution dated {display_date(when)}" if when else None


def _resolution_pages(a: AuthorityFact) -> list[Evidence]:
    """The pages a board resolution's terms were read from."""
    return ([e for v in (a.borrowing_limit, a.lender, a.resolution_date) if v for e in v.evidence[:1]]
            + [e for s in a.signatories for e in s.evidence[:1]])


def _value_column(ctx: Context, key: str, side: FindingSide, line: str, *, unit: str = "text",
                  coverage: str | None = None, value: str | float | None = None,
                  shown: str | float | None = None) -> SourceColumn:
    """A side with one value: the value, and one row naming it, linked to its page."""
    return column(ctx, key, side.label, sources=side.sources, value=side.value if value is None else value,
                  unit=unit, coverage=coverage, differs=side.differs, manual=side.relies_on_manual,
                  awaiting=side.awaiting_review, field_ids=side.field_ids, evidence=side.evidence,
                  row_columns=["Particular", "Value"],
                  rows=[row([line, side.value if shown is None else shown], side.evidence)])


# --- BR-01 ---


@builds("borrowing_limit")
def limit_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    sides = {s.label: s for s in finding.sides}
    limit, requested = sides.get("Board resolution limit"), sides.get("Amount requested")
    columns = []
    if limit is not None:
        resolution = _resolution(ctx, rule, "borrowing_limit")
        stating = [a for a in ctx.facts.authority if a.borrowing_limit]
        coverage = _dated(resolution) or page_line(limit.evidence)
        if len(stating) > 1:
            coverage = " · ".join(filter(None, [coverage, f"the highest of {len(stating)} resolutions"]))
        columns.append(_value_column(ctx, "limit", limit, "Borrowing limit", unit="inr", coverage=coverage))
    elif requested is not None and ctx.facts.authority:
        # The resolution's limit could not be read: the resolution, without a value.
        pages = [e for a in ctx.facts.authority for e in _resolution_pages(a)][:1]
        columns.append(column(ctx, "limit", "Board resolution limit", sources=[RESOLUTION], unit="inr",
                              coverage="Not read from the resolution", evidence=pages,
                              row_columns=["Particular", "Value"], rows=[row(["Borrowing limit", None], pages)]))
    if requested is not None:
        columns.append(_value_column(ctx, "requested", requested, "Amount requested", unit="inr",
                                     coverage="On the case record"))
    finding.columns = columns
    if finding.outcome == "incomplete":
        if not finding.missing and limit is None and requested is not None and not waits_for_review(finding):
            # The resolution is on file, but no borrowing limit could be read from it.
            finding.request = f"{document(ctx.type_names[RESOLUTION])} that states the borrowing limit"
        return
    if finding.outcome not in ("pass", "fail") or limit is None or requested is None:
        return
    authorised, asked = float(limit.value or 0), float(requested.value or 0)
    shortfall = asked - authorised
    pct = round(abs(shortfall) / asked * 100, 1) if asked else None
    if finding.outcome == "fail":
        finding.gaps = [GapLeg(label="Shortfall against the amount requested", amount=shortfall, pct=pct,
                               base="requested", legs="limit against amount requested", breached=True)]
        finding.amount = shortfall if shortfall > 0 else None
    else:
        finding.gaps = [GapLeg(label="Headroom over the amount requested", amount=-shortfall, pct=pct,
                               base="requested", legs="limit against amount requested", breached=False)]


# --- BR-02 ---


def _signatories_column(ctx: Context, side: FindingSide) -> SourceColumn:
    rows = [row([s.name, a.label], s.evidence) for a in ctx.facts.authority for s in a.signatories]
    return column(ctx, "signatories", side.label, sources=side.sources, value=side.value,
                  coverage=f"{plural(len(rows), 'signatory', 'signatories')} authorised", differs=side.differs,
                  manual=side.relies_on_manual, awaiting=side.awaiting_review, field_ids=side.field_ids,
                  evidence=traced(rows, side.evidence), row_columns=NAME_COLUMNS, rows=rows)


def _directors_column(ctx: Context, side: FindingSide) -> SourceColumn:
    """The directors the rule holds the signatories against, once each as the rule lists them,
    with every document that names them."""
    sets = [p for p in ctx.facts.persons if p.source in DIRECTOR_SOURCES]
    unique = {normalise_name(d.name): d for d in ctx.persons(*DIRECTOR_SOURCES)}
    rows = []
    for key, director in unique.items():
        named = [(p, e) for p in sets for e in p.entries if normalise_name(e.name) == key]
        where = "; ".join(dict.fromkeys(ctx.type_names.get(p.source, p.label) for p, _ in named))
        rows.append(row([director.name, where], [ev for _, e in named for ev in e.evidence[:1]]))
    return column(ctx, "directors", side.label, sources=side.sources, value=side.value,
                  coverage=f"{plural(len(rows), 'director')} on file", differs=side.differs,
                  manual=side.relies_on_manual, awaiting=side.awaiting_review, field_ids=side.field_ids,
                  evidence=traced(rows, side.evidence), row_columns=NAME_COLUMNS, rows=rows)


@builds("signatories_are_directors")
def signatories_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    finding.columns = [
        _signatories_column(ctx, side) if side.label == "Authorised in the board resolution"
        else _directors_column(ctx, side) if side.label == "Directors on file"
        else column_from_side(ctx, side, f"side-{i}")
        for i, side in enumerate(finding.sides)
    ]
    names = list(dict.fromkeys(r.label for r in finding.detail.rows if r.flagged)) if finding.detail else []
    if finding.outcome == "fail" and names:
        verb = "is" if len(names) == 1 else "are"
        finding.mismatch = sentence(f"{join(names)} {verb} not among the directors on file")


# --- BR-03 ---


@builds("resolution_lender")
def lender_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    columns = []
    for i, side in enumerate(finding.sides):
        if side.label == "Lender named in the board resolution":
            coverage = _dated(_resolution(ctx, rule, "lender")) or page_line(side.evidence)
            columns.append(_value_column(ctx, "lender", side, "Lender", coverage=coverage))
        elif side.label == "This bank":
            # The names this bank goes by (config: alignment.own_bank_names); no document states them.
            columns.append(column(ctx, "this_bank", side.label, sources=side.sources, value=side.value,
                                  coverage=f"{plural(len(ctx.own_banks), 'name')} accepted", differs=side.differs,
                                  row_columns=["Name accepted"], rows=[row([n]) for n in ctx.own_banks]))
        else:
            columns.append(column_from_side(ctx, side, f"side-{i}"))
    finding.columns = columns
    if finding.outcome == "fail" and len(finding.sides) >= 2:
        finding.mismatch = sentence(f"The resolution names {finding.sides[0].value}, not {finding.sides[1].value}")


# --- BR-04 ---


def _date_column(ctx: Context, key: str, side: FindingSide, line: str) -> SourceColumn:
    when = parse_date(side.value)
    return _value_column(ctx, key, side, line, unit="date" if when else "text", coverage=page_line(side.evidence),
                         value=when.isoformat() if when else None, shown=display_date(when) if when else None)


def _date_mismatch(ctx: Context, finding: Finding) -> str | None:
    """The problems the rule found, from its own sides: dated before the incorporation on file, or
    after the appraisal date."""
    sides = {s.label: s for s in finding.sides}
    when = parse_date(sides["Board resolution dated"].value) if "Board resolution dated" in sides else None
    inc = sides.get("Date of incorporation")
    incorporated = parse_date(inc.value) if inc else None
    if when is None:
        return None
    problems = []
    if incorporated and when < incorporated:
        problems.append(f"before the company was incorporated on {display_date(incorporated)}")
    if when > ctx.as_of:
        problems.append(f"after the appraisal date of {display_date(ctx.as_of)}")
    return sentence(f"The resolution is dated {display_date(when)}, {' and '.join(problems)}") if problems else None


@builds("resolution_date")
def date_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    columns = []
    for i, side in enumerate(finding.sides):
        if side.label == "Board resolution dated":
            columns.append(_date_column(ctx, "resolution_date", side, "Resolution date"))
        elif side.label == "Date of incorporation":
            columns.append(_date_column(ctx, "incorporation", side, "Date of incorporation"))
        elif side.label == "Appraisal date":
            # The case's own date, fixed when it was created; no document states it.
            columns.append(column(ctx, "appraisal_date", side.label, sources=side.sources, value=ctx.as_of.isoformat(),
                                  unit="date", coverage="Fixed when the case was created", differs=side.differs,
                                  row_columns=["Particular", "Value"],
                                  rows=[row(["Appraisal date", display_date(ctx.as_of)])]))
        else:
            columns.append(column_from_side(ctx, side, f"side-{i}"))
    finding.columns = columns
    if finding.outcome == "fail":
        finding.mismatch = _date_mismatch(ctx, finding)
