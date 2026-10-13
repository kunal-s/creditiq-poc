"""The draft Credit Approval Memo (FRD F-23).

Sections in the configured order (config/cam.yaml): an assumed layout, modelled on a business-banking
credit approval memo, until RBL's template arrives (F-23.1). Each section is drafted from the facts
only, in a neutral register, as blocks of paragraphs, key facts, tables, subheadings and notes, and
every figure carries the pages it rests on (F-23.2). The memo ends with a structured summary of
findings (F-19), checks not completed, deviations (F-20) and open queries (F-14) (F-23.3), then an
empty recommendation with the prompts credit completes and the sign-off (F-23.4). The documents
cited are numbered in the order they are first cited (engine/output_sources.py), so the screen and
the downloads agree. Each finding's explanation is stated once, in the cross-verification section;
the summary lists the findings as a register.

The text is composed from the facts, not written by a model, and reads no clock, so the same case
always gives the same memo (F-23.6, principle 6).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import approval, completeness, facts as facts_module, output_sources, policy as policy_module, reads
from . import spread as spread_module, statements as statements_module, xv
from .config import find_user_by_id, load_app_config
from .configstore import reader
from .contracts import (
    AuthorityFact,
    Cam,
    CamBlock,
    CamFact,
    CamSection,
    CamSignOff,
    CamSummaryItem,
    CamTable,
    CamText,
    CaseDetail,
    CaseFacts,
    Evidence,
    EvidenceRow,
    FactValue,
    Finding,
    NormResult,
    PersonEntry,
    TurnoverFigure,
    TurnoverYear,
    XvItem,
)
from .crosschecks import _mentions
from .names import name_parts, normalise_name, same_by_parts, similarity
from .util import display_date, parse_date, ranges_label

inr = facts_module.inr
NONE = "—"
NOT_ON_FILE = "Not on file"
MESSAGE = "application_message"
# A discrepancy's standing on the board: accept is a valid finding, dismiss one found not valid.
ACCEPTED, DISMISSED, ESCALATED, OPEN = "Accepted as valid", "Not valid", "Escalated", "Open"
# The time zone the configuration's publish date is read in.
IST = timezone(timedelta(hours=5, minutes=30))

# How the memo names each constitution in a sentence.
ENTITY = {
    "private_limited": "a private limited company",
    "partnership": "a partnership firm",
    "proprietorship": "a proprietorship concern",
}
# The areas of the cross-verification board, as the memo names them.
AREAS = {
    "identity": "Identity consistency",
    "authority": "Borrowing authority",
    "turnover": "Turnover",
    "tax": "Income tax",
    "financials": "Financial statements",
    "accounts": "Bank accounts",
    "obligations": "Existing obligations",
}
SEVERITY = {"serious": "Serious", "moderate": "Moderate", "mild": "Mild"}
RESULT = {"deviation": "Deviation", "pass": "Met", "cannot_evaluate": "Not assessed"}
ITEM_STATUS = {"missing": "Missing", "insufficient": "Insufficient", "in_review": "In review"}
# The identity checks on the borrower's own particulars, and those on its people, by the fact compared.
ENTITY_CHECKS = {"entity_pan", "gstin", "legal_name", "cin", "incorporation_particulars"}
PEOPLE_CHECKS = {"promoter_set", "director_identifiers", "memorandum_directors", "person_names"}
# The document each identifier is cited to first: the one that issues or registers it.
ISSUED_BY = {"entity_pan": "company_pan", "gstin": "gstr_3b", "cin": "certificate_of_incorporation"}
# Where the legal name is read first: the certificate of incorporation, then the registrations.
NAME_SOURCES = ("certificate_of_incorporation", "company_pan", "memorandum_articles_of_association", "gstr_3b",
                "income_tax_return", "audited_financial_statements")
# The order people are listed in: the memorandum's directors first, the sourcing message last.
PEOPLE_SOURCES = ("memorandum_articles_of_association", "director_kyc", "commercial_bureau_report",
                  "board_resolution_borrowing", MESSAGE)
# The first two digits of a GSTIN: the state or union territory of the registration.
GST_STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh",
    "23": "Madhya Pradesh", "24": "Gujarat", "25": "Daman and Diu", "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh", "97": "Other Territory",
}
# The rows of the financial performance table: a spread row (a ratio by its configured key), its
# label in the memo and how its figures are written.
FINANCIAL_ROWS = [
    ("revenue_from_operations", "Revenue from operations", "inr"),
    ("growth", "Growth in revenue (%)", "%"),
    ("ebitda", "EBITDA", "inr"),
    ("ebitda_margin", "EBITDA margin (%)", "%"),
    ("profit_after_tax", "Profit after tax", "inr"),
    ("pat_margin", "PAT margin (%)", "%"),
    ("net_worth", "Net worth", "inr"),
    ("total_borrowings", "Total borrowings", "inr"),
    ("current-ratio", "Current ratio", "x"),
    ("tol-tnw", "TOL / TNW", "x"),
    ("debt-equity", "Debt / equity", "x"),
    ("interest-coverage", "Interest coverage", "x"),
    ("dscr", "DSCR", "x"),
    ("wc-cycle", "Working-capital cycle (days)", "days"),
]
# The previous year's lines the latest statements print beside their own (the comparatives).
COMPARATIVE_ROWS = ("revenue_from_operations", "ebitda", "profit_after_tax", "net_worth", "total_borrowings")
# The comparatives set against the previous year's own statements, as the memo names them.
RESTATED = (("revenue_from_operations", "revenue from operations"), ("profit_after_tax", "profit after tax"),
            ("net_worth", "net worth"))
TURNOVER_COLUMNS = [("financials", "Audited"), ("gst", "GST outward supplies (GSTR-3B)"), ("itr", "Income tax return"),
                    ("bank", "Business credits (bank)"), ("declared", "Declared")]
# The bank-credit exclusion (config/alignment.yaml) for a loan paid into the account.
LOAN_DISBURSAL = "loan_disbursal"
# A facility name that is working-capital finance rather than a term loan.
WORKING_CAPITAL_NAME = re.compile(r"cash credit|overdraft|working capital|packing credit|bill|\b(?:cc|od|wcdl)\b", re.I)
# A norm written in words rather than as a threshold (engine/policy.py required_text).
WORD_NORMS = {"positive", "no loss", "none"}
# The inputs of a norm as a sentence names what is not on file.
INPUT_PHRASES = {
    "Years in business": "the date of incorporation",
    "Annual instalments on the proposed term loan": "the proposed term loan's instalment",
    "Annual instalments on existing facilities": "the instalments on existing facilities",
    "Years of audited statements": "the audited financial statements",
    "Amount requested": "the amount requested",
    "Collateral market value": "the collateral's market value",
    "Collateral realisable value": "the collateral's realisable value",
}
PLURAL_INPUTS = {"Current assets", "Current liabilities", "Inventories", "Trade receivables", "Trade payables",
                 "Finance costs", "Long-term borrowings", "Short-term borrowings", "Total borrowings",
                 "Annual instalments on existing facilities", "Years of audited statements"}


# --- Wording ---


def _join(items: list[str]) -> str:
    items = [i for i in dict.fromkeys(items) if i]
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


def _plural(count: int, word: str, plural: str | None = None) -> str:
    return f"{count} {word if count == 1 else plural or word + 's'}"


def _lower(text: str) -> str:
    """The text as it reads inside a sentence: its first letter in lower case, unless it opens an acronym."""
    return text[:1].lower() + text[1:] if text[1:2].islower() else text


def _upper(text: str) -> str:
    return text[:1].upper() + text[1:]


def _a(text: str) -> str:
    text = _lower(text)
    return f"{'an' if text[:1] in 'aeiou' else 'a'} {text}"


def _number(value: float, decimals: int) -> str:
    text = f"{value:.{decimals}f}"
    return text[1:] if text.startswith("-") and float(text) == 0 else text


def _unique(citations) -> list[Evidence]:
    """Each page and region once, in the order first cited."""
    seen, out = set(), []
    for e in citations:
        key = (e.document_id, e.page, e.bbox)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def _pages(citations) -> list[Evidence]:
    """Each page once, in the order first cited."""
    seen, out = set(), []
    for e in citations:
        if (e.document_id, e.page) not in seen:
            seen.add((e.document_id, e.page))
            out.append(e)
    return out


def _t(text: str, citations=()) -> CamText:
    return CamText(text=text, citations=_unique(citations))


def _paragraph(text: str, citations=()) -> CamBlock:
    return CamBlock(kind="paragraph", paragraph=_t(text, citations))


def _facts(rows: list[tuple[str, CamText]]) -> CamBlock:
    return CamBlock(kind="facts", facts=[CamFact(label=label, value=value) for label, value in rows])


def _table(columns: list[str], rows: list[list[CamText]], numeric: list[int] | None = None, title: str | None = None,
           note: str | None = None) -> CamBlock:
    return CamBlock(kind="table", table=CamTable(title=title, columns=columns, rows=rows, numeric=numeric or [],
                                                 note=note))


def _note(text: str) -> CamBlock:
    return CamBlock(kind="note", text=text)


def _subheading(text: str) -> CamBlock:
    return CamBlock(kind="subheading", text=text)


def _tenure(months: int) -> str:
    """Completed months as years and months: "11 years 3 months"."""
    years, rest = divmod(months, 12)
    return " ".join(([_plural(years, "year")] if years else []) + ([_plural(rest, "month")] if rest else [])) \
        or "less than a month"


# --- Findings, as the board holds them ---


def status(item: XvItem) -> str:
    """A discrepancy's standing: accepted as valid or found not valid, else escalated to the Credit
    Manager or open."""
    if item.decision is not None:
        return ACCEPTED if item.decision.decision == "accept" else DISMISSED
    return ESCALATED if item.escalation is not None else OPEN


def finding_title(f: Finding, scope: bool = True) -> str:
    """What is wrong, in plain English, with the year or months the finding covers (left out where
    its explanation follows, which states them)."""
    title = f.finding_title or f.compares or f.title
    return f"{title} · {f.scope}" if scope and f.scope and f.scope not in title else title


def stated_title(f: Finding) -> str:
    """The title over the finding's explanation: with its year or months only where the explanation
    does not state them."""
    return finding_title(f, scope=not (f.scope and f.scope in f.explanation))


def _naming(rows: list[EvidenceRow], label: str, threshold: float) -> list[EvidenceRow]:
    """The rows of a column whose first cell names a row of the finding: the same words, else (a
    person, a lender) a name at least `threshold` alike or the same by its parts."""
    named = [(r, r.cells[0]) for r in rows if r.cells and isinstance(r.cells[0], str)]
    exact = [r for r, cell in named if normalise_name(cell) == normalise_name(label)]
    return exact or [r for r, cell in named if similarity(cell, label) >= threshold or same_by_parts(cell, label)]


def finding_evidence(f: Finding, threshold: float = 0.85) -> list[Evidence]:
    """The pages a finding rests on, read from its card's columns. A finding about particular rows (a
    person, an account, a lender, a month) cites, in each column, the rows that name them, else the
    column's first page; any other finding cites every page of a column that differs and the first
    page of each other column. A finding without columns cites the first page of each side."""
    if not f.columns:
        return _pages(e for s in f.sides for e in s.evidence[:1])
    flagged = [r.label for r in f.detail.rows if r.flagged] if f.detail else []
    out: list[Evidence] = []
    for column in f.columns:
        if flagged:
            named = [e for label in flagged for r in _naming(column.rows, label, threshold) for e in r.evidence]
            out += named or column.evidence[:1]
        else:
            out += column.evidence if column.differs else column.evidence[:1]
    return _pages(out)


def _dismissed(item: XvItem) -> bool:
    return item.decision is not None and item.decision.decision == "dismiss"


# --- People ---


@dataclass
class Person:
    """One person as the documents name them: their entries, grouped as the cross-checks group people
    (names at least `name_match` alike, or the same by their parts)."""

    entries: list[tuple[str, PersonEntry]]
    """(source document type, entry), in the order the sources are read."""

    @property
    def name(self) -> str:
        """The fullest form of the name any source gives."""
        return max((e.name for _, e in self.entries), key=lambda n: (len(name_parts(n).words()), len(n)))

    @property
    def role(self) -> str | None:
        """As the person's KYC designates them, else as another source does."""
        roles = [e.role for s, e in self.entries if e.role and s == "director_kyc"]
        roles += [e.role for _, e in self.entries if e.role]
        return roles[0][:1].upper() + roles[0][1:] if roles else None

    @property
    def kyc(self) -> bool:
        return any(s == "director_kyc" for s, _ in self.entries)

    @property
    def din(self) -> str | None:
        return "; ".join(dict.fromkeys(e.din for _, e in self.entries if e.din)) or None

    def evidence(self, *sources: str) -> list[Evidence]:
        return _unique(ev for s, e in self.entries if not sources or s in sources for ev in e.evidence[:1])

    def identifiers(self, key: str, names: dict[str, str]) -> CamText:
        """Each DIN or PAN the sources print, naming the sources where they differ."""
        found: dict[str, list[tuple[str, PersonEntry]]] = {}
        for s, e in self.entries:
            if getattr(e, key):
                found.setdefault(getattr(e, key), []).append((s, e))
        if not found:
            return _t(NONE)
        if len(found) == 1:
            return _t(next(iter(found)), [ev for _, e in next(iter(found.values())) for ev in e.evidence[:1]])
        return _t("; ".join(f"{value} ({_join([names.get(s, s) for s, _ in held])})" for value, held in found.items()),
                  [ev for held in found.values() for _, e in held for ev in e.evidence[:1]])

    def sources(self, names: dict[str, str]) -> list[str]:
        return list(dict.fromkeys(names.get(s, s) for s, _ in self.entries))


def name_match(root: Path) -> float:
    """How alike two names must be to be one person or one lender (config/tolerances.yaml)."""
    return next((t.value for t in reader.load_tolerances(root).tolerances if t.key == "name_match"), 0.85)


def type_names(root: Path) -> dict[str, str]:
    """Each document type's name, as the case lists its documents."""
    return {MESSAGE: "Sourcing message", **{t.id: t.name for t in reader.load_document_types(root).types}}


def _origin(source: str, e: PersonEntry) -> set[str]:
    """Where an entry is listed: its documents, or its source for a name with no page (a list typed on
    the case), as the cross-checks read it."""
    return {ev.document_id for ev in e.evidence} or {f"source:{source}"}


def people(root: Path, facts: CaseFacts) -> list[Person]:
    """The promoters, directors and partners the documents name, each person once. An entry joins the
    person whose name it matches best (the same name before a similar one), never a person another
    entry of the same document, or of the same list typed on the case, names differently: one list
    names different people."""
    threshold = name_match(root)
    order = {s: i for i, s in enumerate(PEOPLE_SOURCES)}
    found: list[Person] = []
    for p in sorted(facts.persons, key=lambda p: order.get(p.source, len(order))):
        for e in p.entries:
            origin, key = _origin(p.source, e), normalise_name(e.name)
            best, score = None, 0.0
            for g in found:
                if any(_origin(s, x) & origin and normalise_name(x.name) != key for s, x in g.entries):
                    continue
                for _, x in g.entries:
                    alike = 2.0 if normalise_name(x.name) == key else similarity(e.name, x.name)
                    if alike > score and (alike >= threshold or same_by_parts(e.name, x.name)):
                        best, score = g, alike
            if best is None:
                found.append(Person([(p.source, e)]))
            else:
                best.entries.append((p.source, e))
    return found


def config_label(root: Path) -> str:
    """The configuration version as Administration numbers it, "Version 15 (published 13 Oct 2026)",
    counted from the publish log; the first 8 characters of its hash when the log does not record it."""
    version = reader.published_version(root)["version"]
    history = reader.publish_history(root)
    at = next((n for n, v in enumerate(history) if v["version"] == version), None)
    if at is None:
        return version[:8]
    try:
        published = datetime.fromisoformat(history[at]["published_at"]).astimezone(IST).date()
    except (TypeError, ValueError):
        return f"Version {len(history) - at}"
    return f"Version {len(history) - at} (published {display_date(published)})"


# --- The draft ---


class Draft:
    def __init__(self, conn: sqlite3.Connection, root: Path, case: CaseDetail) -> None:
        self.case = case
        app = load_app_config()
        self.facility_names = {f["id"]: f["label"] for f in app["facilities"]}
        self.constitutions = {c["id"]: c["label"] for c in app.get("constitutions", [])}
        self.config = reader.load_cam(root)
        self.numbers: dict[str, int] = {}
        for number, s in enumerate(self.config.sections, start=1):
            self.numbers.setdefault(s.kind, number)
        self.facts = facts_module.compute(conn, root, case)
        self.docs = facts_module.load_documents(conn, root, case.id)
        self.message_doc = next((d.id for d in self.docs if MESSAGE in d.types), None)
        self.assessment = policy_module.assess(conn, root, case)
        self.policy_config = reader.load_policy(root)
        self.matrix = reader.load_approval_matrix(root)
        self.authority = approval.from_assessment(self.matrix, self.policy_config, case, self.assessment)
        self.ratio_norms = {n.ratio: n.id for n in self.policy_config.norms if n.ratio}
        self.line_norms = {n.expression.strip(): n.id for n in self.policy_config.norms}
        self.spread = spread_module.build(conn, root, case)
        self.board = xv.view(conn, root, case)
        self.rules = {r.id: r for r in reader.load_crosschecks(root).rules}
        self.readiness, self.results = completeness.evaluate(conn, root, case)
        self.queries = [q for q in reads.query_items(conn, case.id) if not q.resolved]
        self.type_names = type_names(root)
        alignment = reader.load_alignment(root)
        self.noise = [w.lower() for w in alignment.name_noise_words]
        self.fy_start = alignment.financial_year_start_month
        self.tolerances = {t.key: t.value for t in reader.load_tolerances(root).tolerances}
        self.statements_config = reader.load_statements(root)
        self.threshold = name_match(root)
        self.people = people(root, self.facts)
        self.other_names = self._other_names()

    # --- Helpers ---

    def see(self, kind: str) -> str:
        """Where the memo's section of this kind is, as " (see section 11)"; nothing when it has none."""
        return f" (see section {self.numbers[kind]})" if kind in self.numbers else ""

    def section(self, kind: str) -> str:
        """The memo's section of this kind, as " (section 6)"; nothing when it has none."""
        return f" (section {self.numbers[kind]})" if kind in self.numbers else ""

    def same_lender(self, a: str, b: str) -> bool:
        return facts_module.same_lender(a, b, self.noise, self.threshold)

    def norm(self, norm_id: str | None) -> NormResult | None:
        return next((n for n in self.assessment.norms if n.id == norm_id), None)

    def against(self, n: NormResult | None) -> str:
        """How a figure stands against its norm, or nothing when no norm assessed it. A norm in rupees
        is named rather than quoted ("positive" says less than "positive net worth")."""
        if n is None or n.outcome not in ("pass", "deviation"):
            return ""
        if n.unit == "inr":
            named = f"the norm for {_lower(n.label)}"
            return f", meeting {named}" if n.outcome == "pass" else f", a deviation from {named}{self.see('policy')}"
        if n.outcome == "pass":
            return f", within the norm of {n.required}"
        return f", a deviation from the norm of {n.required}{self.see('policy')}"

    def header_evidence(self, name: str) -> list[Evidence]:
        """Where a value of the case header came from: a document's page, else the sourcing message; a
        value a person entered has no page."""
        field = self.case.header.get(name)
        if field is None or not field.value or field.source == "person":
            return []
        found = re.fullmatch(r"document:(.+):p(\d+)", field.source or "")
        if found:
            return [Evidence(document_id=found[1], page=int(found[2]))]
        return [Evidence(document_id=self.message_doc, page=1)] if self.message_doc else []

    def identifier(self, variable: str, recorded: str | None) -> CamText:
        """An identifier as the case records it (else as a document gives it), cited to a document
        that states it, the sourcing message only when no document does."""
        values = getattr(self.facts.identities, variable)
        documents = sorted((v for v in values if v.source != MESSAGE and "within the GSTIN" not in v.label),
                           key=lambda v: v.source != ISSUED_BY.get(variable))
        value = recorded or next((str(v.value) for v in documents + values), None)
        if not value:
            return _t(NOT_ON_FILE)
        backed = next((v for v in documents + values if str(v.value).upper() == value.upper()), None)
        return _t(value, backed.evidence[:1] if backed else [])

    def legal_name(self) -> FactValue | None:
        names = self.facts.identities.legal_name
        return next((v for source in NAME_SOURCES for v in names if v.source == source), None)

    def incorporated(self) -> date | None:
        inc = self.facts.incorporation.date_of_incorporation
        return parse_date(inc.value) if inc else None

    def tenure(self, since: date) -> str:
        """Completed years and months in business at the case's as-of date, never rounded up (EL-01
        counts the same months)."""
        return _tenure(policy_module.completed_months(since, date.fromisoformat(self.case.as_of)))

    def document_field(self, type_id: str, field: str) -> CamText | None:
        for d in self.docs:
            value = d.get(field) if type_id in d.types else None
            if value is not None:
                return _t(str(value.value).strip(), d.evidence(value))
        return None

    def field_of(self, document_id: str, field: str) -> CamText | None:
        d = next((d for d in self.docs if d.id == document_id), None)
        value = d.get(field) if d else None
        return _t(str(value.value).strip(), d.evidence(value)) if d and value is not None else None

    def declared_turnover(self) -> TurnoverFigure | None:
        return next((f for y in self.facts.turnover for f in y.figures if f.source == "declared" and f.value), None)

    def facility_list(self) -> list[str]:
        return [self.facility_names.get(f, f.replace("_", " ")) for f in self.case.facilities]

    def term_facilities(self) -> list[str]:
        """The facilities requested that are not working-capital finance, as a sentence names them."""
        return [_lower(self.facility_names.get(f, f.replace("_", " "))) for f in self.case.facilities
                if f not in policy_module.WORKING_CAPITAL]

    def discrepancies(self, *areas: str) -> list[XvItem]:
        """The failed checks nobody has found not valid, in board order (by area, then rank)."""
        return [i for i in self.board.items if i.finding.outcome == "fail" and not _dismissed(i)
                and (not areas or i.finding.area in areas)]

    def incomplete(self) -> list[XvItem]:
        """The checks that could not be completed, in board order."""
        return [i for i in self.board.items if i.finding.outcome == "incomplete"]

    def checks_note(self, variables: set[str]) -> CamBlock | None:
        """A note pointing to the discrepancies found on these facts, by their board references."""
        found = [i for i in self.discrepancies("identity")
                 if self.rules.get(i.finding.rule_id) and self.rules[i.finding.rule_id].variable in variables]
        if not found:
            return None
        listed = "; ".join(f"{finding_title(i.finding)} ({i.finding.ref or i.finding.rule_id})" for i in found)
        where = f" See section {self.numbers['cross_verification']}." if "cross_verification" in self.numbers else ""
        return _note(f"Identity checks found discrepancies: {listed}.{where}")

    def _other_names(self) -> dict[str, tuple[str, str]]:
        """The documents in another name: each on the differing side of a legal-name discrepancy nobody
        has found not valid, with the name it gives and the finding's board reference."""
        out: dict[str, tuple[str, str]] = {}
        for i in self.discrepancies():
            f = i.finding
            rule = self.rules.get(f.rule_id)
            if rule is None or rule.variable != "legal_name":
                continue
            ref = f.ref or f.rule_id
            for column in f.columns:
                for row in column.rows if column.differs else []:
                    name = row.cells[1] if len(row.cells) > 1 and isinstance(row.cells[1], str) else column.value
                    for e in row.evidence:
                        out.setdefault(e.document_id, (str(name), ref))
            for side in f.sides if not f.columns else []:
                for e in side.evidence if side.differs else []:
                    out.setdefault(e.document_id, (str(side.value), ref))
        return out

    def latest_column(self) -> int | None:
        """The spread column of the year the policy norms assess (the latest audited), else the last
        audited or provisional one."""
        columns = self.spread.columns
        shown = [i for i, c in enumerate(columns) if c.basis in ("audited", "provisional")]
        if not shown:
            return None
        return next((i for i in reversed(shown) if columns[i].fy == self.assessment.period
                     and columns[i].basis == "audited"), shown[-1])

    def column_documents(self, i: int) -> list[str]:
        return list(dict.fromkeys(e.document_id for r in self.spread.rows for e in r.cells[i].evidence))

    def latest_statements(self, fy: str):
        """The audited statements of a financial year, as read."""
        for d in self.docs:
            if "audited_financial_statements" not in d.types:
                continue
            end = statements_module.period_end(d)
            if end and facts_module.fy_name(facts_module.fy_of(end.year, end.month, self.fy_start), self.fy_start) == fy:
                return d
        return None

    def comparatives(self, fy: str) -> dict[str, tuple[float, list[Evidence]]]:
        """The previous year's figures the year's audited statements print beside their own."""
        d = self.latest_statements(fy)
        if d is None:
            return {}
        lines = statements_module.lines(d, self.statements_config, column="previous_period")
        return {key: (lines[key].value, lines[key].evidence) for key in COMPARATIVE_ROWS if key in lines}

    def prior_fy(self, period_end: str) -> str:
        end = date.fromisoformat(period_end)
        return facts_module.fy_name(facts_module.fy_of(end.year, end.month, self.fy_start) - 1, self.fy_start)

    # --- Sections ---

    def snapshot(self) -> list[CamBlock]:
        c, f = self.case, self.facts
        since = self.incorporated()
        inc = f.incorporation.date_of_incorporation
        declared = self.declared_turnover()
        rm = find_user_by_id(c.created_by) or {}
        r = self.readiness
        norms = self.assessment.counts
        limit = self.resolution_limit()
        rows = [
            ("Borrower", _t(c.borrower, self.header_evidence("borrower"))),
            ("Constitution", _t(self.constitutions.get(c.constitution, c.constitution),
                                self.header_evidence("constitution"))),
            ("PAN", self.identifier("entity_pan", c.pan)),
            ("GSTIN", self.identifier("gstin", c.gstin)),
            ("CIN", self.identifier("cin", c.cin)),
            ("Incorporated", _t(f"{display_date(since)} ({self.tenure(since)})", inc.evidence) if since and inc
             else _t(NOT_ON_FILE)),
            ("Facilities proposed", _t(_join([n if i == 0 else _lower(n) for i, n in enumerate(self.facility_list())]),
                                       self.header_evidence("facilities"))),
            ("Amount requested", _t(inr(c.amount_inr), f.requested_amount.evidence if f.requested_amount else [])),
            *([("Board resolution limit", limit)] if limit else []),
            ("Collateral offered", _t("Offered (case record; details not on file)" if c.collateral_present
                                      else "Not offered (case record)")),
            ("Turnover declared in the sourcing message",
             _t(inr(declared.value), declared.evidence) if declared else _t("Not stated")),
            ("Relationship manager and branch", _t(", ".join(p for p in (c.rm, rm.get("branch")) if p) or NONE)),
            ("Approving authority", _t(self.authority_text())),
            ("Cross-checks", _t(self.checks_text())),
            ("Policy norms", _t(f"{_plural(norms.deviations, 'deviation')}, {norms.cannot_evaluate} not assessed")),
            ("Documentation", _t(f"{r.score_pct:g}% ready against a gate of {r.gate_pct}%; "
                                 f"{_plural(r.blocking_open, 'blocking item')} open")),
            ("Case ID", _t(c.id)),
        ]
        return [_facts(rows)]

    def checks_text(self) -> str:
        """Where the cross-checks stand: the discrepancies by their standing, and the checks that
        could not be completed (accepted means a valid finding, not one cleared)."""
        b = self.board
        if b.run is None:
            return "Not run yet"
        failed = [i for i in b.items if i.finding.outcome == "fail"]
        open_ = [i for i in failed if not i.adjudicated]
        blocking = sum(1 for i in open_ if i.finding.blocking)
        accepted = sum(1 for i in failed if status(i) == ACCEPTED)
        dismissed = sum(1 for i in failed if _dismissed(i))
        held = ("blocking submission" if len(failed) == 1 else f"{blocking} blocking submission") if blocking else ""
        text = f"{b.run.rules} run; "
        if not failed:
            text += "no discrepancy"
        elif len(open_) == len(failed):
            text += f"{_plural(len(failed), 'discrepancy', 'discrepancies')} " \
                    f"({', '.join(p for p in ('open' if len(failed) == 1 else 'all open', held) if p)})"
        else:
            parts = [f"{len(open_)} open" + (f" ({held})" if held else "")] if open_ else []
            parts += [f"{accepted} accepted as valid"] if accepted else []
            parts += [f"{dismissed} found not valid"] if dismissed else []
            text += f"{_plural(len(failed), 'discrepancy', 'discrepancies')}: {', '.join(parts)}"
        incomplete = sum(a.incomplete for a in b.areas)
        return text + (f"; {incomplete} could not be completed" if incomplete else "")

    def resolution_limit(self) -> CamText | None:
        """The borrowing limit each board resolution sets, against the amount requested; nothing for a
        borrower that is not a company and has no resolution on file."""
        if not self.facts.authority:
            return _t(NOT_ON_FILE) if self.case.constitution in ("private_limited", "unknown") else None
        amount = self.case.amount_inr
        parts, cites = [], []
        for a in self.facts.authority:
            limit = float(a.borrowing_limit.value) if a.borrowing_limit and a.borrowing_limit.value else None
            if limit is None:
                parts.append("Not stated in the resolution")
                continue
            parts.append(f"{inr(limit)}" + (f" (below the {inr(amount)} requested)" if limit < amount else ""))
            cites += a.borrowing_limit.evidence
        return _t("; ".join(parts), cites)

    def borrower_profile(self) -> list[CamBlock]:
        c, inc = self.case, self.facts.incorporation
        name, since = self.legal_name(), self.incorporated()
        kind = inc.company_type
        entity = ENTITY.get(c.constitution)
        called = str(name.value) if name else c.borrower
        cites = (name.evidence[:1] if name else []) + (kind.evidence[:1] if kind else [])
        dated = since and inc.date_of_incorporation
        if entity:
            shares = re.sub(r"^company\s+", "", str(kind.value).strip(), flags=re.I) if kind else ""
            text = f"{called} is {entity}" + (f" ({_lower(shares)})" if shares else "")
            text += f" incorporated on {display_date(since)}, {self.tenure(since)} in business." if dated else "."
        else:
            text = f"The constitution of {called} is not yet confirmed."
            text += f" It was incorporated on {display_date(since)}, {self.tenure(since)} in business." if dated else ""
        if dated:
            cites += inc.date_of_incorporation.evidence[:1]
        gstin = self.identifier("gstin", c.gstin)
        state = GST_STATES.get(gstin.text[:2]) if gstin.text != NOT_ON_FILE else None
        rows = [("Legal name", _t(str(name.value), name.evidence[:1]) if name else _t(NOT_ON_FILE))]
        company = c.constitution in ("private_limited", "unknown")
        if company or self.facts.identities.cin:
            rows.append(("CIN", self.identifier("cin", c.cin)))
        if company or since:
            rows.append(("Date of incorporation", _t(display_date(since), inc.date_of_incorporation.evidence[:1])
                         if dated else _t(NOT_ON_FILE)))
        if company or kind:
            rows.append(("Company type", _t(str(kind.value), kind.evidence[:1]) if kind else _t(NOT_ON_FILE)))
        rows += [
            ("PAN", self.identifier("entity_pan", c.pan)),
            ("GSTIN", _t(f"{gstin.text} ({state})", gstin.citations) if state else gstin),
        ]
        office = (self.document_field("certificate_of_incorporation", "registered_address")
                  or self.document_field("memorandum_articles_of_association", "registered_office"))
        if office:
            rows.append(("Registered office", office))
        blocks = [_paragraph(text, cites), _facts(rows)]
        note = self.checks_note(ENTITY_CHECKS)
        return blocks + ([note] if note else [])

    def promoters(self) -> list[CamBlock]:
        if not self.people:
            return []
        names = self.type_names
        rows = [[_t(p.name, p.evidence()), _t(p.role or NONE), p.identifiers("din", names), p.identifiers("pan", names),
                 _t("Yes", p.evidence("director_kyc")) if p.kyc else _t("No"), _t(", ".join(p.sources(names)))]
                for p in self.people]
        blocks = [_table(["Name", "Role", "DIN", "PAN", "KYC on file", "Named in"], rows)]
        blocks += [_paragraph(f"No KYC has been received for {p.name}.", p.evidence()) for p in self.people if not p.kyc]
        note = self.checks_note(PEOPLE_CHECKS)
        return blocks + ([note] if note else [])

    def proposal(self) -> list[CamBlock]:
        c, f = self.case, self.facts
        products = {facility: p.label for p in self.matrix.products for facility in p.facilities}
        rows = [[_t(self.facility_names.get(i, i)), _t(products.get(i, "Not in the approval matrix"))]
                for i in c.facilities]
        names = _join([_lower(n) for n in self.facility_list()]) or "facilities"
        total = " in total" if len(c.facilities) > 1 else ""
        declared = self.declared_turnover()
        turnover = (f" The sourcing message states annual turnover of {inr(declared.value)}." if declared
                    else " The sourcing message does not state the turnover.")
        blocks = [_table(["Facility", "Product"], rows),
                  _paragraph(f"The proposal is for {names} of {inr(c.amount_inr)}{total}.{turnover}",
                             (f.requested_amount.evidence if f.requested_amount else [])
                             + (declared.evidence if declared else []))]
        blocks += [self.resolution(a) for a in f.authority]
        blocks.append(_paragraph("Collateral: offered, as recorded on the case at intake; nature and value not on file."
                                 if c.collateral_present else "Collateral: none offered, as recorded on the case at intake."))
        if len(c.facilities) > 1:
            blocks.append(self.amounts_used())
        return blocks

    def resolution(self, a: AuthorityFact) -> CamBlock:
        """What a board resolution for borrowing authorises, and whether it covers the amount requested."""
        when = parse_date(a.resolution_date.value) if a.resolution_date else None
        limit = float(a.borrowing_limit.value) if a.borrowing_limit and a.borrowing_limit.value else None
        purpose = self.field_of(a.document_id, "purpose_of_borrowing")
        text = f"The board resolution{f' of {display_date(when)}' if when else ''} authorises borrowing"
        text += f" from {a.lender.value}" if a.lender and a.lender.value else ""
        text += f" up to {inr(limit)}" if limit is not None else ""
        text += f" for {_lower(purpose.text.rstrip('.'))}" if purpose else ""
        signatories = [s.name for s in a.signatories]
        text += f"; signatories: {_join(signatories)}." if signatories else "."
        amount = self.case.amount_inr
        if limit is None:
            text += " The borrowing limit is not on file."
        elif limit < amount:
            text += f" It covers {inr(limit)} of the {inr(amount)} requested; a fresh resolution is needed."
        else:
            text += f" It covers the {inr(amount)} requested."
        cites = [e for v in (a.resolution_date, a.lender, a.borrowing_limit) if v for e in v.evidence]
        cites += (purpose.citations if purpose else []) + [e for s in a.signatories for e in s.evidence[:1]]
        return _paragraph(text, cites)

    def amounts_used(self) -> CamBlock:
        """What the working-capital method, the norms and the authority are worked out on while the
        amount of each facility is not captured on the case."""
        c, requested = self.case, self.facts.requested_amount
        other = self.term_facilities()
        users = (["the working-capital method" + self.section("working_capital")]
                 if set(c.facilities) & policy_module.WORKING_CAPITAL else [])
        users += ["the policy norms", "the approving authority" + self.section("policy")]
        including = f", including the {_join(other)}" if other and len(other) < len(c.facilities) else ""
        sets_out = "; the sourcing message sets out the facilities asked for" if self.message_doc else ""
        return _paragraph(f"Amounts per facility are not captured on the case{sets_out}. {_upper(_join(users))} therefore "
                          f"use the total of {inr(c.amount_inr)}{including}.",
                          requested.evidence if requested and self.message_doc else [])

    def financial_performance(self) -> list[CamBlock]:
        columns = self.spread.columns
        shown = [i for i, c in enumerate(columns) if c.basis in ("audited", "provisional")][-3:]
        if not shown:
            return []
        rows = {r.key: r for r in self.spread.rows}
        revenue = rows.get("revenue_from_operations")
        dscr = self.norm(self.ratio_norms.get("dscr"))
        latest = next((i for i in reversed(shown) if columns[i].fy == self.assessment.period
                       and columns[i].basis == "audited"), shown[-1])

        def previous(i: int) -> int | None:
            year = int(columns[i].period_end[:4])
            return next((j for j, c in enumerate(columns) if c.basis == columns[i].basis
                         and int(c.period_end[:4]) == year - 1), None)

        prior = previous(latest)
        restated = self.comparatives(columns[latest].fy) if columns[latest].basis == "audited" else {}
        earlier_fy = self.prior_fy(columns[latest].period_end)
        # The previous year's own statements are not on file: the latest statements' comparatives stand in.
        stand_in = prior is None and bool(restated)

        def cell(key: str, i: int) -> tuple[float | None, list[Evidence]]:
            if key == "growth":
                j = previous(i)
                now = revenue.cells[i].value if revenue else None
                if j is None and i == latest and stand_in and "revenue_from_operations" in restated:
                    before, before_cites = restated["revenue_from_operations"]
                else:
                    before = revenue.cells[j].value if revenue and j is not None else None
                    before_cites = revenue.cells[j].evidence if revenue and j is not None else []
                if now is None or not before:
                    return None, []
                return (now - before) / before * 100, revenue.cells[i].evidence + before_cites
            if key == "dscr":
                if i == latest and dscr is not None and dscr.actual is not None:
                    return dscr.actual, norm_evidence(dscr)
                return None, []
            row = rows.get(key)
            return (row.cells[i].value, row.cells[i].evidence) if row else (None, [])

        def written(value: float | None, unit: str) -> str:
            if value is None:
                return NONE
            if unit == "inr":
                return inr(value)
            return f"{_number(value, 2)}x" if unit == "x" else _number(value, 1 if unit == "%" else 0)

        stand_in_label = f"{earlier_fy} (comparatives in the {columns[latest].fy} statements)"
        specs: list[tuple[str, object]] = []
        for i in shown:
            if i == latest and stand_in:
                specs.append((stand_in_label, lambda key: restated.get(key, (None, []))))
            specs.append((f"{columns[i].fy} ({columns[i].basis})", lambda key, i=i: cell(key, i)))
        table = []
        for key, label, unit in FINANCIAL_ROWS:
            cells = [figure(key) for _, figure in specs]  # type: ignore[operator]
            if all(v is None for v, _ in cells):
                continue
            table.append([_t(label), *[_t(written(v, unit), e) for v, e in cells]])
        header = ["Particulars", *[h for h, _ in specs]]
        if prior is not None:
            before = (columns[prior].fy, cell("revenue_from_operations", prior))
        elif stand_in and "revenue_from_operations" in restated:
            before = (f"{earlier_fy} (the comparatives in the {columns[latest].fy} statements)",
                      restated["revenue_from_operations"])
        else:
            before = None
        blocks = [_table(header, table, numeric=list(range(1, len(header)))),
                  *self.performance(columns[latest].fy, {key: cell(key, latest) for key, _, _ in FINANCIAL_ROWS}, before)]
        if prior is not None and restated:
            blocks += self.restatement(columns[latest].fy, columns[prior].fy, {key: cell(key, prior) for key, _ in RESTATED},
                                       restated)
        named = []
        for i in shown:
            for doc in self.column_documents(i):
                if doc in self.other_names:
                    name, ref = self.other_names[doc]
                    named.append(f"The {columns[i].fy} statements are in the name of {name} ({ref}).")
        blocks += [_note(text) for text in dict.fromkeys(named)]
        dscr_shown = any(r[0].text == "DSCR" for r in table)
        blocks.append(_note("Figures as on the spread (interim layout)"
                            + (f"; DSCR as assessed under the policy norms{self.see('policy')}." if dscr_shown else ".")))
        return blocks

    def restatement(self, fy: str, earlier: str, own: dict[str, tuple[float | None, list[Evidence]]],
                    restated: dict[str, tuple[float, list[Evidence]]]) -> list[CamBlock]:
        """Where the latest statements' comparatives differ from the previous year's own statements by
        more than the tolerance (FS-01's), both figures."""
        tolerance = self.tolerances.get("comparatives_variance", 1)
        differ = []
        for key, label in RESTATED:
            (value, cites), shown = own.get(key, (None, [])), restated.get(key)
            if value is None or shown is None or abs(value - shown[0]) <= tolerance / 100 * max(abs(value), abs(shown[0])):
                continue
            differ.append((f"{label} {inr(shown[0])} against {inr(value)}", shown[1] + cites))
        if not differ:
            return []
        return [_paragraph(f"The {fy} statements give different figures for {earlier}: {_join([t for t, _ in differ])} "
                           f"in the {earlier} statements.", [e for _, c in differ for e in c])]

    def performance(self, fy: str, figures: dict[str, tuple[float | None, list[Evidence]]],
                    before: tuple[str, tuple[float | None, list[Evidence]]] | None) -> list[CamBlock]:
        """The latest year in words: revenue, profitability, leverage and liquidity, each figure set
        against the policy norm that assessed it."""
        ratio = lambda key: self.norm(self.ratio_norms.get(key))  # noqa: E731
        line = lambda key: self.norm(self.line_norms.get(key))  # noqa: E731
        out = []
        revenue, cites = figures["revenue_from_operations"]
        last, (earlier, earlier_cites) = before if before else ("", (None, []))
        if revenue is not None and earlier:
            change = (revenue - earlier) / earlier * 100
            moved = ("was unchanged at" if round(change, 1) == 0
                     else f"{'rose' if change > 0 else 'fell'} {abs(change):.1f}% to")
            out.append(_paragraph(f"Revenue from operations {moved} {inr(revenue)} in {fy}, from {inr(earlier)} in {last}.",
                                  cites + earlier_cites))
        elif revenue is not None:
            out.append(_paragraph(f"Revenue from operations was {inr(revenue)} in {fy}.", cites))

        def share(key: str) -> str:
            margin = figures[key][0]
            return f", {_number(margin, 1)}% of revenue" if margin is not None else ""

        def paragraph(sentences: list[tuple[str, list[Evidence]]]) -> None:
            if sentences:
                text = " ".join([f"In {fy}, {_lower(sentences[0][0])}"] + [s for s, _ in sentences[1:]])
                out.append(_paragraph(text, [e for _, c in sentences for e in c]))

        sentences = []
        ebitda, cites = figures["ebitda"]
        if ebitda is not None:
            sentences.append((f"EBITDA was {inr(ebitda)}{share('ebitda_margin')}.", cites))
        profit, cites = figures["profit_after_tax"]
        if profit is not None:
            sentences.append((f"Profit after tax was {inr(profit)}{share('pat_margin')}"
                              f"{self.against(line('profit_after_tax'))}.", cites))
        coverage, cites = figures["interest-coverage"]
        if coverage is not None:
            sentences.append((f"Interest coverage was {_number(coverage, 2)}x{self.against(ratio('interest-coverage'))}.",
                              cites))
        paragraph(sentences)

        sentences = []
        (worth, cites), (borrowings, owed) = figures["net_worth"], figures["total_borrowings"]
        if worth is not None:
            against = f", against total borrowings of {inr(borrowings)}" if borrowings is not None else ""
            sentences.append((f"Net worth was {inr(worth)}{self.against(line('net_worth'))}{against}.",
                              cites + (owed if borrowings is not None else [])))
        leverage = [(label, key) for key, label in (("debt-equity", "debt / equity"), ("tol-tnw", "TOL / TNW"))
                    if figures[key][0] is not None]
        if leverage:
            text = ", and ".join(f"{label}{' was' if n == 0 else ''} {_number(figures[key][0], 2)}x"
                                 f"{self.against(ratio(key))}" for n, (label, key) in enumerate(leverage))
            sentences.append((text[:1].upper() + text[1:] + ".", [e for _, key in leverage for e in figures[key][1]]))
        paragraph(sentences)

        sentences = []
        current, cites = figures["current-ratio"]
        if current is not None:
            sentences.append((f"The current ratio was {_number(current, 2)}x{self.against(ratio('current-ratio'))}.",
                              cites))
        cycle, cites = figures["wc-cycle"]
        if cycle is not None:
            sentences.append((f"The working-capital cycle was {_number(cycle, 0)} days{self.against(ratio('wc-cycle'))}.",
                              cites))
        paragraph(sentences)
        return out

    def working_capital(self) -> list[CamBlock]:
        wc = self.spread.working_capital
        if wc.method == "not_applicable":
            blocks = [_paragraph(wc.reason)]
        elif wc.missing:
            blocks = [_paragraph(f"{wc.reason} It cannot be computed: {_join(wc.missing)} not on file.")]
        else:
            inputs = [e for s in wc.steps for e in s.evidence[:1]]
            table = _table(["Step", "Amount", "Basis"], [
                [_t(s.label), _t(inr(s.value), s.evidence[:2] or inputs), _t(s.basis or "")] for s in wc.steps
            ], numeric=[1])
            verdict = "within" if wc.eligible is not None and wc.requested <= wc.eligible else "above"
            other = self.term_facilities()
            total = ""
            if other and len(other) < len(self.case.facilities):
                limit = self.policy_config.working_capital.mpbf_above_limit_inr
                total = f" The comparison uses the total request, including the {_join(other)}"
                total += (f"; on a working-capital amount of {inr(limit)} or less the turnover method would apply."
                          if wc.method == "mpbf" else ".")
            blocks = [_paragraph(wc.reason), table,
                      _paragraph(f"On the figures for {wc.column}, eligible bank finance is {inr(wc.eligible)}; the "
                                 f"request of {inr(wc.requested)} is {verdict} it.{total}", inputs)]
        if set(self.case.facilities) & policy_module.TERM:
            blocks.append(self.term_loan())
        return blocks

    def term_loan(self) -> CamBlock:
        """The proposed instalment and the DSCR on it, in one sentence where the DSCR could not be
        assessed for want of the instalment."""
        emi, n = self.facts.proposed_emi, self.norm(self.ratio_norms.get("dscr"))
        cites = list(emi.evidence) if emi is not None else []
        text = f"The proposed monthly instalment on the term loan is {inr(float(emi.value))}." if emi is not None else ""
        if n is not None and n.outcome in ("pass", "deviation"):
            text += f" DSCR is {n.actual_text}{self.against(n)}."
        elif n is not None and n.outcome == "cannot_evaluate":
            text += f" {_unassessed_sentence(n, set(self.facts.types_on_file))}"
        elif emi is None:
            text = "The proposed monthly instalment on the term loan is not on file."
        if n is not None:
            cites += norm_evidence(n)
        return _paragraph(text.strip(), cites)

    def statements(self, year: TurnoverYear) -> list[Evidence]:
        """A statement of each account behind the year's business credits (the year's figure cites the
        first account's only)."""
        end = date.fromisoformat(year.fy_end)
        out: list[Evidence] = []
        for c in self.facts.credits:
            months = sorted((m for m in c.by_month if m.evidence
                             and 0 <= (end.year - int(m.month[:4])) * 12 + end.month - int(m.month[5:7]) < 12),
                            key=lambda m: m.month)
            out += months[0].evidence[:1] if months else []
        return out

    def turnover(self) -> list[CamBlock]:
        blocks = []
        if self.facts.turnover:
            rows = []
            for y in self.facts.turnover:
                by = {f.source: f for f in y.figures}
                rows.append([_t(y.fy), *[_figure(by.get(source), self.statements(y) if source == "bank" else [])
                                         for source, _ in TURNOVER_COLUMNS]])
            blocks.append(_table(["Financial year", *[label for _, label in TURNOVER_COLUMNS]], rows,
                                 numeric=list(range(1, len(TURNOVER_COLUMNS) + 1))))
        found = self.discrepancies("turnover", "tax")
        if found:
            # Each is explained once, in the cross-verification section.
            where = f", set out in section {self.numbers['cross_verification']}" if "cross_verification" in self.numbers else ""
            listed = "; ".join(f"{finding_title(i.finding)} ({i.finding.ref or i.finding.rule_id})" for i in found)
            blocks.append(_paragraph(f"The cross-checks found {_plural(len(found), 'discrepancy', 'discrepancies')} on "
                                     f"turnover and tax{where}: {listed}."))
        filed = self.filing()
        return blocks + ([filed] if filed else [])

    def filing(self) -> CamBlock | None:
        """Which returns are on file: GST months, income tax assessment years, whether each audited year
        that is due has its income tax return (TX-01), and the returns not yet due."""
        gst = [m for m in self.facts.months if m.gst is not None]
        tax = self.facts.tax_years
        if not (gst or tax or self.facts.turnover):
            return None
        cites: list[Evidence] = []
        if gst:
            text = (f"GST returns (GSTR-3B) are on file for {_plural(len(gst), 'month')}, "
                    f"{ranges_label([(int(m.month[:4]), int(m.month[5:7])) for m in gst])}")
            cites += [e for m in gst for e in m.gst_evidence[:1]]
        else:
            text = "No GST return is on file"
        if tax:
            years = _join([f"AY {t.assessment_year}" for t in tax])
            text += f"; income tax returns for {years}." if len(tax) > 1 else f"; an income tax return for {years}."
            cites += [e for t in tax for e in t.evidence[:1]]
        else:
            text += "; no income tax return is on file."
        returns = next((i.finding for i in self.board.items if self.rules.get(i.finding.rule_id)
                        and self.rules[i.finding.rule_id].variable == "itr_years"), None)
        # A failure is listed with the other turnover discrepancies above.
        if returns is not None and returns.outcome in ("pass", "incomplete"):
            text += f" {returns.explanation}"
        due_days = int(self.tolerances.get("itr_due_days", 214))
        as_of, filed = date.fromisoformat(self.case.as_of), {t.fy for t in tax}
        pending = [_assessment_year(date.fromisoformat(y.fy_end)) for y in self.facts.financial_years
                   if y.fy not in filed and date.fromisoformat(y.fy_end) + timedelta(days=due_days) > as_of]
        if pending:
            text += (f" The return for {_join(pending)} is not yet due." if len(pending) == 1
                     else f" The returns for {_join(pending)} are not yet due.")
        return _paragraph(text, cites)

    def banking(self) -> list[CamBlock]:
        blocks = []
        if self.facts.credits:
            rows = []
            for c in self.facts.credits:
                months = sorted(m.month for m in c.by_month)
                count = len(months) or len(c.months)
                span = ranges_label([(int(m[:4]), int(m[5:7])) for m in months])
                credited = [e for m in c.by_month for e in m.evidence[:1]]
                removed = [e for x in c.exclusions for e in x.evidence[:1]]
                rows.append([_t(c.account), _t(f"{count} ({span})" if span else str(count)), _t(inr(c.gross), credited),
                             _t(inr(c.excluded), removed), _t(inr(c.net), credited),
                             _t(inr(c.net / count) if count else NONE, credited)])
            blocks.append(_table(["Account", "Months", "Gross credits", "Excluded", "Business credits", "Average a month"],
                                 rows, numeric=[2, 3, 4, 5]))
        for c in self.facts.credits:
            if not c.exclusions:
                continue
            kinds: dict[str, list] = {}
            for x in c.exclusions:
                kinds.setdefault(x.label, []).append(x)
            parts = [f"{_lower(label)} {inr(sum(x.amount for x in found))} ({_plural(len(found), 'credit')})"
                     for label, found in kinds.items()]
            blocks.append(_paragraph(f"In {c.account}, {inr(c.excluded)} of credits is excluded from business credits: "
                                     f"{_join(parts)}.", [e for x in c.exclusions for e in x.evidence[:1]]))
        balances = self.balances()
        if balances:
            blocks.append(balances)
        for a in self.facts.accounts:
            if a.has_statement:
                continue
            where = [f"transfers in {s.removeprefix('Transfer in ')}" if s.startswith("Transfer in ")
                     else f"the {_lower(s)}" for s in a.sources]
            blocks.append(_paragraph(f"No statement has been received for {a.label}, which was "
                                     f"{'declared' if a.declared else 'not declared'} and appears in {_join(where)}.",
                                     a.evidence[:1]))
        return blocks

    def balances(self) -> CamBlock | None:
        """Each account's balance at the latest audited year end, against the cash and bank balances
        in that year's balance sheet."""
        year = next((y for y in self.facts.financial_years if y.fy == self.assessment.period), None)
        on = [b for b in self.facts.balances if year and b.date == year.fy_end]
        if not on:
            return None
        total = sum(b.balance for b in on)
        held = _join([f"{inr(b.balance)} in {b.account}" for b in on])
        text = (f"At {display_date(date.fromisoformat(year.fy_end))} the statements show {held}, {inr(total)} in all"
                if len(on) > 1 else f"At {display_date(date.fromisoformat(year.fy_end))} the statement shows {held}")
        cites = [e for b in on for e in b.evidence[:1]]
        audited = year.current.get("cash_and_bank_balances")
        if audited is not None and audited.value is not None:
            books = float(audited.value)
            text += f", against cash and bank balances of {inr(books)} in the {year.fy} balance sheet"
            if total > books * (1 + self.tolerances.get("balance_variance", 1) / 100):
                text += f"; the statements' balances exceed the audited figure by {inr(total - books)}"
            cites += audited.evidence[:1]
        return _paragraph(text + ".", cites)

    def existing_facilities(self) -> list[CamBlock]:
        f = self.facts
        declared = [x for x in f.facilities if x.source == facts_module.DECLARATION]
        sanctioned = [x for x in f.facilities if x.source == facts_module.SANCTION]
        reported = [x for x in f.facilities if x.source == facts_module.BUREAU]
        messaged = [x for x in f.facilities if x.source == facts_module.MESSAGE]
        message = str(f.declared_banking.value) if f.declared_banking and f.declared_banking.value else ""
        emi_pct = self.tolerances.get("emi_amount_match", 5)
        lenders: list[dict] = []
        # Grouped by lender as OB-01 groups them; the instalments seen in the bank join their lender.
        for x in declared + sanctioned + reported + messaged:
            group = next((g for g in lenders if self.same_lender(x.lender, g["name"])), None)
            if group is None:
                lenders.append({"name": x.lender, "facilities": [x], "paid": []})
            else:
                group["facilities"].append(x)
        for o in f.obligations:
            group = next((g for g in lenders if self.same_lender(o.lender, g["name"])), None)
            if group is None:
                lenders.append({"name": o.lender, "facilities": [], "paid": [o]})
            else:
                group["paid"].append(o)

        def amount(found: list, missing: str, present: str = "On file") -> CamText:
            known = [x for x in found if x.amount is not None]
            if not found:
                return _t(missing)
            return _t(inr(sum(x.amount for x in known)) if known else present, [e for x in found for e in x.evidence[:1]])

        rows, undeclared, message_only = [], [], []
        exposure, outstanding, exposure_cites, outstanding_cites = 0.0, 0.0, [], []
        for g in lenders:
            d = [x for x in g["facilities"] if x.source == facts_module.DECLARATION]
            s = [x for x in g["facilities"] if x.source == facts_module.SANCTION]
            b = [x for x in g["facilities"] if x.source == facts_module.BUREAU]
            m = [x for x in g["facilities"] if x.source == facts_module.MESSAGE]
            named = bool(m) or (bool(message) and _mentions(message, g["name"], self.noise, self.threshold))
            limited = any(x.amount is not None for x in s + b)
            if d:
                declared_cell = amount(d, "", "Declared")
            elif named:
                declared_cell = _t("In the sourcing message" + ("" if limited or not m else "; limit not on file"),
                                   f.declared_banking.evidence[:1] if f.declared_banking else [])
            else:
                declared_cell = _t("Not declared" if f.declaration_received or message else "No declaration on file")
            bureau_cell = amount(b, NONE)
            owed = [x for x in b if x.outstanding is not None]
            if owed:
                bureau_cell = _t(f"{bureau_cell.text}; outstanding {inr(sum(x.outstanding for x in owed))}",
                                 bureau_cell.citations)
                outstanding += sum(x.outstanding for x in owed)
                outstanding_cites += [e for x in owed for e in x.evidence[:1]]
            # Every instalment the lender's declared facilities carry, else its sanction letters', each once.
            counted_d, counted_s = policy_module.counted_facilities(d + s, self.noise, self.threshold, emi_pct)
            paying = counted_d or counted_s
            emi = (_t(inr(sum(x.emi for x in paying)) + (f" ({_plural(len(paying), 'facility', 'facilities')})"
                                                           if len(paying) > 1 else ""),
                      [e for x in paying for e in x.evidence[:1]]) if paying else _t(NONE))
            paid = g["paid"]
            rows.append([
                _t(g["name"]),
                _t(_join([x.facility for x in g["facilities"] if x.facility]) or NONE),
                declared_cell,
                amount(s, NONE),
                bureau_cell,
                emi,
                _t("; ".join(f"{inr(o.typical_amount)} ({_plural(len(o.months), 'month')})" for o in paid),
                   [e for o in paid for e in o.evidence[:1]]) if paid else _t(NONE),
            ])
            basis = next((found for found in (b, s, d) if any(x.amount is not None for x in found)), [])
            if basis:
                exposure += sum(x.amount for x in basis if x.amount is not None)
                exposure_cites += [e for x in basis for e in x.evidence[:1]]
            if paid and not d and not named:
                undeclared += [(g["name"], o) for o in paid]
            if m and not d and not b:
                message_only.append((g["name"], m, limited))
        blocks = []
        if rows:
            blocks.append(_table(["Lender", "Facility", "Declared", "Sanction letter", "Bureau", "Instalment",
                                  "Seen in the bank (a month)"], rows, numeric=[2, 3, 4, 5, 6]))
        if f.declaration_received and not declared and f.declaration is not None:
            blocks.append(_paragraph("The declaration of existing facilities declares none.", f.declaration.evidence[:1]))
        blocks += [self.message_facility(name, found, limited) for name, found, limited in message_only]
        rank = next((i for n in self.assessment.norms for i in n.inputs if i.name == "bureau_rank"), None)
        if rank is not None and rank.value is not None:
            norm = next((n for n in self.assessment.norms if any(i.name == "bureau_rank" for i in n.inputs)), None)
            blocks.append(_paragraph(f"The commercial bureau report gives the borrower rank {rank.value:g}"
                                     f"{self.against(norm)}.", rank.evidence[:1]))
        if exposure:
            counted = sum(1 for g in lenders if any(x.amount is not None for x in g["facilities"]))
            text = f"Existing sanctioned facilities total {inr(exposure)} across {_plural(counted, 'lender')}"
            text += f"; the commercial bureau report shows {inr(outstanding)} outstanding." if outstanding else "."
            blocks.append(_paragraph(text, exposure_cites + outstanding_cites))
        borrowings = self.borrowings()
        if borrowings:
            blocks.append(borrowings)
        if reported:
            overdue = [x for x in reported if x.overdue]
            text = ("The commercial bureau report shows overdues: "
                    + _join([f"{inr(x.overdue)} with {x.lender}" for x in overdue]) + "." if overdue
                    else "The commercial bureau report shows no overdue amount.")
            blocks.append(_paragraph(text, [e for x in (overdue or reported) for e in x.evidence[:1]]))
        if f.obligations:
            seen = sum(o.typical_amount for o in f.obligations)
            counted_d, counted_s = policy_module.counted_facilities(f.facilities, self.noise, self.threshold, emi_pct)
            due = sum(x.emi or 0 for x in counted_d + counted_s)
            text = f"Instalments seen in the bank total about {inr(seen)} a month"
            text += (f"; the facilities on file state instalments of {inr(due)} a month." if due
                     else "; no facility on file states an instalment.")
            blocks.append(_paragraph(text, [e for o in f.obligations for e in o.evidence[:1]]
                                     + [e for x in counted_d + counted_s for e in x.evidence[:1]]))
        why = ("the lender is not declared" if f.declaration_received or message
               else "no declaration of existing facilities is on file")
        for name, o in undeclared:
            # The lender as the table names it, with the statement's narration where that differs.
            called = name if name.casefold() == o.lender.casefold() else f"{name} ({o.lender} in the statement)"
            blocks.append(_paragraph(f"Debits of about {inr(o.typical_amount)} a month to {called} appear in {o.account} "
                                     f"in {_plural(len(o.months), 'month')}; {why}.", o.evidence[:2]))
        return blocks + self.disbursals()

    def message_facility(self, lender: str, found: list, limited: bool) -> CamBlock:
        """A facility only the sourcing message declares: which documents do not show it."""
        f = self.facts
        kinds = _join([_lower(x.facility) for x in found if x.facility]) or "facility"
        account = next((a for a in f.accounts for x in found if x.facility and not a.has_statement
                        and a.label.endswith(f"({_lower(x.facility)})") and a.bank and self.same_lender(a.bank, lender)), None)
        called = f"The {kinds} with {lender}" + (f" (account ·{account.last4})" if account and account.last4 else "")
        declaration, bureau = f.declaration is not None, facts_module.BUREAU in f.types_on_file
        if declaration and bureau:
            shown = "neither the declaration of existing facilities nor the commercial bureau report shows it"
        elif declaration:
            shown = "the declaration of existing facilities does not show it, and no commercial bureau report is on file"
        elif bureau:
            shown = "the commercial bureau report does not show it, and no declaration of existing facilities is on file"
        else:
            shown = "no declaration of existing facilities or commercial bureau report is on file to confirm it"
        limit = "" if limited else "; its limit is not on file"
        return _paragraph(f"{called} is declared only in the sourcing message: {shown}{limit}.",
                          [e for x in found for e in x.evidence[:1]])

    def disbursals(self) -> list[CamBlock]:
        """Each loan paid into an account, and whether a facility on file accounts for it."""
        f = self.facts
        unexplained = [o for o in f.obligations if not any(self.same_lender(o.lender, x.lender) for x in f.facilities)]
        out = []
        for c in f.credits:
            for x in c.exclusions:
                if x.rule != LOAN_DISBURSAL:
                    continue
                when = parse_date(x.date) if x.date else None
                lender = next((y.lender for y in f.facilities if _mentions(x.narration, y.lender, self.noise, self.threshold)),
                              None)
                text = f"A loan of {inr(x.amount)} was disbursed into {x.account}" \
                       f"{f' on {display_date(when)}' if when else ''} ({x.narration})"
                if lender:
                    text += f"; the narration names {lender}, a lender on file."
                else:
                    text += "; no facility on file matches it" + (
                        "." if unexplained else " and no instalment for it appears in the statements.")
                out.append(_paragraph(text, x.evidence[:1]))
        return out

    def borrowings(self) -> CamBlock | None:
        """The latest balance sheet's borrowings, long-term and short-term, and whether a working-capital
        facility on file accounts for the short-term borrowings."""
        i = self.latest_column()
        if i is None:
            return None
        rows = {r.key: r for r in self.spread.rows}
        figure = lambda key: (rows[key].cells[i].value, rows[key].cells[i].evidence) if key in rows else (None, [])  # noqa: E731
        (total, total_cites), long, short = figure("total_borrowings"), figure("long_term_borrowings"), \
            figure("short_term_borrowings")
        parts = [(f"{inr(value)} {term}", cites) for term, (value, cites) in (("long-term", long), ("short-term", short))
                 if value is not None]
        fy = self.spread.columns[i].fy
        if total is not None:
            text = f"The {fy} balance sheet shows borrowings of {inr(total)}" + (
                f": {_join([p for p, _ in parts])}." if parts else ".")
        elif parts:
            text = f"The {fy} balance sheet shows {_join([p for p, _ in parts])} borrowings."
        else:
            return None
        if short[0] and short[0] > 0 and not any(x.facility and WORKING_CAPITAL_NAME.search(x.facility)
                                                 for x in self.facts.facilities):
            text += " No working-capital facility is on file to account for the short-term borrowings."
        return _paragraph(text, total_cites + [e for _, cites in parts for e in cites])

    def cross_verification(self) -> list[CamBlock]:
        b = self.board
        if b.run is None:
            return []
        blocks = [_paragraph(f"The latest cross-check run, {b.run.id}, applied {_plural(b.run.rules, 'check')} to "
                             f"{_plural(b.run.sources, 'type')} of source document.")]
        rows = []
        for a in b.areas:
            accepted = sum(1 for i in b.items if i.finding.area == a.area and status(i) == ACCEPTED)
            counts = (a.rules, a.discrepancies, accepted, a.open, a.incomplete)
            rows.append([_t(AREAS.get(a.area, a.area)), *[_t(str(n)) for n in counts]])
        blocks.append(_table(["Area", "Checks", "Discrepancies", "Accepted as valid", "Open", "Could not be completed"],
                             rows, numeric=[1, 2, 3, 4, 5], title="Checks by area"))
        incomplete = self.incomplete()
        if incomplete:
            blocks.append(_table(["Check", "Why", "What would complete it"], [
                [_t(i.finding.title), _t(i.finding.explanation), _t(_upper(i.finding.request or NONE))]
                for i in incomplete], title="Checks not completed"))
        failed = [i for i in b.items if i.finding.outcome == "fail"]
        if not failed:
            return blocks + [_paragraph("No discrepancy was found.")]
        rows = []
        for i in failed:
            f = i.finding
            standing = status(i) + ("; blocks submission" if f.blocking and not i.adjudicated else "")
            rows.append([_t(f.ref or f.rule_id), _t(SEVERITY[f.severity]), _t(stated_title(f)),
                         _t(f.explanation, finding_evidence(f, self.threshold)), _t(standing)])
        return blocks + [_table(["Ref", "Severity", "Finding", "Detail", "Status"], rows, title="Discrepancies")]

    def policy(self) -> list[CamBlock]:
        norms = [n for n in self.assessment.norms if n.outcome != "not_applicable"]
        outcomes = [n.outcome for n in norms]
        period = f", on the {self.assessment.period} statements" if self.assessment.period else ""
        on_file = set(self.facts.types_on_file)
        blocks = [_paragraph(f"{_plural(len(norms), 'norm')} {'applies' if len(norms) == 1 else 'apply'}{period}: "
                             f"{_plural(outcomes.count('deviation'), 'deviation')}, "
                             f"{outcomes.count('cannot_evaluate')} not assessed and {outcomes.count('pass')} met.")]
        if norms:
            blocks.append(_table(["Norm", "Required", "Actual", "Result", "Category"], [
                [_t(f"{n.label} ({n.id})"), _t(n.required),
                 _t(n.actual_text, norm_evidence(n)) if n.actual_text else _t(NONE), _t(RESULT[n.outcome]),
                 _t(n.category_label)] for n in norms], numeric=[1, 2], note=self.years_note(norms)))
        provisional = [n for n in norms if n.provisional]
        if provisional:
            blocks.append(_note("Every norm is an interim proposal awaiting RBL's policy norms."
                                if len(provisional) == len(norms) else f"{len(provisional)} of {len(norms)} norms are "
                                "interim proposals awaiting RBL's policy norms."))
        blocks += [_paragraph(_deviation_sentence(n), norm_evidence(n)) for n in norms if n.outcome == "deviation"]
        blocks += [_paragraph(_unassessed_sentence(n, on_file), norm_evidence(n)) for n in norms
                   if n.outcome == "cannot_evaluate"]
        return blocks + [_subheading("Approving authority"), _facts(self.authority_facts())]

    def years_note(self, norms: list[NormResult]) -> str | None:
        """Beside the norm that counts the years of audited statements: a year counted from statements
        in another name."""
        columns = self.spread.columns
        fy_of = {doc: columns[i].fy for i in range(len(columns)) for doc in self.column_documents(i)}
        notes = []
        for n in norms:
            if not any(i.name == "audited_years" for i in n.inputs):
                continue
            for e in norm_evidence(n):
                if e.document_id in self.other_names:
                    name, ref = self.other_names[e.document_id]
                    year = fy_of.get(e.document_id)
                    notes.append(f"{n.id} counts the {year + ' ' if year else ''}statements, which are in the name of "
                                 f"{name} ({ref}).")
        return " ".join(dict.fromkeys(notes)) or None

    def documentation(self) -> list[CamBlock]:
        r = self.readiness
        rows = [("Readiness", _t(f"{r.score_pct:g}% against a review gate of {r.gate_pct}%")),
                ("Blocking items open", _t(str(r.blocking_open)))]
        if r.provisional:
            rows.append(("Checklist", _t("Provisional until the constitution and the facilities are confirmed")))
        blocks = [_facts(rows)]
        open_items = [res for res in self.results if res.state.status in ITEM_STATUS]
        if open_items:
            blocks.append(_table(["Item", "Status", "What is missing"], [
                [_t(res.state.name), _t(ITEM_STATUS[res.state.status]),
                 _t(_missing(res.state.deficiency), _evidence(e for d in res.deficiencies for e in d.evidence))]
                for res in open_items]))
        # An outdated document makes its item insufficient, so the table above names it; only one
        # whose item is not listed there is stated here.
        outdated = [d for res in self.results if res.state.status not in ITEM_STATUS for d in res.deficiencies
                    if d.kind == "outdated"]
        if outdated:
            listed = "; ".join(f"{d.name}, dated {d.extra['date']} (permitted age {d.extra['max_age_days']} days)"
                               for d in outdated)
            blocks.append(_paragraph(f"Outdated documents: {listed}.", _evidence(e for d in outdated for e in d.evidence)))
        return blocks

    # --- The approving authority and the summary ---

    def authority_text(self) -> str:
        a = self.authority
        if a.required is None:
            return "Not determined: no facility requested is in the approval matrix"
        matrix = " (provisional matrix)" if a.provisional else ""
        return ("At least " if a.lower_bound else "") + a.required.label + matrix

    def authority_facts(self) -> list[tuple[str, CamText]]:
        a = self.authority
        if a.required is None:
            return [("Authority required", _t(self.authority_text()))]
        requested = self.facts.requested_amount
        rows = [("Amount requested", _t(inr(a.amount_inr), requested.evidence if requested else []))]
        if len(self.case.facilities) > 1:
            each = " for each product" if len(a.products) > 1 else ""
            rows.append(("Amounts used", _t(f"The total of {inr(a.amount_inr)}{each} (amounts per facility not captured)")))
        for s in a.steps:
            if s.kind == "amount":
                band = (f"above {inr(s.band_from_inr)} up to {inr(s.band_to_inr)}" if s.band_from_inr and s.band_to_inr
                        else f"up to {inr(s.band_to_inr)}" if s.band_to_inr else f"above {inr(s.band_from_inr)}")
                rows.append((f"Amount authority, {_lower(s.product_label or s.product or '')}",
                             _t(f"{s.authority.label} (amounts {band})")))
            else:
                levels = {1: "one level", 2: "two levels", 3: "three levels"}.get(s.levels_above or 0,
                                                                                  _plural(s.levels_above or 0, "level"))
                rule = [f"{levels} above the amount authority" if s.levels_above else "the amount authority"]
                # The floor is named only where it decided the authority.
                rule += [f"at least {s.at_least.label}"] if s.at_least and s.at_least.level == s.authority.level else []
                rule += ["capped at the highest authority"] if s.capped else []
                rule += [_join([f"{n} {label}" for n, label in zip(s.norms, s.norm_labels)])]
                rows.append((f"Deviation, {_lower(s.category_label or s.category or '')}",
                             _t(f"{s.authority.label} ({'; '.join(rule)})")))
        rows.append(("Authority required", _t(("At least " if a.lower_bound else "") + a.required.label)))
        if a.lower_bound and a.could_rise_to is not None:
            verb = "proves a deviation" if len(a.unevaluated_labels) == 1 else "prove deviations"
            unassessed = _join([_lower(n) for n in a.unevaluated_labels])
            rows.append(("Could rise to", _t(f"No change if {unassessed} {verb}" if a.could_rise_to.level == a.required.level
                                             else f"{a.could_rise_to.label}, if {unassessed} {verb}")))
        if a.provisional:
            rows.append(("Matrix", _t("Provisional matrix")))
        return rows

    def summary(self) -> list[CamSummaryItem]:
        """The findings as a register (each explained in the cross-verification section), the checks
        not completed with what would complete them, the deviations, the norms not assessed and the
        open queries."""
        items: list[CamSummaryItem] = []
        for i in self.discrepancies():
            f = i.finding
            items.append(CamSummaryItem(kind="finding", text="", severity=f.severity, ref=f.ref or f.rule_id,
                                        rule=f.rule_id, title=finding_title(f), status=status(i),
                                        blocking=f.blocking and not i.adjudicated,
                                        citations=finding_evidence(f, self.threshold)))
        for i in self.incomplete():
            f = i.finding
            items.append(CamSummaryItem(kind="incomplete", text=f.explanation, severity=f.severity, ref=f.rule_id,
                                        rule=f.rule_id, title=f.title, request=f.request))
        for n in self.assessment.norms:
            if n.outcome == "deviation":
                items.append(CamSummaryItem(kind="deviation", ref=n.id, rule=n.id, title=n.label,
                                            text=f"{n.category_label}: {_norm_statement(n)}.",
                                            citations=norm_evidence(n)))
        on_file = set(self.facts.types_on_file)
        for n in self.assessment.norms:
            if n.outcome == "cannot_evaluate":
                items.append(CamSummaryItem(kind="unassessed", ref=n.id, rule=n.id, title=n.label,
                                            text=_unassessed_sentence(n, on_file), citations=norm_evidence(n)))
        findings = {i.finding.id: i.finding for i in self.board.items}
        for q in self.queries:
            # A query raised by a finding cites the finding's pages, as the memo cites the finding.
            found = findings.get(q.source_ref.split(":", 1)[-1]) if q.source_kind == "finding" else None
            items.append(CamSummaryItem(kind="query", ref=q.id, group=q.group, text=q.text,
                                        citations=finding_evidence(found, self.threshold) if found else _unique(q.evidence)))
        return items


def _figure(f: TurnoverFigure | None, more: list[Evidence]) -> CamText:
    if f is None or f.value is None:
        return _t(NONE)
    partial = f" ({f.months_covered} of 12 months)" if f.months_covered is not None and f.months_covered < 12 else ""
    return _t(f"{inr(f.value)}{partial}", [*f.evidence, *more])


def _assessment_year(fy_end: date) -> str:
    start = fy_end.year if fy_end.month <= 3 else fy_end.year + 1
    return f"AY {start}-{str(start + 1)[2:]}"


def norm_evidence(n: NormResult) -> list[Evidence]:
    return _unique(e for i in n.inputs for e in i.evidence)


def _evidence(found) -> list[Evidence]:
    return _unique(Evidence.model_validate(e) for e in found if e.get("document_id") and e.get("page"))


def _missing(deficiency: str | None) -> str:
    text = (deficiency or "").removeprefix("Not received: ").strip()
    return text[:1].upper() + text[1:] if text else NONE


def _norm_statement(n: NormResult) -> str:
    """A norm's result in a sentence, without its full stop: "DSCR is 1.05x against a norm of at least
    1.20x"; a norm in words reads "where the norm is none"."""
    against = f", where the norm is {n.required}" if n.required in WORD_NORMS else f" against a norm of {n.required}"
    if n.unit == "count":
        return f"{n.label}: {n.actual_text}{against}"
    years = re.fullmatch(r"Years of (.+)", n.label)
    if years:
        return f"{_upper(years[1])} cover {n.actual_text}{against}"
    return f"{n.label} is {n.actual_text}{against}"


def _deviation_sentence(n: NormResult) -> str:
    return f"{_norm_statement(n)} ({n.category_label})."


def _unassessed_sentence(n: NormResult, on_file: set[str] | None = None) -> str:
    """Why a norm has no result: the inputs not on file, a zero divisor, or a figure in review."""
    inputs = _join(n.reason_inputs)
    if n.reason == "zero_denominator":
        return f"{n.label} could not be computed: {_lower(inputs)} is zero."
    if n.reason == "denominator_not_positive":
        return f"{n.label} could not be computed: {_lower(inputs)} is zero or negative."
    if n.reason == "awaiting_review":
        return f"{n.label} could not be assessed: {_lower(inputs)} awaits review."
    if n.missing == ["Commercial bureau rank"]:
        report = ("The commercial bureau report on file gives no rank" if "commercial_bureau_report" in (on_file or set())
                  else "The commercial bureau report is not on file")
        return f"{report}, so the {_lower(n.label)} could not be assessed."
    if [m.casefold() for m in n.missing] == [n.label.casefold()]:
        return f"{n.label} is not on file, so it could not be assessed."
    phrases = [INPUT_PHRASES.get(m, _lower(m)) for m in n.missing]
    verb = "are" if len(phrases) > 1 or n.missing[0] in PLURAL_INPUTS else "is"
    return f"{n.label} could not be assessed: {_join(phrases)} {verb} not on file."


def build(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> Cam:
    d = Draft(conn, root, case)
    config = d.config
    sections = []
    for number, s in enumerate(config.sections, start=1):
        blocks = getattr(d, s.kind)()
        sections.append(CamSection(id=s.id, number=number, title=s.title, blocks=blocks,
                                   empty=None if blocks else "Nothing on file yet."))
    cam = Cam(
        case_id=case.id, title=config.title, borrower=case.borrower, as_of=case.as_of,
        config_version=reader.published_version(root)["version"], config_label=config_label(root),
        run_id=d.board.run.id if d.board.run else None,
        interim_template=config.interim_template, template_note=config.template_note, sections=sections,
        summary_number=len(sections) + 1, summary_title=config.summary_title, summary=d.summary(),
        recommendation_number=len(sections) + 2, recommendation_title=config.recommendation_title,
        recommendation_prompts=config.recommendation_prompts, sign_off=[CamSignOff(role=r) for r in config.sign_off],
        labels=dict(getattr(config, "labels", None) or {}),
    )
    cam.sources = output_sources.sources(conn, root, case.id, output_sources.cam_citations(cam))
    return cam
