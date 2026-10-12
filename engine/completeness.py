"""Document sufficiency: every checklist item satisfied, insufficient,
missing, in review or waived, with the specific deficiency (F-12, F-13).

Computed from the stored documents, their extracted values, the party set,
the waivers and the published configuration, measured from the case's
fixed as_of date (principle 8): the same case gives the same checklist.

- Documents map to items through their type's `satisfies` list, case-aware:
  the item must apply to the case (constitution and attributes) and, for
  audited statements, the statement's year decides which year it covers.
  Unclassified documents are never mapped (F-09.5).
- Coverage rules (config/checklist_taxonomy.yaml `coverage`): financial
  years, assessment years, twelve monthly GST periods, twelve months of
  statements for every declared account, KYC for every party.
- Document defects reported by the sidecar (pages absent, period gap,
  unsigned, unstamped, plain paper, broken pagination) make the item
  insufficient (F-13.3); they never lower extraction confidence.
- Outdated: older than config/document_ages.yaml permits, from as_of.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .checklist import CaseAttributes, applies
from .config import load_app_config
from .configstore import reader
from .configstore.schema import ChecklistItemDef
from .contracts import CaseDetail, ChecklistItemState, Readiness
from .parties import field_map, table_rows
from .pipeline import effective_types
from .util import (
    assessment_year_start,
    display_date,
    fy_end,
    fy_end_of,
    fy_label,
    month_end,
    months_before,
    parse_date,
    parse_period,
    period_months,
    ranges_label,
)

ALL_CONSTITUTIONS = ("private_limited", "proprietorship", "partnership")
USABLE = {"accepted", "in_review", "extracted", "classified"}

# Where a permitted age is measured from (config/document_ages.yaml), by the
# dictionary fields that carry that date.
AGE_FIELDS = {
    "as_at_date": ["as_at_date"],
    "period_end": ["statement_period_end"],
    "valuation_date": ["valuation_date"],
    "document_date": ["date_of_issue", "filing_date", "audit_date", "resolution_date", "meeting_date"],
}

DEFECT_TEXT = {
    "unsigned": "not signed",
    "unstamped": "not stamped",
    "plain_paper": "on plain paper, not on letterhead",
    "pages_absent": "pages absent",
    "pagination_break": "page numbering broken",
    "period_gap": "period gap",
}

SECTION_LABEL = {
    "balance_sheet": "balance sheet",
    "profit_and_loss": "profit and loss",
    "cash_flow": "cash flow",
    "notes": "notes to accounts",
}


@dataclass
class Deficiency:
    kind: str
    """gap (documents needed) | redo (documents to redo) | outdated (to redo)."""
    code: str
    text: str
    """As shown on the checklist."""
    request: str
    """For the query list (config/app.yaml query_phrasing): for a gap, what
    to send; for a redo, what is wrong with the copy received."""
    evidence: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    name: str = ""
    """The document concerned, for redo and outdated phrasing."""


@dataclass
class ItemResult:
    item: ChecklistItemDef
    state: ChecklistItemState
    deficiencies: list[Deficiency]
    missing_request: str | None = None


@dataclass
class Doc:
    row: sqlite3.Row
    types: list[str]
    fields: dict[str, tuple[object, int | None]]

    @property
    def id(self) -> str:
        return self.row["id"]

    @property
    def status(self) -> str:
        return self.row["status"]

    @property
    def label(self) -> str:
        return self.row["archive_path"] or self.row["original_name"]

    def value(self, *names: str) -> object:
        for name in names:
            v = self.fields.get(name)
            if v is not None and v[0] not in (None, ""):
                return v[0]
        return None

    def page(self, *names: str) -> int:
        for name in names:
            v = self.fields.get(name)
            if v is not None and v[1]:
                return v[1]
        return self.row["page_from"]

    def evidence(self, *names: str) -> dict:
        return {"document_id": self.id, "page": self.page(*names)}

    @property
    def defects(self) -> list[dict]:
        return json.loads(self.row["defects"] or "[]")


@dataclass
class CaseData:
    case: CaseDetail
    as_of: date
    docs: list[Doc]
    parties: list[sqlite3.Row]
    waivers: dict[str, str]
    declared_accounts: list[tuple[str, str]]
    """(bank, last four digits) from the declaration of existing facilities."""
    existing_facilities_declared: bool


def _last4(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-4:] if len(digits) >= 4 else None


def load_case_data(conn: sqlite3.Connection, case: CaseDetail) -> CaseData:
    rows = conn.execute(
        """SELECT d.*, f.label_hint, f.original_name, f.archive_path FROM documents d JOIN files f ON f.id = d.file_id
           WHERE d.case_id = ? AND d.status NOT IN ('duplicate', 'superseded') ORDER BY d.created_at, d.id""",
        (case.id,),
    ).fetchall()
    docs = [Doc(row=r, types=effective_types(r), fields=field_map(conn, r["id"])) for r in rows]
    docs = [d for d in docs if d.types]
    waivers = {
        r["item_id"]: r["reason"]
        for r in conn.execute("SELECT item_id, reason FROM checklist_waivers WHERE case_id = ?", (case.id,))
    }
    parties = conn.execute(
        "SELECT * FROM parties WHERE case_id = ? AND role <> 'borrower' ORDER BY ord", (case.id,)
    ).fetchall()

    return CaseData(
        case=case,
        as_of=date.fromisoformat(case.as_of),
        docs=docs,
        parties=parties,
        waivers=waivers,
        declared_accounts=[],
        existing_facilities_declared=False,
    )


class Evaluator:
    def __init__(self, root: Path, data: CaseData) -> None:
        self.data = data
        self.as_of = data.as_of
        self.types = {t.id: t for t in reader.load_document_types(root).types}
        ages = reader.load_document_ages(root)
        self.ages = {a.type_id: a for a in ages.ages}
        self.validity_rules = ages.validity

    def type_name(self, type_id: str) -> str:
        t = self.types.get(type_id)
        return t.name if t else type_id

    def candidates(self, item: ChecklistItemDef) -> list[Doc]:
        return [
            d for d in self.data.docs if any(item.id in (self.types[t].satisfies if t in self.types else []) for t in d.types)
        ]

    # --- per item ---

    def evaluate(self, item: ChecklistItemDef) -> ItemResult:
        def state(status: str, deficiency: str | None, docs: list[Doc]) -> ChecklistItemState:
            return ChecklistItemState(
                item_id=item.id,
                name=item.name,
                section=item.category,
                blocking=item.blocking,
                weight=item.weight,
                status=status,
                deficiency=deficiency,
                document_ids=[d.id for d in docs],
                why=item.why,
                basis=item.basis,
            )

        if item.id in self.data.waivers:
            return ItemResult(item, state("waived", f"Waived: {self.data.waivers[item.id]}", []), [])

        cands = self.candidates(item)
        usable = [d for d in cands if d.status in USABLE]
        exceptions = [d for d in cands if d.status == "in_exception"]
        request = item.request or item.name
        cov = item.coverage

        if not usable:
            if exceptions:
                names = ", ".join(d.label for d in exceptions)
                return ItemResult(
                    item, state("in_review", f"Awaiting a readable copy or manual entry: {names}", exceptions), []
                )
            missing = self.missing_request(item)
            return ItemResult(item, state("missing", f"Not received: {missing}", []), [], missing)

        defs: list[Deficiency] = []
        docs = usable
        if cov is not None:
            kind = cov.kind
            if kind == "financial_year":
                target = fy_end(self.as_of, cov.offset)
                docs = [d for d in usable if fy_end_of(d.value("financial_year") or d.row["instance_key"]) == target]
                if not docs:
                    others = sorted(
                        {fy_end_of(d.value("financial_year") or d.row["instance_key"]) for d in usable} - {None}
                    )
                    missing = self.missing_request(item)
                    received = (
                        " (received: " + ", ".join(fy_label(o) for o in others) + ")" if others else ""
                    )
                    return ItemResult(item, state("missing", f"Not received: {missing}{received}", []), [], missing)
                defs += self.sections(docs, cov.statements)
            elif kind == "statements":
                defs += self.sections(docs, cov.statements)
            elif kind == "assessment_years":
                defs += self.assessment_years(item, docs, cov.count)
            elif kind == "monthly_periods":
                defs += self.monthly_periods(item, docs, cov.months)
            elif kind == "account_months":
                defs += self.account_months(item, docs, cov.months)
            elif kind == "parties":
                result = self.parties(item, docs)
                if isinstance(result, ItemResult):
                    return result
                defs += result
        defs += self.defects(item, docs)
        defs += self.outdated(item, docs, per_account=cov is not None and cov.kind == "account_months")
        defs += self.validity(docs)

        if defs:
            return ItemResult(item, state("insufficient", "; ".join(d.text for d in defs), docs), defs)
        if any(d.status == "in_review" for d in docs):
            return ItemResult(item, state("in_review", "Awaiting review of extracted values", docs), [])
        return ItemResult(item, state("satisfied", None, docs), [])

    def missing_request(self, item: ChecklistItemDef) -> str:
        request = item.request or item.name
        cov = item.coverage
        if cov is None:
            return request
        if cov.kind == "financial_year":
            return f"{request} for {fy_label(fy_end(self.as_of, cov.offset))}"
        if cov.kind == "assessment_years":
            return f"{request} for {self._ay_list(self._required_ays(cov.count))}"
        if cov.kind == "monthly_periods":
            return f"{request} for {ranges_label(months_before(self.as_of, cov.months))}"
        if cov.kind == "account_months":
            window = ranges_label(months_before(self.as_of, cov.months))
            accounts = self.data.declared_accounts
            if accounts:
                names = ", ".join(f"{bank} ·{last4}".strip() for bank, last4 in accounts)
                return f"{request} for {window} for every operative account ({names})"
            return f"{request} for {window} for every operative account"
        if cov.kind == "parties":
            names = [p["name"] for p in self.data.parties]
            return f"{request}" + (f": {', '.join(names)}" if names else "")
        return request

    # --- coverage rules ---

    def sections(self, docs: list[Doc], required: list[str]) -> list[Deficiency]:
        """Statements the document must carry: a table of printed rows for each (F-13.2)."""
        out = []
        for d in docs:
            if any(df.get("code") == "pages_absent" for df in d.defects):
                continue  # reported from the defect itself
            if not required:
                continue
            absent = [s for s in required if not any(k.startswith(f"{s}[") and v[0] is not None for k, v in d.fields.items())]
            if absent:
                what = " and ".join(SECTION_LABEL.get(s, s) for s in absent)
                out.append(
                    Deficiency(
                        "redo",
                        f"sections:{d.id}",
                        f"{what} not found ({d.label})",
                        f"the {what} pages are absent",
                        [d.evidence(*absent)],
                        name=self._doc_name(d),
                    )
                )
        return out

    def _required_ays(self, count: int) -> list[int]:
        latest = fy_end(self.as_of, 1).year
        return [latest - k for k in range(count)]

    @staticmethod
    def _ay_list(years: list[int]) -> str:
        return " and ".join(f"AY {y}-{str(y + 1)[2:]}" for y in years)

    def assessment_years(self, item: ChecklistItemDef, docs: list[Doc], count: int) -> list[Deficiency]:
        required = self._required_ays(count)
        have = {assessment_year_start(d.value("assessment_year") or d.row["instance_key"]) for d in docs}
        absent = [y for y in required if y not in have]
        if not absent:
            return []
        request = item.request or item.name
        return [
            Deficiency(
                "gap",
                "years",
                f"{self._ay_list(absent)} not received ({len(required) - len(absent)} of {len(required)} years)",
                f"{request} for {self._ay_list(absent)}",
            )
        ]

    def monthly_periods(self, item: ChecklistItemDef, docs: list[Doc], months: int) -> list[Deficiency]:
        window = months_before(self.as_of, months)
        have: set[tuple[int, int]] = set()
        for d in docs:
            if any(self.types[t].partner_output for t in d.types if t in self.types):
                missing = self._partner_missing_periods(d)
                have |= set(window) - missing
                continue
            have |= set(period_months(d.value("tax_period") or d.row["instance_key"], d.value("financial_year")))
        absent = [p for p in window if p not in have]
        if not absent:
            return []
        request = item.request or item.name
        return [
            Deficiency(
                "gap",
                "periods",
                f"{ranges_label(absent)} absent ({months - len(absent)} of {months} months)",
                f"{request} for {ranges_label(absent)}",
                [],
                {"absent": [f"{y}-{m:02d}" for y, m in absent]},
            )
        ]

    def _partner_missing_periods(self, d: Doc) -> set[tuple[int, int]]:
        out = set()
        for name, (value, _) in d.fields.items():
            if not name.startswith("periods_missing"):
                continue
            for part in re.split(r"[,;]", str(value or "")):
                p = parse_period(part.strip())
                if p:
                    out.add(p)
        return out

    def _account_of(self, d: Doc) -> str | None:
        return _last4(d.value("account_number")) or _last4(d.row["instance_key"])

    def account_months(self, item: ChecklistItemDef, docs: list[Doc], months: int) -> list[Deficiency]:
        window = months_before(self.as_of, months)
        covered: dict[str, set[tuple[int, int]]] = {}
        seen_bank: dict[str, str] = {}
        for d in docs:
            if any(self.types[t].partner_output for t in d.types if t in self.types):
                for row in table_rows(d.fields, "accounts"):
                    last4 = _last4((row.get("account_number_masked") or (None, None))[0])
                    if last4:
                        covered.setdefault(last4, set()).update(window)
                        seen_bank.setdefault(last4, str((row.get("bank") or ("", None))[0] or ""))
                continue
            last4 = self._account_of(d) or "?"
            seen_bank.setdefault(last4, str(d.value("bank_name") or ""))
            start, end = parse_date(d.value("statement_period_start")), parse_date(d.value("statement_period_end"))
            months_cov = covered.setdefault(last4, set())
            if start and end:
                for p in window:
                    first, last = date(p[0], p[1], 1), month_end(*p)
                    if start <= first and end >= last:
                        months_cov.add(p)
        declared = self.data.declared_accounts
        accounts = [(bank, last4) for bank, last4 in declared] or [(seen_bank.get(a, ""), a) for a in covered]
        request = item.request or item.name
        out: list[Deficiency] = []
        received = sum(1 for _, a in accounts if a in covered)
        for bank, last4 in accounts:
            name = f"{bank} ·{last4}".strip()
            if last4 not in covered:
                out.append(
                    Deficiency(
                        "gap",
                        f"account:{last4}",
                        f"statement not received for declared account {name} ({received} of {len(accounts)} accounts)",
                        f"{request} for account {name} for {ranges_label(window)}",
                    )
                )
                continue
            absent = [p for p in window if p not in covered[last4]]
            if absent:
                out.append(
                    Deficiency(
                        "gap",
                        f"account:{last4}:months",
                        f"account {name}: {ranges_label(absent)} absent",
                        f"{request} for account {name} for {ranges_label(absent)}",
                        [],
                        {"absent": [f"{y}-{m:02d}" for y, m in absent]},
                    )
                )
        return out

    def parties(self, item: ChecklistItemDef, docs: list[Doc]) -> list[Deficiency] | ItemResult:
        needed = self.data.parties
        if not needed:
            return []
        have = {d.row["party_id"] for d in docs if d.row["party_id"]}
        absent = [p for p in needed if p["id"] not in have]
        if not absent:
            return []
        names = ", ".join(p["name"] for p in absent)
        request = item.request or item.name
        if len(absent) == len(needed):
            missing = f"{request}: {names}"
            return ItemResult(
                item,
                ChecklistItemState(
                    item_id=item.id, name=item.name, section=item.category, blocking=item.blocking,
                    weight=item.weight, status="missing", deficiency=f"Not received: {missing}",
                    document_ids=[d.id for d in docs], why=item.why, basis=item.basis,
                ),
                [],
                missing,
            )
        return [
            Deficiency(
                "gap",
                "parties",
                f"KYC missing for {len(absent)} of {len(needed)}: {names}",
                f"KYC (PAN and address proof) of {names}",
            )
        ]

    # --- defects and age ---

    def _doc_name(self, d: Doc) -> str:
        return " and ".join(self.type_name(t) for t in d.types)

    def defects(self, item: ChecklistItemDef, docs: list[Doc]) -> list[Deficiency]:
        out = []
        for d in docs:
            found = list(d.defects)
            for df in found:
                code = df.get("code")
                what = DEFECT_TEXT.get(code, code)
                detail = (df.get("detail") or "").strip()
                if code == "pages_absent":
                    text = detail or what
                elif detail and code in ("period_gap", "pagination_break"):
                    text = f"{what}: {detail}"
                else:
                    text = what
                pages = df.get("pages") or [d.row["page_from"]]
                name = self._doc_name(d)
                if code == "period_gap":
                    kind, request = "gap", f"{name} for the missing period ({detail or what})"
                elif code == "pages_absent":
                    kind, request = "redo", detail or what
                elif code == "pagination_break":
                    kind, request = "redo", f"{what}" + (f" ({detail})" if detail else "")
                else:
                    kind, request = "redo", f"the copy provided is {what}" + (f" ({detail})" if detail else "")
                out.append(
                    Deficiency(
                        kind,
                        f"defect:{d.id}:{code}",
                        f"{text} ({d.label})",
                        request,
                        [{"document_id": d.id, "page": p} for p in pages[:3]],
                        name=name,
                    )
                )
        return out

    def _dated(self, d: Doc, type_id: str) -> tuple[date | None, str]:
        age = self.ages[type_id]
        names = AGE_FIELDS.get(age.measured_from, [])
        when = parse_date(d.value(*names))
        if when is None and age.measured_from == "period_end":
            # A return has no period-end date of its own: it is the last day of its last month.
            months = period_months(d.value("tax_period") or d.row["instance_key"], d.value("financial_year"))
            if months:
                return month_end(*months[-1]), "tax_period"
        return when, names[0] if names else ""

    def validity(self, docs: list[Doc]) -> list[Deficiency]:
        """Printed dates that must hold at as_of: an expiry or validity end not yet passed,
        a document date not after as_of. An absent or unreadable date is no finding."""
        out = []
        for d in docs:
            for rule in self.validity_rules:
                if rule.type_id not in d.types:
                    continue
                when = parse_date(d.value(rule.field))
                if when is None:
                    continue
                name = self.type_name(rule.type_id)
                if rule.kind == "expires" and when < self.as_of:
                    out.append(Deficiency(
                        "redo", f"expired:{d.id}:{rule.field}",
                        f"Expired: valid until {display_date(when)}, before {display_date(self.as_of)} ({d.label})",
                        f"expired on {display_date(when)}; a copy valid on {display_date(self.as_of)} is needed",
                        [d.evidence(rule.field)], {"date": display_date(when)}, name=name,
                    ))
                elif rule.kind == "not_future" and when > self.as_of:
                    out.append(Deficiency(
                        "redo", f"future_dated:{d.id}:{rule.field}",
                        f"Dated {display_date(when)}, after {display_date(self.as_of)} ({d.label})",
                        f"dated {display_date(when)}, which is after {display_date(self.as_of)}; please check the date",
                        [d.evidence(rule.field)], {"date": display_date(when)}, name=name,
                    ))
        return out

    def outdated(self, item: ChecklistItemDef, docs: list[Doc], *, per_account: bool) -> list[Deficiency]:
        """F-13.2: the newest document of each aged type (per account for bank
        statements) must be within its permitted age of as_of."""
        groups: dict[tuple[str, str], list[Doc]] = {}
        for d in docs:
            for t in d.types:
                if t in self.ages:
                    key = self._account_of(d) or "" if per_account else ""
                    groups.setdefault((t, key), []).append(d)
        out = []
        for (type_id, key), members in sorted(groups.items()):
            age = self.ages[type_id]
            dated = [(self._dated(d, type_id)[0], d) for d in members]
            known = [(dt, d) for dt, d in dated if dt is not None]
            if not known:
                d = members[0]
                out.append(
                    Deficiency(
                        "redo",
                        f"undated:{type_id}:{key}",
                        f"date not found on {d.label}; permitted age {age.max_age_days} days cannot be checked",
                        "the date cannot be read",
                        [{"document_id": d.id, "page": d.row["page_from"]}],
                        name=self.type_name(type_id),
                    )
                )
                continue
            newest, d = max(known, key=lambda x: x[0])
            days = (self.as_of - newest).days
            if days > age.max_age_days:
                suffix = f" (account ·{key})" if key else ""
                out.append(
                    Deficiency(
                        "outdated",
                        f"outdated:{type_id}:{key}",
                        f"Outdated{suffix}: dated {display_date(newest)}, permitted age {age.max_age_days} days"
                        f" from {display_date(self.as_of)}",
                        "",
                        [d.evidence(*AGE_FIELDS.get(age.measured_from, []))],
                        {"date": display_date(newest), "max_age_days": age.max_age_days},
                        name=self.type_name(type_id) + suffix,
                    )
                )
        return out


def applicable_items(root: Path, case: CaseDetail, data: CaseData | None) -> tuple[list[ChecklistItemDef], bool]:
    """F-12: the items for the case's constitution and attributes. While the
    constitution is unknown, only the items every constitution needs (F-12.3).
    Without the case's documents (`data` None), no facilities are taken as declared."""
    taxonomy = reader.load_checklist_taxonomy(root)
    policy = reader.load_policy(root)
    facility_sets = {f["id"]: f.get("sets") for f in load_app_config()["facilities"]}
    attrs = CaseAttributes.from_case(
        facilities=case.facilities,
        amount_inr=case.amount_inr,
        collateral_present=case.collateral_present,
        facility_sets=facility_sets,
        mpbf_above_limit_inr=policy.working_capital.mpbf_above_limit_inr,
        existing_facilities_declared=data.existing_facilities_declared if data else False,
    )
    provisional = case.constitution not in ALL_CONSTITUTIONS
    if provisional:
        items = [
            item
            for item in taxonomy.items
            if set(ALL_CONSTITUTIONS) <= set(item.constitutions) and all(attrs.has(a) for a in item.requires_attributes)
        ]
    else:
        items = [item for item in taxonomy.items if applies(item, case.constitution, attrs)]
    return items, provisional


def evaluate(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> tuple[Readiness, list[ItemResult]]:
    taxonomy = reader.load_checklist_taxonomy(root)
    data = load_case_data(conn, case)
    items, provisional = applicable_items(root, case, data)
    evaluator = Evaluator(root, data)
    results = [evaluator.evaluate(item) for item in items]
    states = [r.state for r in results]

    # F-13.4: weighted by section weight, then by item weight within the section.
    sections: dict[str, list[ChecklistItemState]] = {}
    for s in states:
        sections.setdefault(s.section, []).append(s)
    total_section_weight = sum(taxonomy.section_weight.get(name, 0) for name in sections) or 1
    score = 0.0
    for name, members in sections.items():
        total = sum(m.weight for m in members) or 1
        done = sum(m.weight for m in members if m.status in ("satisfied", "waived"))
        score += taxonomy.section_weight.get(name, 0) * done / total
    score_pct = round(100 * score / total_section_weight, 1)
    blocking_open = sum(1 for s in states if s.blocking and s.status not in ("satisfied", "waived"))
    readiness = Readiness(
        score_pct=score_pct,
        gate_pct=taxonomy.review_gate_threshold,
        gate_met=score_pct >= taxonomy.review_gate_threshold and blocking_open == 0,
        blocking_open=blocking_open,
        provisional=provisional,
        items=states,
        ready_for_credit=not provisional and bool(states) and all(s.status in ("satisfied", "waived") for s in states),
    )
    return readiness, results
