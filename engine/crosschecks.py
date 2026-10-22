"""Cross-checks across the nine document types (FRD F-19; docs/cross-verification-plan.md).

Each configured rule (config/crosschecks.yaml) compares one aligned fact
(engine/facts.py) across its sources; a rule switched off there (`enabled:
false`) is not run and gives no finding. The outcome is pass, fail, incomplete
(with the missing coverage named) or not applicable (F-19.3):

- a check that would rely on a value still waiting for review is incomplete
  until a person confirms or corrects it (F-17.2);
- a check short of sources is incomplete when the case's checklist expects a
  source document that is not on file, and not applicable otherwise.

A failure keeps both sides' values with their evidence, marks the side that
differs, and carries the line-by-line detail (months, people, years) behind
it; it says when it relies on a person's entry (F-19.4). Findings are
replaced on every run, so changing one tolerance changes exactly the
findings that use it (F-19.6).

After a rule decides its outcome, engine/xv_cards builds the finding's card for
the cross-verification board (its sources as columns, the gap per leg); the card
never changes the outcome. engine/xv keeps the finding references and the run.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from . import facts as facts_module
from .config import load_app_config
from .configstore import reader
from .configstore.schema import CrossCheckRule
from .contracts import (
    CaseDetail,
    CaseFacts,
    Evidence,
    FactValue,
    Finding,
    FindingDetail,
    FindingDetailRow,
    FindingSide,
    FinancialYear,
    PersonEntry,
    PersonSet,
    TurnoverFigure,
)
from .db import transaction
from .names import compare_name_parts, name_parts, same_by_parts, normalise_name, similarity
from .review_items import raise_item
from .util import display_date, dumps, parse_date, parse_period, ranges_label, stable_id

inr = facts_module.inr

TURNOVER_PAIRS = {
    "turnover_audited_vs_gst": ("financials", "gst"),
    "turnover_gst_vs_bank": ("gst", "bank"),
    "turnover_audited_vs_bank": ("financials", "bank"),
    "turnover_declared_vs_evidenced": ("declared", "financials"),
    "turnover_itr_vs_audited": ("itr", "financials"),
    "turnover_itr_vs_gst": ("itr", "gst"),
    "turnover_itr_vs_bank": ("itr", "bank"),
}
"""The two turnover sources each comparison holds against each other (TO-01 to TO-04, TX-03 to TX-05)."""

# Not a document a person uploads: the case's own record of the sourcing message.
CASE_RECORD = "application_message"
ITR = "income_tax_return"
DECLARATION, SANCTION, BUREAU = facts_module.DECLARATION, facts_module.SANCTION, facts_module.BUREAU
YES, NO = "✓", "—"

LINE_LABELS = {
    "revenue_from_operations": "Revenue from operations",
    "profit_after_tax": "Profit after tax",
    "net_worth": "Net worth",
    "total_borrowings": "Total borrowings",
}
CIN_CLASSES = {
    "PTC": "Private limited company",
    "PLC": "Public limited company",
    "OPC": "One person company",
    "NPL": "Not-for-profit company",
    "FTC": "Subsidiary of a foreign company",
    "GOI": "Government company",
}
_CIN_RE = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")


class _Fmt(dict):
    def __missing__(self, key: str) -> str:
        return ""


class Context:
    def __init__(self, root: Path, case: CaseDetail, facts: CaseFacts) -> None:
        from .completeness import applicable_items

        self.case = case
        self.facts = facts
        self.tolerances = {t.key: t for t in reader.load_tolerances(root).tolerances}
        alignment = reader.load_alignment(root)
        self.noise = [w.lower() for w in alignment.name_noise_words]
        self.own_banks = alignment.own_bank_names
        self.fy_start = alignment.financial_year_start_month
        self.version = reader.published_version(root)["version"]
        self.rules = reader.load_crosschecks(root).enabled_rules
        types = reader.load_document_types(root).types
        self.type_names = {t.id: t.name for t in types}
        self.type_names[CASE_RECORD] = "Sourcing message"
        self.provenance = {t.id: t.provenance for t in types if t.provenance}
        items = {i.id for i in applicable_items(root, case, None)[0]}
        self.expected = {t.id for t in types if set(t.satisfies) & items}
        self.on_file = set(facts.types_on_file)
        self.threshold = self.tol("name_match", 0.85)
        self.as_of = date.fromisoformat(case.as_of)
        self.constitutions = {c["id"]: c["label"] for c in load_app_config().get("constitutions", [])}

    def tol(self, key: str | None, default: float) -> float:
        return self.tolerances[key].value if key and key in self.tolerances else default

    def tol_text(self, key: str | None) -> str | None:
        if not key or key not in self.tolerances:
            return None
        t = self.tolerances[key]
        return f"{t.value:g}%" if t.unit == "%" else f"{t.value:g}"

    def missing(self, rule: CrossCheckRule) -> list[str]:
        """The rule's source documents the case's checklist expects and that are not on file."""
        return [self.type_names.get(s, s) for s in rule.sources
                if s != CASE_RECORD and s in self.expected and s not in self.on_file]

    def same_person(self, a: str, b: str) -> bool:
        return similarity(a, b) >= self.threshold

    def persons(self, *sources: str) -> list[PersonEntry]:
        return [e for p in self.facts.persons if p.source in sources for e in p.entries]


# --- Building findings ---


def _finding(ctx: Context, rule: CrossCheckRule, outcome: str, sides: list[FindingSide], scope: str = "", *,
             note: str = "", detail: FindingDetail | None = None, missing: list[str] | None = None,
             review: list[str] | None = None, **fmt: str) -> Finding:
    """`review` names the values waiting for review where a side's label says more (a side of agreeing
    sources, only one of them waiting)."""
    waiting = list(dict.fromkeys(s.label for s in sides if s.awaiting_review))
    if waiting and outcome in ("pass", "fail"):
        # F-17.2: a value below its threshold is reviewed before a check relies on it.
        outcome = "incomplete"
        # A side's label may itself list several sources ("Company PAN, Income tax return").
        named = _join(review) if review else ", ".join(
            _lower(part) for label in waiting for part in label.split(", "))
        note = f"Waiting for review of {named}; confirm or correct the value to complete this check."
    values = _Fmt(fmt)
    values.setdefault("tolerance", ctx.tol_text(rule.tolerance) or "")
    explanation = rule.explanation.format_map(values) if outcome == "fail" else note
    title = f"{rule.title} · {scope}" if scope else rule.title
    return Finding(
        id=stable_id("FND", ctx.case.id, rule.id, scope),
        case_id=ctx.case.id,
        rule_id=rule.id,
        title=title,
        finding_title=rule.finding_title,
        compares=rule.title,
        policy_ref=rule.policy_ref,
        area=rule.area,
        scope=scope or None,
        outcome=outcome,  # type: ignore[arg-type]
        severity=rule.severity,
        blocking=rule.blocking,
        explanation=explanation,
        sides=sides,
        detail=detail,
        missing=missing or [],
        # Shown only where it is the comparison's allowance; a name-matching
        # threshold is how sources are matched, not a finding's tolerance.
        tolerance=(ctx.tol_text(rule.tolerance)
                   if rule.comparison in ("tolerance", "bound") and outcome != "not_applicable" else None),
        config_version=ctx.version,
        query=rule.query.format_map(values) if outcome == "fail" and rule.query else None,
    )


def _absent(ctx: Context, rule: CrossCheckRule, sides: list[FindingSide] | None = None, scope: str = "", *,
            note: str = "Fewer than two sources state this.") -> Finding:
    """Too little to compare: incomplete if an expected document is missing (named), else not applicable."""
    missing = ctx.missing(rule)
    if missing:
        return _finding(ctx, rule, "incomplete", sides or [], scope, note=f"{_labels(missing)} not on file.",
                        missing=missing)
    return _finding(ctx, rule, "not_applicable", sides or [], scope, note=note)


def _side(label: str, value: str | float | None, evidence: list[Evidence], manual: bool = False, *,
          awaiting: bool = False, differs: bool = False, field_ids: list[str] | None = None,
          sources: list[str] | None = None) -> FindingSide:
    return FindingSide(label=label, value=value, evidence=evidence, relies_on_manual=manual,
                       awaiting_review=awaiting, differs=differs, field_ids=field_ids or [],
                       sources=list(dict.fromkeys(sources or [])))


def _fact_side(v: FactValue, label: str | None = None, *, differs: bool = False) -> FindingSide:
    return _side(label or v.label, v.value, v.evidence[:1], v.relies_on_manual, awaiting=v.awaiting_review,
                 differs=differs, field_ids=v.field_ids, sources=[v.source])


def _people_side(label: str, people: list[PersonEntry], *, differs: bool = False, show: Callable[[PersonEntry], str] | None = None,
                 sources: list[str] | None = None) -> FindingSide:
    return _side(label, "; ".join((show or (lambda e: e.name))(e) for e in people) or None,
                 [ev for e in people for ev in e.evidence[:1]][:6], any(e.relies_on_manual for e in people),
                 awaiting=any(e.awaiting_review for e in people), differs=differs, sources=sources)


def _join(items: list[str]) -> str:
    items = list(dict.fromkeys(items))
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _lower(label: str) -> str:
    """A source's label as it reads inside a sentence: its first letter in lower case, unless it opens
    an acronym (GST outward supplies, KYC received, GSTR-3B)."""
    return label[:1].lower() + label[1:] if label[1:2].islower() else label


def _labels(labels: list[str]) -> str:
    """Labels joined into a sentence's subject: the first as it is, the rest as they read inside it."""
    return _join([label if i == 0 else _lower(label) for i, label in enumerate(labels)])


def _variance(a: float, b: float) -> float:
    top = max(abs(a), abs(b))
    return abs(a - b) / top * 100 if top else 0.0


def _rows(columns: list[str], rows: list[tuple]) -> FindingDetail:
    """Rows of (label, cells, flagged) and, where only some cells are the reason, their positions."""
    return FindingDetail(columns=columns, rows=[
        FindingDetailRow(label=r[0], cells=r[1], flagged=r[2], flagged_cells=list(r[3]) if len(r) > 3 else [])
        for r in rows])


# --- Identity: one value across sources (ID-01, ID-02, ID-03, ID-05) ---


def _same_name(a: str, b: str, threshold: float) -> bool:
    """Name variants of one entity; a bank's truncated account name is a prefix of the full one."""
    if similarity(a, b) >= threshold:
        return True
    na, nb = sorted((normalise_name(a), normalise_name(b)), key=len)
    return len(na) >= 8 and len(na.split()) >= 2 and nb.startswith(na)


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


def _identity(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    values = [v for v in getattr(ctx.facts.identities, rule.variable) if v.source in rule.sources or v.source == CASE_RECORD]
    if rule.variable == "legal_name":
        threshold = ctx.tol(rule.tolerance, 0.85)
        groups = _groups(values, lambda a, b: _same_name(str(a), str(b), threshold))
    else:
        groups = _groups(values, lambda a, b: str(a) == str(b))
    largest = max((len(g) for g in groups), default=0)
    clear_majority = sum(1 for g in groups if len(g) == largest) == 1
    sides = [
        _side(
            ", ".join(dict.fromkeys(v.label for v in g)),
            g[0].value,
            [e for v in g for e in v.evidence[:1]],
            any(v.relies_on_manual for v in g),
            awaiting=any(v.awaiting_review for v in g),
            differs=len(groups) > 1 and not (clear_majority and len(g) == largest),
            field_ids=[i for v in g for i in v.field_ids],
            sources=[v.source for v in g],
        )
        for g in groups
    ]
    if len({(v.source, v.label, str(v.value)) for v in values}) < 2:
        return [_absent(ctx, rule, sides)]
    statements = _Statements(ctx, rule, values)
    review = statements.awaiting()
    if len(groups) == 1:
        return [_finding(ctx, rule, "pass", sides, note=f"Consistent across {len(values)} sources.", review=review)]
    names = statements.names(groups)
    first = _reference_group(rule, sides, groups)
    order = [first] + [k for k in range(len(groups)) if k != first]
    others = order[1:]
    # "X in the company PAN and income tax return; Y in the commercial bureau report": the reference first.
    items = "; ".join(f"{sides[k].value} in the {_join(names[k])}" for k in order)
    return [_finding(ctx, rule, "fail", sides, items=items, review=review, reference=str(sides[first].value),
                     differing="the " + _join([n for k in others for n in names[k]]),
                     others=_join([str(sides[k].value) for k in others]))]


IDENTITY_FIELDS = {"entity_pan": "PAN", "gstin": "GSTIN", "cin": "CIN", "legal_name": "name"}
YEARLY = ("audited_financial_statements", ITR)
"""Documents that cover a year: named with it where one type gives two values."""


class _Statements:
    """One value's statements (ID-01, ID-02, ID-03, ID-05), as an explanation names them. A PAN read from
    within a GSTIN is named only for a document that prints no PAN of its own, so a document that prints
    a PAN and a GSTIN carrying another is named once, for the PAN it prints. Where one document type
    gives two values (the audited statements of two years), each is named with its year."""

    def __init__(self, ctx: Context, rule: CrossCheckRule, values: list[FactValue]) -> None:
        self.ctx, self.rule, self.values = ctx, rule, values
        self.gstins = {tuple(v.field_ids): v for v in ctx.facts.identities.gstin if v.field_ids}
        self.printing = {self.document(v) for v in values if not self.derived(v)} - {None}

    def derived(self, v: FactValue) -> FactValue | None:
        """The GSTIN statement a PAN was read from, or None for a PAN the document prints."""
        return self.gstins.get(tuple(v.field_ids)) if self.rule.variable == "entity_pan" and v.field_ids else None

    @staticmethod
    def document(v: FactValue) -> str | None:
        return v.evidence[0].document_id if v.evidence else None

    def awaiting(self) -> list[str]:
        """The values waiting for review, each as read: "the PAN read from the income tax return"."""
        field = IDENTITY_FIELDS.get(self.rule.variable, "value")
        out = []
        for v in self.values:
            if not v.awaiting_review:
                continue
            gstin = self.derived(v)
            label = _lower(gstin.label if gstin else v.label)
            if gstin:
                out.append(f"the GSTIN read from the {label}")
            elif field.lower() in label.lower().split():
                out.append(f"the {label}")
            else:
                out.append(f"the {field} read from the {label}")
        return list(dict.fromkeys(out))

    def names(self, groups: list[list[FactValue]]) -> list[list[str]]:
        """Each group's documents in words, each once."""
        kept = [[v for v in g if not (self.derived(v) and self.document(v) in self.printing)] or g for g in groups]
        where: dict[str, set[int]] = {}
        for k, g in enumerate(kept):
            for v in g:
                where.setdefault(v.label, set()).add(k)
        years = _years(self.ctx)
        out = []
        for g in kept:
            named: dict[str, list[str]] = {}
            for v in g:
                year = years.get(self.document(v) or "") if v.source in YEARLY and len(where[v.label]) > 1 else None
                covered = named.setdefault(v.label, [])
                if year and year not in covered:
                    covered.append(year)
            out.append([_documents(label, covered) for label, covered in named.items()])
        return out


def _documents(label: str, years: list[str]) -> str:
    """A document type inside a sentence, with the years its documents cover: "audited financial
    statements for FY 2024-25", "income tax returns for AY 2025-26 and AY 2026-27"."""
    if not years:
        return _lower(label)
    many = label if len(years) == 1 or label.endswith("s") else f"{label}s"
    return f"{_lower(many)} for {_join(sorted(years))}"


def _years(ctx: Context) -> dict[str, str]:
    """The year each audited statement and income tax return covers, by its document: "FY 2024-25",
    "AY 2025-26"."""
    found: dict[str, str] = {}
    for y in ctx.facts.financial_years:
        for e in (e for v in y.current.values() for e in v.evidence[:1]):
            found.setdefault(e.document_id, y.fy)
    for t in ctx.facts.tax_years:
        for e in t.evidence[:1] + [e for v in t.lines.values() for e in v.evidence[:1]]:
            found.setdefault(e.document_id, f"AY {t.assessment_year}")
    return found


def _reference_group(rule: CrossCheckRule, sides: list[FindingSide], groups: list[list[FactValue]]) -> int:
    """The group the others are held against: the clear majority, else the group of the source the
    rule lists first (the certificate of incorporation for a name, the company PAN for a PAN)."""
    agree = [k for k, s in enumerate(sides) if not s.differs]
    if len(agree) == 1:
        return agree[0]
    rank = {s: i for i, s in enumerate(rule.sources)}
    return min(range(len(groups)), key=lambda k: min(rank.get(v.source, len(rank)) for v in groups[k]))


# --- People (ID-04, ID-06, ID-08; ID-09 below) ---


def _origin(p: PersonSet, e: PersonEntry) -> set[str]:
    """Where an entry is listed: its documents, or its source for a name with no page (typed on the
    case), so that two names one list gives are never one person."""
    return {ev.document_id for ev in e.evidence} or {f"source:{p.source}"}


def _alike(ctx: Context, a: str, b: str, by_parts: bool = False) -> float:
    """How alike two names are, to choose between matches: the same name above a close one (at least
    name_match alike), and a match by the name's parts (ID-09) below both; 0 when not one person."""
    if normalise_name(a) == normalise_name(b):
        return 3.0
    score = similarity(a, b)
    if score >= ctx.threshold:
        return 1.0 + score
    return 0.5 if by_parts and same_by_parts(a, b) else 0.0


def _people(ctx: Context, sets: list[PersonSet], *, lead_only: bool = False,
            by_parts: bool = False) -> list[list[tuple[PersonSet, PersonEntry]]]:
    """The sources' entries as people, each in the order first named. One name is one person; then the
    most alike people join first: by their first names with lead_only, else by any of their names. Two
    people never join when one document (or one list typed on the case) names both: two directors with
    similar names in one memorandum are two people however alike."""
    entries = [(p, e) for p in sets for e in p.entries]
    by_name: dict[str, list[int]] = {}
    for i, (_, e) in enumerate(entries):
        by_name.setdefault(normalise_name(e.name), []).append(i)
    groups = list(by_name.values())
    origins = [set().union(*(_origin(*entries[i]) for i in g)) for g in groups]

    def link(a: list[int], b: list[int]) -> float:
        pairs = [(a[0], b[0])] if lead_only else [(i, j) for i in a for j in b]
        return max(_alike(ctx, entries[i][1].name, entries[j][1].name, by_parts) for i, j in pairs)

    while True:
        best = None
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                score = 0.0 if origins[a] & origins[b] else link(groups[a], groups[b])
                if score and (best is None or score > best[0]):
                    best = (score, a, b)
        if best is None:
            return [[entries[i] for i in g] for g in groups]
        _, a, b = best
        groups[a], origins[a] = sorted(groups[a] + groups[b]), origins[a] | origins[b]
        del groups[b], origins[b]


def _best_matches(ctx: Context, name: str, entries: list[PersonEntry]) -> list[int]:
    """The entries that name is the same person as, at its best: the same name before a close one."""
    scores = [_alike(ctx, name, e.name) for e in entries]
    top = max(scores, default=0.0)
    return [i for i, s in enumerate(scores) if s and s == top]


def _not_named(person: str, absent: list[PersonSet]) -> str:
    """ID-04: what a source lacks for a person, in words."""
    parts = ["has no KYC on file"] if any(p.source == "director_kyc" for p in absent) else []
    others = [f"the {_lower(p.label)}" for p in absent if p.source != "director_kyc"]
    if others:
        parts.append(f"is not named in {_join(others)}")
    return f"{person} {' and '.join(parts)}"


def _promoter_set(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    # In the rule's order of sources, so the result does not depend on the order documents arrived in.
    sets = sorted((p for p in ctx.facts.persons if p.source in rule.sources), key=lambda p: rule.sources.index(p.source))
    if len(sets) < 2:
        return [_absent(ctx, rule, [_people_side(p.label, p.entries, sources=[p.source]) for p in sets],
                        note="Fewer than two sources name the promoters.")]
    # A source names a person when one of its entries is that person (the first name met stands for
    # them), so a similar name of someone else does not count.
    people = _people(ctx, sets, lead_only=True)
    gaps, rows, short = [], [], set()
    for group in people:
        person = group[0][1].name
        named = [any(q is p for q, _ in group) for p in sets]
        absent = [p for p, ok in zip(sets, named) if not ok]
        short |= {p.label for p in absent}
        if absent:
            gaps.append(_not_named(person, absent))
        rows.append((person, [YES if ok else NO for ok in named], bool(absent)))
    sides = [_people_side(p.label, p.entries, differs=p.label in short, sources=[p.source]) for p in sets]
    detail = _rows([p.label for p in sets], rows)
    if not gaps:
        return [_finding(ctx, rule, "pass", sides, detail=detail,
                         note=f"The same {len(people)} person(s) in {len(sets)} sources.")]
    return [_finding(ctx, rule, "fail", sides, detail=detail, items="; ".join(gaps))]


def _director_identifiers(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    """ID-06: each KYC's DIN against the memorandum's, and the KYC PAN is an individual's."""
    moa = ctx.persons("memorandum_articles_of_association")
    kyc = ctx.persons("director_kyc")
    entity_pans = {str(v.value) for v in ctx.facts.identities.entity_pan}
    sides = [s for s in (
        _people_side("Memorandum and articles", moa, show=lambda e: f"{e.name} (DIN {e.din or '—'})",
                     sources=["memorandum_articles_of_association"]) if moa else None,
        _people_side("KYC received", kyc, show=lambda e: f"{e.name} (DIN {e.din or '—'}, PAN {e.pan or '—'})",
                     sources=["director_kyc"]) if kyc else None,
    ) if s]
    rows, problems, compared = [], [], 0
    for k in kyc:
        # The memorandum's entry for this director: the same name before a close one.
        m = next((moa[i] for i in _best_matches(ctx, k.name, moa)), None)
        issues = []
        if m and m.din and k.din:
            compared += 1
            if m.din != k.din:
                issues.append(f"DIN {k.din} on the KYC against {m.din} in the memorandum")
        if k.pan:
            compared += 1
            masked = re.fullmatch(r"[A-Z][X*]{4}\d{4}[A-Z]", k.pan) is not None   # a masked PAN does not show its fourth character
            if len(k.pan) == 10 and not masked and k.pan[3] != "P":
                issues.append(f"PAN {k.pan} is not an individual's PAN")
            elif k.pan in entity_pans:
                issues.append(f"PAN {k.pan} is the company's PAN")
        if issues:
            problems.append(f"{k.name}: {'; '.join(issues)}")
        rows.append((k.name, [m.din if m else None, k.din, k.pan], bool(issues)))
    detail = _rows(["DIN in the memorandum", "DIN on the KYC", "PAN on the KYC"], rows) if rows else None
    if not compared:
        return [_absent(ctx, rule, sides, note="No DIN or PAN is printed for the directors to compare.")]
    if problems:
        for s in sides:
            s.differs = True
        return [_finding(ctx, rule, "fail", sides, detail=detail, items="; ".join(problems))]
    return [_finding(ctx, rule, "pass", sides, detail=detail, note=f"Identifiers agree for {len(rows)} director(s).")]


def _memorandum_directors(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    """ID-08: the memorandum's directors are each accounted for by a KYC or the sourcing message."""
    moa = ctx.persons("memorandum_articles_of_association")
    kyc = ctx.persons("director_kyc")
    message = ctx.persons(CASE_RECORD) if CASE_RECORD in rule.sources else []
    sides = [s for s in (
        _people_side("Memorandum and articles", moa, sources=["memorandum_articles_of_association"]) if moa else None,
        _people_side("KYC received", kyc, sources=["director_kyc"]) if kyc else None,
        _people_side("Sourcing message", message, sources=[CASE_RECORD]) if message else None) if s]
    if not moa or not (kyc or message):
        return [_absent(ctx, rule, sides, note="Nothing to hold the memorandum's directors against.")]
    # A KYC or a name in the message accounts for the director it matches best: two directors with
    # similar names in the memorandum are two people, and one KYC does not account for both.
    with_kyc = {i for k in kyc for i in _best_matches(ctx, k.name, moa)}
    in_messages = {i for k in message for i in _best_matches(ctx, k.name, moa)}
    rows, unaccounted = [], []
    for i, e in enumerate(moa):
        in_kyc, in_message = i in with_kyc, i in in_messages
        if not (in_kyc or in_message):
            unaccounted.append(e.name)
        rows.append((e.name, [YES if in_kyc else NO, YES if in_message else NO], not (in_kyc or in_message)))
    detail = _rows(["KYC received", "Sourcing message"], rows)
    if unaccounted:
        sides[0].differs = True
        return [_finding(ctx, rule, "fail", sides, detail=detail, items=_join(unaccounted))]
    return [_finding(ctx, rule, "pass", sides, detail=detail, note=f"All {len(moa)} director(s) in the memorandum are on file.")]


NAME_PARTS = ("first", "middle", "last")
PART_CELLS = {"same": YES, None: "", "missing": "Missing", "initial": "Initial only", "different": "Different"}
PART_WORDS = {"missing": "missing", "initial": "only an initial", "different": "different"}


def _person_names(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    """ID-09: each person named by two or more sources, by the parts of their name. The people are
    matched as the other checks match them (names at least name_match alike), or by their parts
    where that misses (the same surname and a first name that is the same or its initial); this
    check then looks inside the match: a first, middle or last name missing in one source, given
    only as an initial, or written differently, against the fullest form of the name."""
    sets = sorted((p for p in ctx.facts.persons if p.source in rule.sources), key=lambda p: rule.sources.index(p.source))
    sides = [_people_side(p.label, p.entries, sources=[p.source]) for p in sets]
    groups = _people(ctx, sets, by_parts=True)
    named = [g for g in groups if len({p.source for p, _ in g}) >= 2]
    if not named:
        return [_absent(ctx, rule, sides, note="No person is named in two or more documents.")]
    rows, problems, differing = [], [], set()
    for group in named:
        full = max((e.name for _, e in group), key=lambda n: (len(name_parts(n).words()), len(n)))
        found: dict[tuple[str, str, str], list[str]] = {}
        for p, e in group:
            status = compare_name_parts(full, e.name)
            off = [part for part in NAME_PARTS if status[part] not in (None, "same")]
            for part in off:
                written = _part_word(e.name, part) if status[part] == "different" else ""
                found.setdefault((part, status[part], written), []).append(p.label)
            if off:
                differing.add(p.label)
            rows.append((full, [p.label, e.name, *[PART_CELLS[status[part]] for part in NAME_PARTS]], bool(off),
                         [2 + NAME_PARTS.index(part) for part in off]))
        if found:
            problems.append(f"{full}: " + "; ".join(
                f"{part} name {PART_WORDS[s]}{f' ({written})' if written else ''} in "
                + _join([f"the {_lower(label)}" for label in labels])
                for (part, s, written), labels in found.items()))
    for side in sides:
        side.differs = side.label in differing
    detail = _rows(["Document", "As written", "First name", "Middle name", "Last name"], rows)
    if problems:
        return [_finding(ctx, rule, "fail", sides, detail=detail, items="; ".join(problems))]
    return [_finding(ctx, rule, "pass", sides, detail=detail,
                     note=f"The names of {len(named)} person(s) agree in full across the documents.")]


def _part_word(name: str, part: str) -> str:
    parts = name_parts(name)
    return {"first": parts.first or "", "middle": " ".join(parts.middle), "last": parts.last or ""}[part]


def _incorporation(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    """ID-07: what the CIN encodes against the certificate's date and the case's constitution."""
    cins = sorted(ctx.facts.identities.cin, key=lambda v: (v.source != "certificate_of_incorporation", v.source == CASE_RECORD))
    cin = cins[0] if cins else None
    if cin is None:
        return [_absent(ctx, rule, note="No CIN is on file.")]
    number = str(cin.value)
    if not _CIN_RE.fullmatch(number):
        return [_finding(ctx, rule, "not_applicable", [_fact_side(cin, f"CIN ({cin.label})")],
                         note=f"The CIN {number} is not in the standard format.")]
    sides = [_fact_side(cin, f"CIN ({cin.label})")]
    rows: list[tuple[str, list, bool]] = []
    inc = ctx.facts.incorporation.date_of_incorporation
    when = parse_date(inc.value) if inc else None
    if inc and when:
        sides.append(_fact_side(inc, "Date of incorporation"))
        rows.append(("Year of incorporation", [number[8:12], str(when.year)], number[8:12] != str(when.year)))
    constitution = ctx.case.constitution
    if constitution in ctx.constitutions and constitution != "unknown":
        cls = number[12:15]
        label = ctx.constitutions[constitution]
        sides.append(_side("Constitution on the case", label, [], sources=["case.constitution"]))
        rows.append(("Company class", [f"{CIN_CLASSES.get(cls, cls)} ({cls})", label],
                     (constitution == "private_limited") != (cls == "PTC")))
        if constitution == "private_limited":
            rows.append(("Listing", ["Listed" if number[0] == "L" else "Unlisted", "Unlisted (private company)"],
                         number[0] == "L"))
    if not rows:
        return [_absent(ctx, rule, sides, note="Nothing on file to hold the CIN against.")]
    detail = _rows(["In the CIN", "On file"], rows)
    flagged = [r for r in rows if r[2]]
    if flagged:
        for s in sides:
            s.differs = True
        items = "; ".join(f"{r[0].lower()} {r[1][0]} in the CIN against {r[1][1]} on file" for r in flagged)
        return [_finding(ctx, rule, "fail", sides, detail=detail, items=items)]
    return [_finding(ctx, rule, "pass", sides, detail=detail, note=f"The CIN agrees with {len(rows)} particular(s) on file.")]


# --- Borrowing authority (BR-01 to BR-04) ---


def _resolution(ctx: Context, rule: CrossCheckRule, field: str):
    """The board resolution that states `field` (the highest limit, for BR-01), or None."""
    stating = [a for a in ctx.facts.authority if getattr(a, field)]
    if field == "borrowing_limit":
        return max(stating, key=lambda a: float(a.borrowing_limit.value or 0), default=None)
    return stating[0] if stating else None


def _borrowing_limit(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    if not ctx.facts.authority:
        return [_absent(ctx, rule, note="No board resolution is on file.")]
    requested = ctx.facts.requested_amount
    if requested is None or not requested.value:
        return [_finding(ctx, rule, "not_applicable", [], note="The case records no amount requested.")]
    a = _resolution(ctx, rule, "borrowing_limit")
    req_side = _fact_side(requested, "Amount requested")
    if a is None:
        return [_finding(ctx, rule, "incomplete", [req_side], note="The board resolution's borrowing limit could not be read.")]
    limit, amount = float(a.borrowing_limit.value), float(requested.value)
    fmt = dict(left=inr(limit), right=inr(amount))
    if limit >= amount:
        return [_finding(ctx, rule, "pass", [_fact_side(a.borrowing_limit, "Board resolution limit"), req_side],
                         note=f"The resolution's limit of {inr(limit)} covers the {inr(amount)} requested.", **fmt)]
    sides = [_fact_side(a.borrowing_limit, "Board resolution limit", differs=True), req_side]
    return [_finding(ctx, rule, "fail", sides, **fmt)]


def _signatories(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    if not ctx.facts.authority:
        return [_absent(ctx, rule, note="No board resolution is on file.")]
    signatories = [s for a in ctx.facts.authority for s in a.signatories]
    if not signatories:
        return [_finding(ctx, rule, "not_applicable", [], note="The board resolution names no authorised signatories.")]
    directors = ctx.persons("director_kyc", "memorandum_articles_of_association", CASE_RECORD)
    director_sources = [p.source for p in ctx.facts.persons
                        if p.source in ("director_kyc", "memorandum_articles_of_association", CASE_RECORD)]
    sig_side = _people_side("Authorised in the board resolution", signatories, sources=["board_resolution_borrowing"])
    if not directors:
        return [_absent(ctx, rule, [sig_side], note="No list of directors is on file to hold the signatories against.")]
    rows, outside = [], []
    for s in signatories:
        ok = any(ctx.same_person(s.name, d.name) for d in directors)
        if not ok:
            outside.append(s.name)
        rows.append((s.name, [YES if ok else NO], not ok))
    unique = list({normalise_name(d.name): d for d in directors}.values())
    sides = [sig_side, _people_side("Directors on file", unique, sources=director_sources)]
    detail = _rows(["Director on file"], rows)
    if outside:
        sides[0].differs = True
        return [_finding(ctx, rule, "fail", sides, detail=detail, items=_join(outside))]
    return [_finding(ctx, rule, "pass", sides, detail=detail, note=f"All {len(signatories)} signatories are directors on file.")]


def _resolution_lender(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    if not ctx.facts.authority:
        return [_absent(ctx, rule, note="No board resolution is on file.")]
    a = _resolution(ctx, rule, "lender")
    if a is None or not ctx.own_banks:
        return [_finding(ctx, rule, "not_applicable", [], note="The board resolution names no lender.")]
    lender = str(a.lender.value)
    ok = any(facts_module.same_entity(lender, own, ctx.noise, ctx.threshold) for own in ctx.own_banks)
    sides = [_fact_side(a.lender, "Lender named in the board resolution", differs=not ok),
             _side("This bank", ctx.own_banks[0], [], sources=["alignment.own_bank_names"])]
    if ok:
        return [_finding(ctx, rule, "pass", sides, note="The resolution is in favour of this bank.")]
    return [_finding(ctx, rule, "fail", sides, left=lender, right=ctx.own_banks[0])]


def _resolution_date(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    if not ctx.facts.authority:
        return [_absent(ctx, rule, note="No board resolution is on file.")]
    a = _resolution(ctx, rule, "resolution_date")
    when = parse_date(a.resolution_date.value) if a else None
    if a is None or when is None:
        return [_finding(ctx, rule, "not_applicable", [], note="The board resolution's date could not be read.")]
    inc_fact = ctx.facts.incorporation.date_of_incorporation
    incorporated = parse_date(inc_fact.value) if inc_fact else None
    sides = [_fact_side(a.resolution_date, "Board resolution dated")]
    if inc_fact:
        sides.append(_fact_side(inc_fact, "Date of incorporation"))
    sides.append(_side("Appraisal date", display_date(ctx.as_of), [], sources=["case.as_of"]))
    problems = []
    if incorporated and when < incorporated:
        problems.append(f"dated {display_date(when)}, before the company was incorporated on {display_date(incorporated)}")
    if when > ctx.as_of:
        problems.append(f"dated {display_date(when)}, after the appraisal date of {display_date(ctx.as_of)}")
    if problems:
        sides[0].differs = True
        return [_finding(ctx, rule, "fail", sides, items="; ".join(problems))]
    return [_finding(ctx, rule, "pass", sides, note=f"Dated {display_date(when)}, within the company's life on file.")]


# --- Turnover (TO-01 to TO-05) ---


FIGURE_SOURCES = {"financials": "audited_financial_statements", "gst": "gstr_3b", "bank": "bank_statement",
                  "declared": CASE_RECORD, "itr": "income_tax_return"}


def _figure_side(f: TurnoverFigure, differs: bool = False) -> FindingSide:
    return _side(f.label, f.value, f.evidence[:12], f.relies_on_manual, awaiting=f.awaiting_review, differs=differs,
                 field_ids=f.field_ids, sources=[FIGURE_SOURCES[f.source]])


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
            return [_absent(ctx, rule, note="Neither source is on file.")]
        y, lf, rf = present[0]
        have = lf or rf
        missing = _label(right_key) if lf else _label(left_key)
        return [_finding(ctx, rule, "incomplete", [_figure_side(have)], y.fy,
                         note=f"{missing} for {y.fy} is not on file.")]
    tol = ctx.tol(rule.tolerance, 10)
    return [_compare_year(ctx, rule, y, lf, rf, tol) for y, lf, rf in both]


def _compare_year(ctx: Context, rule: CrossCheckRule, y: TurnoverYear, lf: TurnoverFigure, rf: TurnoverFigure,
                  tol: float) -> Finding:
    """One financial year's two turnover figures: incomplete while a monthly figure lacks months of
    the year, else within the tolerance or not."""
    short = [f for f in (lf, rf) if f.months_covered is not None and f.months_covered < 12]
    if short:
        return _finding(ctx, rule, "incomplete", [_figure_side(lf), _figure_side(rf)], y.fy,
                        note=_months_short(ctx, short) + ".")
    a, b = float(lf.value or 0), float(rf.value or 0)
    variance = abs(a - b) / max(a, b) * 100 if max(a, b) else 0.0
    failed = variance > tol
    sides = [_figure_side(lf, failed), _figure_side(rf, failed)]
    # The right-hand label sits inside the sentence: "… against business credits in bank statements …".
    fmt = dict(period=y.fy, left=inr(a), right=inr(b), left_label=lf.label, right_label=_lower(rf.label),
               variance=f"{variance:.1f}%")
    if not failed:
        return _finding(ctx, rule, "pass", sides, y.fy,
                        note=f"Variance {variance:.1f}% within {ctx.tol_text(rule.tolerance)}.", **fmt)
    return _finding(ctx, rule, "fail", sides, y.fy, **fmt)


def _months_short(ctx: Context, short: list[TurnoverFigure]) -> str:
    """The months monthly figures lack, as runs: "GST outward supplies cover 7 of 12 months (Apr 2025
    to Aug 2025 not on file)". A month that has not ended by the appraisal date is not missing: it
    has not happened yet."""
    now = (ctx.as_of.year, ctx.as_of.month)
    gaps = []
    for i, f in enumerate(short):
        months = [m for m in (parse_period(label) for label in f.months_missing) if m]
        past = ranges_label([m for m in months if m < now])
        future = ranges_label([m for m in months if m >= now])
        absent = ", ".join(t for t in (past and f"{past} not on file", future and f"{future} not yet ended") if t)
        gaps.append(f"{f.label if i == 0 else _lower(f.label)} cover {f.months_covered} of 12 months"
                    + (f" ({absent})" if absent else ""))
    return "; ".join(gaps)


def _itr_turnover(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    """TX-03 to TX-05: the turnover each income tax return shows, against another source's turnover
    for the year the return covers (audited revenue, GST outward supplies or cleansed bank credits).
    The returns set the years: a return is filed after its year ends, so the latest year's figures
    have no return to meet yet. A return that shows no turnover leaves nothing to compare."""
    _, right_key = TURNOVER_PAIRS[rule.variable]
    filed = []
    for y in ctx.facts.turnover:
        by = {f.source: f for f in y.figures}
        if "itr" in by:
            filed.append((y, by["itr"], by.get(right_key)))
    if not filed:
        if ctx.facts.tax_years:
            return [_finding(ctx, rule, "not_applicable", [],
                             note="The income tax return on file does not show its turnover.")]
        if ITR in ctx.expected and ITR not in ctx.on_file:
            # The return is expected: the check waits for it (and any other source missing).
            return [_absent(ctx, rule, note="No income tax return is on file.")]
        # No return is expected: another source arriving would not complete the check.
        return [_finding(ctx, rule, "not_applicable", [], note="No income tax return is on file.")]
    compared = [(y, lf, rf) for y, lf, rf in filed if rf is not None]
    if not compared:
        # The other source does not reach the years the returns cover.
        years = _join([y.fy for y, _, _ in filed])
        return [_absent(ctx, rule, [_figure_side(filed[0][1])], filed[0][0].fy if len(filed) == 1 else "",
                        note=f"{_label(right_key)} for {years}, the year the income tax return covers, is not on file.")]
    tol = ctx.tol(rule.tolerance, 10)
    return [_compare_year(ctx, rule, y, lf, rf, tol) for y, lf, rf in compared]


def _label(source: str) -> str:
    return {
        "financials": "Audited turnover",
        "gst": "GST outward supplies",
        "bank": "Bank statements",
        "declared": "Declared turnover",
        "itr": "Turnover in the income tax return",
    }[source]


def _ym(month: str) -> tuple[int, int]:
    return int(month[:4]), int(month[5:7])


def _turnover_window(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    """TO-05: GST against cleansed bank credits over the months both cover, in any financial year."""
    months = ctx.facts.months
    gst = [m for m in months if m.gst is not None]
    bank = [m for m in months if m.bank is not None]
    if not gst or not bank:
        return [_absent(ctx, rule, note="Needs both GST returns and bank statements.")]
    both = [m for m in months if m.gst is not None and m.bank is not None]
    need = int(ctx.tol("turnover_window_min_months", 3))
    if len(both) < need:
        return [_finding(ctx, rule, "incomplete", [], note=(
            f"The GST returns ({ranges_label([_ym(m.month) for m in gst])}) and the bank statements "
            f"({ranges_label([_ym(m.month) for m in bank])}) share {len(both)} month(s); "
            f"at least {need} are needed to compare them."))]
    window = [_ym(m.month) for m in both]
    years = {facts_module.fy_of(y, mo, ctx.fy_start) for y, mo in window}
    whole_year = len(years) == 1 and window == facts_module.fy_months(years.pop(), ctx.fy_start)
    if whole_year and any(r.variable == "turnover_gst_vs_bank" for r in ctx.rules):
        # One whole financial year: TO-02 compares it.
        return [_finding(ctx, rule, "not_applicable", [], note="The months both cover are one financial year, compared above.")]
    scope = ranges_label(window)
    tol = ctx.tol(rule.tolerance, 10)
    g_total = sum(m.gst or 0 for m in both)
    b_total = sum(m.bank or 0 for m in both)
    variance = _variance(g_total, b_total)
    failed = variance > tol
    sides = [
        _side(f"GST outward supplies ({len(both)} returns)", g_total, [e for m in both for e in m.gst_evidence][:12],
              awaiting=any(m.awaiting_review for m in both), differs=failed, sources=["gstr_3b"]),
        _side("Business credits in bank statements", b_total, [e for m in both for e in m.bank_evidence][:12],
              differs=failed, sources=["bank_statement"]),
    ]
    detail = _rows(["GST outward supplies", "Business credits", "Difference"],
                   [(m.label, [m.gst, m.bank, f"{_variance(m.gst or 0, m.bank or 0):.1f}%"],
                     _variance(m.gst or 0, m.bank or 0) > tol) for m in both])
    fmt = dict(period=scope, left=inr(g_total), right=inr(b_total), left_label="GST outward supplies",
               right_label="business credits", variance=f"{variance:.1f}%")
    if failed:
        return [_finding(ctx, rule, "fail", sides, scope, detail=detail, **fmt)]
    return [_finding(ctx, rule, "pass", sides, scope, detail=detail,
                     note=f"Variance {variance:.1f}% over {len(both)} months, within {ctx.tol_text(rule.tolerance)}.", **fmt)]


# --- Tax: the income tax return against the books (TX-01, TX-02) ---


def _itr_years(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    years, tax = ctx.facts.financial_years, ctx.facts.tax_years
    if not years or not tax:
        return [_absent(ctx, rule, note="Needs audited statements and income tax returns.")]
    have = {t.fy for t in tax}
    due_days = int(ctx.tol("itr_due_days", 214))
    rows, missing = [], []
    for y in years:
        due = date.fromisoformat(y.fy_end) + timedelta(days=due_days)
        filed = y.fy in have
        if filed:
            state = YES
        elif due > ctx.as_of:
            state = f"Not yet due ({display_date(due)})"
        else:
            state = NO
            missing.append(y.fy)
        rows.append((y.fy, [state], state == NO))
    sides = [_side("Audited statements", ", ".join(y.fy for y in years), [], sources=["audited_financial_statements"]),
             _side("Income tax returns", ", ".join(f"AY {t.assessment_year}" for t in tax),
                   [e for t in tax for e in t.evidence[:1]], differs=bool(missing), sources=["income_tax_return"])]
    detail = _rows(["Return on file"], rows)
    if missing:
        return [_finding(ctx, rule, "fail", sides, detail=detail, items=_join(missing))]
    return [_finding(ctx, rule, "pass", sides, detail=detail, note="Every audited year that is due has its return on file.")]


def _itr_profit(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    tax = {t.fy: t for t in ctx.facts.tax_years}
    pairs = [(y, tax[y.fy]) for y in ctx.facts.financial_years if y.fy in tax]
    if not pairs:
        return [_absent(ctx, rule, note="No audited year has its income tax return on file.")]
    out = []
    tol = ctx.tol(rule.tolerance, 10)
    for y, t in pairs:
        book, filed = y.current.get("profit_before_tax"), t.lines.get("profit_before_tax")
        if not book or not filed:
            out.append(_finding(ctx, rule, "not_applicable", [], y.fy,
                                note="The return's computation does not print the profit as per the accounts."
                                if book else "The audited statements do not print profit before tax."))
            continue
        a, b = float(book.value or 0), float(filed.value or 0)
        variance = _variance(a, b)
        failed = variance > tol
        sides = [_fact_side(book, "Profit before tax, audited statements", differs=failed),
                 _fact_side(filed, "Profit as per accounts, income tax return", differs=failed)]
        fmt = dict(period=y.fy, left=inr(a), right=inr(b), variance=f"{variance:.1f}%")
        if failed:
            out.append(_finding(ctx, rule, "fail", sides, y.fy, **fmt))
        else:
            out.append(_finding(ctx, rule, "pass", sides, y.fy,
                                note=f"Variance {variance:.1f}% within {ctx.tol_text(rule.tolerance)}.", **fmt))
    return out


# --- Statements against each other and the bank (FS-01, FS-02) ---


def _previous_year(years: list[FinancialYear], year: FinancialYear) -> FinancialYear | None:
    end = date.fromisoformat(year.fy_end)
    return next((y for y in years if date.fromisoformat(y.fy_end).year == end.year - 1), None)


def _comparatives(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    years = ctx.facts.financial_years
    pairs = [(y, p) for y in years if (p := _previous_year(years, y))]
    if not pairs:
        return [_absent(ctx, rule, note="Fewer than two consecutive years of audited statements are on file.")]
    out = []
    tol = ctx.tol(rule.tolerance, 1)
    for y, p in pairs:
        rows, flagged = [], []
        for key, label in LINE_LABELS.items():
            shown, filed = y.previous.get(key), p.current.get(key)
            if not (shown and filed):
                continue
            variance = _variance(float(shown.value or 0), float(filed.value or 0))
            bad = variance > tol
            rows.append((label, [shown.value, filed.value, f"{variance:.1f}%"], bad))
            if bad:
                flagged.append((label, shown, filed))
        if not rows:
            out.append(_finding(ctx, rule, "not_applicable", [], y.fy, note="No line is printed in both years."))
            continue
        detail = _rows([f"{p.fy} as shown in {y.fy}", f"{p.fy} statements", "Difference"], rows)
        first = flagged[0] if flagged else next(((k, y.previous[key], p.current[key]) for key, k in LINE_LABELS.items()
                                                  if key in y.previous and key in p.current))
        sides = [_fact_side(first[1], f"{first[0]}, {p.fy} column of the {y.fy} statements", differs=bool(flagged)),
                 _fact_side(first[2], f"{first[0]}, {p.fy} statements", differs=bool(flagged))]
        if flagged:
            items = "; ".join(f"{_lower(label)} {inr(float(s.value or 0))} against {inr(float(f.value or 0))}"
                              for label, s, f in flagged)
            out.append(_finding(ctx, rule, "fail", sides, y.fy, detail=detail, period=p.fy, items=items))
        else:
            out.append(_finding(ctx, rule, "pass", sides, y.fy, detail=detail,
                                note=f"The {p.fy} figures agree with that year's audited statements."))
    return out


def _year_end_balance(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    years = ctx.facts.financial_years
    if not years or "bank_statement" not in ctx.on_file:
        return [_absent(ctx, rule, note="Needs audited statements and bank statements.")]
    latest = years[0]
    end = date.fromisoformat(latest.fy_end)
    balances = [b for b in ctx.facts.balances if b.date == latest.fy_end]
    if not balances:
        return [_finding(ctx, rule, "not_applicable", [], latest.fy,
                         note=f"The bank statements on file do not cover {display_date(end)}.")]
    audited = latest.current.get("cash_and_bank_balances")
    if audited is None:
        return [_finding(ctx, rule, "not_applicable", [], latest.fy,
                         note="The audited balance sheet does not print cash and bank balances.")]
    total = sum(b.balance for b in balances)
    limit = float(audited.value or 0) * (1 + ctx.tol(rule.tolerance, 1) / 100)
    failed = total > limit
    sides = [_side(f"Bank balances on {display_date(end)} ({len(balances)} account(s))", total,
                   [e for b in balances for e in b.evidence[:1]], differs=failed, sources=["bank_statement"]),
             _fact_side(audited, f"Cash and bank balances, {latest.fy} balance sheet")]
    detail = _rows(["Balance"], [(b.account, [b.balance], False) for b in balances])
    fmt = dict(period=display_date(end), left=inr(total), right=inr(float(audited.value or 0)))
    if failed:
        return [_finding(ctx, rule, "fail", sides, latest.fy, detail=detail, **fmt)]
    return [_finding(ctx, rule, "pass", sides, latest.fy, detail=detail,
                     note=f"The statements' balances ({inr(total)}) are within the audited figure.", **fmt)]


# --- Bank accounts (BA-01, BA-02) ---


def _declared_accounts(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    declared = [a for a in ctx.facts.accounts if a.declared]
    if not declared:
        note = ("The sourcing message names no account numbers." if ctx.facts.declared_banking
                else "No accounts were declared in the sourcing message.")
        return [_finding(ctx, rule, "not_applicable", [], note=note)]
    without = [a for a in declared if not a.has_statement]
    sides = [_declared_accounts_side(ctx, declared), _statements_side(ctx, differs=bool(without))]
    detail = _rows(["Statement on file"], [(a.label, [YES if a.has_statement else NO], not a.has_statement) for a in declared])
    if without:
        return [_finding(ctx, rule, "fail", sides, detail=detail, items=_join([a.label for a in without]))]
    return [_finding(ctx, rule, "pass", sides, detail=detail, note=f"All {len(declared)} declared account(s) have statements.")]


def _declared_accounts_side(ctx: Context, declared: list) -> FindingSide:
    """The accounts declared, and where: the declaration of existing facilities, the sourcing message."""
    message = ctx.facts.declared_banking
    by_declaration = any(ctx.type_names[DECLARATION] in a.sources for a in declared)
    if message and not by_declaration:
        return _fact_side(message, "Declared in the sourcing message")
    return _side("Declared accounts", ", ".join(a.label for a in declared) or None,
                 [e for a in declared for e in a.evidence[:1]],
                 sources=[DECLARATION] + ([CASE_RECORD] if message else []))


def _statements_side(ctx: Context, *, differs: bool = False) -> FindingSide:
    statements = [a for a in ctx.facts.accounts if a.has_statement]
    return _side("Statements on file", ", ".join(a.label for a in statements) or None,
                 [e for a in statements for e in a.evidence[:1]], differs=differs, sources=["bank_statement"])


def _evidenced_accounts(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    """BA-02: every account on file is declared. An account seen only in transfers is flagged; so is
    an account with a statement that was not declared, once the RM or a declaration declared accounts."""
    accounts = ctx.facts.accounts
    if "bank_statement" not in ctx.on_file and not accounts:
        return [_absent(ctx, rule, note="No bank statements are on file.")]
    declared = [a for a in accounts if a.declared]
    in_transfers = [a for a in accounts if not a.has_statement and not a.declared]
    undeclared = [a for a in accounts if a.has_statement and not a.declared] if declared else []
    flagged = {a.label for a in in_transfers + undeclared}
    sides = ([_declared_accounts_side(ctx, declared)] if declared else []) + [_statements_side(ctx, differs=bool(undeclared))]
    if in_transfers:
        sides.append(_side("Seen in transfers", ", ".join(a.label for a in in_transfers),
                           [e for a in in_transfers for e in a.evidence[:1]], differs=True, sources=["bank_statement"]))
    detail = _rows(["Declared", "Statement on file", "Where it appears"],
                   [(a.label, [YES if a.declared else NO, YES if a.has_statement else NO, "; ".join(a.sources)], a.label in flagged)
                    for a in accounts])
    if not flagged:
        note = ("Every account on file is declared." if declared
                else "No account other than those with statements appears in the documents, and none was declared.")
        return [_finding(ctx, rule, "pass", sides, detail=detail, note=note)]
    items = [f"{a.label} has a statement but was not declared" for a in undeclared]
    items += [f"{a.label} appears in transfers but has no statement and was not declared" for a in in_transfers]
    return [_finding(ctx, rule, "fail", sides, detail=detail, items="; ".join(items),
                     accounts=_join([a.label for a in undeclared + in_transfers]))]


# --- Obligations (OB-02, OB-03) ---


def _mentions(text: str, lender: str, noise: list[str], threshold: float) -> bool:
    """Whether a declaration names the lender: a significant word of its name, or a close match."""
    words = normalise_name(text).split()
    resolved = facts_module.resolve_name(lender, noise).split()
    if any(len(w) >= 3 and w in words for w in resolved[:1]):
        return True
    span = len(resolved)
    return any(similarity(" ".join(resolved), " ".join(words[i:i + span])) >= threshold for i in range(len(words)))


def _same_lender(a: str, b: str, ctx: Context) -> bool:
    """One lender under two printings ("Tidewater Finance Limited", "TIDEWATER FIN"): the same
    resolved name, or the same leading significant word."""
    return facts_module.same_lender(a, b, ctx.noise, ctx.threshold)


def _emis_declared(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    if "bank_statement" not in ctx.on_file:
        return [_absent(ctx, rule, note="No bank statements are on file.")]
    obligations = ctx.facts.obligations
    if not obligations:
        return [_finding(ctx, rule, "pass", [], note="No regular instalments to a lender appear in the statements.")]
    message = ctx.facts.declared_banking
    text = str(message.value) if message and message.value else ""
    declaration = ctx.facts.declaration
    declared_lenders = [f.lender for f in ctx.facts.facilities if f.source == DECLARATION]

    def line(o) -> str:
        return f"{o.lender} ({inr(o.typical_amount)} a month in {len(o.months)} months, {o.account})"

    emi_side = _side("Instalments in bank statements", "; ".join(f"{o.lender} ({inr(o.typical_amount)} × {o.debits})" for o in obligations),
                     [e for o in obligations for e in o.evidence[:1]], sources=["bank_statement"])
    if not text and declaration is None:
        # A lender whose sanction letter is on file needs no confirmation of its facility, only the declaration.
        sanctioned = [f.lender for f in ctx.facts.facilities if f.source == SANCTION]
        unconfirmed = [o for o in obligations if not any(_same_lender(o.lender, s, ctx) for s in sanctioned)]
        none = "No declaration of existing facilities is on file and the sourcing message declares none"
        note = (f"{none}; confirm the facility behind {_join([line(o) for o in unconfirmed])}." if unconfirmed else
                f"{none}, so the instalments to {_join([line(o) for o in obligations])} cannot be held against one.")
        return [_finding(ctx, rule, "incomplete", [emi_side], note=note)]
    rows, undeclared = [], []
    for o in obligations:
        ok = (any(_same_lender(o.lender, lender, ctx) for lender in declared_lenders)
              or bool(text and _mentions(text, o.lender, ctx.noise, ctx.threshold)))
        if not ok:
            undeclared.append(o)
        rows.append((o.lender, [o.account, o.typical_amount, len(o.months), YES if ok else NO], not ok))
    detail = _rows(["Account", "Monthly instalment", "Months", "Declared"], rows)
    emi_side.differs = bool(undeclared)
    sides = [emi_side]
    if declaration is not None:
        sides.append(_fact_side(declaration, "Declaration of existing facilities"))
    if text:
        sides.append(_fact_side(message, "Declared in the sourcing message"))
    if undeclared:
        return [_finding(ctx, rule, "fail", sides, detail=detail, items="; ".join(line(o) for o in undeclared),
                         lenders=_join([o.lender for o in undeclared]))]
    return [_finding(ctx, rule, "pass", sides, detail=detail, note="Every lender paid by instalment is declared.")]


def _facility_side(label: str, facilities: list, *, differs: bool = False, empty: str = "None",
                   source: str | None = None) -> FindingSide:
    return _side(label, "; ".join(f"{f.lender} {inr(f.amount)}" if f.amount else f.lender for f in facilities) or empty,
                 [e for f in facilities for e in f.evidence[:1]][:6], any(f.relies_on_manual for f in facilities),
                 awaiting=any(f.awaiting_review for f in facilities), differs=differs,
                 sources=[source] if source else [f.source for f in facilities])


def _facilities_reconcile(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    """OB-01: each existing facility, by lender, in the declaration (or the sourcing message), the
    sanction letters and the commercial bureau report, with the sanctioned amounts within tolerance."""
    facilities = ctx.facts.facilities
    declared = [f for f in facilities if f.source == DECLARATION]
    sanctioned = [f for f in facilities if f.source == SANCTION]
    reported = [f for f in facilities if f.source == BUREAU]
    message = ctx.facts.declared_banking
    text = str(message.value) if message and message.value else ""
    declaration = ctx.facts.declaration
    evidence_on_file = [t for t in (SANCTION, BUREAU) if t in ctx.on_file]
    if declaration is None and not text and not evidence_on_file:
        return [_finding(ctx, rule, "not_applicable", [],
                         note="No existing facilities are declared, and no sanction letter or bureau report is on file.")]
    if declaration is None and not text:
        name = ctx.type_names[DECLARATION]
        sides = [_facility_side("Sanction letters", sanctioned, source=SANCTION)] if SANCTION in ctx.on_file else []
        sides += [_facility_side(ctx.type_names[BUREAU], reported, source=BUREAU)] if BUREAU in ctx.on_file else []
        return [_finding(ctx, rule, "incomplete", sides, missing=[name],
                         note=f"The facilities on file cannot be held against a declaration: the {_lower(name)} "
                              "is not on file.")]
    declared_side = (_fact_side(declaration, "Declaration of existing facilities") if declaration is not None
                     else _fact_side(message, "Declared in the sourcing message"))
    if not evidence_on_file:
        names = [ctx.type_names[SANCTION], ctx.type_names[BUREAU]]
        return [_finding(ctx, rule, "incomplete", [declared_side], missing=names,
                         note=f"Nothing to reconcile the declared facilities against: {_join([_lower(n) for n in names])} "
                              "not on file.")]

    groups: list[list] = []
    for f in declared + sanctioned + reported:
        for g in groups:
            if _same_lender(f.lender, g[0].lender, ctx):
                g.append(f)
                break
        else:
            groups.append([f])

    def total(rows: list) -> float | None:
        amounts = [f.amount for f in rows if f.amount is not None]
        return sum(amounts) if amounts else None

    tol = ctx.tol(rule.tolerance, 5)
    issues, rows, odd = [], [], set()
    for g in groups:
        lender = g[0].lender
        d = [f for f in g if f.source == DECLARATION]
        s = [f for f in g if f.source == SANCTION]
        b = [f for f in g if f.source == BUREAU]
        in_message = bool(text) and _mentions(text, lender, ctx.noise, ctx.threshold)
        problems = []
        if (s or b) and not (d or in_message):
            problems.append("not declared")
            odd.add(DECLARATION)
        if d and not (s or b):
            problems.append("declared, but neither a sanction letter nor the bureau report shows it"
                            if BUREAU in ctx.on_file else "declared, but no sanction letter is on file")
            odd |= {SANCTION, BUREAU}
        amounts = {k: v for k, v in (("declared", total(d)), ("sanction letter", total(s)), ("bureau", total(b))) if v is not None}
        if len(amounts) >= 2 and max(_variance(x, y) for x in amounts.values() for y in amounts.values()) > tol:
            problems.append("sanctioned amounts differ: " + ", ".join(f"{k} {inr(v)}" for k, v in amounts.items()))
            odd |= {DECLARATION, SANCTION, BUREAU}
        declared_cell = total(d) if d and total(d) is not None else (YES if d or in_message else NO)
        outstanding = sum(f.outstanding for f in b if f.outstanding is not None) if any(f.outstanding is not None for f in b) else None
        rows.append((lender, [declared_cell, total(s) if s else NO, total(b) if b else NO, outstanding], bool(problems)))
        if problems:
            issues.append(f"{lender}: {'; '.join(problems)}")
    sides = [declared_side if declaration is None else _facility_side(
                 "Declaration of existing facilities", declared, empty="None declared",
                 differs=DECLARATION in odd and bool(issues), source=DECLARATION)]
    if declaration is not None and not declared:
        sides[0] = _fact_side(declaration, "Declaration of existing facilities", differs=DECLARATION in odd and bool(issues))
    if SANCTION in ctx.on_file:
        sides.append(_facility_side("Sanction letters", sanctioned, differs=SANCTION in odd and bool(issues), source=SANCTION))
    if BUREAU in ctx.on_file:
        sides.append(_facility_side(ctx.type_names[BUREAU], reported, differs=BUREAU in odd and bool(issues), source=BUREAU))
    detail = _rows(["Declared", "Sanction letter", "Bureau", "Bureau outstanding"], rows)
    if issues:
        flagged = [r[0] for r in rows if r[2]]
        return [_finding(ctx, rule, "fail", sides, detail=detail, items="; ".join(issues), lenders=_join(flagged))]
    return [_finding(ctx, rule, "pass", sides, detail=detail,
                     note=(f"The facility agrees" if len(groups) == 1 else f"The {len(groups)} facilities agree")
                     + " across the declaration, the sanction letters and the bureau report.")]


def _borrowings_serviced(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    years = ctx.facts.financial_years
    if not years or "bank_statement" not in ctx.on_file:
        return [_absent(ctx, rule, note="Needs audited statements and bank statements.")]
    latest = years[0]
    borrowings = latest.current.get("long_term_borrowings")
    if borrowings is None:
        return [_finding(ctx, rule, "not_applicable", [], latest.fy,
                         note="The latest audited balance sheet does not print long-term borrowings.")]
    obligations = ctx.facts.obligations
    monthly = sum(o.typical_amount for o in obligations)
    amount = float(borrowings.value or 0)
    emi_side = _side("Instalments in bank statements",
                     "; ".join(f"{o.lender} ({inr(o.typical_amount)} a month)" for o in obligations) or "None found",
                     [e for o in obligations for e in o.evidence[:1]], sources=["bank_statement"])
    sides = [_fact_side(borrowings, f"Long-term borrowings, {latest.fy} balance sheet"), emi_side]
    fmt = dict(period=latest.fy, left=inr(amount), right=inr(monthly))
    if amount > 0 and not obligations:
        sides[1].differs = True
        return [_finding(ctx, rule, "fail", sides, latest.fy, items=(
            f"The {latest.fy} balance sheet shows long-term borrowings of {inr(amount)}, "
            "but no instalments appear in the bank statements."), **fmt)]
    if amount <= 0 and obligations:
        sides[0].differs = True
        return [_finding(ctx, rule, "fail", sides, latest.fy, items=(
            f"Instalments of {inr(monthly)} a month appear in the bank statements, "
            f"but the {latest.fy} balance sheet shows no long-term borrowings."), **fmt)]
    note = ("The borrowings in the books are serviced in the bank statements." if obligations
            else "No long-term borrowings and no instalments.")
    return [_finding(ctx, rule, "pass", sides, latest.fy, note=note, **fmt)]


EVALUATORS: dict[str, Callable[[Context, CrossCheckRule], list[Finding]]] = {
    "entity_pan": _identity,
    "gstin": _identity,
    "legal_name": _identity,
    "cin": _identity,
    "promoter_set": _promoter_set,
    "director_identifiers": _director_identifiers,
    "incorporation_particulars": _incorporation,
    "memorandum_directors": _memorandum_directors,
    "person_names": _person_names,
    "borrowing_limit": _borrowing_limit,
    "signatories_are_directors": _signatories,
    "resolution_lender": _resolution_lender,
    "resolution_date": _resolution_date,
    **{v: _turnover for v in TURNOVER_PAIRS},
    "turnover_itr_vs_audited": _itr_turnover,
    "turnover_itr_vs_gst": _itr_turnover,
    "turnover_itr_vs_bank": _itr_turnover,
    "turnover_gst_vs_bank_window": _turnover_window,
    "itr_years": _itr_years,
    "itr_profit": _itr_profit,
    "comparatives": _comparatives,
    "year_end_balance": _year_end_balance,
    "declared_accounts_with_statements": _declared_accounts,
    "evidenced_accounts_declared": _evidenced_accounts,
    "facilities_reconcile": _facilities_reconcile,
    "emis_to_declared_lenders": _emis_declared,
    "borrowings_serviced": _borrowings_serviced,
}


def evaluate(root: Path, case: CaseDetail, facts: CaseFacts) -> list[Finding]:
    from . import xv_cards

    ctx = Context(root, case, facts)
    out: list[Finding] = []
    for rule in ctx.rules:
        evaluator = EVALUATORS.get(rule.variable)
        if evaluator is not None:
            found = evaluator(ctx, rule)
            for f in found:
                xv_cards.enrich(ctx, rule, f)
            out.extend(found)
    return out


CARD_FIELDS = {"ref", "finding_title", "compares", "policy_ref", "columns", "gaps", "gap_tolerance", "mismatch",
               "reference", "amount", "request", "highlights"}


def run(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> list[Finding]:
    """Evaluate every rule switched on and replace the case's findings. A failure
    raises a finding review item (F-17.4); an open item whose finding no longer
    fails, or whose rule was switched off, is withdrawn. Decided items stay, as
    the record of the decision. An escalation to the Credit Manager outlives a
    withdrawn item (engine/review_items.py): the item raised when the discrepancy
    fails again carries it, so it is still the Credit Manager's to decide."""
    from . import xv
    from .review_items import unresolved_escalations

    found = evaluate(root, case, facts_module.compute(conn, root, case))
    failing = {f"finding:{f.id}" for f in found if f.outcome == "fail"}
    with transaction(conn):
        rules = reader.load_crosschecks(root).enabled_rules
        xv.assign_refs(conn, case.id, found, rules)
        xv.record_run(conn, case.id, found, rules, [t.id for t in reader.load_document_types(root).types])
        escalated = unresolved_escalations(conn, case.id)
        conn.execute("DELETE FROM findings WHERE case_id = ?", (case.id,))
        for f in found:
            conn.execute(
                """INSERT INTO findings (id, case_id, rule_id, title, outcome, severity, blocking, explanation, sides,
                   tolerance, config_version, run_id, query, area, scope, detail, missing, card)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f.id, case.id, f.rule_id, f.title, f.outcome, f.severity, int(f.blocking), f.explanation,
                 dumps([s.model_dump() for s in f.sides]), f.tolerance, f.config_version, f.run_id, f.query,
                 f.area, f.scope, dumps(f.detail.model_dump()) if f.detail else None, dumps(f.missing),
                 dumps(f.model_dump(mode="json", include=CARD_FIELDS))),
            )
            if f.outcome == "fail":
                detail: dict = {"finding_id": f.id, "rule_id": f.rule_id}
                # Raised again after a run withdrew it: still with the Credit Manager. An item that
                # is still there (open or decided) is left as it is.
                escalation = escalated.get((f.rule_id, f.scope or ""))
                if escalation:
                    detail["escalation"] = escalation
                raise_item(conn, case_id=case.id, kind="finding", ref=f"finding:{f.id}",
                           summary=f"{f.rule_id} {f.title}: {f.explanation}", detail=detail)
        for row in conn.execute(
            "SELECT id, ref FROM review_items WHERE case_id = ? AND kind = 'finding' AND status = 'open'", (case.id,)
        ).fetchall():
            if row["ref"] not in failing:
                conn.execute("DELETE FROM review_items WHERE id = ?", (row["id"],))
    return found
