"""The PD question note (FRD F-24).

Questions for the personal discussion with the promoter, generated from the failed cross-checks
nobody has found not valid, the policy deviations, the observations (material facts the memo states
that need the promoter's answer: a fall in revenue, borrowings no facility on file explains, a loan
paid in that no facility matches) and the gaps still open (checks left incomplete, norms that could
not be evaluated). Each is asked under its topic (identity, turnover, bank accounts, existing
borrowings, then policy norms), ranked within it by severity and then finding, deviation,
observation and gap, and numbered across the note. Findings of a topic that come to the same
question are asked once, and the checks of a topic that could not be completed are asked together,
leaving out what the documents to collect already ask for. Each states the bare question, why it
is asked (the finding's explanation, the norm, or the memo's own sentence for an observation, whose
status names the memo section that states it), and its evidence (F-24.1, F-24.2). The note also
names the people to meet, leaves the record of the discussion blank and lists the documents still
to collect. The wording is configuration; the documents cited are numbered in the order they are
first cited (engine/output_sources.py).
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import get_args

from . import facts as facts_module
from . import output_sources
from . import policy as policy_module
from .cam import (NONE, Draft, _join, _lower, _norm_statement, _pages, _unassessed_sentence, _unique, config_label,
                  finding_evidence, finding_title, norm_evidence, plain, status)
from .config import load_app_config
from .configstore import reader
from .configstore.schema import PdNoteConfig, PdTopicArea
from .contracts import (CamFact, CamSignOff, CamText, CaseDetail, Finding, NormResult, PdNote, PdPerson, PdQuestion,
                        PdRef, PdTopic, QueryItem, XvItem)
from .util import display_date, stable_id

SEVERITY = {"serious": 0, "moderate": 1, "mild": 2}
SOURCE = {"finding": 0, "deviation": 1, "observation": 2, "gap": 3}
# The topic each area of the cross-verification board is asked under.
TOPIC = {"identity": "identity", "authority": "identity", "turnover": "turnover", "tax": "turnover",
         "financials": "turnover", "accounts": "accounts", "obligations": "obligations"}
COLLECT = ("documents_needed", "documents_to_redo")
# What a version published before these settings existed reads them as.
PD_FINDING = "{explanation} What is the position, and what will be provided?"
SIGN_OFF = ["Discussion held by"]
# A figure a norm rests on, by input, written in rupees.
MONEY = {*policy_module.FINANCIAL_INPUTS, "amount_requested", "market_value", "realisable_value", "annual_instalments",
         "proposed_instalments"}
MARKS = ("✓", "—", "")


class _Fmt(dict):
    def __missing__(self, key: str) -> str:
        return ""


def question_template(norm_config, policy_config, result) -> str | None:
    """What to ask the promoter about a norm, or None: the norm's own question, then its family's for a
    deviation; for a norm that could not be evaluated, the question for its reason, else the norm's own
    gap question, else the general one. A figure awaiting review is an internal step, and a norm
    marked pd_gap skip rests on an input the bank obtains."""
    if result.outcome == "deviation":
        return (norm_config.pd_question if norm_config else None) or policy_config.pd_questions.get(result.family)
    if result.outcome != "cannot_evaluate" or result.reason == "awaiting_review":
        return None
    if norm_config is not None and norm_config.pd_gap == "skip":
        return None
    if result.reason in ("zero_denominator", "denominator_not_positive"):
        return policy_config.pd_questions.get(result.reason)
    return getattr(norm_config, "pd_gap_question", None) or policy_config.pd_questions.get("cannot_evaluate")


def split(text: str) -> tuple[str, str]:
    """A worded question in two: what it rests on, and the question itself (its closing sentences that ask)."""
    sentences = re.split(r"(?<=[.?!])\s+", text.strip())
    cut = len(sentences)
    while cut and sentences[cut - 1].endswith("?"):
        cut -= 1
    return " ".join(sentences[:cut]), " ".join(sentences[cut:])


def _parts(worded: str) -> tuple[str, str]:
    """Why and what to ask; wording that asks nothing is put to the promoter as it stands."""
    context, question = split(worded)
    return (context, question) if question else ("", worded)


def _clean(text: str) -> str:
    return re.sub(r"\s+([?.,;:])", r"\1", re.sub(r"\s+", " ", text)).strip()


def _distinct(texts: list[str]) -> list[str]:
    """Each text once, in order, leaving out one that another contains."""
    texts = list(dict.fromkeys(t.strip().rstrip(".") for t in texts if t.strip()))
    return [t for t in texts if not any(t != u and t.casefold() in u.casefold() for u in texts)]


def _requests(found: list[Finding]) -> list[str]:
    """What would complete the checks, each thing once: a request naming several documents is read as
    its parts ("the director KYC and the memorandum…")."""
    return _distinct([p for f in found for p in re.split(r",\s+(?=the\s)|\s+and\s+(?=the\s)", f.request or "")])


def _collected(f: Finding, types: dict[str, set[str]], asked: set[str]) -> bool:
    """Whether everything a check waits for is among the documents to collect: each document it names
    as not on file satisfies a checklist item the query list asks for."""
    wanted = [types.get(m.casefold()) for m in f.missing]
    return bool(wanted) and all(items is not None and items & asked for items in wanted)


def _context(items: list[XvItem]) -> str:
    """Why a question is asked: the finding's explanation; for findings asked together, each with its
    board reference."""
    if len(items) == 1:
        return items[0].finding.explanation
    return " ".join(f"{i.finding.explanation.rstrip('.')} ({i.finding.ref or i.finding.rule_id})." for i in items)


def _written(value: object) -> str:
    """A side's value or a detail cell as a sentence writes it: an amount in rupees, a count (months)
    as a number."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return facts_module.inr(float(value)) if abs(value) >= 1000 else f"{value:g}"
    return str(value).strip() if value is not None else ""


def finding_values(f: Finding) -> _Fmt:
    """What a finding's question may name: {items} the rows it flags (people, accounts, lenders; also
    {lenders} and {accounts}), {count} how many and {s} the plural ending for that count, {values} the
    values its sides give ("AAACK1234F and AAACK9999Z"), {left} and {right} the first two, {detail}
    each flagged row with its figures, and {period} the year or months it covers."""
    rows = [r for r in f.detail.rows if r.flagged] if f.detail else []
    flagged = [r.label for r in rows]
    columns = f.detail.columns if f.detail else []
    shown = []
    for r in rows:
        cells = [f"{_lower(str(c))} {_written(v)}" for c, v in zip(columns, r.cells) if _written(v) not in MARKS]
        shown.append(f"{r.label} ({', '.join(cells)})" if cells else r.label)
    sides = [_written(s.value) for s in f.sides if s.value not in (None, "")]
    items = _join(flagged)
    return _Fmt(explanation="", items=items, lenders=items, accounts=items, count=str(len(flagged)),
                s="" if len(flagged) == 1 else "s", values=_join(list(dict.fromkeys(str(s.value) for s in f.sides
                                                                                  if s.value not in (None, "")))),
                left=sides[0] if sides else "", right=sides[1] if len(sides) > 1 else "", detail="; ".join(shown),
                period=f.scope or "")


def norm_values(n: NormResult, norm_config, policy_config, period: str | None, on_file: set[str]) -> _Fmt:
    """What a norm's question may name: {label} and {subject} the norm, {actual} and {required}, {period},
    {missing} and {inputs} what is not on file, {reason} why it could not be evaluated, {statement} the
    memo's sentence for it, {figures} each figure it rests on, each figure by its input's name
    ({amount_requested}, {revenue_from_operations}), {shortfall} how far the actual is from the norm in
    its unit ("1 year") and {s} the plural ending for that shortfall."""
    figures = {}
    for i in n.inputs:
        if i.value is None:
            continue
        figures[i.name] = (facts_module.inr(i.value) if i.name in MONEY
                           else policy_module.unit_text(i.value, "years") if i.name == "vintage_years"
                           else policy_module.unit_text(i.value, "rank") if i.name == "bureau_rank" else f"{i.value:g}")
    ratio = next((r for r in policy_config.ratios if norm_config is not None and r.key == norm_config.ratio), None)
    threshold = (norm_config.threshold if norm_config is not None and norm_config.threshold is not None
                 else ratio.acceptable if ratio else None)
    gap = abs(threshold - n.actual) if threshold is not None and n.actual is not None else None
    values = _Fmt(label=n.label, subject=_lower(n.label), required=n.required, period=period or "the latest year",
                  missing=_join([_lower(m) for m in n.missing]), inputs=", ".join(_lower(i) for i in n.reason_inputs),
                  actual=n.actual_text or "",
                  reason=_unassessed_sentence(n, on_file) if n.outcome == "cannot_evaluate" else "",
                  statement=f"{_norm_statement(n)}." if n.outcome == "deviation" else "",
                  figures=_join([f"{_lower(i.label)} {figures[i.name]}" for i in n.inputs if i.name in figures]),
                  shortfall=policy_module.unit_text(gap, n.unit) if gap is not None else "",
                  s="" if gap == 1 else "s")
    values.update({name: text for name, text in figures.items() if name not in values})
    return values


def _proposal(case: CaseDetail, facility_names: dict[str, str]) -> str:
    labels = [facility_names.get(f, f.replace("_", " ")) for f in case.facilities]
    facilities = _join([labels[0], *(_lower(label) for label in labels[1:])]) if labels else ""
    return ", ".join(p for p in (facilities, facts_module.inr(case.amount_inr)) if p)


def build(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> PdNote:
    config = reader.load_cam(root).pd_note
    checks = reader.load_crosschecks(root)
    rules = {r.id: r for r in checks.rules}
    policy_config = reader.load_policy(root)
    draft = Draft(conn, root, case)
    threshold = draft.threshold
    queries: list[QueryItem] = draft.queries
    collecting = [q for q in queries if q.group in COLLECT]
    # The checklist items the documents to collect ask for, and the items each document type satisfies.
    asked = {q.source_ref.split(":")[0] for q in collecting if q.source_kind == "checklist"}
    satisfies = {t.name.casefold(): set(t.satisfies) for t in reader.load_document_types(root).types}
    questions: list[PdQuestion] = []

    def ask(key: str, context: str, question: str, **fields) -> None:
        questions.append(PdQuestion(id=stable_id("PDQ", case.id, key), number=0, question=question, context=context,
                                    text=f"{context} {question}".strip(), **fields))

    def evidence(f: Finding):
        return finding_evidence(f, threshold, draft.naming)

    # Findings, one question for those of a topic that ask the same; the checks not completed, by topic.
    asking: dict[tuple[str, str], list[XvItem]] = {}
    gaps: dict[str, list[Finding]] = {}
    general = getattr(checks, "pd_finding", None) or PD_FINDING
    for item in draft.board.items:
        f = item.finding
        rule = rules.get(f.rule_id)
        area = TOPIC.get(f.area, "identity")
        dismissed = item.decision is not None and item.decision.decision == "dismiss"
        if f.outcome == "fail" and not dismissed:
            # The bare question: the rule's wording without the explanation, which is why it is asked.
            values = finding_values(f)
            # A rule that asks nothing of its own is put the general question, so every finding is asked.
            question = (_clean(((rule.pd_question if rule else None) or general).format_map(values))
                        or _clean(general.format_map(values)))
            if question:
                asking.setdefault((area, question), []).append(item)
        elif f.outcome == "incomplete" and f.request and not _collected(f, satisfies, asked):
            # A check with nothing to ask for (it waits for a person's review, or for months still to
            # come) is not put to the promoter, nor one whose documents are already to be collected.
            gaps.setdefault(area, []).append(f)

    for (area, question), items in asking.items():
        items = sorted(items, key=lambda i: SEVERITY[i.finding.severity])
        first = items[0]
        also = [PdRef(ref=i.finding.id, xv_ref=i.finding.ref, rule=i.finding.rule_id, title=finding_title(i.finding),
                      status=status(i), evidence=evidence(i.finding)) for i in items[1:]]
        ask(first.finding.id, _context(items), question, severity=first.finding.severity, source="finding",
            ref=first.finding.id, xv_ref=first.finding.ref, rule=first.finding.rule_id, title=finding_title(first.finding),
            area=area, status=status(first), target="cross_verification", also=also,
            evidence=_pages(e for i in items for e in evidence(i.finding)))

    for area, found in gaps.items():
        found = sorted(found, key=lambda f: SEVERITY[f.severity])
        first = found[0]
        values = _Fmt(title=_join([plain(f.title) for f in found]),
                      explanation=" ".join(f"{e}." for e in _distinct([plain(f.explanation) for f in found])),
                      request=_join(_requests(found)))
        worded = _clean(checks.pd_incomplete.format_map(values))
        ask(first.id, *_parts(worded), severity=first.severity, source="gap", ref=first.id, rule=first.rule_id,
            title=plain(first.title), area=area, target="cross_verification",
            also=[PdRef(ref=f.id, rule=f.rule_id, title=plain(f.title), evidence=evidence(f)) for f in found[1:]],
            evidence=_pages(e for f in found for e in evidence(f)))

    assessment = draft.assessment
    facts = draft.facts
    on_file = set(facts.types_on_file)
    for n in assessment.norms:
        norm_config = next((c for c in policy_config.norms if c.id == n.id), None)
        template = question_template(norm_config, policy_config, n)
        if template is None:
            continue
        values = norm_values(n, norm_config, policy_config, assessment.period, on_file)
        deviation = n.outcome == "deviation"
        ask(n.id, *_parts(_clean(template.format_map(values))), severity="moderate" if deviation else "mild",
            source="deviation" if deviation else "gap", ref=n.id, rule=n.id, title=n.label, area="policy",
            evidence=norm_evidence(n), target="policy")

    # Observations: the memo's sentence is why each is asked; its status names the section that states it.
    for o in draft.observations():
        number = draft.numbers.get(o.section)
        ask(o.key, o.context, o.question, severity=o.severity, source="observation", ref=o.key, rule="OBS",
            title=o.title, area=o.area, status=f"section {number}" if number else None, evidence=o.evidence,
            target="cam")

    titles = {**PdNoteConfig().topics, **config.topics}
    order = list(get_args(PdTopicArea))
    questions.sort(key=lambda q: (order.index(q.area), SEVERITY[q.severity], SOURCE[q.source]))
    for number, q in enumerate(questions, start=1):
        q.number = number
    topics = [PdTopic(area=area, title=titles[area], question_ids=[q.id for q in questions if q.area == area])
              for area in order if any(q.area == area for q in questions)]

    names = draft.type_names
    met = []
    for p in draft.people:
        # Where documents give different DINs, each with the documents it comes from.
        din = p.identifiers("din", names)
        met.append(PdPerson(name=p.name, role=p.role, din=din.text if din.text != NONE else None, sources=p.sources(names),
                            evidence=_unique(p.evidence() + din.citations)))
    collect = [CamText(text=q.text, citations=q.evidence) for q in collecting]
    labels = dict(getattr(config, "labels", None) or {})
    app = load_app_config()
    constitutions = {c["id"]: c["label"] for c in app.get("constitutions", [])}
    version = config_label(root)
    header = [(labels.get("borrower", "Borrower"), case.borrower), (labels.get("case_id", "Case ID"), case.id),
              (labels.get("constitution", "Constitution"), constitutions.get(case.constitution, case.constitution)),
              (labels.get("proposal", "Proposal"), _proposal(case, {f["id"]: f["label"] for f in app["facilities"]})),
              (labels.get("data_as_of", "Data as of"), display_date(date.fromisoformat(case.as_of))),
              (labels.get("configuration", "Configuration version"), version)]
    note = PdNote(case_id=case.id, title=config.title, borrower=case.borrower, as_of=case.as_of,
                  config_version=reader.published_version(root)["version"], config_label=version,
                  header=[CamFact(label=label, value=CamText(text=value)) for label, value in header if value],
                  people=met, questions=questions, topics=topics, documents_to_collect=collect,
                  record_fields=config.record_fields,
                  sign_off=[CamSignOff(role=r) for r in (getattr(config, "sign_off", None) or SIGN_OFF)], labels=labels)
    note.sources = output_sources.sources(conn, root, case.id, output_sources.pd_citations(note))
    return note
