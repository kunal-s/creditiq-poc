"""Document identity (FRD F-08.1, F-08.1a, F-08.3; decision 14; Epic 4 of the classification restructure).

A run of pages of one type is split where its period, account or person changes (keywords.yaml, each type's
`identity.by`), and each document's period is read as a date range from its own pages, in this order:

1. its title lines (the header band and print that stands out), then its footer;
2. its body, for a type whose period sits in a details block (`identity.body`: a bank statement's "Statement 01 Apr
   2025 to 31 Mar 2026");
3. its tables' year columns, the latest being the document's own;
4. for a bank statement, its first and last transaction dates, marked as derived;
5. the model, asked for the words that state the period, which are then found on their line and read like any other;
6. none: the document is kept, marked "period not found", for a person to set.

Only the kinds the type accepts count (`identity.period`); a period is never taken from another document, the file
name or the upload date (principle 7). A title that disagrees with the table's columns is a conflict, for review."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config.models import IngestionConfig, KwIdentity
from ..llm.provider import ModelError, ModelRequest
from ..llm.recorder import ModelClient
from ..pageindex import Page
from . import furniture
from . import keywords as K
from .extract.identifiers import PATTERNS
from .periods import Period, in_line, page_level, vocab


@dataclass
class Identity:
    by: str
    key: str | None = None                 # what the engine reads the instance by (an ISO year end, "AY 2025-26", ...)
    period: Period | None = None
    status: str = "none"                   # found | derived | conflict | not_found | none (the type has no period)
    source: str | None = None              # title | footer | body | columns | rows | model
    page: int | None = None
    note: str | None = None
    account: str | None = None
    person: str | None = None
    trace: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"by": self.by, "key": self.key, "status": self.status, "source": self.source, "page": self.page,
                "note": self.note, "account": self.account, "person": self.person,
                "period": self.period.to_json() if self.period else None}


def rule_of(cfg: IngestionConfig, doc_type: str) -> KwIdentity:
    kw = cfg.keywords
    t = kw.types.get(doc_type) if kw else None
    return (t.identity if t and t.identity else None) or KwIdentity()


def _zone_lines(cfg: IngestionConfig, page: Page, zone: str) -> list[str]:
    return [l.text for l, z in K.line_zones(cfg.keywords, page) if z == zone]


def _one_year(p: Period, fy_start: int) -> bool:
    """A range that is one financial year: from the first day of the year's first month to the day before it a year on."""
    return (p.kind == "range" and p.start.day == 1 and p.start.month == fy_start
            and (p.end.year, p.end.month) == (p.start.year + (1 if fy_start > 1 else 0), (fy_start - 2) % 12 + 1)
            and p.end.day >= 28)


def _accepted(rule: KwIdentity, ps: list[Period], fy_start: int | None = None) -> list[Period]:
    """The periods the type accepts. A range that is one financial year ("for period 01/04/2023 to 31/03/2024") is that
    year's end for a type that is read by its year end."""
    out = []
    for p in ps:
        if p.kind in rule.period and p.kind != "columns":
            out.append(p)
        elif fy_start and {"year_end", "financial_year"} & set(rule.period) and _one_year(p, fy_start):
            out.append(Period(p.start, p.end, "year_end", p.text))
    return out


def _reader(cfg: IngestionConfig):
    """The financial year's first month and the configured period words."""
    s = cfg.keywords.settings
    return s.identity.financial_year_start_month, vocab(s.periods)


def _page_period(cfg: IngestionConfig, rule: KwIdentity, page: Page, zones=("title", "footer")) -> tuple[Period | None, str | None]:
    """The period the page states. Its running header or footer (furniture.py) comes first: printed on every page of
    the document, it says which period the document is, and a period a sentence near the top of a page mentions does
    not override it. Then each zone's lines, in order."""
    fy, v = _reader(cfg)
    for zone in [z for z in zones if z in ("title", "footer")]:
        for line in furniture.lines(page, "top" if zone == "title" else "bottom"):
            got = _accepted(rule, in_line(line.text, fy, v), fy)
            if got:
                return got[0], zone
    for zone in zones:
        lines = _zone_lines(cfg, page, zone)
        for line in lines:
            got = _accepted(rule, in_line(line, fy, v), fy)
            if got:
                return got[0], zone
        got = _accepted(rule, page_level(lines, fy, v), fy)
        if got:
            return got[0], zone
    return None, None


def _columns(cfg: IngestionConfig, pages: list[Page]) -> tuple[Period | None, int | None]:
    """The latest of the first year columns printed. Column headings may be stacked over lines, a range to a line: a
    line of dates, a line of the range's joining words ("to  to"), a line of dates: the columns end on the last."""
    fy, v = _reader(cfg)
    joiners = {j.casefold() for j in cfg.keywords.settings.periods.range_joiners}
    for p in pages:
        lines = p.content_lines()
        for i, l in enumerate(lines):
            got = [x for x in in_line(l.text, fy, v) if x.kind == "columns"]
            if not got:
                continue
            nxt = lines[i + 1:i + 3]
            if len(nxt) == 2 and nxt[0].text.split() and all(w.casefold() in joiners for w in nxt[0].text.split()):
                ends = [x for x in in_line(nxt[1].text, fy, v) if x.kind == "columns"]
                if ends:
                    return ends[0], p.no
            return got[0], p.no
    return None, None


def _account(cfg: IngestionConfig, page: Page) -> str | None:
    """The account number after the first label, in the configured order, that a number of the configured length (or
    masked digits) follows; a label may wrap across lines."""
    text = page.text()
    least, most = cfg.keywords.settings.identity.account_digits
    for label in cfg.keywords.settings.identity.account_labels:
        rx = r"\s+".join(map(re.escape, label.split()))
        m = re.search(rf"\b{rx}\s*[:.]?\s*([0-9Xx*]{{{least},{most}}})\b", text, re.I)
        if m:
            return m.group(1).upper()
    return None


def _person(cfg: IngestionConfig, page: Page) -> str | None:
    """The person a personal document is about, by the configured rules in order: the DIN beside its label, else an
    individual's PAN (its fourth letter the configured one), else a masked PAN."""
    rules = cfg.keywords.settings.identity.person
    text = page.text()
    labels = "|".join(r"\s+".join(map(re.escape, x.split())) for x in rules.din_labels)
    m = re.search(rf"\b(?:{labels})\s*[:.]?\s*(\d{{8}})\b", text, re.I) if labels else None
    if m:
        return "DIN " + m.group(1)
    for p in re.findall(PATTERNS["pan"], text):
        if p[3] == rules.individual_pan_letter.upper():
            return "PAN " + p
    m = re.search(PATTERNS["masked_pan"], text) if rules.masked_pan else None
    return "PAN " + m.group(0) if m else None


def _key_of(cfg: IngestionConfig, rule: KwIdentity, page: Page) -> str | None:
    if rule.by == "account":
        return _account(cfg, page)
    if rule.by == "person":
        return _person(cfg, page)
    if rule.by == "period":
        p, _ = _page_period(cfg, rule, page, ("title", "body") if rule.body else ("title",))
        return p.end.isoformat() if p else None
    return None


def _periods_named(cfg: IngestionConfig, rule: KwIdentity, page: Page) -> set[tuple]:
    fy, v = _reader(cfg)
    return {(p.start, p.end) for l in page.content_lines() for p in _accepted(rule, in_line(l.text, fy, v), fy)}


def _part_index(cfg: IngestionConfig, order: list[str], page: Page) -> int | None:
    """Where the page's best part comes in the type's parts, when it is one of them."""
    if not order:
        return None
    ps = K.part_scores(cfg.keywords, page)
    best = max(order, key=lambda pn: (ps[pn].score, -order.index(pn)))
    return order.index(best) if ps[best].score > 0 else None


def split(cfg: IngestionConfig, doc_type: str, pages: list[Page]) -> tuple[list[int], list[list[Page]]]:
    """(front matter, documents): the run's pages grouped into documents. A page naming another period, account or
    person than the document before opens a new one; a page naming none stays with it. Pages before the first that
    names one join the first (an auditor's report before the balance sheet), unless a page lists `cover_min_periods`
    periods of the type or more (a compilation's cover listing its returns): that is front matter. A statements' cover
    naming its year and the comparative year is not."""
    real = [p for p in pages if not p.blank]
    rule = rule_of(cfg, doc_type)
    if rule.by == "none" or not real:
        return [], ([real] if real else [])
    front: list[int] = []
    if rule.by == "period":
        least = cfg.keywords.settings.identity.cover_min_periods
        while real and len(_periods_named(cfg, rule, real[0])) >= least:
            front.append(real.pop(0).no)
    # A page going back in the order of the type's parts (an auditor's report after the notes) opens the next document,
    # which takes its period from the pages that follow; the pages before the first key join the first document.
    order = cfg.keywords.types[doc_type].parts if cfg.keywords and doc_type in cfg.keywords.types else []
    groups: list[list[Page]] = [[]]
    keys: list[str | None] = [None]
    current: str | None = None
    prev_part: int | None = None
    for p in real:
        part = _part_index(cfg, order, p)
        if part is not None and prev_part is not None and part < prev_part and groups[-1] and current is not None:
            groups.append([])
            keys.append(None)
            current = None
        k = _key_of(cfg, rule, p)
        if k and k != current:
            if current is not None:
                groups.append([])
                keys.append(None)
            current = k
            keys[-1] = k
        groups[-1].append(p)
        prev_part = part if part is not None else prev_part
    # A document opened by going back in the parts stands only with a period of its own: one that finds the same period
    # as the document before, or none, was a page of it (notes listing the balance sheet's lines).
    out: list[list[Page]] = []
    last: str | None = None
    for g, k in zip(groups, keys):
        if not g:
            continue
        if out and (k is None or k == last):
            out[-1] += g
        else:
            out.append(g)
            last = k
    return front, out


def identify(cfg: IngestionConfig, doc_type: str, pages: list[Page], model: ModelClient | None) -> Identity:
    rule = rule_of(cfg, doc_type)
    ident = Identity(rule.by)
    if rule.by == "account":
        ident.account = next((a for p in pages if (a := _account(cfg, p))), None)
        ident.key = ident.account
    if rule.by == "person":
        ident.person = next((x for p in pages if (x := _person(cfg, p))), None)
        ident.key = ident.person
    if not rule.period:
        return ident
    zones = ("title", "footer", "body") if rule.body else ("title", "footer")
    # The kinds in the type's order of preference, each looked for in every zone of every page before the next kind:
    # audited statements are the year they end, though the balance sheet before the profit and loss is "as at".
    found, where, page = None, None, None
    for kind in rule.period:
        one = rule.model_copy(update={"period": [kind]})
        for zone in zones:
            for p in pages:
                got, z = _page_period(cfg, one, p, (zone,))
                if got:
                    found, where, page = got, z, p.no
                    break
            if found:
                break
        if found:
            break
    cols, cols_page = _columns(cfg, pages) if rule.columns else (None, None)
    if found:
        ident.period, ident.source, ident.page, ident.status = found, where, page, "found"
        if cols and cols.end.year != found.end.year and found.kind in ("year_end", "as_of", "financial_year", "period_end"):
            ident.status = "conflict"
            ident.note = f'the title says "{found.text}" but the table\'s latest column is {cols.end.isoformat()} (page {cols_page})'
    elif cols:
        ident.period, ident.source, ident.page, ident.status = cols, "columns", cols_page, "found"
    elif rule.derive_from_rows:
        rows = _row_dates(cfg, pages)
        if rows:
            ident.period, ident.source, ident.status = rows, "rows", "derived"
            ident.note = "taken from the first and last transaction dates; the statement prints no period"
    if ident.period is None and model is not None:
        got = _ask(cfg, rule, doc_type, pages, model, ident)
        if got:
            ident.period, ident.source, ident.status, ident.page = got[0], "model", "found", got[1]
    if ident.period is None:
        ident.status = "not_found"
        ident.note = ident.note or "no period on the document's own pages; a person sets it"
    if ident.period and rule.by == "period":
        ident.key = _engine_key(ident.period)
    return ident


def _engine_key(p: Period) -> str:
    """The period in a form the engine reads (engine/util.py): a year end as an ISO date, an assessment year as
    "AY 2025-26", a month as "Apr 2025", a quarter as "Apr-Jun 2025"."""
    if p.kind == "assessment_year":
        y = p.end.year
        return f"AY {y}-{(y + 1) % 100:02d}"
    if p.kind == "month":
        return p.start.strftime("%b %Y")
    if p.kind == "quarter":
        return f"{p.start.strftime('%b')}-{p.end.strftime('%b')} {p.end.year}"
    return p.end.isoformat()


def _row_dates(cfg: IngestionConfig, pages: list[Page]) -> Period | None:
    from .periods import DATE, _date_of
    row = re.compile(cfg.keywords.settings.matching.table_row)
    reach = cfg.keywords.settings.identity.row_date_chars
    seen = []
    for p in pages:
        for l in p.content_lines():
            if not row.search(l.text):
                continue
            m = DATE.search(l.text[:reach])
            if m and (d := _date_of(m)):
                seen.append(d)
    if len(seen) < 2:
        return None
    return Period(min(seen), max(seen), "range", f"{min(seen).isoformat()} to {max(seen).isoformat()} (from the transactions)")


_SCHEMA = {"type": "object", "properties": {"text": {"type": ["string", "null"]}, "line_id": {"type": ["string", "null"]}},
           "required": ["text", "line_id"], "additionalProperties": False}


def _ask(cfg: IngestionConfig, rule: KwIdentity, doc_type: str, pages: list[Page], model: ModelClient,
         ident: Identity) -> tuple[Period, int] | None:
    """The model names the words that state the period and their line; they count only when they are on that line and
    read as a period of a kind the type accepts (a value never taken from another document)."""
    by_id = {}
    lines, budget = [], cfg.llm.classify_chars
    for p in pages:
        for l in p.content_lines():
            row = f"{l.id}: {l.text}"
            if budget - len(row) < 0:
                break
            budget -= len(row) + 1
            lines.append(row)
            by_id[l.id] = (l.text, p.no)
    pr = cfg.llm.prompts["period"]
    name = cfg.document_types.by_id()[doc_type].display_name
    req = ModelRequest("period", pr.system.strip(), pr.user.replace("{{type_name}}", name).replace("{{lines}}", "\n".join(lines)).strip(), _SCHEMA)
    try:
        ans = model.call(req)
    except ModelError as e:
        ident.trace.append({"model_error": e.code})
        return None
    text, lid = ans.get("text"), ans.get("line_id")
    confused = cfg.keywords.settings.matching.confused_digits
    if not text or lid not in by_id or K.fold(text, confused) not in K.fold(by_id[lid][0], confused):
        ident.trace.append({"model": ans, "outcome": "not on its line"})
        return None
    fy, v = _reader(cfg)
    got = _accepted(rule, in_line(text, fy, v), fy)
    if not got:
        ident.trace.append({"model": ans, "outcome": "not a period this type accepts"})
        return None
    return got[0], by_id[lid][1]
