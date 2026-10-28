"""The draft Credit Approval Memo (FRD F-23).

Sections in the configured order (config/cam.yaml): an assumed layout, modelled on a business-banking
credit approval memo, until RBL's template arrives (F-23.1). Each section is drafted from the facts
only, in a neutral register, as blocks of paragraphs, key facts, tables, subheadings and notes, and
every figure carries the pages it rests on (F-23.2). The memo ends with a structured summary of
findings (F-19), checks not completed, deviations (F-20) and open queries (F-14) (F-23.3), then an
empty recommendation with the prompts credit completes and the sign-off (F-23.4). The documents
cited are numbered in the order they are first cited (engine/output_sources.py), so the screen and
the downloads agree. Each finding's explanation is stated once, in the cross-verification section;
the summary lists the findings as a register. The material facts the memo states that need the
promoter's answer (a fall in revenue, borrowings no facility on file explains) are its observations,
which the PD note asks in the memo's own words (Draft.observations), so the two agree.

The text is composed from the facts, not written by a model, and reads no clock, so the same case
always gives the same memo (F-23.6, principle 6).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import cached_property
from pathlib import Path

from . import approval, completeness, facts as facts_module, output_sources, policy as policy_module, reads
from . import cam_copilot, cam_review, cam_templates
from . import spread as spread_module, statements as statements_module, xv
from .config import find_user_by_id, load_app_config
from .configstore import reader
from .contracts import (
    AuthorityFact,
    Cam,
    CamBlock,
    CamFact,
    CamPart,
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
from .units import money
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
COMPARATIVE_ROWS = ("revenue_from_operations", "ebitda", "profit_before_tax", "profit_after_tax", "share_capital",
                    "reserves_and_surplus", "net_worth", "total_borrowings")
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
NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")
# Observations, the material facts the memo states that the PD note asks the promoter about: a fall
# in revenue or net worth year on year of this much (%), serious from the second figure; and a gap
# between the balance sheet and the documents on file as large as both its amount (INR) and its
# share of the larger figure (%).
FALL_PCT, SERIOUS_FALL_PCT = 25, 50
BORROWINGS_GAP = (2_500_000, 20)
CASH_GAP = (1_000_000, 20)
# The identifier an identity check compares, as a sentence names it.
IDENTIFIER_NOUN = {"entity_pan": "PAN", "gstin": "GSTIN", "cin": "CIN", "legal_name": "legal name"}
# What the cross-checks call the bank credits left after the exclusions, and what the memo calls them.
CLEANSED = re.compile(r"cleansed bank credits", re.I)


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
    return text[:1].lower() + text[1:] if not text[1:2].isupper() else text


def _upper(text: str) -> str:
    return text[:1].upper() + text[1:]


def _a(text: str) -> str:
    text = _lower(text)
    return f"{'an' if text[:1] in 'aeiou' else 'a'} {text}"


def _number(value: float, decimals: int) -> str:
    text = f"{value:.{decimals}f}"
    return text[1:] if text.startswith("-") and float(text) == 0 else text


def _count(n: int) -> str:
    """A small count in words ("three"), a larger one in figures."""
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


def plain(text: str) -> str:
    """A check's wording as the memo and the note use it: business credits, never cleansed bank credits."""
    return CLEANSED.sub("business credits", text or "")


def sentence_case(text: str) -> str:
    """A configured name as a sentence writes it: capitalised words after the first in lower case,
    acronyms kept ("Income Tax Return" reads "Income tax return")."""
    words = text.split(" ")
    return " ".join([words[0]] + [w.lower() if w[:1].isupper() and w[1:].islower() else w for w in words[1:]])


def _change(now: float, before: float) -> str:
    """How a figure moved on an earlier one: "up 17.6%", "down 50.6%", "unchanged"."""
    change = (now - before) / before * 100
    return "unchanged" if round(change, 1) == 0 else f"{'up' if change > 0 else 'down'} {abs(change):.1f}%"


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
    title = plain(f.finding_title or f.compares or f.title)
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


def finding_evidence(f: Finding, threshold: float = 0.85, naming=None) -> list[Evidence]:
    """The pages a finding rests on, read from its card's columns. A finding about particular rows (a
    person, an account, a lender, a month) cites, in each column, the rows that name them; a column
    that does not name them is cited by its first page only when it is one document (the list on that
    page leaves them out), never by another row's own document (another person's KYC). A row missing
    from a column is cited where `naming` (a name to its pages) finds it named, the memorandum for a
    director. Any other finding cites every page of a column that differs and the first page of each
    other column. A finding without columns cites the first page of each side."""
    if not f.columns:
        return _pages(e for s in f.sides for e in s.evidence[:1])
    flagged = [r.label for r in f.detail.rows if r.flagged] if f.detail else []
    out: list[Evidence] = []
    absent: list[str] = []
    for column in f.columns:
        if flagged:
            named = [e for label in flagged for r in _naming(column.rows, label, threshold) for e in r.evidence]
            documents = {e.document_id for r in column.rows for e in r.evidence}
            out += named or (column.evidence[:1] if len(documents) <= 1 else [])
            absent += [label for label in flagged if not _naming(column.rows, label, threshold)]
        else:
            out += column.evidence if column.differs else column.evidence[:1]
    if naming is not None:
        out += [e for label in dict.fromkeys(absent) for e in naming(label)]
    return _pages(out) or _pages(e for c in f.columns for e in c.evidence[:1])


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


def naming(found: list[Person], threshold: float):
    """A name to the pages that name that person (finding_evidence's `naming`)."""
    def pages(name: str) -> list[Evidence]:
        key = normalise_name(name)
        person = next((p for p in found for _, e in p.entries if normalise_name(e.name) == key
                       or similarity(e.name, name) >= threshold or same_by_parts(e.name, name)), None)
        return person.evidence() if person else []
    return pages


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


@dataclass
class Observation:
    """A material fact the memo states that needs the promoter's answer: the PD note asks it under its
    topic, in the memo's words, and links it to the memo section that states it."""

    key: str
    """Stable for the case: the memo section's id and what is observed ("financials:fall")."""
    section: str
    """The kind of the memo section that states it."""
    area: str
    """The PD topic it is asked under."""
    title: str
    context: str
    question: str
    evidence: list[Evidence] = field(default_factory=list)
    severity: str = "moderate"


@dataclass
class Trend:
    """The years the financial performance shows: the spread columns, the year the norms assess, the
    previous year's own column and the comparatives the latest statements print."""

    shown: list[int]
    latest: int
    prior: int | None
    restated: dict[str, tuple[float, list[Evidence]]]
    earlier_fy: str

    @property
    def stand_in(self) -> bool:
        """The previous year's own statements are not on file: the comparatives stand in."""
        return self.prior is None and bool(self.restated)


class Draft:
    def __init__(self, conn: sqlite3.Connection, root: Path, case: CaseDetail) -> None:
        self.case = case
        app = load_app_config()
        self.facility_names = {f["id"]: f["label"] for f in app["facilities"]}
        self.constitutions = {c["id"]: c["label"] for c in app.get("constitutions", [])}
        self.config = reader.load_cam(root)
        # The layout the case's memo follows: the template chosen for it, else the configured one.
        self.template = cam_templates.for_case(conn, self.config, case.id)
        self.sections = self.template["sections"]
        self.numbers: dict[str, int] = {}
        self.section_ids: dict[str, str] = {}
        # A part keeps the id it is linked by; the number is its section's.
        for number, s in enumerate(self.sections, start=1):
            for part in s.drafted_from():
                self.numbers.setdefault(part.kind, number)
                self.section_ids.setdefault(part.kind, part.id)
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
        self.display_unit = self.statements_config.display_unit
        self.threshold = name_match(root)
        self.people = people(root, self.facts)
        self.naming = naming(self.people, self.threshold)
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
        """How a figure stands against its norm, or nothing when no norm assessed it: "above the minimum
        of 2.50x", "below the maximum of 3.00x". A norm in rupees is named rather than quoted
        ("positive" says less than "positive net worth")."""
        if n is None or n.outcome not in ("pass", "deviation"):
            return ""
        where = f"; see section {self.numbers['policy']}" if "policy" in self.numbers else ""
        if n.unit == "inr":
            named = f"the norm for {_lower(n.label)}"
            return f", meeting {named}" if n.outcome == "pass" else f", a deviation from {named}{self.see('policy')}"
        found = re.fullmatch(r"at (least|most) (.+)", n.required)
        if found is None:
            return (f", meeting the norm of {n.required}" if n.outcome == "pass"
                    else f", a deviation from the norm of {n.required}{self.see('policy')}")
        bound = "minimum" if found[1] == "least" else "maximum"
        if n.actual is not None and n.actual_text == found[2]:
            side = "at"
        else:
            side = "above" if (found[1] == "least") == (n.outcome == "pass") else "below"
        return f", {side} the {bound} of {found[2]}" + (f" (a deviation{where})" if n.outcome == "deviation" else "")

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
        """The checks that could not be completed, in board order; not one for a financial year still
        in progress that has nothing to ask for (its months are still to come)."""
        return [i for i in self.board.items if i.finding.outcome == "incomplete"
                and (i.finding.request or not self.in_progress(i.finding.scope))]

    def in_progress(self, scope: str | None) -> bool:
        """Whether a check's scope is a financial year that has not ended at the case's as-of date."""
        found = re.fullmatch(r"FY (\d{4})(?:-(\d{2}))?", scope or "")
        if not found:
            return False
        end = facts_module.fy_end_date(int(found[1]) + (1 if found[2] else 0), self.fy_start)
        return end > date.fromisoformat(self.case.as_of)

    def why_incomplete(self, f: Finding) -> str:
        """Why a check could not be completed. A check that waits for a value in review names the values
        in review, as read: "The PAN read from the income tax return awaits internal review"."""
        ids = {i for s in f.sides if s.awaiting_review for i in s.field_ids}
        if not ids or f.request:
            return f.explanation
        waiting = list(dict.fromkeys(f"the {_lower(' and '.join(d.type_names))}" for d in self.docs
                                     for v in d.fields.values() if v.pending and v.field_id in ids))
        if not waiting:
            return f.explanation
        rule = self.rules.get(f.rule_id)
        return f"The {IDENTIFIER_NOUN.get(rule.variable if rule else '', 'value')} read from {_join(waiting)} awaits " \
               "internal review."

    def checks_note(self, variables: set[str]) -> CamBlock | None:
        """A note pointing to the discrepancies found on these facts, by their board references."""
        found = [i for i in self.discrepancies("identity")
                 if self.rules.get(i.finding.rule_id) and self.rules[i.finding.rule_id].variable in variables]
        if not found:
            return None
        listed = "; ".join(f"{_lower(finding_title(i.finding))} ({i.finding.ref or i.finding.rule_id})" for i in found)
        where = f" See section {self.numbers['cross_verification']}." if "cross_verification" in self.numbers else ""
        return _note(f"Identity checks found {'a discrepancy' if len(found) == 1 else 'discrepancies'}: {listed}.{where}")

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

    def previous(self, i: int) -> int | None:
        """The spread column of the year before column i, on the same basis."""
        columns = self.spread.columns
        year = int(columns[i].period_end[:4])
        return next((j for j, c in enumerate(columns) if c.basis == columns[i].basis
                     and int(c.period_end[:4]) == year - 1), None)

    @cached_property
    def spread_rows(self) -> dict:
        return {r.key: r for r in self.spread.rows}

    @cached_property
    def trend(self) -> Trend | None:
        columns = self.spread.columns
        shown = [i for i, c in enumerate(columns) if c.basis in ("audited", "provisional")][-3:]
        if not shown:
            return None
        latest = next((i for i in reversed(shown) if columns[i].fy == self.assessment.period
                       and columns[i].basis == "audited"), shown[-1])
        restated = self.comparatives(columns[latest].fy) if columns[latest].basis == "audited" else {}
        return Trend(shown, latest, self.previous(latest), restated, self.prior_fy(columns[latest].period_end))

    def figure(self, key: str, i: int) -> tuple[float | None, list[Evidence]]:
        """A spread row's figure in column i, with its pages; growth against the year before (the
        comparatives where that year's statements are not on file), and the DSCR as the norm assessed it."""
        rows = self.spread_rows
        t = self.trend
        if key == "growth":
            revenue, j = rows.get("revenue_from_operations"), self.previous(i)
            now = revenue.cells[i].value if revenue else None
            if j is None and t and i == t.latest and t.stand_in and "revenue_from_operations" in t.restated:
                before, before_cites = t.restated["revenue_from_operations"]
            else:
                before = revenue.cells[j].value if revenue and j is not None else None
                before_cites = revenue.cells[j].evidence if revenue and j is not None else []
            if now is None or not before:
                return None, []
            return (now - before) / before * 100, revenue.cells[i].evidence + before_cites
        if key == "dscr":
            dscr = self.norm(self.ratio_norms.get("dscr"))
            if t and i == t.latest and dscr is not None and dscr.actual is not None:
                return dscr.actual, norm_evidence(dscr)
            return None, []
        row = rows.get(key)
        return (row.cells[i].value, row.cells[i].evidence) if row else (None, [])

    def renamed(self, i: int | None) -> tuple[str, str] | None:
        """The name and board reference of column i's statements where they are in another name."""
        return next((self.other_names[d] for d in self.column_documents(i) if d in self.other_names), None) \
            if i is not None else None

    def earlier(self, key: str) -> tuple[str, float, list[Evidence]] | None:
        """The previous year's figure the memo sets the latest against, with the year as the memo names
        it: the previous year's own statements; the latest statements' comparatives where those are not
        on file or are in another name."""
        t = self.trend
        if t is None:
            return None
        own = self.figure(key, t.prior) if t.prior is not None else (None, [])
        restated = t.restated.get(key)
        if restated is not None and (own[0] is None or self.renamed(t.prior)):
            return (f"{t.earlier_fy} (the comparatives in the {self.spread.columns[t.latest].fy} statements)",
                    restated[0], restated[1])
        return (self.spread.columns[t.prior].fy, own[0], own[1]) if own[0] is not None else None

    def fall(self, key: str) -> float | None:
        """How far (%) a figure fell on the previous year, as the memo sets them against each other."""
        now = self.figure(key, self.trend.latest)[0] if self.trend else None
        before = self.earlier(key)
        if now is None or not before or before[1] <= 0 or now >= before[1]:
            return None
        return (before[1] - now) / before[1] * 100

    # --- Sections ---

    def snapshot(self) -> list[CamBlock]:
        c, f = self.case, self.facts
        since = self.incorporated()
        inc = f.incorporation.date_of_incorporation
        declared = self.declared_turnover()
        rm = find_user_by_id(c.created_by) or {}
        r = self.readiness
        norms = self.assessment.counts
        limit, eligible = self.resolution_limit(), self.eligible_finance()
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
            *([("Eligible bank finance (working capital)", eligible)] if eligible else []),
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
        incomplete = len(self.incomplete())
        return text + (f"; {incomplete} could not be completed" if incomplete else "")

    def eligible_finance(self) -> CamText | None:
        """The bank finance the working-capital method allows, against the request; nothing where no
        working-capital facility is requested. The comparison uses the total while the amount of each
        facility is not captured (FRD F-02)."""
        wc = self.spread.working_capital
        if wc.method == "not_applicable":
            return None
        method = "MPBF method" if wc.method == "mpbf" else "turnover method"
        if wc.missing or wc.eligible is None:
            return _t(f"Not computed ({method}): {_join(wc.missing)} not on file" if wc.missing else "Not computed")
        cites = _pages(e for s in wc.steps for e in s.evidence[:1])
        other = self.term_facilities()
        total = f", the total including the {_join(other)}," if other and len(other) < len(self.case.facilities) else ""
        verdict = "within" if wc.requested <= wc.eligible else "above"
        figures = re.sub(r"\s*\((\w+)\)$", r" \1", wc.column or "").strip()
        on = f", on the {figures} figures" if figures else ""
        return _t(f"{self.fin(wc.eligible)} ({method}{on}); the request of {self.fin(wc.requested)}{total} is {verdict} it", cites)

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
        without = [p for p in self.people if not p.kyc]
        if without:
            blocks.append(_paragraph(f"No KYC has been received for {_join([p.name for p in without])}.",
                                     [e for p in without for e in p.evidence()]))
        unknown = [p for p in self.people if not p.role]
        if unknown:
            text = f"No document on file states the role of {_join([p.name for p in unknown])}"
            text += ("; the memorandum and articles of association is not on file."
                     if "memorandum_articles_of_association" not in self.facts.types_on_file else ".")
            blocks.append(_paragraph(text, [e for p in unknown for e in p.evidence()]))
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
        # The signatories and the persons authorised to borrow, each as the resolution lists them.
        doc = next((d for d in self.docs if d.id == a.document_id), None)
        named, people_cites = [], []
        for field_name, one, several in (("authorized_signatories", "authorised signatory", "authorised signatories"),
                                         ("authorized_persons", "person authorised to borrow",
                                          "persons authorised to borrow")):
            values = [v for v in (doc.list(field_name) if doc else []) if str(v.value or "").strip()]
            names = list(dict.fromkeys(str(v.value).strip() for v in values))
            if names:
                named.append(f"{one if len(names) == 1 else several}: {_join(names)}")
                people_cites += [e for v in values for e in doc.evidence(v)[:1]]
        if not named and a.signatories:
            named.append(f"signatories: {_join([s.name for s in a.signatories])}")
            people_cites += [e for s in a.signatories for e in s.evidence[:1]]
        text += f"; {'; '.join(named)}." if named else "."
        amount = self.case.amount_inr
        if limit is None:
            text += " The borrowing limit is not on file."
        elif limit < amount:
            text += f" It covers {inr(limit)} of the {inr(amount)} requested; a fresh resolution is needed."
        else:
            text += f" It covers the {inr(amount)} requested."
        cites = [e for v in (a.resolution_date, a.lender, a.borrowing_limit) if v for e in v.evidence]
        cites += (purpose.citations if purpose else []) + people_cites
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

    def fin(self, value: float | None) -> str:
        """A financial figure in the unit configured for financial figures (config/statements.yaml)."""
        return money(value, self.display_unit)

    def financial_performance(self) -> list[CamBlock]:
        t = self.trend
        if t is None:
            return []
        columns = self.spread.columns
        fy = columns[t.latest].fy

        def written(value: float | None, unit: str) -> str:
            if value is None:
                return NONE
            if unit == "inr":
                return self.fin(value)
            return f"{_number(value, 2)}x" if unit == "x" else _number(value, 1 if unit == "%" else 0)

        def heading(i: int) -> str:
            other = self.renamed(i)
            return f"{columns[i].fy} ({columns[i].basis}; in the name of {other[0]})" if other \
                else f"{columns[i].fy} ({columns[i].basis})"

        specs: list[tuple[str, object]] = []
        for i in t.shown:
            if i == t.latest and t.stand_in:
                specs.append((f"{t.earlier_fy} (comparatives in the {fy} statements)",
                              lambda key: t.restated.get(key, (None, []))))
            specs.append((heading(i), lambda key, i=i: self.figure(key, i)))
        table = []
        for key, label, unit in FINANCIAL_ROWS:
            cells = [figure(key) for _, figure in specs]  # type: ignore[operator]
            if all(v is None for v, _ in cells):
                continue
            table.append([_t(label), *[_t(written(v, unit), e) for v, e in cells]])
        header = ["Particulars", *[h for h, _ in specs]]
        blocks = [_table(header, table, numeric=list(range(1, len(header)))), *self.performance()]
        if t.prior is not None and t.restated:
            blocks += self.restatement(fy, columns[t.prior].fy, {key: self.figure(key, t.prior) for key, _ in RESTATED},
                                       t.restated)
        named = []
        for i in t.shown:
            other = self.renamed(i)
            if other:
                named.append(f"The {columns[i].fy} statements are in the name of {other[0]} ({other[1]}).")
        blocks += [_note(text) for text in dict.fromkeys(named)]
        if any(r[0].text == "DSCR" for r in table):
            blocks.append(_note(f"DSCR as assessed under the policy norms{self.see('policy')}."))
        blocks += self.edited_figures()
        return blocks

    def edited_figures(self) -> list[CamBlock]:
        """A figure that rests on a person's edit of a statement line says so, with what the statement gives
        and the reason, so a reader of the memo is never shown an edited figure as the document's own."""
        notes = []
        for row in self.spread.rows:
            if row.kind != "line":
                continue
            for column, cell in zip(self.spread.columns, row.cells):
                edit = cell.working.edit if cell.working else None
                if edit is None:
                    continue
                scale = cell.working.source.scale if cell.working.source else 1.0
                given = "no figure" if edit.original is None else self.fin(edit.original * scale)
                notes.append(_paragraph(
                    f"{row.label} for {column.fy} is {self.fin(edit.value * scale)}, as entered by {edit.edited_by} on "
                    f"{edit.edited_at[:10]}; the statements give {given}. Reason: {edit.reason}",
                    cell.evidence))
        return notes

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
            differ.append((f"{label} {self.fin(shown[0])} against {self.fin(value)}", shown[1] + cites))
        if not differ:
            return []
        return [_paragraph(f"The {fy} statements give different figures for {earlier}: {_join([t for t, _ in differ])} "
                           f"in the {earlier} statements.", [e for _, c in differ for e in c])]

    def revenue_sentence(self) -> tuple[str, list[Evidence]] | None:
        """Revenue in the latest year against the year before. Where the previous year's own statements
        are in another name, against the comparatives first, then against those statements."""
        t = self.trend
        if t is None:
            return None
        columns = self.spread.columns
        fy = columns[t.latest].fy
        now, cites = self.figure("revenue_from_operations", t.latest)
        if now is None:
            return None
        restated = t.restated.get("revenue_from_operations")
        own = self.figure("revenue_from_operations", t.prior) if t.prior is not None else (None, [])
        if restated and restated[0] and own[0] and self.renamed(t.prior):
            return (f"Revenue from operations was {self.fin(now)} in {fy}: {_change(now, restated[0])} on the comparatives in "
                    f"the {fy} statements ({self.fin(restated[0])} for {t.earlier_fy}), and {_change(now, own[0])} on the "
                    f"{columns[t.prior].fy} statements ({self.fin(own[0])}), which are in another entity's name.",
                    cites + restated[1] + own[1])
        before = self.earlier("revenue_from_operations")
        if before and before[1]:
            change = (now - before[1]) / before[1] * 100
            moved = ("was unchanged at" if round(change, 1) == 0
                     else f"{'rose' if change > 0 else 'fell'} {abs(change):.1f}% to")
            return f"Revenue from operations {moved} {self.fin(now)} in {fy}, from {self.fin(before[1])} in {before[0]}.", \
                cites + before[2]
        return f"Revenue from operations was {self.fin(now)} in {fy}.", cites

    def net_worth_fall(self) -> tuple[str, list[Evidence]] | None:
        """Net worth fallen by FALL_PCT or more on the year before: both figures, the profit it fell
        despite, and the share capital and reserves where they fell too."""
        pct = self.fall("net_worth")
        if pct is None or pct < FALL_PCT:
            return None
        latest = self.trend.latest
        (now, cites), before = self.figure("net_worth", latest), self.earlier("net_worth")
        text = f"Net worth fell from {self.fin(before[1])} to {self.fin(now)}"
        cites = cites + before[2]
        profit, profit_cites = self.figure("profit_after_tax", latest)
        if profit is not None and profit > 0:
            text += f" despite a profit of {self.fin(profit)}"
            cites += profit_cites
        parts = []
        for label, before, value, found in self.capital_falls():
            parts.append(f"{label}{'' if parts else ' fell'} from {self.fin(before)} to {self.fin(value)}")
            cites += found
        return text + (f"; {' and '.join(parts)}." if parts else "."), cites

    def capital_falls(self) -> list[tuple[str, float, float, list[Evidence]]]:
        """The share capital and the reserves, where either fell on the year before: (label, before,
        now, pages)."""
        out = []
        for key, label in (("share_capital", "share capital"), ("reserves_and_surplus", "reserves and surplus")):
            (value, found), prior = self.figure(key, self.trend.latest), self.earlier(key)
            if value is not None and prior and value < prior[1] * 0.99:
                out.append((label, prior[1], value, found + prior[2]))
        return out

    def performance(self) -> list[CamBlock]:
        """The latest year in words: revenue (and a fall in net worth), profitability, leverage and
        liquidity, each figure set against the policy norm that assessed it."""
        ratio = lambda key: self.norm(self.ratio_norms.get(key))  # noqa: E731
        line = lambda key: self.norm(self.line_norms.get(key))  # noqa: E731
        latest = self.trend.latest
        fy = self.spread.columns[latest].fy
        figures = {key: self.figure(key, latest) for key, _, _ in FINANCIAL_ROWS}
        out = [_paragraph(*found) for found in (self.revenue_sentence(), self.net_worth_fall()) if found]

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
            sentences.append((f"EBITDA was {self.fin(ebitda)}{share('ebitda_margin')}.", cites))
        profit, cites = figures["profit_after_tax"]
        if profit is not None:
            sentences.append((f"Profit after tax was {self.fin(profit)}{share('pat_margin')}"
                              f"{self.against(line('profit_after_tax'))}.", cites))
        coverage, cites = figures["interest-coverage"]
        if coverage is not None:
            sentences.append((f"Interest coverage was {_number(coverage, 2)}x{self.against(ratio('interest-coverage'))}.",
                              cites))
        paragraph(sentences)

        sentences = []
        (worth, cites), (borrowings, owed) = figures["net_worth"], figures["total_borrowings"]
        if worth is not None:
            against = f", against total borrowings of {self.fin(borrowings)}" if borrowings is not None else ""
            sentences.append((f"Net worth was {self.fin(worth)}{self.against(line('net_worth'))}{against}.",
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
                [_t(s.label), _t(self.fin(s.value), s.evidence[:2] or inputs), _t(s.basis or "")] for s in wc.steps
            ], numeric=[1])
            verdict = "within" if wc.eligible is not None and wc.requested <= wc.eligible else "above"
            other = self.term_facilities()
            total = ""
            if other and len(other) < len(self.case.facilities):
                limit = self.policy_config.working_capital.mpbf_above_limit_inr
                total = f" The comparison uses the total request, including the {_join(other)}"
                total += (f"; on a working-capital amount of {self.fin(limit)} or less the turnover method would apply."
                          if wc.method == "mpbf" else ".")
            blocks = [_paragraph(wc.reason), table,
                      _paragraph(f"On the figures for {wc.column}, eligible bank finance is {self.fin(wc.eligible)}; the "
                                 f"request of {self.fin(wc.requested)} is {verdict} it.{total}", inputs)]
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

    def stand_in_year(self) -> tuple[str, float, list[Evidence]] | None:
        """The previous year's audited revenue from the comparatives in the latest statements, where that
        year's own statements are not on file: (year, revenue, pages)."""
        t = self.trend
        if t is None or not t.stand_in or "revenue_from_operations" not in t.restated:
            return None
        return (t.earlier_fy, *t.restated["revenue_from_operations"])

    def turnover(self) -> list[CamBlock]:
        blocks = []
        stand_in = self.stand_in_year()
        entries = [(y.fy, {f.source: f for f in y.figures}, y) for y in self.facts.turnover]
        if stand_in and not any(fy == stand_in[0] for fy, _, _ in entries) and entries:
            entries = sorted(entries + [(stand_in[0], {}, None)], key=lambda e: e[0], reverse=True)
        if entries:
            rows = []
            for fy, by, y in entries:
                cells = []
                for source, _ in TURNOVER_COLUMNS:
                    if source == "financials" and source not in by and stand_in and fy == stand_in[0]:
                        cells.append(_t(f"{self.fin(stand_in[1])} (comparatives)", stand_in[2]))
                    else:
                        cells.append(_figure(by.get(source), self.statements(y) if source == "bank" and y else []))
                rows.append([_t(fy), *cells])
            latest = self.spread.columns[self.trend.latest].fy if stand_in else ""
            note = (f"The {stand_in[0]} audited figure is the comparative printed in the {latest} statements; the "
                    f"{stand_in[0]} statements are not on file.") if stand_in else None
            blocks.append(_table(["Financial year", *[label for _, label in TURNOVER_COLUMNS]], rows,
                                 numeric=list(range(1, len(TURNOVER_COLUMNS) + 1)), note=note))
        agree = self.sources_agree()
        if agree:
            blocks.append(agree)
        if stand_in:
            profit = self.return_profit(stand_in[0])
            if profit:
                blocks.append(profit)
        found = self.discrepancies("turnover", "tax")
        if found:
            # Each is explained once, in the cross-verification section.
            where = f", set out in section {self.numbers['cross_verification']}" if "cross_verification" in self.numbers else ""
            listed = "; ".join(f"{_lower(finding_title(i.finding))} ({i.finding.ref or i.finding.rule_id})" for i in found)
            blocks.append(_paragraph(f"The cross-checks found {_plural(len(found), 'discrepancy', 'discrepancies')} on "
                                     f"turnover and tax{where}: {listed}."))
        filed = self.filing()
        return blocks + ([filed] if filed else [])

    def sources_agree(self) -> CamBlock | None:
        """Where every source of the latest year's turnover covers the year and the checks found them
        within tolerance of each other: a sentence that says so, with each figure."""
        year = next((y for y in self.facts.turnover if y.fy == self.assessment.period), None)
        if year is None:
            return None
        by = {f.source: f for f in year.figures if f.value is not None}
        named = [(label, by[source]) for source, label in (("financials", "audited"), ("gst", "GST"),
                                                           ("itr", "income tax return"), ("bank", "business credits"))
                 if source in by]
        if len(named) < 2 or any(f.months_covered not in (None, 12) for _, f in named):
            return None
        checks = [i.finding for i in self.board.items if i.finding.area in ("turnover", "tax")]
        scoped = [f for f in checks if f.scope == year.fy]
        if (any(f.outcome == "fail" for f in checks) or any(f.outcome == "incomplete" for f in scoped)
                or not any(f.outcome == "pass" for f in scoped)):
            return None
        return _paragraph("All sources agree within tolerance: " + ", ".join(f"{label} {self.fin(f.value)}" for label, f in named)
                          + ".", [e for _, f in named for e in f.evidence[:1]])

    def return_profit(self, fy: str) -> CamBlock | None:
        """The profit in the income tax return for a year whose own statements are not on file, against
        the comparatives the latest statements print for it."""
        tax = next((y for y in self.facts.tax_years if y.fy == fy), None)
        profit = tax.lines.get("profit_before_tax") if tax else None
        books = self.trend.restated.get("profit_before_tax")
        if profit is None or profit.value is None or books is None:
            return None
        latest = self.spread.columns[self.trend.latest].fy
        return _paragraph(f"The income tax return for AY {tax.assessment_year} shows profit before tax of "
                          f"{self.fin(float(profit.value))}, against {self.fin(books[0])} for {fy} in the comparatives in the "
                          f"{latest} statements.", profit.evidence[:1] + books[1])

    def returns_due(self) -> list[tuple[str, date, bool]]:
        """The income tax returns not on file and not yet due: (assessment year, due date, whether the
        checklist asks for it)."""
        due_days = int(self.tolerances.get("itr_due_days", 214))
        as_of, filed = date.fromisoformat(self.case.as_of), {t.fy for t in self.facts.tax_years}
        out = []
        for y in self.facts.financial_years:
            due = date.fromisoformat(y.fy_end) + timedelta(days=due_days)
            if y.fy not in filed and due > as_of:
                year = _assessment_year(date.fromisoformat(y.fy_end))
                asked = any(year in (d.request or "") for res in self.results for d in res.deficiencies) \
                    or any(year in (res.missing_request or "") for res in self.results)
                out.append((year, due, asked))
        return out

    def filing(self) -> CamBlock | None:
        """Which returns are on file: GST months, income tax assessment years, whether each audited year
        that is due has its income tax return (TX-01), and the returns not yet due, with their due date."""
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
        for year, due, asked in self.returns_due():
            text += f" The return for {year} is due by {display_date(due)} (not yet due)" \
                    + ("; the checklist asks for it." if asked else ".")
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
        position = self.cash_position()
        if position:
            blocks.append(_paragraph(position[0], position[1]))
        blocks += [self.no_statement(a) for a in self.facts.accounts if not a.has_statement]
        return blocks

    def no_statement(self, a) -> CamBlock:
        """An account with no statement on file: where it is declared or named, and the transfers that
        show it."""
        declaration = self.type_names.get(facts_module.DECLARATION, "")
        in_message = "Sourcing message" in a.sources
        if declaration in a.sources:
            how = "declared in the declaration of existing facilities" + (
                " and named in the sourcing message" if in_message else "")
        elif in_message:
            how = "named in the sourcing message" + (" but not in the declaration" if self.facts.declaration else "")
        else:
            how = "which was not declared"
        called = a.label if a.bank else _lower(a.label)
        text = f"No statement has been received for {called}, {how}"
        moved = self.transfers(a.last4) if a.last4 else []
        cites = list(a.evidence[:1])
        if moved:
            account, when, amount, out, evidence = moved[0]
            if len(moved) == 1:
                text += (f"; {account} shows a transfer of {inr(amount)} {'to' if out else 'from'} it"
                         f"{f' on {display_date(when)}' if when else ''}")
            else:
                text += (f"; {_join(list(dict.fromkeys(m[0] for m in moved)))} show {len(moved)} transfers with it, "
                         f"{inr(sum(m[2] for m in moved))} in all")
            cites += [e for m in moved for e in m[4][:1]]
        return _paragraph(text + ".", cites)

    def transfers(self, last4: str) -> list[tuple[str, date | None, float, bool, list[Evidence]]]:
        """The statement transactions whose narration names an account by these last four digits:
        (the statement's account, date, amount, whether paid out to it, pages)."""
        out = []
        for d in self.docs:
            if "bank_statement" not in d.types:
                continue
            bank = d.get("bank_name")
            number = d.get("account_number")
            digits = re.sub(r"\D", "", str(number.value if number else ""))
            account = f"{str(bank.value).strip() if bank else 'Bank'}" + (f" ·{digits[-4:]}" if len(digits) >= 4 else "")
            for r in d.rows("transactions"):
                narration = str(r["description"].value) if r.get("description") else ""
                if not any(re.sub(r"\D", "", m)[-4:] == last4 for m in facts_module.NARRATION_ACCOUNT.findall(narration)):
                    continue
                debit, credit = facts_module._amount(r.get("debit")), facts_module._amount(r.get("credit"))
                if debit or credit:
                    when = parse_date(r["date"].value) if r.get("date") else None
                    out.append((account, when, debit or credit, bool(debit),
                                d.evidence(r.get("debit") if debit else r.get("credit"), r.get("description"))))
        return out

    def cash_position(self) -> tuple[str, list[Evidence], float, float] | None:
        """Each account's balance at the latest audited year end against the cash and bank balances in
        that year's balance sheet, and the difference either way beyond the tolerance (in the unit set for
        financial figures, so the figures add up as written): (sentence, pages, statements less the audited figure, the larger of
        the two)."""
        year = next((y for y in self.facts.financial_years if y.fy == self.assessment.period), None)
        on = [b for b in self.facts.balances if year and b.date == year.fy_end]
        if not on:
            return None
        total = sum(b.balance for b in on)
        cites = [e for b in on for e in b.evidence[:1]]
        audited = year.current.get("cash_and_bank_balances")
        books = float(audited.value) if audited is not None and audited.value is not None else None
        tolerance = self.tolerances.get("balance_variance", 1) / 100
        gap = total - books if books is not None else 0.0
        if books is not None and total > books * (1 + tolerance):
            ending = "; the statements' balances exceed the audited figure by {}"
        elif books is not None and total < books * (1 - tolerance):
            ending = "; {} of the audited balance is not in any statement on file"
        else:
            ending = ""
        money = self.fin
        held = _join([f"{money(b.balance)} in {b.account}" for b in on])
        when = display_date(date.fromisoformat(year.fy_end))
        text = (f"At {when} the statements show {held}, {money(total)} in all" if len(on) > 1
                else f"At {when} the statement shows {held}")
        if books is not None:
            text += f", against cash and bank balances of {money(books)} in the {year.fy} balance sheet"
            text += ending.format(money(abs(gap))) if ending else ""
            cites += audited.evidence[:1]
        return text + ".", cites, gap if ending else 0.0, max(total, books or 0.0)

    @cached_property
    def lenders(self) -> list[dict]:
        """The facilities on file by lender, as OB-01 groups them, each with the instalments the bank
        statements show it is paid."""
        f = self.facts
        order = (facts_module.DECLARATION, facts_module.SANCTION, facts_module.BUREAU, facts_module.MESSAGE)
        groups: list[dict] = []
        for x in sorted(f.facilities, key=lambda x: order.index(x.source) if x.source in order else len(order)):
            group = next((g for g in groups if self.same_lender(x.lender, g["name"])), None)
            if group is None:
                groups.append({"name": x.lender, "facilities": [x], "paid": []})
            else:
                group["facilities"].append(x)
        for o in f.obligations:
            group = next((g for g in groups if self.same_lender(o.lender, g["name"])), None)
            if group is None:
                groups.append({"name": o.lender, "facilities": [], "paid": [o]})
            else:
                group["paid"].append(o)
        return groups

    def existing_facilities(self) -> list[CamBlock]:
        f = self.facts
        declared = [x for x in f.facilities if x.source == facts_module.DECLARATION]
        reported = [x for x in f.facilities if x.source == facts_module.BUREAU]
        message = str(f.declared_banking.value) if f.declared_banking and f.declared_banking.value else ""
        emi_pct = self.tolerances.get("emi_amount_match", 5)

        def amount(found: list, missing: str, present: str = "On file") -> CamText:
            known = [x for x in found if x.amount is not None]
            if not found:
                return _t(missing)
            return _t(inr(sum(x.amount for x in known)) if known else present, [e for x in found for e in x.evidence[:1]])

        def owing(cell: CamText, found: list) -> CamText:
            owed = [x for x in found if x.outstanding is not None]
            return _t(f"{cell.text}; outstanding {inr(sum(x.outstanding for x in owed))}", cell.citations) if owed else cell

        rows, undeclared = [], []
        exposure, outstanding, exposure_cites, outstanding_cites = 0.0, 0.0, [], []
        for g in self.lenders:
            d = [x for x in g["facilities"] if x.source == facts_module.DECLARATION]
            s = [x for x in g["facilities"] if x.source == facts_module.SANCTION]
            b = [x for x in g["facilities"] if x.source == facts_module.BUREAU]
            m = [x for x in g["facilities"] if x.source == facts_module.MESSAGE]
            named = bool(m) or (bool(message) and _mentions(message, g["name"], self.noise, self.threshold))
            limited = any(x.amount is not None for x in s + b)
            if d:
                declared_cell = owing(amount(d, "", "Declared"), d)
            elif named:
                declared_cell = _t("In the sourcing message" + ("" if limited or not m else "; limit not on file"),
                                   f.declared_banking.evidence[:1] if f.declared_banking else [])
            else:
                declared_cell = _t("Not declared" if f.declaration_received or message else "No declaration on file")
            bureau_cell = owing(amount(b, NONE), b)
            owed = [x for x in b if x.outstanding is not None]
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
        blocks = []
        if rows:
            blocks.append(_table(["Lender", "Facility", "Declared", "Sanction letter", "Bureau", "Instalment",
                                  "Seen in the bank (a month)"], rows, numeric=[2, 3, 4, 5, 6]))
        if f.declaration_received and not declared and f.declaration is not None:
            blocks.append(_paragraph("The declaration of existing facilities declares none.", f.declaration.evidence[:1]))
        blocks += [self.message_facility(name, found, limited) for name, found, limited in self.message_only()]
        rank = next((i for n in self.assessment.norms for i in n.inputs if i.name == "bureau_rank"), None)
        if rank is not None and rank.value is not None:
            norm = next((n for n in self.assessment.norms if any(i.name == "bureau_rank" for i in n.inputs)), None)
            blocks.append(_paragraph(f"The commercial bureau report gives the borrower rank {rank.value:g}"
                                     f"{self.against(norm)}.", rank.evidence[:1]))
        if exposure:
            counted = [g["name"] for g in self.lenders if any(x.amount is not None for x in g["facilities"])]
            text = (f"Existing sanctioned facilities total {inr(exposure)} across {_plural(len(counted), 'lender')}"
                    if len(counted) > 1 else f"Existing sanctioned facilities with {counted[0]} total {inr(exposure)}")
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
        return blocks + [_paragraph(text, cites) for _, _, text, cites in self.loan_disbursals()]

    def message_only(self) -> list[tuple[str, list, bool]]:
        """The facilities only the sourcing message declares, by lender: (lender, facilities, whether a
        limit is on file for the lender)."""
        out = []
        for g in self.lenders:
            kinds = {x.source for x in g["facilities"]}
            if facts_module.MESSAGE in kinds and not kinds & {facts_module.DECLARATION, facts_module.BUREAU}:
                found = [x for x in g["facilities"] if x.source == facts_module.MESSAGE]
                limited = any(x.amount is not None for x in g["facilities"]
                              if x.source in (facts_module.SANCTION, facts_module.BUREAU))
                out.append((g["name"], found, limited))
        return out

    def message_facility(self, lender: str, found: list, limited: bool) -> CamBlock:
        """A facility only the sourcing message declares: which documents do not show it."""
        return _paragraph(*self.message_facility_text(lender, found, limited))

    def message_facility_text(self, lender: str, found: list, limited: bool) -> tuple[str, list[Evidence]]:
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
        return (f"{called} is declared only in the sourcing message: {shown}{limit}.",
                [e for x in found for e in x.evidence[:1]])

    def loan_disbursals(self) -> list[tuple[object, str | None, str, list[Evidence]]]:
        """Each loan paid into an account, and whether a facility on file accounts for it: one whose
        lender the narration names, or one of that amount. (disbursal, the lender that accounts for it,
        sentence, pages)."""
        f = self.facts
        emi_pct = self.tolerances.get("emi_amount_match", 5)
        unexplained = [o for o in f.obligations if not any(self.same_lender(o.lender, x.lender) for x in f.facilities)]
        out = []
        for c in f.credits:
            for x in c.exclusions:
                if x.rule != LOAN_DISBURSAL:
                    continue
                when = parse_date(x.date) if x.date else None
                text = f"A loan of {inr(x.amount)} was disbursed into {x.account}" \
                       f"{f' on {display_date(when)}' if when else ''} ({x.narration})"
                lender = next((y.lender for y in f.facilities if _mentions(x.narration, y.lender, self.noise, self.threshold)),
                              None)
                sized = next((y.lender for y in f.facilities if y.amount
                              and abs(y.amount - x.amount) <= emi_pct / 100 * max(y.amount, x.amount)), None)
                if lender:
                    text += f"; the narration names {lender}, a lender on file."
                elif sized:
                    text += f"; a facility of that amount with {sized} is on file."
                else:
                    text += "; no facility on file matches it" + (
                        "." if unexplained else " and no instalment for it appears in the statements.")
                out.append((x, lender or sized, text, x.evidence[:1]))
        return out

    def borrowings_gap(self) -> tuple[str, str, list[Evidence], float] | None:
        """The latest balance sheet's borrowings against the outstanding of the facilities on file (the
        bureau's, else the declaration's), where the gap is material: (the memo's sentence, the note's
        sentence, pages, the gap). Nothing where a lender's outstanding is not on file, or where neither
        the bureau report nor the declaration is on file to say what is outstanding."""
        i = self.latest_column()
        row = self.spread_rows.get("total_borrowings")
        total = row.cells[i].value if row and i is not None else None
        on_file = set(self.facts.types_on_file)
        if not total or total <= 0 or not {facts_module.BUREAU, facts_module.DECLARATION} & on_file:
            return None
        outstanding, cites = 0.0, list(row.cells[i].evidence)
        for g in self.lenders:
            owed = [x for x in g["facilities"] if x.source == facts_module.BUREAU and x.outstanding is not None] or \
                   [x for x in g["facilities"] if x.source == facts_module.DECLARATION and x.outstanding is not None]
            if not owed:
                return None
            outstanding += sum(x.outstanding for x in owed)
            cites += [e for x in owed for e in x.evidence[:1]]
        gap = total - outstanding
        least, share = BORROWINGS_GAP
        if gap < least or gap < share / 100 * total:
            return None
        against = (f"against {self.fin(outstanding)} outstanding on the facilities on file" if outstanding
                   else "against no outstanding on the facilities on file")
        fy = self.spread.columns[i].fy
        return (f"Borrowings of {self.fin(total)} {against}; {self.fin(gap)} is not explained.",
                f"The {fy} balance sheet shows borrowings of {self.fin(total)} {against}; {self.fin(gap)} is not explained.",
                cites, gap)

    def borrowings(self) -> CamBlock | None:
        """The latest balance sheet's borrowings, long-term and short-term, whether a working-capital
        facility on file accounts for the short-term borrowings, and borrowings no facility explains."""
        i = self.latest_column()
        if i is None:
            return None
        rows = self.spread_rows
        figure = lambda key: (rows[key].cells[i].value, rows[key].cells[i].evidence) if key in rows else (None, [])  # noqa: E731
        (total, total_cites), long, short = figure("total_borrowings"), figure("long_term_borrowings"), \
            figure("short_term_borrowings")
        parts = [(f"{self.fin(value)} {term}", cites) for term, (value, cites) in (("long-term", long), ("short-term", short))
                 if value is not None]
        fy = self.spread.columns[i].fy
        if total is not None:
            text = f"The {fy} balance sheet shows borrowings of {self.fin(total)}" + (
                f": {_join([p for p, _ in parts])}." if parts else ".")
        elif parts:
            text = f"The {fy} balance sheet shows {_join([p for p, _ in parts])} borrowings."
        else:
            return None
        if short[0] and short[0] > 0 and not any(x.facility and WORKING_CAPITAL_NAME.search(x.facility)
                                                 for x in self.facts.facilities):
            text += " No working-capital facility is on file to account for the short-term borrowings."
        cites = total_cites + [e for _, cites in parts for e in cites]
        gap = self.borrowings_gap()
        if gap:
            text += f" {gap[0]}"
            cites += gap[2]
        return _paragraph(text, cites)

    def cross_verification(self) -> list[CamBlock]:
        b = self.board
        if b.run is None:
            return []
        blocks = [_paragraph(f"The latest cross-check run, {b.run.id}, applied {_plural(b.run.rules, 'check')} to "
                             f"{_plural(b.run.sources, 'type')} of source document.")]
        rows = []
        incomplete = self.incomplete()
        for a in b.areas:
            accepted = sum(1 for i in b.items if i.finding.area == a.area and status(i) == ACCEPTED)
            counts = (a.rules, a.discrepancies, accepted, a.open, sum(1 for i in incomplete if i.finding.area == a.area))
            rows.append([_t(AREAS.get(a.area, a.area)), *[_t(str(n)) for n in counts]])
        blocks.append(_table(["Area", "Checks", "Discrepancies", "Accepted as valid", "Open", "Could not be completed"],
                             rows, numeric=[1, 2, 3, 4, 5], title="Checks by area"))
        if incomplete:
            blocks.append(_table(["Check", "Why", "What would complete it"], [
                [_t(plain(i.finding.title)), _t(self.why_incomplete(i.finding)), _t(_upper(i.finding.request or NONE))]
                for i in incomplete], title="Checks not completed"))
        failed = [i for i in b.items if i.finding.outcome == "fail"]
        if not failed:
            return blocks + [_paragraph("No discrepancy was found.")]
        rows = []
        for i in failed:
            f = i.finding
            standing = status(i) + ("; blocks submission" if f.blocking and not i.adjudicated else "")
            rows.append([_t(f.ref or f.rule_id), _t(SEVERITY[f.severity]), _t(stated_title(f)),
                         _t(f.explanation, finding_evidence(f, self.threshold, self.naming)), _t(standing)])
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
        # The table states each result; why a norm was not assessed is said once, here or where the
        # memo states it first (the DSCR, under the term loan).
        stated = {self.ratio_norms.get("dscr")} if self.term_stated() else set()
        blocks += [_paragraph(_unassessed_sentence(n, on_file), norm_evidence(n)) for n in norms
                   if n.outcome == "cannot_evaluate" and n.id not in stated]
        return blocks + [_subheading("Approving authority"), _facts(self.authority_facts())]

    def term_stated(self) -> bool:
        """Whether the working-capital section states the term loan's instalment and DSCR."""
        return "working_capital" in self.numbers and bool(set(self.case.facilities) & policy_module.TERM)

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
                [_t(sentence_case(res.state.name)), _t(ITEM_STATUS[res.state.status]),
                 _t(self.missing_text(res), _evidence(e for d in res.deficiencies for e in d.evidence))]
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

    # --- Observations ---

    def observations(self) -> list[Observation]:
        """The material facts the memo states that need the promoter's answer, each raised only where
        the data shows it, in the memo's order, with the memo's own sentence as why it is asked: a fall
        in revenue or net worth, a return not yet due that nothing asks for, a gap between the year-end
        bank balances and the audited figure, borrowings no facility on file explains, a facility named
        only in the sourcing message with no limit on file, a loan paid in that no facility matches,
        and collateral offered with no details on file."""
        out: list[Observation] = []

        def observe(kind: str, name: str, area: str, title: str, context: str, question: str,
                    evidence: list[Evidence], severity: str = "moderate") -> None:
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            out.append(Observation(key=f"{self.section_ids.get(kind, kind)}:{slug}", section=kind, area=area,
                                   title=title, context=context, question=question, evidence=_pages(evidence),
                                   severity=severity))

        revenue_pct, worth = self.fall("revenue_from_operations"), self.net_worth_fall()
        revenue = self.revenue_sentence() if revenue_pct is not None and revenue_pct >= FALL_PCT else None
        if revenue or worth:
            found = [s for s in (revenue, worth) if s]
            fell = _join((["revenue"] if revenue else []) + (["net worth"] if worth else []))
            capital = [label.removesuffix(" and surplus") for label, *_ in self.capital_falls()] if worth else []
            expected = "what turnover is expected for the current year"
            question = (f"Why did {fell} fall, {expected}, and why did the {_join(capital)} fall (a capital reduction, "
                        f"a buy-back or a write-off)?" if capital else f"Why did {fell} fall, and {expected}?")
            worst = max(p for p in (revenue_pct if revenue else None, self.fall("net_worth") if worth else None) if p)
            observe("financial_performance", "fall", "turnover", f"{_upper(fell)} fell", " ".join(s for s, _ in found),
                    question, [e for _, c in found for e in c], "serious" if worst >= SERIOUS_FALL_PCT else "moderate")
        asked = " ".join(q.text for q in self.queries if q.group in ("documents_needed", "documents_to_redo"))
        for year, due, listed in self.returns_due():
            if not listed and year not in asked:
                observe("turnover", f"return {year}", "turnover", "Income tax return not yet filed",
                        f"The return for {year} is due by {display_date(due)} (not yet due).",
                        f"When will the income tax return for {year} be filed?", [], "mild")
        position = self.cash_position()
        least, share = CASH_GAP
        if position and abs(position[2]) >= least and abs(position[2]) >= share / 100 * position[3]:
            gap = position[2]
            question = (f"Why do the year-end statement balances exceed the audited cash and bank balance by "
                        f"{self.fin(gap)}, and which accounts does the audited figure include?" if gap > 0 else
                        f"Where is the {self.fin(-gap)} of the audited cash and bank balance that is in no statement on "
                        f"file held (another account, deposits or cash in hand), and can its statements be provided?")
            observe("banking", "cash", "accounts", "Year-end bank balances differ from the audited figure", position[0],
                    question, position[1])
        gap = self.borrowings_gap()
        if gap:
            observe("existing_facilities", "borrowings", "obligations", "Borrowings no facility on file explains", gap[1],
                    f"Who are the lenders for the {inr(gap[3])} of borrowings the facilities on file do not explain (bank "
                    f"lines, unsecured or promoter loans, current maturities), and on what terms?", gap[2])
        for lender, found, limited in self.message_only():
            if limited:
                continue
            text, cites = self.message_facility_text(lender, found, limited)
            kinds = _join([_lower(x.facility) for x in found if x.facility]) or "facility"
            observe("existing_facilities", f"facility {lender} {kinds}", "obligations", "Facility with no limit on file",
                    text, f"What are the limit and the outstanding of the {kinds} with {lender}, and can the lender's "
                    f"sanction letter be provided?", cites)
        for x, matched, text, cites in self.loan_disbursals():
            if matched:
                continue
            seen = "no instalment" not in text
            observe("existing_facilities", f"disbursal {x.date or ''} {x.amount:.0f}", "obligations",
                    "Loan disbursal no facility matches", text,
                    "Which lender disbursed this loan, and on what terms?" if seen else
                    "Which lender disbursed this loan, on what terms, and why is no instalment for it seen in the "
                    "statements?", cites)
        collateral = any(i.name in ("market_value", "realisable_value") and i.value is not None
                         for n in self.assessment.norms for i in n.inputs)
        if self.case.collateral_present and not collateral:
            observe("proposal", "collateral", "policy", "Collateral details not on file",
                    "Collateral is offered, as recorded on the case at intake; its nature and value are not on file.",
                    "What collateral is offered (the asset, its owner and its value), and are its title documents "
                    "available?", [])
        return sorted(out, key=lambda o: self.numbers.get(o.section, len(self.numbers) + 1))

    def missing_text(self, res) -> str:
        """What an open checklist item lacks, its configured request in sentence case."""
        text = _missing(res.state.deficiency)
        request = res.item.request or res.item.name
        return sentence_case(request) + text[len(request):] if request and text.startswith(request) else text

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
            verb = "is a deviation" if len(a.unevaluated_labels) == 1 else "are deviations"
            unassessed = _join([_lower(n) for n in a.unevaluated_labels])
            rows.append((f"If {unassessed} {verb}", _t("No change" if a.could_rise_to.level == a.required.level
                                                       else a.could_rise_to.label)))
        if a.provisional:
            rows.append(("Matrix", _t("Provisional matrix")))
        return rows

    def summary(self) -> list[CamSummaryItem]:
        """The findings as a register (each explained in the cross-verification section), those that
        block submission first, then the serious, then the rest in board order; the checks not
        completed with what would complete them (why is in the cross-verification section); the
        deviations, the norms not assessed and the open queries."""
        items: list[CamSummaryItem] = []
        found = self.discrepancies()
        for i in sorted(found, key=lambda i: (0 if i.finding.blocking and not i.adjudicated
                                              else 1 if i.finding.severity == "serious" else 2, found.index(i))):
            f = i.finding
            items.append(CamSummaryItem(kind="finding", text="", severity=f.severity, ref=f.ref or f.rule_id,
                                        rule=f.rule_id, title=finding_title(f), status=status(i),
                                        blocking=f.blocking and not i.adjudicated,
                                        citations=finding_evidence(f, self.threshold, self.naming)))
        for i in self.incomplete():
            f = i.finding
            items.append(CamSummaryItem(kind="incomplete", text="", severity=f.severity, ref=f.rule_id,
                                        rule=f.rule_id, title=plain(f.title), request=f.request))
        for n in self.assessment.norms:
            if n.outcome == "deviation":
                items.append(CamSummaryItem(kind="deviation", ref=n.id, rule=n.id, title=n.label,
                                            text=f"{n.category_label}: {_lower(_norm_statement(n))}.",
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
                                        citations=finding_evidence(found, self.threshold, self.naming) if found else _unique(q.evidence)))
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
    1.20x"; a norm in words reads "where the norm is positive"; a count of open items reads "Three
    blocking checklist items are open; the norm allows none"."""
    against = f", where the norm is {n.required}" if n.required in WORD_NORMS else f" against a norm of {n.required}"
    counted = re.fullmatch(r"(.+) (open|outstanding)", n.label)
    if n.unit == "count" and counted and n.actual is not None and float(n.actual).is_integer():
        count = int(n.actual)
        noun = _lower(counted[1]) if count != 1 else re.sub(r"s$", "", _lower(counted[1]))
        allows = n.required.removeprefix("at most ")
        return f"{_upper(_count(count))} {noun} {'is' if count == 1 else 'are'} {counted[2]}; the norm allows {allows}"
    if n.unit == "count":
        return f"{n.label}: {n.actual_text}{against}"
    years = re.fullmatch(r"Years of (.+)", n.label)
    if years:
        return f"{_upper(years[1])} cover {n.actual_text}{against}"
    return f"{n.label} is {n.actual_text}{against}"


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
    for number, s in enumerate(d.sections, start=1):
        defs = s.drafted_from()
        parts = [CamPart(id=p.id, kind=p.kind, title=p.title, blocks=getattr(d, p.kind)()) for p in defs]
        # One part reads as the section itself; several each go under their subheading.
        blocks = (parts[0].blocks if len(parts) == 1 else
                  [b for p in parts if p.blocks for b in [_subheading(p.title), *p.blocks]])
        # A section with no parts is left for the analyst to write.
        empty = None if blocks else ("For the analyst to write." if not defs else "Nothing on file yet.")
        sections.append(CamSection(id=s.id, number=number, title=s.title, purpose=s.purpose, blocks=blocks,
                                   parts=parts, empty=empty, blank=not defs))
    cam = Cam(
        case_id=case.id, title=config.title, borrower=case.borrower, as_of=case.as_of,
        config_version=reader.published_version(root)["version"], config_label=config_label(root),
        run_id=d.board.run.id if d.board.run else None,
        interim_template=config.interim_template, template_note=config.template_note, sections=sections,
        summary_number=len(sections) + 1, summary_title=config.summary_title,
        summary_purpose=config.summary_purpose, summary=d.summary(), rating_note=config.rating_note,
        recommendation_number=len(sections) + 2, recommendation_title=config.recommendation_title,
        recommendation_purpose=config.recommendation_purpose,
        recommendation_prompts=config.recommendation_prompts, sign_off=[CamSignOff(role=r) for r in config.sign_off],
        labels=dict(getattr(config, "labels", None) or {}),
    )
    # A person's words, the copilot's redrafts, the figures overridden and the data asked for.
    cam.template_id, cam.template_name = d.template["id"], d.template["name"]
    cam_review.apply(conn, cam)
    cam.copilot = cam_copilot.available(config.copilot)
    cam.sources = output_sources.sources(conn, root, case.id, output_sources.cam_citations(cam))
    return cam
