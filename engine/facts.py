"""Fact alignment: extracted fields made comparable (FRD F-18).

Read-only over the case's field values. A person's correction wins over the
value read (the effective value), and a value entered or corrected by a
person is flagged (F-19.4). Every fact keeps the field-value ids and the
evidence it came from (F-18.6), so a finding can point at both sides.

- Identities (PAN, GSTIN, legal name) by document.
- Promoter sets by source.
- Turnover by financial year from the financial statements, GST returns,
  cleansed bank credits and the RM's message (F-18.1).
- Bank credits cleansed by configured narration rules (F-18.2).
- Lender and person names resolved by similarity (F-18.3).
- Recurring debits to lenders inferred as obligations (F-18.4).
- The account set across documents (F-18.5).
"""

from __future__ import annotations

import calendar
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .configstore import reader
from .configstore.schema import AlignmentSection
from .contracts import (
    AccountCredits,
    AccountFact,
    CaseDetail,
    CaseFacts,
    Evidence,
    Exclusion,
    FacilityFact,
    FactValue,
    IdentityFacts,
    Obligation,
    PersonSet,
    TurnoverFigure,
    TurnoverYear,
)
from .names import normalise_name, similarity
from .parties import PARTY_TABLES
from .pipeline import effective_types
from .store import MESSAGE_FILE_NAME
from .util import format_inr, month_add, month_label, parse_date, parse_period

USABLE = {"accepted", "in_review", "extracted", "classified"}

# Where each identity is read, by field name (first found wins per document).
PAN_FIELDS = ("pan", "entity_pan", "pan_number")
GSTIN_FIELDS = ("gstin",)
NAME_FIELDS = ("legal_name", "entity_name", "company_name", "name_of_company", "subject_name", "enterprise_name",
               "name")
# Document types whose "name" is a person's, not the entity's.
PERSON_DOCS = {"kyc_pan_individual", "kyc_aadhaar", "kyc_passport", "kyc_voter_id", "kyc_driving_licence",
               "bureau_consumer"}
KYC_TYPES = PERSON_DOCS - {"bureau_consumer"}


# --- Loading ---


@dataclass
class Value:
    field_id: str
    value: object
    evidence: dict | None
    manual: bool


@dataclass
class Doc:
    id: str
    types: list[str]
    type_names: list[str]
    page_from: int
    fields: dict[str, Value]
    party_id: str | None = None

    @property
    def label(self) -> str:
        return " + ".join(self.type_names)

    def get(self, *names: str) -> Value | None:
        for name in names:
            v = self.fields.get(name)
            if v is not None and v.value not in (None, ""):
                return v
        return None

    def rows(self, table: str) -> list[dict[str, Value]]:
        out: dict[int, dict[str, Value]] = defaultdict(dict)
        pattern = re.compile(rf"^{re.escape(table)}\[(\d+)\]\.(.+)$")
        for name, v in self.fields.items():
            m = pattern.match(name)
            if m:
                out[int(m[1])][m[2]] = v
        return [out[i] for i in sorted(out)]

    def evidence(self, *values: Value | None) -> list[Evidence]:
        found = []
        for v in values:
            if v is not None and v.evidence and v.evidence.get("page"):
                found.append(Evidence.model_validate({**v.evidence, "document_id": v.evidence.get("document_id") or self.id}))
        return found or [Evidence(document_id=self.id, page=self.page_from)]


def _effective(row: sqlite3.Row) -> object:
    if row["status"] == "corrected" and row["corrected_value"] is not None:
        return json.loads(row["corrected_value"])
    return json.loads(row["value"]) if row["value"] is not None else None


def load_documents(conn: sqlite3.Connection, root: Path, case_id: str) -> list[Doc]:
    types = {t.id: t.name for t in reader.load_document_types(root).types}
    docs: list[Doc] = []
    for row in conn.execute(
        """SELECT d.* FROM documents d WHERE d.case_id = ? AND d.status IN ('accepted', 'in_review', 'extracted',
           'classified') ORDER BY d.created_at, d.id""",
        (case_id,),
    ):
        doc_types = effective_types(row)
        if not doc_types:
            continue
        fields: dict[str, Value] = {}
        for fv in conn.execute(
            "SELECT id, field, value, corrected_value, status, evidence, method FROM field_values WHERE document_id = ?",
            (row["id"],),
        ):
            if fv["status"] in ("missing", "rejected"):
                continue
            fields[fv["field"]] = Value(
                field_id=fv["id"],
                value=_effective(fv),
                evidence=json.loads(fv["evidence"]) if fv["evidence"] else None,
                manual=fv["method"] == "manual" or fv["status"] == "corrected",
            )
        docs.append(
            Doc(
                id=row["id"],
                types=doc_types,
                type_names=[types.get(t, t.replace("_", " ")) for t in doc_types],
                page_from=row["page_from"],
                fields=fields,
                party_id=row["party_id"] if "party_id" in row.keys() else None,
            )
        )
    return docs


# --- Names (F-18.3) ---


def resolve_name(name: str, noise: list[str]) -> str:
    """A lender or firm name without its noise words, for comparison."""
    words = [w for w in normalise_name(name).split() if w not in noise]
    return " ".join(words) or normalise_name(name)


def same_entity(a: str, b: str, noise: list[str], threshold: float) -> bool:
    ra, rb = resolve_name(a, noise), resolve_name(b, noise)
    return ra == rb or similarity(ra, rb) >= threshold


def cluster(names: list[str], noise: list[str], threshold: float) -> list[list[str]]:
    """Group variant names for one entity; the first seen names the group."""
    groups: list[list[str]] = []
    for name in names:
        for g in groups:
            if same_entity(name, g[0], noise, threshold):
                if name not in g:
                    g.append(name)
                break
        else:
            groups.append([name])
    return groups


# --- Financial years (F-18.1) ---


def fy_of(year: int, month: int, start: int) -> int:
    """The calendar year in which the financial year containing (year, month) ends."""
    return year + 1 if month >= start and start != 1 else year


def fy_months(end_year: int, start: int) -> list[tuple[int, int]]:
    first = (end_year - 1, start) if start != 1 else (end_year, 1)
    return [month_add(*first, k) for k in range(12)]


def fy_name(end_year: int, start: int) -> str:
    if start == 1:
        return f"FY {end_year}"
    return f"FY {end_year - 1}-{str(end_year)[2:]}"


def fy_end_date(end_year: int, start: int) -> date:
    y, m = month_add(end_year - 1, start, 11) if start != 1 else (end_year, 12)
    return date(y, m, calendar.monthrange(y, m)[1])


# --- Bank transactions ---


@dataclass
class Txn:
    account: str
    date: date | None
    narration: str
    debit: float
    credit: float
    evidence: list[Evidence]
    doc: Doc


def _amount(v: Value | None) -> float:
    if v is None or v.value in (None, ""):
        return 0.0
    try:
        return float(str(v.value).replace(",", ""))
    except ValueError:
        return 0.0


def _last4(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-4:] if len(digits) >= 4 else None


def _account_label(bank: str, last4: str | None) -> str:
    return f"{bank} ·{last4}" if last4 else bank


def _phrase(text: str, cues: list[str]) -> str | None:
    """The first cue found in the text as a whole word or phrase."""
    low = text.lower()
    for cue in cues:
        c = cue.strip().lower()
        if c and re.search(rf"(?<![a-z0-9]){re.escape(c)}(?![a-z0-9])", low):
            return cue
    return None


# --- The facts ---


@dataclass
class Build:
    root: Path
    case: CaseDetail
    docs: list[Doc]
    align: AlignmentSection
    name_threshold: float
    emi_tolerance_pct: float
    emi_min: int
    message_doc: str | None
    header: dict
    out: dict = field(default_factory=dict)

    @property
    def start(self) -> int:
        return self.align.financial_year_start_month

    @property
    def noise(self) -> list[str]:
        return [w.lower() for w in self.align.name_noise_words]

    def of_type(self, *type_ids: str) -> list[Doc]:
        return [d for d in self.docs if any(t in d.types for t in type_ids)]

    def primary(self, d: Doc) -> str:
        return d.types[0]

    def message_value(self, name: str) -> FactValue | None:
        h = self.header.get(name) or {}
        if not h.get("value"):
            return None
        evidence = [Evidence(document_id=self.message_doc, page=1)] if self.message_doc else []
        return FactValue(
            source="application_message",
            label="Sourcing message",
            value=h["value"],
            evidence=evidence,
            relies_on_manual=h.get("source") == "person" or (h.get("proposed") not in (None, h["value"])),
        )


def _identities(b: Build) -> IdentityFacts:
    facts = IdentityFacts()
    for d in b.docs:
        pan = d.get(*PAN_FIELDS) if not set(d.types) & PERSON_DOCS else None
        if pan:
            facts.entity_pan.append(_fv(d, pan, str(pan.value).strip().upper().replace(" ", "")))
        gstin = d.get(*GSTIN_FIELDS)
        if gstin:
            facts.gstin.append(_fv(d, gstin, str(gstin.value).strip().upper().replace(" ", "")))
        if not set(d.types) & PERSON_DOCS:
            name = d.get(*NAME_FIELDS)
            if name:
                facts.legal_name.append(_fv(d, name, str(name.value).strip()))
    for key, target in (("pan", facts.entity_pan), ("gstin", facts.gstin)):
        v = b.message_value(key)
        if v:
            v.value = str(v.value).strip().upper()
            target.append(v)
    return facts


def _fv(d: Doc, v: Value, value: str | float | None) -> FactValue:
    return FactValue(
        source=d.types[0],
        label=d.label,
        value=value,
        evidence=d.evidence(v),
        field_ids=[v.field_id],
        relies_on_manual=v.manual,
    )


def _persons(b: Build) -> list[PersonSet]:
    sets: list[PersonSet] = []
    for d in b.docs:
        for type_id in d.types:
            if type_id not in PARTY_TABLES:
                continue
            table, _role = PARTY_TABLES[type_id]
            rows = [r for r in d.rows(table) if r.get("name") and r["name"].value]
            if rows:
                sets.append(
                    PersonSet(
                        source=type_id,
                        label=d.label,
                        names=[str(r["name"].value).strip() for r in rows],
                        evidence=d.evidence(*(r["name"] for r in rows[:1])),
                        relies_on_manual=any(r["name"].manual for r in rows),
                    )
                )
    kyc = [d for d in b.docs if set(d.types) & KYC_TYPES]
    kyc_names, kyc_evidence, kyc_manual = [], [], False
    for d in kyc:
        name = d.get("name", "holder_name", "full_name")
        if name:
            kyc_names.append(str(name.value).strip())
            kyc_evidence += d.evidence(name)
            kyc_manual = kyc_manual or name.manual
    if kyc_names:
        sets.append(PersonSet(source="kyc_pan_individual", label="KYC received", names=kyc_names,
                              evidence=kyc_evidence, relies_on_manual=kyc_manual))
    promoters = b.message_value("promoters")
    if promoters:
        sets.append(
            PersonSet(
                source="application_message",
                label="Sourcing message",
                names=[n.strip() for n in str(promoters.value).split(";") if n.strip()],
                evidence=promoters.evidence,
                relies_on_manual=promoters.relies_on_manual,
            )
        )
    return sets


def _transactions(b: Build) -> tuple[list[Txn], dict[str, set[tuple[int, int]]]]:
    """Every statement transaction, and the months each account's statements cover."""
    txns: list[Txn] = []
    coverage: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for d in b.of_type("bank_statement"):
        bank = str((d.get("bank").value if d.get("bank") else "") or "Bank")
        last4 = _last4(d.get("account_number_masked", "account_number").value if d.get("account_number_masked", "account_number") else None)
        account = _account_label(bank, last4)
        start = parse_date(d.get("period_from").value) if d.get("period_from") else None
        end = parse_date(d.get("period_to").value) if d.get("period_to") else None
        rows = d.rows("transactions")
        if start and end:
            ym = (start.year, start.month)
            while ym <= (end.year, end.month):
                coverage[account].add(ym)
                ym = month_add(*ym, 1)
        for r in rows:
            debit, credit = _amount(r.get("debit")), _amount(r.get("credit"))
            if not debit and not credit:
                continue
            when = parse_date(r["date"].value) if r.get("date") else None
            if when and not (start and end):
                coverage[account].add((when.year, when.month))
            txns.append(
                Txn(
                    account=account,
                    date=when,
                    narration=str(r["narration"].value) if r.get("narration") else "",
                    debit=debit,
                    credit=credit,
                    evidence=d.evidence(r.get("credit") or r.get("debit"), r.get("narration")),
                    doc=d,
                )
            )
    return txns, coverage


def _accounts(b: Build, txns: list[Txn]) -> tuple[list[AccountFact], bool]:
    """The account set (F-18.5): statements, the declaration, partner
    analyses and accounts named in transfer narrations."""
    found: dict[tuple[str, str | None], AccountFact] = {}

    def add(bank: str, last4: str | None, source: str, evidence: list[Evidence], *, declared: bool = False,
            statement: bool = False) -> None:
        key = next(
            (k for k in found if (last4 and k[1] == last4 and (not bank or same_entity(bank, k[0], b.noise, b.name_threshold)))
             or (not last4 and not k[1] and same_entity(bank, k[0], b.noise, b.name_threshold))),
            None,
        )
        if key is None:
            key = (bank, last4)
            found[key] = AccountFact(bank=bank, last4=last4, label=_account_label(bank or "Account", last4),
                                     sources=[], declared=False, has_statement=False, evidence=[])
        fact = found[key]
        if source not in fact.sources:
            fact.sources.append(source)
        fact.declared = fact.declared or declared
        fact.has_statement = fact.has_statement or statement
        fact.evidence += evidence[:1]

    for d in b.of_type("bank_statement"):
        bank = str(d.get("bank").value) if d.get("bank") else ""
        acct = d.get("account_number_masked", "account_number")
        add(bank, _last4(acct.value if acct else None), d.label, d.evidence(acct), statement=True)
    declarations = b.of_type("existing_facilities_declaration")
    for d in declarations:
        for r in d.rows("accounts"):
            bank = str(r["bank"].value) if r.get("bank") else ""
            acct = r.get("account_number_masked") or r.get("account_number")
            add(bank, _last4(acct.value if acct else None), d.label, d.evidence(acct or r.get("bank")), declared=True)
    for field_name in ("existing_banking",):
        v = b.message_value(field_name)
        if v and isinstance(v.value, str):
            for m in re.finditer(r"(?:a/?c|account)[^\d]{0,12}(\d{4,})", v.value, re.I):
                add("", _last4(m[1]), "Sourcing message", v.evidence, declared=True)
    for d in b.of_type("partner_bank_analysis"):
        for r in d.rows("accounts"):
            bank = str(r["bank"].value) if r.get("bank") else ""
            acct = r.get("account_number_masked")
            add(bank, _last4(acct.value if acct else None), d.label, d.evidence(acct or r.get("bank")))
    own = {k[1] for k in found if k[1]}
    for t in txns:
        for m in re.finditer(r"(?:a/?c|acct|account|x{2,})[^\d]{0,6}(\d{4,})", t.narration, re.I):
            last4 = _last4(m[1])
            if last4 and last4 not in own and _phrase(t.narration, ["transfer", "trf", "neft", "rtgs", "imps", "self"]):
                add("", last4, f"Transfer in {t.account}", t.evidence)
    return list(found.values()), bool(declarations)


def _cleanse(b: Build, txns: list[Txn], accounts: list[AccountFact]) -> tuple[list[AccountCredits], dict[str, dict]]:
    """Credits less the configured exclusions (F-18.2), by account and month."""
    own_last4 = {a.last4 for a in accounts if a.last4}
    borrower = normalise_name(b.case.borrower)
    per_account: dict[str, AccountCredits] = {}
    net_by_month: dict[tuple[int, int], float] = defaultdict(float)
    evidence_by_month: dict[tuple[int, int], list[Evidence]] = defaultdict(list)
    for t in txns:
        if not t.credit:
            continue
        acct = per_account.setdefault(
            t.account, AccountCredits(account=t.account, gross=0, excluded=0, net=0, months=[], exclusions=[])
        )
        acct.gross += t.credit
        rule = None
        for ex in b.align.bank_credit_exclusions:
            cue = _phrase(t.narration, ex.narration_any)
            if ex.own_account:
                digits = {_last4(m) for m in re.findall(r"\d{4,}", t.narration)}
                names_borrower = borrower and borrower.split()[0] in normalise_name(t.narration)
                if (digits & own_last4 - {t.account.split("·")[-1]}) or (cue and names_borrower):
                    rule = ex
                    break
            elif cue:
                rule = ex
                break
        if rule:
            acct.excluded += t.credit
            acct.exclusions.append(
                Exclusion(rule=rule.id, label=rule.label, account=t.account,
                          date=t.date.isoformat() if t.date else None, narration=t.narration, amount=t.credit,
                          evidence=t.evidence)
            )
            continue
        acct.net += t.credit
        if t.date:
            ym = (t.date.year, t.date.month)
            net_by_month[ym] += t.credit
            evidence_by_month[ym] += t.evidence[:1]
            label = month_label(ym)
            if label not in acct.months:
                acct.months.append(label)
    return list(per_account.values()), {"net": net_by_month, "evidence": evidence_by_month}


def _obligations(b: Build, txns: list[Txn]) -> list[Obligation]:
    """Recurring debits to a lender (F-18.4): an instalment cue, the same
    counterparty in enough months, amounts within the EMI tolerance."""
    candidates: dict[tuple[str, str], list[Txn]] = defaultdict(list)
    for t in txns:
        if not t.debit or not _phrase(t.narration, b.align.obligation_narration_any):
            continue
        party = _counterparty(t.narration, b.align.obligation_narration_any)
        if not party:
            continue
        key = next((k for k in candidates if k[1] == t.account and same_entity(party, k[0], b.noise, b.name_threshold)),
                   (party, t.account))
        candidates[key].append(t)
    out: list[Obligation] = []
    for (party, account), debits in candidates.items():
        months = sorted({(t.date.year, t.date.month) for t in debits if t.date})
        amounts = sorted(t.debit for t in debits)
        typical = amounts[len(amounts) // 2]
        steady = [a for a in amounts if abs(a - typical) <= typical * b.emi_tolerance_pct / 100]
        if len(months) < b.emi_min or len(steady) < b.emi_min:
            continue
        variants = sorted({_counterparty(t.narration, b.align.obligation_narration_any) or party for t in debits})
        out.append(
            Obligation(lender=party, variants=variants, account=account, months=[month_label(m) for m in months],
                       typical_amount=typical, debits=len(debits),
                       evidence=[e for t in debits[:3] for e in t.evidence[:1]])
        )
    return out


def _counterparty(narration: str, cues: list[str]) -> str | None:
    """The name in an instalment narration, without cues, references and digits:
    "NACH DR LOTUSCREST FIN 000123 EMI" -> "LOTUSCREST FIN"."""
    text = narration
    for cue in sorted(cues, key=len, reverse=True):
        text = re.sub(re.escape(cue.strip()), " ", text, flags=re.I)
    text = re.sub(r"[^A-Za-z& ]+", " ", text)
    text = re.sub(r"\b(dr|cr|to|by|debit|payment|repayment|inst|instalment|installment|ref|no|umrn|mandate)\b", " ",
                  text, flags=re.I)
    words = [w for w in text.split() if len(w) > 1]
    return " ".join(words[:4]).strip() or None


def _facilities(b: Build) -> list[FacilityFact]:
    out: list[FacilityFact] = []
    for d in b.of_type("existing_facilities_declaration"):
        if d.get("nil_declared") and d.get("nil_declared").value is True and not d.rows("facilities"):
            continue
        for r in d.rows("facilities"):
            if r.get("lender") and r["lender"].value:
                out.append(_facility(d, r, "lender", "facility", ("limit", "outstanding"), "emi"))
    for d in b.of_type("sanction_letter_other_lender"):
        if d.get("lender"):
            row = {k: v for k, v in d.fields.items() if "[" not in k}
            out.append(_facility(d, row, "lender", "facility", ("sanctioned_amount",), "emi"))
    for d in b.of_type("bureau_commercial"):
        for r in d.rows("facilities"):
            status = str(r["status"].value).lower() if r.get("status") else ""
            if r.get("lender") and r["lender"].value and "closed" not in status:
                out.append(_facility(d, r, "lender", "facility_type", ("sanctioned", "outstanding"), "emi"))
    return out


def _facility(d: Doc, r: dict[str, Value], lender: str, kind: str, amounts: tuple[str, ...], emi: str) -> FacilityFact:
    amount = next((r[a] for a in amounts if r.get(a) and r[a].value not in (None, "")), None)
    return FacilityFact(
        source=d.types[0],
        label=d.label,
        lender=str(r[lender].value).strip(),
        facility=str(r[kind].value) if r.get(kind) and r[kind].value else None,
        amount=_amount(amount) or None,
        emi=_amount(r.get(emi)) or None,
        evidence=d.evidence(r.get(lender)),
        relies_on_manual=any(v.manual for v in r.values()),
    )


def _turnover(b: Build, credits_by_month: dict, coverage: dict[str, set[tuple[int, int]]]) -> list[TurnoverYear]:
    years: dict[int, list[TurnoverFigure]] = defaultdict(list)
    start = b.start

    # Audited financial statements: revenue from operations for the year.
    for d in b.of_type("audited_financial_statements"):
        end = d.get("period_end")
        revenue = d.get("revenue_from_operations", "turnover", "revenue")
        when = parse_date(end.value) if end else None
        if not (when and revenue):
            continue
        years[fy_of(when.year, when.month, start)].append(TurnoverFigure(source="financials", label="Audited financial statements",
                                        value=_amount(revenue), evidence=d.evidence(revenue),
                                        field_ids=[revenue.field_id], relies_on_manual=revenue.manual))

    # GST: outward taxable supplies per return period (GSTR-3B first, then a partner report).
    gst: dict[tuple[int, int], tuple[float, Doc, Value]] = {}
    for d in b.of_type("gstr_3b"):
        period = parse_period(d.get("period").value) if d.get("period") else None
        supplies = d.get("outward_taxable_supplies")
        if period and supplies and period not in gst:
            gst[period] = (_amount(supplies), d, supplies)
    for d in b.of_type("partner_gst_report"):
        for r in d.rows("periods"):
            period = parse_period(r["period"].value) if r.get("period") else None
            if period and r.get("turnover") and period not in gst:
                gst[period] = (_amount(r["turnover"]), d, r["turnover"])
    for fy in sorted({fy_of(y, m, start) for (y, m) in gst}):
        months = fy_months(fy, start)
        present = [m for m in months if m in gst]
        values = [gst[m] for m in present]
        years[fy].append(TurnoverFigure(
            source="gst", label="GST outward supplies", value=sum(v[0] for v in values),
            months_covered=len(present), months_missing=[month_label(m) for m in months if m not in gst],
            evidence=[e for v in values[:12] for e in v[1].evidence(v[2])[:1]],
            field_ids=[v[2].field_id for v in values], relies_on_manual=any(v[2].manual for v in values)))

    # Bank: cleansed credits; a month counts as covered when every account's statements cover it.
    if coverage:
        covered = set.intersection(*coverage.values())
        net = credits_by_month["net"]
        for fy in sorted({fy_of(y, m, start) for (y, m) in covered}):
            months = fy_months(fy, start)
            present = [m for m in months if m in covered]
            years[fy].append(TurnoverFigure(
                source="bank", label="Business credits in bank statements", value=sum(net.get(m, 0.0) for m in present),
                months_covered=len(present), months_missing=[month_label(m) for m in months if m not in covered],
                evidence=[e for m in present for e in credits_by_month["evidence"].get(m, [])[:1]][:12]))

    # The RM's declared turnover: taken as the latest financial year ended before as_of.
    declared = b.message_value("declared_turnover_inr")
    if declared:
        as_of = date.fromisoformat(b.case.as_of)
        latest = fy_of(as_of.year, as_of.month, start) - 1
        try:
            value = float(str(declared.value).replace(",", ""))
        except ValueError:
            value = None
        years[latest].append(TurnoverFigure(source="declared", label="Turnover declared in the sourcing message",
                                            value=value, evidence=declared.evidence,
                                            relies_on_manual=declared.relies_on_manual))

    return [
        TurnoverYear(fy=fy_name(fy, start), fy_end=fy_end_date(fy, start).isoformat(), figures=figs)
        for fy, figs in sorted(years.items(), reverse=True)
    ]


def compute(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> CaseFacts:
    tolerances = {t.key: t.value for t in reader.load_tolerances(root).tolerances}
    row = conn.execute(
        "SELECT d.id FROM documents d JOIN files f ON f.id = d.file_id WHERE d.case_id = ? AND f.original_name = ?",
        (case.id, MESSAGE_FILE_NAME),
    ).fetchone()
    header_row = conn.execute("SELECT header FROM cases WHERE id = ?", (case.id,)).fetchone()
    b = Build(
        root=root,
        case=case,
        docs=load_documents(conn, root, case.id),
        align=reader.load_alignment(root),
        name_threshold=tolerances.get("name_match", 0.85),
        emi_tolerance_pct=tolerances.get("emi_amount_match", 5),
        emi_min=int(tolerances.get("emi_min_occurrences", 3)),
        message_doc=row["id"] if row else None,
        header=json.loads(header_row["header"] or "{}") if header_row else {},
    )
    txns, coverage = _transactions(b)
    accounts, declared = _accounts(b, txns)
    credits, by_month = _cleanse(b, txns, accounts)
    return CaseFacts(
        case_id=case.id,
        identities=_identities(b),
        persons=_persons(b),
        turnover=_turnover(b, by_month, coverage),
        credits=credits,
        obligations=_obligations(b, txns),
        accounts=accounts,
        facilities=_facilities(b),
        declaration_received=declared,
    )


def inr(value: float | None) -> str:
    """An amount as the screens write it: INR 5.16 cr, INR 95.00 lakh, INR 12,000."""
    if value is None:
        return "—"
    if abs(value) >= 1e7:
        return f"INR {value / 1e7:.2f} cr"
    if abs(value) >= 1e5:
        return f"INR {value / 1e5:.2f} lakh"
    return f"INR {format_inr(value)}"
