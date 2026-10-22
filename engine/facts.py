"""Fact alignment: extracted fields made comparable (FRD F-18).

Read-only over the case's field values. A person's correction wins over the
value read (the effective value), and a value entered or corrected by a
person is flagged (F-19.4). Every fact keeps the field-value ids and the
evidence it came from (F-18.6), so a finding can point at both sides.

A value still waiting for review is carried with `awaiting_review`, so a
check that would rely on it waits for the person (F-17.2).

- Identities (PAN, GSTIN, legal name, CIN) by document; the PAN inside each
  GSTIN counts as a statement of the entity's PAN.
- Promoter sets by source, each person with the DIN and PAN printed there.
- Incorporation, the board resolution's terms, income tax returns and the
  audited statements by year (both columns), for the identity, authority,
  tax and statement checks.
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
    AccountMonth,
    AuthorityFact,
    BalanceFact,
    CaseDetail,
    CaseFacts,
    Evidence,
    Exclusion,
    FacilityFact,
    FactValue,
    FinancialYear,
    IdentityFacts,
    IncorporationFact,
    MonthFigure,
    Obligation,
    PersonEntry,
    PersonSet,
    TaxYear,
    TurnoverFigure,
    TurnoverYear,
)
from .names import normalise_name, similarity
from . import statements
from .parties import party_list_spec
from .pipeline import effective_types
from .store import MESSAGE_FILE_NAME
from .txn_intel import Context, Txn as IntelTxn
from .txn_labels import Final, label_case, load_state
from .util import assessment_year_start, format_inr, month_add, month_label, parse_date, parse_period, period_months

USABLE = {"accepted", "in_review", "extracted", "classified"}

# Where each identity is read, by field name (first found wins per document).
PAN_FIELDS = ("pan",)
GSTIN_FIELDS = ("gstin",)
NAME_FIELDS = ("legal_name", "company_name", "taxpayer_name", "account_holder_name", "borrower_name")
CIN_FIELDS = ("cin",)
# Where existing facilities are recorded (OB-01, OB-02).
DECLARATION = "existing_facilities_declaration"
SANCTION = "sanction_letter"
BUREAU = "commercial_bureau_report"
# Document types whose names and PAN are a person's, not the entity's.
PERSON_DOCS = {"director_kyc"}
KYC_TYPES = {"director_kyc"}
# The statement lines the year-on-year and bank checks read (FS-01, FS-02, OB-03).
YEAR_LINES = ("revenue_from_operations", "profit_before_tax", "profit_after_tax", "net_worth", "total_borrowings",
              "long_term_borrowings", "finance_costs", "cash_and_bank_balances")
MESSAGE = "application_message"
# What the sourcing message may say an account or a facility is, as in "cash credit with Lotuscrest
# Bank a/c 90100005678"; a short form stands for its full name.
BANKING_KINDS = {"current account": None, "savings account": None, "escrow account": None, "cash credit": None,
                 "overdraft": None, "working capital demand loan": None, "working capital loan": None,
                 "term loan": None, "packing credit": None, "bill discounting": None, "letter of credit": None,
                 "bank guarantee": None, "equipment loan": None, "vehicle loan": None, "loan against property": None,
                 "cc": "cash credit", "od": "overdraft", "tl": "term loan"}
DEPOSIT_KINDS = {"current account", "savings account", "escrow account"}
_KINDS = "|".join(re.escape(k) for k in sorted(BANKING_KINDS, key=len, reverse=True))
_BANKING = re.compile(rf"\b(?P<kind>{_KINDS})\b(?:\s+(?:with|from|at)\s+(?P<bank>[A-Za-z][\w&.'\- ]*?))?"
                      rf"(?:[.,]?\s+(?:a/?c|acct|account)\.?\s*(?:no\.?\s*)?(?P<number>\d{{4,}}))?"
                      rf"(?=\s*(?:$|[;,]|\band\s+(?:an?\s+|the\s+)?(?:{_KINDS})\b|\.(?:\s|$)))", re.I)
MESSAGE_ACCOUNT = re.compile(r"(?:a/?c|account)[^\d]{0,12}(\d{4,})", re.I)
# An account a statement narration names: "NEFT TRANSFER TO A/C 778899001122".
NARRATION_ACCOUNT = re.compile(r"(?:a/?c|acct|account|x{2,})[^\d]{0,6}(\d{4,})", re.I)


# --- Loading ---


@dataclass
class Value:
    field_id: str
    value: object
    evidence: dict | None
    manual: bool
    pending: bool = False
    """Still waiting for a person's review (F-17.2)."""
    raw: str | None = None
    """The text as the document prints it ("3,586", "-")."""


@dataclass
class StatementEdit:
    """A person's figure for a statement line, in the unit the statement prints (see statement_edits)."""

    id: str
    line: str
    column: str
    original: float | None
    value: float
    reason: str
    edited_by: str
    edited_at: str


@dataclass
class Doc:
    id: str
    types: list[str]
    type_names: list[str]
    page_from: int
    fields: dict[str, Value]
    party_id: str | None = None
    edits: dict[tuple[str, str], StatementEdit] = field(default_factory=dict)
    """The live edits of this document's statement lines, by line and column."""

    @property
    def label(self) -> str:
        return " + ".join(self.type_names)

    def get(self, *names: str) -> Value | None:
        for name in names:
            v = self.fields.get(name)
            if v is not None and v.value not in (None, ""):
                return v
        return None

    def list(self, name: str) -> list[Value]:
        """The elements of a plain list field, stored as name[0], name[1], ..."""
        pattern = re.compile(rf"^{re.escape(name)}\[(\d+)\]$")
        found = [(int(m[1]), v) for k, v in self.fields.items() if (m := pattern.match(k))]
        return [v for _, v in sorted(found, key=lambda p: p[0])]

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
            "SELECT id, field, value, corrected_value, status, evidence, method, raw FROM field_values WHERE document_id = ?",
            (row["id"],),
        ):
            if fv["status"] in ("missing", "rejected"):
                continue
            fields[fv["field"]] = Value(
                field_id=fv["id"],
                value=_effective(fv),
                evidence=json.loads(fv["evidence"]) if fv["evidence"] else None,
                manual=fv["method"] == "manual" or fv["status"] == "corrected",
                pending=fv["status"] == "in_review",
                raw=fv["raw"],
            )
        edits = {
            (e["line"], e["column_name"]): StatementEdit(e["id"], e["line"], e["column_name"], e["original"], e["value"],
                                                          e["reason"], e["edited_by"], e["edited_at"])
            for e in conn.execute(
                "SELECT * FROM statement_edits WHERE document_id = ? AND superseded_at IS NULL", (row["id"],))
        }
        docs.append(
            Doc(
                id=row["id"],
                types=doc_types,
                type_names=[types.get(t, t.replace("_", " ")) for t in doc_types],
                page_from=row["page_from"],
                fields=fields,
                party_id=row["party_id"] if "party_id" in row.keys() else None,
                edits=edits,
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


def same_lender(a: str, b: str, noise: list[str], threshold: float) -> bool:
    """One lender under two printings ("Tidewater Finance Limited", "TIDEWATER FIN"): the same
    resolved name, or the same leading significant word."""
    if same_entity(a, b, noise, threshold):
        return True
    ra, rb = resolve_name(a, noise).split(), resolve_name(b, noise).split()
    return bool(ra and rb) and ra[0] == rb[0] and len(ra[0]) >= 4


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
    balance: float | None = None
    reference: str = ""
    """The bank's reference for the entry, as printed."""
    ref: str = ""
    """The id of the row's description cell: a key that survives a rerun of the same extraction."""
    seq: int = 0
    """The row's place in its statement."""


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


def banking_named(text: str | None) -> list[tuple[str, str, str | None]]:
    """What the sourcing message says of the existing banking, clause by clause: (kind, bank, last four
    digits) for "cash credit with Lotuscrest Bank a/c 90100005678"; the bank or the number may be absent."""
    out = []
    for m in _BANKING.finditer(text or ""):
        kind = m["kind"].lower()
        out.append((BANKING_KINDS[kind] or kind, (m["bank"] or "").strip(), _last4(m["number"])))
    return out


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
        return FactValue(
            source="application_message",
            label="Sourcing message",
            value=h["value"],
            evidence=self.header_evidence(h.get("source")),
            relies_on_manual=h.get("source") == "person" or (h.get("proposed") not in (None, h["value"])),
        )

    def header_evidence(self, source: str | None) -> list[Evidence]:
        """Where a header value came from (HeaderField.source): a span in the sourcing message, a
        document page, or a person, who has no page to cite."""
        found = re.fullmatch(r"document:(.+):p(\d+)", source or "")
        if found:
            return [Evidence(document_id=found[1], page=int(found[2]))]
        if source == "person" or not self.message_doc:
            return []
        return [Evidence(document_id=self.message_doc, page=1)]


def _ident(value: object) -> str:
    return str(value).strip().upper().replace(" ", "")


def _identities(b: Build) -> IdentityFacts:
    facts = IdentityFacts()
    for d in b.docs:
        pan = d.get(*PAN_FIELDS) if not set(d.types) & PERSON_DOCS else None
        if pan:
            facts.entity_pan.append(_fv(d, pan, _ident(pan.value)))
        gstin = d.get(*GSTIN_FIELDS)
        if gstin:
            number = _ident(gstin.value)
            facts.gstin.append(_fv(d, gstin, number))
            # Characters 3 to 12 of a GSTIN are the holder's PAN (ID-01).
            if len(number) == 15 and not set(d.types) & PERSON_DOCS:
                derived = _fv(d, gstin, number[2:12])
                derived.label = f"{d.label} (PAN within the GSTIN)"
                facts.entity_pan.append(derived)
        cin = d.get(*CIN_FIELDS)
        if cin and not set(d.types) & PERSON_DOCS:
            facts.cin.append(_fv(d, cin, _ident(cin.value)))
        if not set(d.types) & PERSON_DOCS:
            name = d.get(*NAME_FIELDS)
            if name:
                facts.legal_name.append(_fv(d, name, str(name.value).strip()))
    for key, target in (("pan", facts.entity_pan), ("gstin", facts.gstin), ("cin", facts.cin)):
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
        awaiting_review=v.pending,
    )


def _line_fv(d: Doc, line: statements.Line) -> FactValue:
    return FactValue(source=d.types[0], label=d.label, value=line.value, evidence=line.evidence,
                     field_ids=line.field_ids, relies_on_manual=line.manual, awaiting_review=line.pending)


def _persons(b: Build) -> list[PersonSet]:
    sets: list[PersonSet] = []
    types = {t.id: t for t in reader.load_document_types(b.root).types}
    for d in b.docs:
        for type_id in d.types:
            spec = party_list_spec(types.get(type_id))
            if spec is None:
                continue
            entries: list[PersonEntry] = []
            if spec.name_key:
                for r in d.rows(spec.field):
                    name = r.get(spec.name_key)
                    if not (name and name.value):
                        continue
                    din = r.get(spec.din_key) if spec.din_key else None
                    pan = r.get(spec.pan_key) if spec.pan_key else None
                    title = r.get(spec.designation_key) if spec.designation_key else None
                    entries.append(PersonEntry(
                        name=str(name.value).strip(), din=_ident(din.value) if din and din.value else None,
                        pan=_ident(pan.value) if pan and pan.value else None,
                        role=str(title.value).strip() if title and title.value else spec.role,
                        evidence=d.evidence(name), relies_on_manual=name.manual,
                        awaiting_review=name.pending or bool(din and din.pending) or bool(pan and pan.pending)))
            else:
                for v in d.list(spec.field):
                    if v.value:
                        entries.append(PersonEntry(name=str(v.value).strip(), role=spec.role, evidence=d.evidence(v),
                                                   relies_on_manual=v.manual, awaiting_review=v.pending))
            if entries:
                sets.append(PersonSet(source=type_id, label=d.label, names=[e.name for e in entries],
                                      evidence=entries[0].evidence,
                                      relies_on_manual=any(e.relies_on_manual for e in entries), entries=entries))
    kyc_entries: list[PersonEntry] = []
    for d in b.docs:
        if not set(d.types) & KYC_TYPES:
            continue
        name = d.get("person_name")
        if not name:
            continue
        din, pan = d.get("din"), d.get("pan")
        kyc_entries.append(PersonEntry(
            name=str(name.value).strip(), din=_ident(din.value) if din else None, pan=_ident(pan.value) if pan else None,
            role=str(d.get("designation").value) if d.get("designation") else "director",
            evidence=d.evidence(name), relies_on_manual=name.manual or bool(din and din.manual),
            awaiting_review=name.pending or bool(din and din.pending) or bool(pan and pan.pending)))
    if kyc_entries:
        sets.append(PersonSet(source="director_kyc", label="KYC received", names=[e.name for e in kyc_entries],
                              evidence=[e for k in kyc_entries for e in k.evidence[:1]],
                              relies_on_manual=any(k.relies_on_manual for k in kyc_entries), entries=kyc_entries))
    promoters = b.message_value("promoters")
    if promoters:
        sets.append(
            PersonSet(
                source="application_message",
                label="Sourcing message",
                names=[n.strip() for n in str(promoters.value).split(";") if n.strip()],
                evidence=promoters.evidence,
                relies_on_manual=promoters.relies_on_manual,
                entries=[PersonEntry(name=n.strip(), evidence=promoters.evidence, relies_on_manual=promoters.relies_on_manual)
                         for n in str(promoters.value).split(";") if n.strip()],
            )
        )
    return sets


def _number(v: Value | None) -> float | None:
    return _amount(v) if v is not None and v.value not in (None, "") else None


def _facility(d: Doc, lender: str, row: dict[str, Value], anchor: Value) -> FacilityFact:
    facility = row.get("facility")
    used = [v for v in row.values() if v is not None] + [anchor]
    return FacilityFact(
        source=d.types[0], label=d.label, lender=lender,
        facility=str(facility.value).strip() if facility and facility.value else None,
        amount=_number(row.get("sanctioned_amount")), emi=_number(row.get("emi")),
        outstanding=_number(row.get("outstanding")), overdue=_number(row.get("overdue")),
        evidence=d.evidence(row.get("sanctioned_amount") or anchor),
        relies_on_manual=any(v.manual for v in used), awaiting_review=any(v.pending for v in used),
    )


def _facilities(b: Build) -> list[FacilityFact]:
    """Existing facilities as the declaration, each sanction letter and the bureau record them (OB-01)."""
    out: list[FacilityFact] = []
    for d in b.of_type(DECLARATION):
        for r in d.rows("facilities"):
            lender = r.get("lender")
            if lender and lender.value:
                out.append(_facility(d, str(lender.value).strip(), r, lender))
    for d in b.of_type(SANCTION):
        lender = d.get("lender_name")
        if lender:
            for r in d.rows("facilities") or [{}]:
                out.append(_facility(d, str(lender.value).strip(), r, lender))
    for d in b.of_type(BUREAU):
        for r in d.rows("credit_facilities"):
            lender = r.get("lender")
            if lender and lender.value:
                out.append(_facility(d, str(lender.value).strip(), r, lender))
    # A facility the sourcing message names with its lender ("cash credit with Lotuscrest Bank"); its
    # limit is not stated there. The checks compare the documents only (OB-01 reads the message as text).
    message = b.message_value("existing_banking")
    if message and isinstance(message.value, str):
        seen: set[tuple[str, str]] = set()
        for kind, bank, _ in banking_named(message.value):
            if kind in DEPOSIT_KINDS or not bank or (bank.casefold(), kind) in seen:
                continue
            seen.add((bank.casefold(), kind))
            out.append(FacilityFact(source=MESSAGE, label=message.label, lender=bank, facility=kind[:1].upper() + kind[1:],
                                    evidence=message.evidence, relies_on_manual=message.relies_on_manual))
    return out


def _declaration(b: Build) -> FactValue | None:
    """The declaration of existing facilities: the lenders it declares, or that it declares none."""
    docs = b.of_type(DECLARATION)
    if not docs:
        return None
    d = docs[0]
    lenders = [str(r["lender"].value).strip() for r in d.rows("facilities") if r.get("lender") and r["lender"].value]
    anchor = d.get("company_name", "declaration_date")
    return FactValue(source=DECLARATION, label=d.label, value="; ".join(lenders) if lenders else "None declared",
                     evidence=d.evidence(anchor), field_ids=[anchor.field_id] if anchor else [],
                     relies_on_manual=bool(anchor and anchor.manual), awaiting_review=bool(anchor and anchor.pending))


def _requested(b: Build) -> FactValue | None:
    """The amount requested, as the case records it, with the message as its evidence."""
    if not b.case.amount_inr:
        return None
    v = b.message_value("amount_inr")
    evidence = v.evidence if v else ([Evidence(document_id=b.message_doc, page=1)] if b.message_doc else [])
    return FactValue(source="application_message", label="Amount requested", value=float(b.case.amount_inr),
                     evidence=evidence, relies_on_manual=bool(v and v.relies_on_manual))


def _proposed_emi(b: Build) -> FactValue | None:
    """The proposed term loan's monthly instalment, as the RM entered it on the case (FR-03)."""
    v = b.message_value("proposed_emi_inr")
    if v is None:
        return None
    try:
        v.value = float(str(v.value).replace(",", ""))
    except ValueError:
        return None
    v.label = "Proposed monthly instalment"
    return v


def _incorporation(b: Build) -> IncorporationFact:
    fact = IncorporationFact()
    for d in b.of_type("certificate_of_incorporation"):
        when, kind = d.get("date_of_incorporation"), d.get("company_type")
        if when and fact.date_of_incorporation is None:
            fact.date_of_incorporation = _fv(d, when, str(when.value))
        if kind and fact.company_type is None:
            fact.company_type = _fv(d, kind, str(kind.value))
    return fact


def _authority(b: Build) -> list[AuthorityFact]:
    """Each board resolution's terms: the limit, the lender, the date, the signatories."""
    out = []
    for d in b.of_type("board_resolution_borrowing"):
        limit, lender, when = d.get("borrowing_limit"), d.get("lender_name"), d.get("resolution_date")
        signatories: list[PersonEntry] = []
        for name in ("authorized_signatories", "authorized_persons"):
            for v in d.list(name):
                text = str(v.value or "").strip()
                if text and not any(normalise_name(text) == normalise_name(s.name) for s in signatories):
                    signatories.append(PersonEntry(name=text, evidence=d.evidence(v), relies_on_manual=v.manual,
                                                   awaiting_review=v.pending))
        amount = _amount(limit) if limit else None
        out.append(AuthorityFact(
            document_id=d.id, label=d.label,
            borrowing_limit=_fv(d, limit, amount) if limit and amount else None,
            lender=_fv(d, lender, str(lender.value).strip()) if lender else None,
            resolution_date=_fv(d, when, str(when.value)) if when else None,
            signatories=signatories,
        ))
    return out


def _tax_years(b: Build) -> list[TaxYear]:
    cfg = reader.load_statements(b.root)
    out: dict[str, TaxYear] = {}
    for d in b.of_type("income_tax_return"):
        ay = d.get("assessment_year")
        start = assessment_year_start(ay.value) if ay else None
        if not start:
            continue
        end = date(start, 3, 31)
        fy = fy_name(fy_of(end.year, end.month, b.start), b.start)
        year = out.setdefault(fy, TaxYear(assessment_year=f"{start}-{str(start + 1)[2:]}", fy=fy,
                                          fy_end=end.isoformat(), evidence=d.evidence(ay)))
        for key, line in statements.itr_lines(d, cfg).items():
            year.lines.setdefault(key, _line_fv(d, line))
        total = d.get("total_income")
        if total and "total_income" not in year.lines:
            year.lines["total_income"] = _fv(d, total, _amount(total))
    return sorted(out.values(), key=lambda y: y.fy_end, reverse=True)


def _financial_years(b: Build) -> list[FinancialYear]:
    """Each audited year's lines, its own column and the comparative column."""
    cfg = reader.load_statements(b.root)
    out: dict[str, FinancialYear] = {}
    for d in b.of_type("audited_financial_statements"):
        end = statements.period_end(d)
        if not end:
            continue
        fy_year = fy_of(end.year, end.month, b.start)
        fy = fy_name(fy_year, b.start)
        if fy in out:
            continue
        current = statements.lines(d, cfg)
        previous = statements.lines(d, cfg, column="previous_period")
        out[fy] = FinancialYear(
            fy=fy, fy_end=fy_end_date(fy_year, b.start).isoformat(), label=d.label,
            current={k: _line_fv(d, v) for k, v in current.items() if k in YEAR_LINES},
            previous={k: _line_fv(d, v) for k, v in previous.items() if k in YEAR_LINES},
        )
    return sorted(out.values(), key=lambda y: y.fy_end, reverse=True)


def _balances(b: Build, txns: list[Txn], years: list[FinancialYear]) -> list[BalanceFact]:
    """Each account's balance on each audited year end its statements cover (FS-02)."""
    out = []
    for year in years:
        end = date.fromisoformat(year.fy_end)
        for d in b.of_type("bank_statement"):
            start = parse_date(d.get("statement_period_start").value) if d.get("statement_period_start") else None
            stop = parse_date(d.get("statement_period_end").value) if d.get("statement_period_end") else None
            if not (start and stop and start <= end <= stop):
                continue
            bank = str((d.get("bank_name").value if d.get("bank_name") else "") or "Bank")
            account = _account_label(bank, _last4(d.get("account_number").value if d.get("account_number") else None))
            dated = [t for t in txns if t.doc is d and t.date and t.date <= end and t.balance is not None]
            if dated:
                last = max(dated, key=lambda t: t.date)
                out.append(BalanceFact(account=account, date=end.isoformat(), balance=last.balance,
                                       evidence=last.evidence[:1]))
            elif d.get("opening_balance"):
                v = d.get("opening_balance")
                out.append(BalanceFact(account=account, date=end.isoformat(), balance=_amount(v), evidence=d.evidence(v)))
    return out


def _transactions(b: Build) -> tuple[list[Txn], dict[str, set[tuple[int, int]]]]:
    """Every statement transaction, and the months each account's statements cover."""
    txns: list[Txn] = []
    coverage: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for d in b.of_type("bank_statement"):
        bank = str((d.get("bank_name").value if d.get("bank_name") else "") or "Bank")
        last4 = _last4(d.get("account_number").value if d.get("account_number") else None)
        account = _account_label(bank, last4)
        start = parse_date(d.get("statement_period_start").value) if d.get("statement_period_start") else None
        end = parse_date(d.get("statement_period_end").value) if d.get("statement_period_end") else None
        rows = d.rows("transactions")
        if start and end:
            ym = (start.year, start.month)
            while ym <= (end.year, end.month):
                coverage[account].add(ym)
                ym = month_add(*ym, 1)
        for seq, r in enumerate(rows):
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
                    narration=str(r["description"].value) if r.get("description") else "",
                    debit=debit,
                    credit=credit,
                    evidence=d.evidence(r.get("credit") or r.get("debit"), r.get("description")),
                    doc=d,
                    balance=_amount(r["balance"]) if r.get("balance") and r["balance"].value not in (None, "") else None,
                    reference=str(r["reference_number"].value or "").strip() if r.get("reference_number") else "",
                    ref=next((v.field_id for v in (r.get("description"), r.get("credit"), r.get("debit")) if v is not None and v.field_id), ""),
                    seq=seq,
                )
            )
    return txns, coverage


def _accounts(b: Build, txns: list[Txn]) -> tuple[list[AccountFact], bool]:
    """The account set (F-18.5): statements, the declaration, partner
    analyses and accounts named in transfer narrations."""
    found: dict[tuple[str, str | None], AccountFact] = {}

    def add(bank: str, last4: str | None, source: str, evidence: list[Evidence], *, declared: bool = False,
            statement: bool = False, named: str = "", kind: str = "") -> None:
        # `named` and `kind`: the bank and what the account is, as the sourcing message says; they
        # describe an account only the message gives, and are not used to match one.
        key = next(
            (k for k in found if (last4 and k[1] == last4 and (not bank or same_entity(bank, k[0], b.noise, b.name_threshold)))
             or (not last4 and not k[1] and same_entity(bank, k[0], b.noise, b.name_threshold))),
            None,
        )
        if key is None:
            key = (bank, last4)
            label = _account_label(bank or named or "Account", last4) + (f" ({kind})" if kind else "")
            found[key] = AccountFact(bank=bank or named, last4=last4, label=label, sources=[], declared=False,
                                     has_statement=False, evidence=[])
        fact = found[key]
        if source not in fact.sources:
            fact.sources.append(source)
        fact.declared = fact.declared or declared
        fact.has_statement = fact.has_statement or statement
        fact.evidence += evidence[:1]

    for d in b.of_type("bank_statement"):
        bank = str(d.get("bank_name").value) if d.get("bank_name") else ""
        acct = d.get("account_number")
        add(bank, _last4(acct.value if acct else None), d.label, d.evidence(acct), statement=True)
    # The accounts a declaration of existing facilities lists are declared (BA-01, BA-02).
    for d in b.of_type(DECLARATION):
        for r in d.rows("bank_accounts"):
            number = r.get("account_number")
            last4 = _last4(number.value if number else None)
            if last4:
                bank = str(r["bank"].value).strip() if r.get("bank") and r["bank"].value else ""
                add(bank, last4, d.label, d.evidence(number), declared=True)
    v = b.message_value("existing_banking")
    if v and isinstance(v.value, str):
        named = {last4: (kind, bank) for kind, bank, last4 in banking_named(v.value) if last4}
        for m in MESSAGE_ACCOUNT.finditer(v.value):
            kind, bank = named.get(_last4(m[1]) or "", ("", ""))
            add("", _last4(m[1]), "Sourcing message", v.evidence, declared=True, named=bank, kind=kind)
    own = {k[1] for k in found if k[1]}
    for t in txns:
        for m in NARRATION_ACCOUNT.finditer(t.narration):
            last4 = _last4(m[1])
            if last4 and last4 not in own and _phrase(t.narration, ["transfer", "trf", "neft", "rtgs", "imps", "self"]):
                add("", last4, f"Transfer in {t.account}", t.evidence)
    return list(found.values()), bool(b.of_type(DECLARATION))


def _cleanse(b: Build, txns: list[Txn], finals: list[Final], accounts: list[AccountFact]) -> tuple[list[AccountCredits], dict[str, dict]]:
    """Credits less the categories the configuration removes (F-18.2), by account and month. A credit's category is
    its final label: the rules' reading, the model's answer where the rules left it open, a person's decision over
    both. A credit nothing has filed is counted, and reported as unsettled."""
    removes = {c: ex for ex in b.align.bank_credit_exclusions for c in ex.categories}
    per_account: dict[str, AccountCredits] = {}
    net_by_month: dict[tuple[int, int], float] = defaultdict(float)
    evidence_by_month: dict[tuple[int, int], list[Evidence]] = defaultdict(list)
    # Each account's credits month by month, for the evidence behind a bank figure.
    account_months: dict[str, dict[tuple[int, int], dict]] = defaultdict(dict)
    for t, final in zip(txns, finals):
        if not t.credit:
            continue
        acct = per_account.setdefault(
            t.account, AccountCredits(account=t.account, gross=0, excluded=0, net=0, months=[], exclusions=[])
        )
        acct.gross += t.credit
        slot = None
        if t.date:
            slot = account_months[t.account].setdefault(
                (t.date.year, t.date.month), {"gross": 0.0, "excluded": 0.0, "net": 0.0, "evidence": []})
            slot["gross"] += t.credit
            slot["evidence"] = slot["evidence"] or t.evidence[:1]
        rule = removes.get(final.category)
        if rule:
            acct.excluded += t.credit
            if slot is not None:
                slot["excluded"] += t.credit
            acct.exclusions.append(
                Exclusion(rule=rule.id, label=rule.label, account=t.account,
                          date=t.date.isoformat() if t.date else None, narration=t.narration, amount=t.credit,
                          evidence=t.evidence)
            )
            continue
        if not final.settled:
            acct.unsettled += t.credit
            acct.unsettled_count += 1
        acct.net += t.credit
        if slot is not None:
            slot["net"] += t.credit
        if t.date:
            ym = (t.date.year, t.date.month)
            net_by_month[ym] += t.credit
            evidence_by_month[ym] += t.evidence[:1]
            label = month_label(ym)
            if label not in acct.months:
                acct.months.append(label)
    for acct in per_account.values():
        acct.by_month = [
            AccountMonth(month=f"{y}-{m:02d}", label=month_label((y, m)), gross=s["gross"], excluded=s["excluded"],
                         net=s["net"], evidence=s["evidence"])
            for (y, m), s in sorted(account_months[acct.account].items())
        ]
    return list(per_account.values()), {"net": net_by_month, "evidence": evidence_by_month}


def _obligations(b: Build, txns: list[Txn], finals: list[Final]) -> list[Obligation]:
    """Recurring debits to a lender (F-18.4): debits filed under loan_emi, the same lender in enough months, amounts
    within the EMI tolerance."""
    candidates: dict[tuple[str, str], list[tuple[Txn, str]]] = defaultdict(list)
    for t, final in zip(txns, finals):
        if not t.debit or final.category != "loan_emi" or not final.counterparty:
            continue
        party = final.counterparty
        key = next((k for k in candidates if k[1] == t.account and same_entity(party, k[0], b.noise, b.name_threshold)),
                   (party, t.account))
        candidates[key].append((t, party))
    out: list[Obligation] = []
    for (party, account), found in candidates.items():
        debits = [t for t, _ in found]
        months = sorted({(t.date.year, t.date.month) for t in debits if t.date})
        amounts = sorted(t.debit for t in debits)
        typical = amounts[len(amounts) // 2]
        steady = [a for a in amounts if abs(a - typical) <= typical * b.emi_tolerance_pct / 100]
        if len(months) < b.emi_min or len(steady) < b.emi_min:
            continue
        variants = sorted({p for _, p in found})
        out.append(
            Obligation(lender=party, variants=variants, account=account, months=[month_label(m) for m in months],
                       typical_amount=typical, debits=len(debits),
                       evidence=[e for t in debits[:3] for e in t.evidence[:1]])
        )
    return out


def _gst_by_month(b: Build) -> dict[tuple[int, int], tuple[float, Doc, statements.Line]]:
    """Outward supplies per return period, from each GSTR-3B (the first return for a period)."""
    cfg = reader.load_statements(b.root)
    gst: dict[tuple[int, int], tuple[float, Doc, statements.Line]] = {}
    for d in b.of_type("gstr_3b"):
        tp, fy = d.get("tax_period"), d.get("financial_year")
        # A month named without its year ("Sep", in financial year 2026-27) is placed by the return's own financial year.
        months = period_months(tp.value, fy.value if fy else None) if tp else []
        period = months[0] if len(months) == 1 else (parse_period(tp.value) if tp else None)
        line = statements.gst_outward(d, cfg)
        if period and line and period not in gst:
            gst[period] = (line.value, d, line)
    return gst


def _months(b: Build, credits_by_month: dict, coverage: dict[str, set[tuple[int, int]]]) -> list[MonthFigure]:
    """GST and cleansed bank credits month by month (TO-05). A month has a bank
    figure only when every account's statements cover it."""
    gst = _gst_by_month(b)
    covered = set.intersection(*coverage.values()) if coverage else set()
    out = []
    for ym in sorted(set(gst) | covered):
        g = gst.get(ym)
        out.append(MonthFigure(
            month=f"{ym[0]}-{ym[1]:02d}", label=month_label(ym),
            gst=g[0] if g else None, bank=credits_by_month["net"].get(ym, 0.0) if ym in covered else None,
            gst_evidence=g[2].evidence[:1] if g else [],
            bank_evidence=credits_by_month["evidence"].get(ym, [])[:1] if ym in covered else [],
            awaiting_review=bool(g and g[2].pending),
            gst_filed=str(g[1].get("filing_date").value) if g and g[1].get("filing_date") else None))
    return out


def _turnover(b: Build, credits_by_month: dict, coverage: dict[str, set[tuple[int, int]]],
              tax_years: list[TaxYear]) -> list[TurnoverYear]:
    years: dict[int, list[TurnoverFigure]] = defaultdict(list)
    start = b.start

    cfg = reader.load_statements(b.root)

    # Audited financial statements: revenue from operations for the year.
    for d in b.of_type("audited_financial_statements"):
        when = statements.period_end(d)
        revenue = statements.lines(d, cfg).get("revenue_from_operations")
        if not (when and revenue):
            continue
        years[fy_of(when.year, when.month, start)].append(TurnoverFigure(
            source="financials", label="Audited financial statements", value=revenue.value, evidence=revenue.evidence,
            field_ids=revenue.field_ids, relies_on_manual=revenue.manual, awaiting_review=revenue.pending))

    # GST: outward supplies per return period, from each GSTR-3B.
    gst = _gst_by_month(b)
    for fy in sorted({fy_of(y, m, start) for (y, m) in gst}):
        months = fy_months(fy, start)
        present = [m for m in months if m in gst]
        values = [gst[m] for m in present]
        years[fy].append(TurnoverFigure(
            source="gst", label="GST outward supplies", value=sum(v[0] for v in values),
            months_covered=len(present), months_missing=[month_label(m) for m in months if m not in gst],
            evidence=[e for v in values[:12] for e in v[2].evidence[:1]],
            field_ids=[i for v in values for i in v[2].field_ids], relies_on_manual=any(v[2].manual for v in values),
            awaiting_review=any(v[2].pending for v in values)))

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

    # The income tax return: the turnover its computation shows (statements.itr_lines), for the
    # financial year the return covers (TX-03 to TX-05).
    for t in tax_years:
        line = t.lines.get("turnover")
        end = parse_date(t.fy_end)
        if line is None or end is None:
            continue
        try:
            value = float(str(line.value).replace(",", ""))
        except (TypeError, ValueError):
            continue
        years[fy_of(end.year, end.month, start)].append(TurnoverFigure(
            source="itr", label="Turnover in the income tax return", value=value, evidence=line.evidence,
            field_ids=line.field_ids, relies_on_manual=line.relies_on_manual, awaiting_review=line.awaiting_review))

    return [
        TurnoverYear(fy=fy_name(fy, start), fy_end=fy_end_date(fy, start).isoformat(), figures=figs)
        for fy, figs in sorted(years.items(), reverse=True)
    ]


def _build(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> Build:
    tolerances = {t.key: t.value for t in reader.load_tolerances(root).tolerances}
    row = conn.execute(
        "SELECT d.id FROM documents d JOIN files f ON f.id = d.file_id WHERE d.case_id = ? AND f.original_name = ?",
        (case.id, MESSAGE_FILE_NAME),
    ).fetchone()
    header_row = conn.execute("SELECT header FROM cases WHERE id = ?", (case.id,)).fetchone()
    return Build(
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


@dataclass
class StatementInputs:
    """What the transaction classifier needs of a case: its statement rows and the names a narration may mention."""

    txns: list[Txn]
    borrower: str
    own_account_last4: frozenset[str]
    lender_names: tuple[str, ...]
    director_names: tuple[str, ...]
    emi_min_months: int
    emi_tolerance_pct: float


def _inputs(b: Build, txns: list[Txn], accounts: list[AccountFact]) -> StatementInputs:
    lenders = dict.fromkeys(f.lender for f in _facilities(b) if f.lender)
    people = dict.fromkeys(n for ps in _persons(b) for n in ps.names if n)
    return StatementInputs(
        txns=txns,
        borrower=b.case.borrower or "",
        own_account_last4=frozenset(a.last4 for a in accounts if a.last4),
        lender_names=tuple(lenders),
        director_names=tuple(people),
        emi_min_months=b.emi_min,
        emi_tolerance_pct=b.emi_tolerance_pct,
    )


def statement_inputs(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> StatementInputs:
    b = _build(conn, root, case)
    txns, _ = _transactions(b)
    accounts, _ = _accounts(b, txns)
    return _inputs(b, txns, accounts)


def labelled_statement(conn: sqlite3.Connection, root: Path, case: CaseDetail):
    """The statement rows with their final labels, the months each account's statements cover, and the credit
    categories removed from business inflow."""
    b = _build(conn, root, case)
    txns, coverage = _transactions(b)
    accounts, _ = _accounts(b, txns)
    inputs = _inputs(b, txns, accounts)
    removed = {c for ex in b.align.bank_credit_exclusions for c in ex.categories}
    return inputs, label_statement(conn, root, case.id, inputs), coverage, removed


def label_statement(conn: sqlite3.Connection, root: Path, case_id: str, inputs: StatementInputs) -> list[Final]:
    """Each statement row's final label (rules, then the model, then a person), in the order of `inputs.txns`."""
    version = reader.published_version(root)["version"]
    models, overrides = load_state(conn, case_id, version)
    ctx = Context(borrower_name=inputs.borrower, own_account_last4=inputs.own_account_last4,
                  lender_names=inputs.lender_names, director_names=inputs.director_names,
                  emi_min_months=inputs.emi_min_months, emi_tolerance_pct=inputs.emi_tolerance_pct)
    rows = [IntelTxn(t.ref or f"row-{i}", t.account, t.date, t.narration, t.debit, t.credit,
                     t.account.rsplit("·", 1)[-1] if "·" in t.account else None) for i, t in enumerate(inputs.txns)]
    return label_case(reader.load_txn_classification(root), rows, ctx, models, overrides)


def compute(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> CaseFacts:
    b = _build(conn, root, case)
    txns, coverage = _transactions(b)
    accounts, declared = _accounts(b, txns)
    finals = label_statement(conn, root, case.id, _inputs(b, txns, accounts))
    credits, by_month = _cleanse(b, txns, finals, accounts)
    years = _financial_years(b)
    tax_years = _tax_years(b)
    return CaseFacts(
        case_id=case.id,
        identities=_identities(b),
        persons=_persons(b),
        turnover=_turnover(b, by_month, coverage, tax_years),
        credits=credits,
        obligations=_obligations(b, txns, finals),
        accounts=accounts,
        facilities=_facilities(b),
        declaration_received=declared,
        declaration=_declaration(b),
        declared_banking=b.message_value("existing_banking"),
        requested_amount=_requested(b),
        proposed_emi=_proposed_emi(b),
        incorporation=_incorporation(b),
        authority=_authority(b),
        tax_years=tax_years,
        financial_years=years,
        months=_months(b, by_month, coverage),
        balances=_balances(b, txns, years),
        types_on_file=sorted({t for d in b.docs for t in d.types}),
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
