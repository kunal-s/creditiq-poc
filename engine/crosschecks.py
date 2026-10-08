"""Cross-checks across the nine document types (FRD F-19; docs/cross-verification-plan.md).

Each configured rule (config/crosschecks.yaml) compares one aligned fact
(engine/facts.py) across its sources. The outcome is pass, fail, incomplete
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
    TurnoverFigure,
)
from .db import transaction
from .names import normalise_name, similarity
from .review_items import raise_item
from .util import display_date, dumps, parse_date, ranges_label, stable_id

inr = facts_module.inr

TURNOVER_PAIRS = {
    "turnover_audited_vs_gst": ("financials", "gst"),
    "turnover_gst_vs_bank": ("gst", "bank"),
    "turnover_audited_vs_bank": ("financials", "bank"),
    "turnover_declared_vs_evidenced": ("declared", "financials"),
}

# Not a document a person uploads: the case's own record of the sourcing message.
CASE_RECORD = "application_message"
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
        self.rules = reader.load_crosschecks(root).rules
        types = reader.load_document_types(root).types
        self.type_names = {t.id: t.name for t in types}
        self.type_names[CASE_RECORD] = "Sourcing message"
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
             **fmt: str) -> Finding:
    waiting = list(dict.fromkeys(s.label for s in sides if s.awaiting_review))
    if waiting and outcome in ("pass", "fail"):
        # F-17.2: a value below its threshold is reviewed before a check relies on it.
        outcome = "incomplete"
        note = f"Waiting for review of {', '.join(waiting)}; confirm or correct the value to complete this check."
    values = _Fmt(fmt)
    values.setdefault("tolerance", ctx.tol_text(rule.tolerance) or "")
    explanation = rule.explanation.format_map(values) if outcome == "fail" else note
    title = f"{rule.title} · {scope}" if scope else rule.title
    return Finding(
        id=stable_id("FND", ctx.case.id, rule.id, scope),
        case_id=ctx.case.id,
        rule_id=rule.id,
        title=title,
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
        return _finding(ctx, rule, "incomplete", sides or [], scope, note=f"{_join(missing)} not on file.",
                        missing=missing)
    return _finding(ctx, rule, "not_applicable", sides or [], scope, note=note)


def _side(label: str, value: str | float | None, evidence: list[Evidence], manual: bool = False, *,
          awaiting: bool = False, differs: bool = False, field_ids: list[str] | None = None) -> FindingSide:
    return FindingSide(label=label, value=value, evidence=evidence, relies_on_manual=manual,
                       awaiting_review=awaiting, differs=differs, field_ids=field_ids or [])


def _fact_side(v: FactValue, label: str | None = None, *, differs: bool = False) -> FindingSide:
    return _side(label or v.label, v.value, v.evidence[:1], v.relies_on_manual, awaiting=v.awaiting_review,
                 differs=differs, field_ids=v.field_ids)


def _people_side(label: str, people: list[PersonEntry], *, differs: bool = False, show: Callable[[PersonEntry], str] | None = None) -> FindingSide:
    return _side(label, "; ".join((show or (lambda e: e.name))(e) for e in people) or None,
                 [ev for e in people for ev in e.evidence[:1]][:6], any(e.relies_on_manual for e in people),
                 awaiting=any(e.awaiting_review for e in people), differs=differs)


def _join(items: list[str]) -> str:
    items = list(dict.fromkeys(items))
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _variance(a: float, b: float) -> float:
    top = max(abs(a), abs(b))
    return abs(a - b) / top * 100 if top else 0.0


def _rows(columns: list[str], rows: list[tuple[str, list, bool]]) -> FindingDetail:
    return FindingDetail(columns=columns, rows=[FindingDetailRow(label=r[0], cells=r[1], flagged=r[2]) for r in rows])


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
        )
        for g in groups
    ]
    if len({(v.source, v.label, str(v.value)) for v in values}) < 2:
        return [_absent(ctx, rule, sides)]
    if len(groups) == 1:
        return [_finding(ctx, rule, "pass", sides, note=f"Consistent across {len(values)} sources.")]
    items = " · ".join(f"{s.value} ({s.label})" for s in sides)
    return [_finding(ctx, rule, "fail", sides, items=items)]


# --- People (ID-04, ID-06, ID-08) ---


def _promoter_set(ctx: Context, rule: CrossCheckRule) -> list[Finding]:
    # In the rule's order of sources, so the result does not depend on the order documents arrived in.
    sets = sorted((p for p in ctx.facts.persons if p.source in rule.sources), key=lambda p: rule.sources.index(p.source))
    if len(sets) < 2:
        return [_absent(ctx, rule, [_people_side(p.label, p.entries) for p in sets],
                        note="Fewer than two sources name the promoters.")]
    people: list[str] = []
    for p in sets:
        for name in p.names:
            if not any(ctx.same_person(name, q) for q in people):
                people.append(name)
    gaps, rows, short = [], [], set()
    for person in people:
        named = [any(ctx.same_person(person, n) for n in p.names) for p in sets]
        absent = [p.label for p, ok in zip(sets, named) if not ok]
        short |= set(absent)
        if absent:
            gaps.append(f"{person} is not in {', '.join(absent)}")
        rows.append((person, [YES if ok else NO for ok in named], bool(absent)))
    sides = [_people_side(p.label, p.entries, differs=p.label in short) for p in sets]
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
        _people_side("Memorandum and articles", moa, show=lambda e: f"{e.name} (DIN {e.din or '—'})") if moa else None,
        _people_side("KYC received", kyc, show=lambda e: f"{e.name} (DIN {e.din or '—'}, PAN {e.pan or '—'})") if kyc else None,
    ) if s]
    rows, problems, compared = [], [], 0
    for k in kyc:
        m = next((e for e in moa if ctx.same_person(k.name, e.name)), None)
        issues = []
        if m and m.din and k.din:
            compared += 1
            if m.din != k.din:
                issues.append(f"DIN {k.din} on the KYC against {m.din} in the memorandum")
        if k.pan:
            compared += 1
            if len(k.pan) == 10 and k.pan[3] != "P":
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
    sides = [s for s in (_people_side("Memorandum and articles", moa) if moa else None,
                         _people_side("KYC received", kyc) if kyc else None,
                         _people_side("Sourcing message", message) if message else None) if s]
    if not moa or not (kyc or message):
        return [_absent(ctx, rule, sides, note="Nothing to hold the memorandum's directors against.")]
    rows, unaccounted = [], []
    for e in moa:
        in_kyc = any(ctx.same_person(e.name, k.name) for k in kyc)
        in_message = any(ctx.same_person(e.name, k.name) for k in message)
        if not (in_kyc or in_message):
            unaccounted.append(e.name)
        rows.append((e.name, [YES if in_kyc else NO, YES if in_message else NO], not (in_kyc or in_message)))
    detail = _rows(["KYC received", "Sourcing message"], rows)
    if unaccounted:
        sides[0].differs = True
        return [_finding(ctx, rule, "fail", sides, detail=detail, items=_join(unaccounted))]
    return [_finding(ctx, rule, "pass", sides, detail=detail, note=f"All {len(moa)} director(s) in the memorandum are on file.")]


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
        sides.append(_side("Constitution on the case", label, []))
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
    sig_side = _people_side("Authorised in the board resolution", signatories)
    if not directors:
        return [_absent(ctx, rule, [sig_side], note="No list of directors is on file to hold the signatories against.")]
    rows, outside = [], []
    for s in signatories:
        ok = any(ctx.same_person(s.name, d.name) for d in directors)
        if not ok:
            outside.append(s.name)
        rows.append((s.name, [YES if ok else NO], not ok))
    unique = list({normalise_name(d.name): d for d in directors}.values())
    sides = [sig_side, _people_side("Directors on file", unique)]
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
             _side("This bank", ctx.own_banks[0], [])]
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
    sides.append(_side("Appraisal date", display_date(ctx.as_of), []))
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


def _figure_side(f: TurnoverFigure, differs: bool = False) -> FindingSide:
    return _side(f.label, f.value, f.evidence[:12], f.relies_on_manual, awaiting=f.awaiting_review, differs=differs,
                 field_ids=f.field_ids)


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
    out = []
    tol = ctx.tol(rule.tolerance, 10)
    for y, lf, rf in both:
        gaps = [f"{f.label} covers {f.months_covered} of 12 months ({', '.join(f.months_missing[:3])}"
                f"{'…' if len(f.months_missing) > 3 else ''} absent)"
                for f in (lf, rf) if f.months_covered is not None and f.months_covered < 12]
        if gaps:
            out.append(_finding(ctx, rule, "incomplete", [_figure_side(lf), _figure_side(rf)], y.fy,
                                note="; ".join(gaps) + "."))
            continue
        a, b = float(lf.value or 0), float(rf.value or 0)
        variance = abs(a - b) / max(a, b) * 100 if max(a, b) else 0.0
        failed = variance > tol
        sides = [_figure_side(lf, failed), _figure_side(rf, failed)]
        fmt = dict(period=y.fy, left=inr(a), right=inr(b), left_label=lf.label, right_label=rf.label,
                   variance=f"{variance:.1f}%")
        if not failed:
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
              awaiting=any(m.awaiting_review for m in both), differs=failed),
        _side("Business credits in bank statements", b_total, [e for m in both for e in m.bank_evidence][:12],
              differs=failed),
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
    sides = [_side("Audited statements", ", ".join(y.fy for y in years), []),
             _side("Income tax returns", ", ".join(f"AY {t.assessment_year}" for t in tax),
                   [e for t in tax for e in t.evidence[:1]], differs=bool(missing))]
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
            items = "; ".join(f"{label} {inr(float(s.value or 0))} against {inr(float(f.value or 0))}" for label, s, f in flagged)
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
                   [e for b in balances for e in b.evidence[:1]], differs=failed),
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
                 [e for a in declared for e in a.evidence[:1]])


def _statements_side(ctx: Context, *, differs: bool = False) -> FindingSide:
    statements = [a for a in ctx.facts.accounts if a.has_statement]
    return _side("Statements on file", ", ".join(a.label for a in statements) or None,
                 [e for a in statements for e in a.evidence[:1]], differs=differs)


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
                           [e for a in in_transfers for e in a.evidence[:1]], differs=True))
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
    if facts_module.same_entity(a, b, ctx.noise, ctx.threshold):
        return True
    ra, rb = facts_module.resolve_name(a, ctx.noise).split(), facts_module.resolve_name(b, ctx.noise).split()
    return bool(ra and rb) and ra[0] == rb[0] and len(ra[0]) >= 4


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
                     [e for o in obligations for e in o.evidence[:1]])
    if not text and declaration is None:
        return [_finding(ctx, rule, "incomplete", [emi_side],
                         note=f"No declaration of existing facilities is on file and the sourcing message declares none; "
                              f"confirm the facility behind {_join([line(o) for o in obligations])}.")]
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


def _facility_side(label: str, facilities: list, *, differs: bool = False, empty: str = "None") -> FindingSide:
    return _side(label, "; ".join(f"{f.lender} {inr(f.amount)}" if f.amount else f.lender for f in facilities) or empty,
                 [e for f in facilities for e in f.evidence[:1]][:6], any(f.relies_on_manual for f in facilities),
                 awaiting=any(f.awaiting_review for f in facilities), differs=differs)


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
        sides = [_facility_side("Sanction letters", sanctioned)] if SANCTION in ctx.on_file else []
        sides += [_facility_side(ctx.type_names[BUREAU], reported)] if BUREAU in ctx.on_file else []
        return [_finding(ctx, rule, "incomplete", sides, missing=[name],
                         note=f"The facilities on file cannot be held against a declaration: {name} not on file.")]
    declared_side = (_fact_side(declaration, "Declaration of existing facilities") if declaration is not None
                     else _fact_side(message, "Declared in the sourcing message"))
    if not evidence_on_file:
        names = [ctx.type_names[SANCTION], ctx.type_names[BUREAU]]
        return [_finding(ctx, rule, "incomplete", [declared_side], missing=names,
                         note=f"Nothing to reconcile the declared facilities against: {_join(names)} not on file.")]

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
                 "Declaration of existing facilities", declared, empty="None declared", differs=DECLARATION in odd and bool(issues))]
    if declaration is not None and not declared:
        sides[0] = _fact_side(declaration, "Declaration of existing facilities", differs=DECLARATION in odd and bool(issues))
    if SANCTION in ctx.on_file:
        sides.append(_facility_side("Sanction letters", sanctioned, differs=SANCTION in odd and bool(issues)))
    if BUREAU in ctx.on_file:
        sides.append(_facility_side(ctx.type_names[BUREAU], reported, differs=BUREAU in odd and bool(issues)))
    detail = _rows(["Declared", "Sanction letter", "Bureau", "Outstanding (bureau)"], rows)
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
                     [e for o in obligations for e in o.evidence[:1]])
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
    "borrowing_limit": _borrowing_limit,
    "signatories_are_directors": _signatories,
    "resolution_lender": _resolution_lender,
    "resolution_date": _resolution_date,
    **{v: _turnover for v in TURNOVER_PAIRS},
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
    ctx = Context(root, case, facts)
    out: list[Finding] = []
    for rule in ctx.rules:
        evaluator = EVALUATORS.get(rule.variable)
        if evaluator is not None:
            out.extend(evaluator(ctx, rule))
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
                   tolerance, config_version, run_id, query, area, scope, detail, missing)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f.id, case.id, f.rule_id, f.title, f.outcome, f.severity, int(f.blocking), f.explanation,
                 dumps([s.model_dump() for s in f.sides]), f.tolerance, f.config_version, f.run_id, f.query,
                 f.area, f.scope, dumps(f.detail.model_dump()) if f.detail else None, dumps(f.missing)),
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
