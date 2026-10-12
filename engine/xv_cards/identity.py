"""Cards for ID-01 to ID-08 (PAN, GSTIN, legal name, promoter set, CIN, director identifiers, CIN particulars, memorandum directors).

Presentation only: built after the rule has decided its outcome (see engine/xv_cards/__init__.py).

- One value across documents (ID-01 PAN, ID-02 GSTIN, ID-03 legal name, ID-05 CIN): with at most
  four statements of the value, each statement is a column; with more, each group of statements
  that agree (the rule's sides) is a column with a row per statement. Two documents of one type
  are told apart by what each covers ("Income tax return · AY 2025-26"). The reference is the
  value of the clear majority, and the mismatch names the sources that give another value.
- People (ID-04 promoter set, ID-06 director identifiers, ID-08 memorandum directors): each source
  is a column with a row per person and the DIN and PAN printed there; the mismatch puts the
  finding's flagged rows in words.
- ID-07: the CIN with the particulars it encodes, the date of incorporation and the constitution
  on the case; the mismatch puts the flagged particulars in words.

None of them has an amount or a gap: the difference is a value, not a sum of money. A check short
of documents asks for them in the words every card uses (engine/xv_cards/__init__.py).

The key figures: for one value across documents, the values side by side (the majority first, the
others marked as the card marks them), or on a pass the agreed value "same across 18 sources"; for
the people checks and ID-07, the difference in words as the note (at most two people), or what the
rule confirmed.

A value of the case record is "In the sourcing message" when it was read from the message, and
"Entered on the case" when a person typed it: it has no place in the message to point to.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ..contracts import Evidence, FactValue, Finding, FindingDetail, FindingSide, PersonEntry, SourceColumn, XvHighlight
from ..crosschecks import CASE_RECORD, NO, YES
from ..names import name_parts
from ..util import display_date, parse_date, ranges_label
from . import MAX_COLUMNS, builds, column, fact, highlight, join, plural, row, sentence, wanted

if TYPE_CHECKING:
    from ..configstore.schema import CrossCheckRule
    from ..crosschecks import Context

FIELD_NAMES = {"entity_pan": "PAN", "gstin": "GSTIN", "cin": "CIN", "legal_name": "Legal name"}
LINE_LABELS = {
    "person_names": "Names of people","entity_pan": "PAN", "gstin": "GSTIN", "cin": "CIN", "legal_name": "Company name",
               "promoter_set": "Promoters", "director_identifiers": "Director identifiers",
               "memorandum_directors": "Directors in the memorandum", "incorporation_particulars": "CIN particulars"}
"""What each check's line on the overview card is labelled."""
SHORT_NAME = 40
"""The longest group label a line shows as it is; a longer one is counted: "16 documents and the sourcing message"."""
FEW = 2
"""People a line names before counting the rest."""
PEOPLE_ROWS = ["Name", "DIN", "PAN"]
CONSTITUTION = "case.constitution"
AUDITED, ITR, GSTR, BANK = "audited_financial_statements", "income_tax_return", "gstr_3b", "bank_statement"
IN_MESSAGE, ON_CASE = "the sourcing message", "an entry on the case"
"""A case-record value read from the sourcing message, or typed on the case by a person."""


# --- One value across documents (ID-01, ID-02, ID-03, ID-05) ---


@builds("entity_pan", "gstin", "legal_name", "cin")
def identifier(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    statements = [v for v in getattr(ctx.facts.identities, rule.variable)
                  if v.source in rule.sources or v.source == CASE_RECORD]
    sides = finding.sides
    owners = [_owner(v, sides) for v in statements]
    members = [[v for v, k in zip(statements, owners) if k == i] for i in range(len(sides))]
    field = FIELD_NAMES.get(rule.variable, rule.variable)
    names = {id(v): name for v, name in zip(statements, _names(ctx, statements))}
    if len(statements) <= MAX_COLUMNS:
        finding.columns = [_statement_column(ctx, f"statement-{i}", v, names[id(v)], field,
                                             sides[k] if k is not None else None)
                           for i, (v, k) in enumerate(zip(statements, owners))]
    else:
        finding.columns = _group_columns(ctx, field, sides, members, names)
    finding.reference = _reference(sides)
    if finding.outcome == "fail":
        finding.mismatch = _value_mismatch(sides, members, "read" if rule.variable == "legal_name" else "give")
    finding.highlights = _value_lines(rule, finding, statements, members, names)


def _value_lines(rule: CrossCheckRule, finding: Finding, statements: list[FactValue], members: list[list[FactValue]],
                 names: dict[int, str]) -> list[XvHighlight]:
    """The overview card's line: each value with the sources that give it, the majority first and the
    others marked as the rule marks them (at most as many as a card has columns); on a pass, the
    agreed value and how many sources give it; for a check that could not run, the values so far
    and what would complete it."""
    label = LINE_LABELS[rule.variable]
    sides = finding.sides
    if finding.outcome == "pass" and sides:
        n = plural(len(statements), "source")
        return [highlight(finding, label, [fact(n, sides[0].value)], f"same across {n}")]
    if finding.outcome not in ("fail", "incomplete"):
        return []
    order = sorted(range(len(sides)), key=lambda k: sides[k].differs)
    facts = [fact(_group_name(sides[k], members[k], names), sides[k].value, differs=sides[k].differs)
             for k in order[:MAX_COLUMNS]]
    if finding.outcome == "incomplete":
        note = wanted(finding)
    else:
        note = f"{len(sides)} different values" if len(sides) > MAX_COLUMNS else None
    return [highlight(finding, label, facts, note)]


def _group_name(side: FindingSide, statements: list[FactValue], names: dict[int, str]) -> str:
    """The sources of one value, shortly: the document as its column names it, the group's own label
    when it is short, else how many documents ("16 documents and the sourcing message")."""
    if len(statements) == 1:
        return names.get(id(statements[0]), statements[0].label)
    if len(side.label) <= SHORT_NAME or not statements:
        return side.label
    documents = {v.evidence[0].document_id if v.evidence else str(id(v))
                 for v in statements if v.source != CASE_RECORD}
    record = [v for v in statements if v.source == CASE_RECORD]
    words = [plural(len(documents), "document")] if documents else []
    if record:
        words.append(IN_MESSAGE if any(v.evidence for v in record) else ON_CASE)
    return " and ".join(words)


def _owner(v: FactValue, sides: list[FindingSide]) -> int | None:
    """The side (the rule's group) that carries a statement: the side holding its field, or for the
    sourcing message, which has no field, the side it is a source of; failing both, the side with
    its value (identical values are always grouped together)."""
    held = [i for i, s in enumerate(sides) if v.source in s.sources]
    if v.field_ids:
        found = next((i for i in held if set(v.field_ids) <= set(sides[i].field_ids)), None)
        if found is not None:
            return found
    elif len(held) == 1:
        return held[0]
    return next((i for i, s in enumerate(sides) if str(s.value) == str(v.value)), None)


def _statement_column(ctx: Context, key: str, v: FactValue, label: str, field: str,
                      side: FindingSide | None) -> SourceColumn:
    evidence = v.evidence[:1]
    return column(ctx, key, label, sources=[v.source], value=v.value, coverage=_coverage([(v.source, evidence)]),
                  differs=side is not None and side.differs, manual=v.relies_on_manual, awaiting=v.awaiting_review,
                  field_ids=v.field_ids, evidence=evidence, row_columns=["Field", "Value"],
                  rows=[row([field, v.value], evidence)])


def _group_columns(ctx: Context, field: str, sides: list[FindingSide], members: list[list[FactValue]],
                   names: dict[int, str]) -> list[SourceColumn]:
    """A column per group of statements that agree, with a row per statement. Beyond four groups the
    last column holds the rest, so that no value goes unshown; the agreeing group always keeps its own."""
    keep = list(range(len(sides)))
    if len(sides) > MAX_COLUMNS:
        keep = sorted(sorted(keep, key=lambda k: sides[k].differs)[:MAX_COLUMNS - 1])
    cols = [_group_column(ctx, f"group-{k}", sides[k].label, [sides[k]], members[k], field, names) for k in keep]
    rest = [k for k in range(len(sides)) if k not in keep]
    if rest:
        cols.append(_group_column(ctx, "group-rest", join(sides[k].label for k in rest), [sides[k] for k in rest],
                                  [v for k in rest for v in members[k]], field, names))
    return cols


def _group_column(ctx: Context, key: str, label: str, sides: list[FindingSide], statements: list[FactValue],
                  field: str, names: dict[int, str]) -> SourceColumn:
    value = sides[0].value if len(sides) == 1 else "; ".join(dict.fromkeys(str(s.value) for s in sides))
    return column(ctx, key, label, sources=[src for s in sides for src in s.sources], value=value,
                  coverage=_coverage([(v.source, v.evidence) for v in statements]),
                  differs=any(s.differs for s in sides), manual=any(s.relies_on_manual for s in sides),
                  awaiting=any(s.awaiting_review for s in sides), field_ids=[i for s in sides for i in s.field_ids],
                  evidence=_distinct([e for s in sides for e in s.evidence]), row_columns=["Document", field],
                  rows=[row([names.get(id(v), v.label), v.value], v.evidence[:1]) for v in statements])


def _names(ctx: Context, statements: list[FactValue]) -> list[str]:
    """Each statement's label as its column or row shows it. Two documents of one type would read
    alike, so each is told apart by what it covers where the facts say (the year of audited
    statements, the assessment year of a return, the month of a GSTR-3B, the account and months of
    a bank statement), else by its page, else by its place among them: "Audited financial
    statements · FY 2024-25", "Income tax return · AY 2025-26", "GSTR-3B · page 3", "GSTR-3B · 2 of 3"."""
    names = [v.label for v in statements]
    covers = _covers(ctx)
    for label in dict.fromkeys(v.label for v in statements):
        group = [i for i, v in enumerate(statements) if v.label == label]
        if len(group) < 2:
            continue
        firsts = [statements[i].evidence[0] if statements[i].evidence else None for i in group]
        tags = _apart([covers.get((statements[i].source, e.document_id), []) if e else [] for i, e in zip(group, firsts)],
                      [f"page {e.page}" if e else None for e in firsts])
        for i, tag in zip(group, tags):
            names[i] = f"{label} · {tag}"
    return names


def _covers(ctx: Context) -> dict[tuple[str, str], list[str]]:
    """What each document covers, by its type and id, as far as the facts say, most telling first:
    the year of audited statements, the assessment year of an income tax return, the month of a
    GSTR-3B, and a bank statement's account, then the months of the credits read from it."""
    found: dict[tuple[str, str], list[str]] = {}
    f = ctx.facts
    for y in f.financial_years:
        for e in (e for v in y.current.values() for e in v.evidence[:1]):
            found.setdefault((AUDITED, e.document_id), [y.fy])
    for t in f.tax_years:
        for e in t.evidence[:1] + [e for v in t.lines.values() for e in v.evidence[:1]]:
            found.setdefault((ITR, e.document_id), [f"AY {t.assessment_year}"])
    for m in f.months:
        for e in m.gst_evidence[:1]:
            found.setdefault((GSTR, e.document_id), [m.label])
    # An account with a statement holds a page of each statement read for it (engine/facts.py _accounts);
    # each month of its credits, the page of the month's first credit.
    accounts = {e.document_id: a.label for a in f.accounts if a.has_statement for e in a.evidence}
    months: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for c in f.credits:
        for m in c.by_month:
            for e in m.evidence[:1]:
                months[e.document_id].add((int(m.month[:4]), int(m.month[5:7])))
    for doc in accounts.keys() | months.keys():
        found[(BANK, doc)] = [x for x in (accounts.get(doc), ranges_label(sorted(months.get(doc, ())))) if x]
    return found


def _apart(covers: list[list[str]], pages: list[str | None]) -> list[str]:
    """A tag for each of several documents that share a label: what each covers, at the first level
    that tells every one apart; else what each covers, or its page where that is not known; and for
    any still alike, its place among them ("2 of 3")."""
    n = len(covers)
    for level in range(max(map(len, covers), default=0)):
        tags = [c[level] if len(c) > level else None for c in covers]
        if None not in tags and len(set(tags)) == n:
            return tags  # type: ignore[return-value]
    tags = [c[0] if c else p for c, p in zip(covers, pages)]
    return [t if t and tags.count(t) == 1 else f"{i} of {n}" for i, t in enumerate(tags, start=1)]


def _reference(sides: list[FindingSide]) -> str | None:
    """The value of the clear majority: the one side that does not differ while the others do."""
    agree = [s for s in sides if not s.differs]
    if len(sides) > 1 and len(agree) == 1 and agree[0].value is not None:
        return str(agree[0].value)
    return None


def _value_mismatch(sides: list[FindingSide], members: list[list[FactValue]], verb: str) -> str | None:
    """The sources that give another value than the majority, or every value when none has one."""
    if len(sides) < 2:
        return None

    def labels(k: int) -> list[str]:
        return list(dict.fromkeys(v.label for v in members[k])) or [sides[k].label]

    agree = [k for k, s in enumerate(sides) if not s.differs]
    if len(agree) != 1:
        values = "; ".join(f"{s.value} ({join(labels(k))})" for k, s in enumerate(sides))
        return sentence(f"{len(sides)} different values: {values}")
    major = agree[0]
    others = [f"{join(labels(k))} {_verb(verb, len(labels(k)))} {s.value}" for k, s in enumerate(sides) if k != major]
    n = len(members[major])
    rest = f"the other {n} sources {verb}" if n > 1 else f"the other source {_verb(verb, 1)}"
    # A value can end with a full stop of its own ("Kestrel Tools Pvt. Ltd."): no second one.
    return sentence(f"{'; '.join(others)}; {rest} {sides[major].value}")


def _verb(verb: str, subjects: int) -> str:
    return f"{verb}s" if subjects == 1 else verb


# --- People (ID-04, ID-06, ID-08) ---


@builds("promoter_set")
def promoter_set(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    # The rule's sets in its order of sources: one side each, in the same order.
    sets = sorted((p for p in ctx.facts.persons if p.source in rule.sources), key=lambda p: rule.sources.index(p.source))
    paired = len(sets) == len(finding.sides) and all(p.label == s.label for p, s in zip(sets, finding.sides))
    finding.columns = [_people_column(ctx, f"people-{i}", s, sets[i].entries if paired else ctx.persons(*s.sources))
                       for i, s in enumerate(finding.sides)]
    absent: list[str] = []
    if finding.outcome == "fail" and finding.detail is not None:
        d = finding.detail
        # A flagged row is a person; the columns whose cell is not a tick are the sources that do not name them.
        missed = [(r.label, [c for c, cell in zip(d.columns, r.cells) if cell != YES]) for r in d.rows if r.flagged]
        absent = [f"{person} is not in {join(where)}" for person, where in missed if where]
        finding.mismatch = sentence("; ".join(absent))
    people = len(finding.detail.rows) if finding.detail else 0
    finding.highlights = _people_lines(rule, finding, absent,
                                       f"the same {plural(people, 'person', 'people')} in "
                                       f"{plural(len(finding.sides), 'source')}")


@builds("director_identifiers")
def director_identifiers(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    finding.columns = [_people_column(ctx, f"people-{i}", s, ctx.persons(*s.sources)) for i, s in enumerate(finding.sides)]
    problems = _identifier_problems(ctx, finding.detail) if finding.outcome == "fail" else []
    if finding.outcome == "fail":
        finding.mismatch = sentence("; ".join(problems))
    directors = len(finding.detail.rows) if finding.detail else 0
    finding.highlights = _people_lines(rule, finding, problems,
                                       f"identifiers agree for {plural(directors, 'director')}")


@builds("person_names")
def person_names(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    """ID-09: one column per document, each person's name split into its first, middle and last
    name; the overview card names who differs and how."""
    finding.columns = [_name_parts_column(ctx, f"people-{i}", s, ctx.persons(*s.sources))
                       for i, s in enumerate(finding.sides)]
    rows = finding.detail.rows if finding.detail else []
    people = list(dict.fromkeys(r.label for r in rows))
    if finding.outcome == "fail":
        finding.mismatch = sentence(finding.explanation.removeprefix("Names differ in part: ").rstrip("."))
        lines = []
        for person in [p for p in people if any(r.flagged for r in rows if r.label == p)][:FEW]:
            mine = [r for r in rows if r.label == person]
            facts = [fact(str(r.cells[0]), str(r.cells[1]), differs=r.flagged) for r in mine][:3]
            off = [f"{part} {CELL_WORDS.get(str(cell), str(cell).lower())} in {r.cells[0]}" for r in mine if r.flagged
                   for part, cell in zip(("first name", "middle name", "last name"), r.cells[2:])
                   if cell not in (YES, NO, "")]
            lines.append(highlight(finding, person, facts, "; ".join(dict.fromkeys(off)) or None))
        finding.highlights = lines
    elif finding.outcome == "pass":
        finding.highlights = [highlight(finding, LINE_LABELS[rule.variable],
                                        note=f"names agree in full for {plural(len(people), 'person', 'people')}")]
    elif finding.outcome == "incomplete":
        finding.highlights = [highlight(finding, LINE_LABELS[rule.variable], note=wanted(finding))]


CELL_WORDS = {"Missing": "missing", "Initial only": "only an initial", "Different": "written differently"}


def _name_parts_column(ctx: Context, key: str, side: FindingSide, people: list[PersonEntry]) -> SourceColumn:
    source = side.sources[0] if side.sources else ""
    return column(ctx, key, side.label, sources=side.sources, value=side.value,
                  coverage=_coverage([(source, p.evidence) for p in people]), differs=side.differs,
                  manual=side.relies_on_manual, awaiting=side.awaiting_review, field_ids=side.field_ids,
                  evidence=_distinct([e for p in people for e in p.evidence[:1]]) or side.evidence,
                  row_columns=["Person", "First name", "Middle name", "Last name"],
                  rows=[row([p.name, *_parts(p.name)], p.evidence[:1]) for p in people])


def _parts(name: str) -> list[str | None]:
    parts = name_parts(name)
    return [parts.first, " ".join(parts.middle) or None, parts.last]


@builds("memorandum_directors")
def memorandum_directors(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    finding.columns = [_people_column(ctx, f"people-{i}", s, ctx.persons(*s.sources)) for i, s in enumerate(finding.sides)]
    names = list(dict.fromkeys(r.label for r in finding.detail.rows if r.flagged)) if finding.detail else []
    unaccounted = []
    if finding.outcome == "fail" and names:
        one = len(names) == 1
        rest = f"{'has' if one else 'have'} no KYC and {'is' if one else 'are'} not named in the sourcing message"
        finding.mismatch = f"{join(names)} in the memorandum {rest}."
        # The line names at most two of them.
        few = (join(names) if len(names) <= FEW
               else f"{', '.join(names[:FEW])} and {plural(len(names) - FEW, 'other')}")
        unaccounted = [f"{few} {rest}"]
    directors = len(finding.detail.rows) if finding.detail else 0
    every = ("accounted for" if directors < 2 else "both accounted for" if directors == 2
             else f"all {directors} accounted for")
    finding.highlights = _people_lines(rule, finding, unaccounted, every)


def _people_lines(rule: CrossCheckRule, finding: Finding, problems: list[str], confirmed: str) -> list[XvHighlight]:
    """The overview card's line for a check of people or particulars: the problems in words (at most
    two people, then how many more), what the rule confirmed on a pass, or what would complete it."""
    label = LINE_LABELS[rule.variable]
    if finding.outcome == "fail":
        shown = "; ".join(problems[:FEW]) + (f"; and {len(problems) - FEW} more" if len(problems) > FEW else "")
        return [highlight(finding, label, note=shown or None)]
    if finding.outcome == "pass":
        return [highlight(finding, label, note=confirmed)]
    if finding.outcome == "incomplete":
        return [highlight(finding, label, note=wanted(finding))]
    return []


def _people_column(ctx: Context, key: str, side: FindingSide, people: list[PersonEntry]) -> SourceColumn:
    source = side.sources[0] if side.sources else ""
    return column(ctx, key, side.label, sources=side.sources, value=side.value,
                  coverage=_coverage([(source, p.evidence) for p in people]), differs=side.differs,
                  manual=side.relies_on_manual, awaiting=side.awaiting_review, field_ids=side.field_ids,
                  evidence=_distinct([e for p in people for e in p.evidence[:1]]) or side.evidence,
                  row_columns=PEOPLE_ROWS, rows=[row([p.name, p.din, p.pan], p.evidence[:1]) for p in people])


def _identifier_problems(ctx: Context, detail: FindingDetail | None) -> list[str]:
    """Each flagged director (a row per KYC: the memorandum's DIN, the KYC's DIN and PAN): the DIN
    against the memorandum's, or why the PAN is not the director's own, as the rule found them."""
    if detail is None:
        return []
    company = {str(v.value) for v in ctx.facts.identities.entity_pan}
    problems = []
    for r in detail.rows:
        if not r.flagged:
            continue
        moa, din, pan = (list(r.cells) + [None, None, None])[:3]
        issues = []
        if moa and din and moa != din:
            issues.append(f"DIN {din} on the KYC against {moa} in the memorandum")
        if pan:
            if len(str(pan)) == 10 and str(pan)[3] != "P":
                issues.append(f"PAN {pan} is not an individual's PAN")
            elif str(pan) in company:
                issues.append(f"PAN {pan} is the company's PAN")
        problems.append(f"{r.label}: {'; '.join(issues) or 'the identifiers disagree'}")
    return problems


# --- The CIN against the incorporation particulars (ID-07) ---


@builds("incorporation_particulars")
def incorporation_particulars(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    # The sides: the CIN, then the date of incorporation and the constitution on the case when the rule had them.
    particulars = finding.detail.rows if finding.detail else []
    columns = []
    for i, s in enumerate(finding.sides):
        if i == 0:
            # The particulars the CIN encodes; a CIN the rule could not read has only itself to show.
            evidence = s.evidence[:1]
            rows = [row([r.label, r.cells[0] if r.cells else None], evidence) for r in particulars]
            headings = ["Particular", "In the CIN"] if rows else ["Field", "Value"]
            columns.append(column(ctx, "cin", s.label, sources=s.sources, value=s.value,
                                  coverage=_coverage([(src, s.evidence) for src in s.sources[:1]]), differs=s.differs,
                                  manual=s.relies_on_manual, awaiting=s.awaiting_review, field_ids=s.field_ids,
                                  evidence=s.evidence, row_columns=headings, rows=rows or [row(["CIN", s.value], evidence)]))
        elif CONSTITUTION in s.sources:
            columns.append(column(ctx, "constitution", s.label, sources=s.sources, value=s.value, coverage="Set on the case",
                                  differs=s.differs, row_columns=["Particular", "On the case"],
                                  rows=[row(["Constitution", s.value])]))
        else:
            # A date as the other cards write one: ISO for the board to format, and as read in the row.
            when = parse_date(s.value)
            columns.append(column(ctx, "incorporation", s.label, sources=s.sources,
                                  value=when.isoformat() if when else s.value, unit="date" if when else "text",
                                  coverage=_coverage([(src, s.evidence) for src in s.sources[:1]]), differs=s.differs,
                                  manual=s.relies_on_manual, awaiting=s.awaiting_review, field_ids=s.field_ids,
                                  evidence=s.evidence, row_columns=["Particular", "On the certificate"],
                                  rows=[row(["Date of incorporation", display_date(when) if when else s.value],
                                            s.evidence[:1])]))
    finding.columns = columns
    problems: list[str] = []
    if finding.outcome == "fail":
        flagged = [(r.label, list(r.cells) + [None, None]) for r in particulars if r.flagged]
        problems = [f"{label.lower()} {cells[0]} in the CIN against {cells[1]} on file" for label, cells in flagged]
        finding.mismatch = sentence("; ".join(problems))
    # Every particular the CIN was held against: the line names them all.
    finding.highlights = _people_lines(rule, finding, ["; ".join(problems)] if problems else [],
                                       f"agrees with {plural(len(particulars), 'particular')} on file")


# --- Shared ---


def _coverage(stated: list[tuple[str, list[Evidence]]]) -> str | None:
    """Where a value is stated, in one line: its page, how many documents state it, or the case
    record: "In the sourcing message" for a value read from the message, "Entered on the case" for
    one a person typed, which has no page. `stated`: the source and evidence of each statement (the
    first evidence is its page)."""
    record = [evidence for source, evidence in stated if source == CASE_RECORD]
    pages = list(dict.fromkeys((e.document_id, e.page) for source, evidence in stated if source != CASE_RECORD
                               for e in evidence[:1]))
    documents = list(dict.fromkeys(d for d, _ in pages))
    if not documents:
        if not record:
            return None
        return "In the sourcing message" if any(record) else "Entered on the case"
    if len(documents) == 1 and not record:
        numbers = sorted({p for _, p in pages})
        return f"Page {numbers[0]}" if len(numbers) == 1 else "Pages " + join(str(p) for p in numbers)
    count = plural(len(documents), "document")
    return f"{count} and {IN_MESSAGE if any(record) else ON_CASE}" if record else count


def _distinct(evidence: list[Evidence]) -> list[Evidence]:
    seen: set[tuple] = set()
    out = []
    for e in evidence:
        key = (e.document_id, e.page, e.bbox)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
