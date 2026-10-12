"""The cards of the cross-verification board (F-19.3; docs/cross-verification-logic.md).

A finding's card shows each source the rule compared as a column (2 to 4): its provenance,
headline value, what it covers, the rows extracted behind it and the page each came from. It
also shows the gap on each leg of the comparison, for a check without an amount the difference
in words, and for an incomplete check what would complete it.

A card is built after the rule has decided its outcome, from the finding and the facts the rule
compared, and never changes the outcome. Each rule family has a builder in this package
(identity, numbers, accounts, obligations, authority); a rule without one gets its columns from
the finding's sides.

A check short of documents asks for them here, in one wording for every rule (`documents`):
"the director KYC and the memorandum and articles of association". A builder words only what
else would complete its check, naming any document the same way (`document`): months of
returns, a resolution that states its limit, any one of several documents.

Each builder also gives the finding its key-figure lines for the area's overview card
(`highlight`): what it compares, the figures side by side as the card shows them (`fact`), and a
short note ("25.0% apart · tolerance 10%", "declared, no statement"). A check that could not run
says there what would complete it (`wanted`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from ..contracts import Evidence, EvidenceRow, Finding, FindingSide, GapLeg, SourceColumn, XvFact, XvHighlight
from ..facts import inr

if TYPE_CHECKING:
    from ..configstore.schema import CrossCheckRule
    from ..crosschecks import Context

Builder = Callable[["Context", "CrossCheckRule", Finding], None]
BUILDERS: dict[str, Builder] = {}
MAX_COLUMNS = 4
STRICT = False
"""Raise a builder's error instead of falling back to the sides (the tests set it)."""
CARD_DEFAULTS = {"columns": [], "gaps": [], "gap_tolerance": None, "mismatch": None, "reference": None,
                 "amount": None, "request": None, "highlights": []}

log = logging.getLogger("creditiq.xv_cards")

__all__ = ["BUILDERS", "MAX_COLUMNS", "STRICT", "builds", "column", "column_from_side", "columns_from_sides",
           "document", "documents", "enrich", "fact", "highlight", "inr", "join", "pair_leg", "plural", "provenance",
           "requested", "row", "sentence", "wanted"]


def builds(*variables: str) -> Callable[[Builder], Builder]:
    """Register a card builder for the rules with these variables (config/crosschecks.yaml)."""
    def register(fn: Builder) -> Builder:
        for v in variables:
            BUILDERS[v] = fn
        return fn
    return register


def enrich(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    """Build the finding's card. Never touches the outcome, the explanation or the sides.

    A card is presentation, so a builder that fails does not stop the checks: the card falls back
    to the finding's sides, and the failure is logged."""
    builder = BUILDERS.get(rule.variable)
    if builder is not None:
        try:
            builder(ctx, rule, finding)
        except Exception:
            if STRICT:
                raise
            log.exception("the card for %s %s could not be built", rule.id, finding.scope or "")
            for name, default in CARD_DEFAULTS.items():
                setattr(finding, name, list(default) if isinstance(default, list) else default)
    if not finding.columns:
        finding.columns = columns_from_sides(ctx, finding.sides)
    finding.columns = finding.columns[:MAX_COLUMNS]
    if finding.outcome == "incomplete" and finding.request is None:
        finding.request = requested(finding)


def requested(finding: Finding) -> str | None:
    """What would complete a check that could not run: what its builder asks for, else the
    documents it is missing, in the words every card uses. None for any other outcome. A builder
    reads it before `enrich` settles the request, for its key-figure lines (`wanted`)."""
    if finding.outcome != "incomplete":
        return None
    if finding.request is not None:
        return finding.request
    return documents(finding.missing) if finding.missing else None


def provenance(ctx: Context, sources: Iterable[str]) -> list[str]:
    """The provenance of each source document type, in order, once each."""
    return list(dict.fromkeys(ctx.provenance[s] for s in sources if s in ctx.provenance))


def row(cells: list, evidence: Iterable[Evidence] = (), kind: str = "row") -> EvidenceRow:
    return EvidenceRow(cells=list(cells), evidence=list(evidence), kind=kind)  # type: ignore[arg-type]


def column(ctx: Context, key: str, label: str, *, sources: Iterable[str], value: str | float | None = None,
           unit: str = "text", coverage: str | None = None, differs: bool = False, manual: bool = False,
           awaiting: bool = False, field_ids: Iterable[str] = (), evidence: Iterable[Evidence] = (),
           row_columns: Iterable[str] = (), rows: Iterable[EvidenceRow] = ()) -> SourceColumn:
    sources = list(dict.fromkeys(sources))
    return SourceColumn(key=key, label=label, sources=sources, provenance=provenance(ctx, sources),  # type: ignore[arg-type]
                        value=value, unit=unit, coverage=coverage, differs=differs,  # type: ignore[arg-type]
                        relies_on_manual=manual, awaiting_review=awaiting, field_ids=list(field_ids),
                        evidence=list(evidence), row_columns=list(row_columns), rows=list(rows))


def column_from_side(ctx: Context, side: FindingSide, key: str) -> SourceColumn:
    unit = "inr" if isinstance(side.value, (int, float)) and not isinstance(side.value, bool) else "text"
    return column(ctx, key, side.label, sources=side.sources, value=side.value, unit=unit, differs=side.differs,
                  manual=side.relies_on_manual, awaiting=side.awaiting_review, field_ids=side.field_ids,
                  evidence=side.evidence,
                  rows=[row([side.label], [e]) for e in side.evidence])


def columns_from_sides(ctx: Context, sides: list[FindingSide]) -> list[SourceColumn]:
    return [column_from_side(ctx, s, f"side-{i}") for i, s in enumerate(sides)]


def pair_leg(left_label: str, a: float, right_label: str, b: float, *, tolerance_pct: float | None = None,
             legs: str | None = None) -> GapLeg:
    """The gap between two amounts as a percentage of the larger, as the rules measure variance
    (engine/crosschecks.py _variance), so the leg agrees with the outcome."""
    top = max(abs(a), abs(b))
    base, against = (left_label, right_label) if abs(a) >= abs(b) else (right_label, left_label)
    pct = abs(a - b) / top * 100 if top else 0.0
    return GapLeg(label=f"Gap against {against}", amount=abs(a - b), pct=round(pct, 1), base=base,
                  legs=legs or f"{left_label} against {right_label}",
                  breached=tolerance_pct is not None and pct > tolerance_pct)


def join(items: Iterable[str], word: str = "and") -> str:
    """"a", "a and b", "a, b and c"; with `word` "or": "a, b or c". Each item once."""
    items = list(dict.fromkeys(items))
    if not items:
        return ""
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} {word} {items[-1]}"


def plural(n: int, noun: str, many: str | None = None) -> str:
    """"1 account", "2 accounts", "2 facilities"."""
    return f"{n} {noun if n == 1 else many or noun + 's'}"


def sentence(text: str | None) -> str | None:
    """A clause as a sentence: a capital first letter and one full stop. A clause that already ends
    with one takes no second, as when it ends with a value such as "Kestrel Tools Pvt. Ltd."."""
    text = (text or "").strip()
    if not text:
        return None
    return text[:1].upper() + text[1:] + ("" if text.endswith(".") else ".")


# --- Key figures for the area's overview card ---


def fact(label: str, value: str | float | None, unit: str = "text", differs: bool = False) -> XvFact:
    """One figure of a key-figure line: a short source label and the value as the card shows it."""
    return XvFact(label=label, value=value, unit=unit, differs=differs)  # type: ignore[arg-type]


def highlight(finding: Finding, label: str, facts: Iterable[XvFact] = (), note: str | None = None) -> XvHighlight:
    """A key-figure line of the area's overview card, from this finding."""
    return XvHighlight(finding_id=finding.id, rule_id=finding.rule_id, outcome=finding.outcome, label=label,
                       facts=list(facts), note=note)


def wanted(finding: Finding) -> str | None:
    """The note of a check that could not run: what would complete it ("the director KYC needed"),
    or, when a value waits for a person's review and nothing is asked of the customer, that."""
    request = requested(finding)
    if request:
        return f"{request} needed"
    if any(s.awaiting_review for s in finding.sides) or any(c.awaiting_review for c in finding.columns):
        return "waiting for review"
    return None


def document(name: str) -> str:
    """A document type, by its name, as a request names it: "Income tax return" -> "the income tax
    return", "Director KYC" -> "the director KYC". A first word that is an acronym or a code keeps
    its capitals: "GSTR-3B" -> "the GSTR-3B" (likewise KYC, PAN, ITR, CIN, GSTIN)."""
    first, space, rest = name.partition(" ")
    if first[1:].islower():  # an ordinary word: "Director", not "GSTR-3B" or "KYC"
        first = first[:1].lower() + first[1:]
    return f"the {first}{space}{rest}"


def documents(names: Iterable[str], word: str = "and") -> str:
    """Document types, by name, as a request reads after "Please provide": "the income tax return
    and the GSTR-3B"; with `word` "or" when any one of them would complete the check."""
    return join((document(n) for n in names), word)


# The rule families' builders register themselves on import.
from . import accounts, authority, identity, numbers, obligations  # noqa: E402,F401
