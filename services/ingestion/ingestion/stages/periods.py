"""Periods as printed, read as date ranges (FRD F-08.1, decision 14; Epic 4 of the classification restructure).

One reader for every document type: the ways Indian financial documents print the period they cover, each turned into
a start and end date. Which kinds a type accepts, and where on its pages they are looked for, is configuration
(keywords.yaml, each type's `identity`). Nothing here reads a clock: a period comes from the document's own text.

The words each kind is printed with are configuration (keywords.yaml settings.periods); dates and month names are read
here, and the financial year starts in the configured month.

Kinds:
  year_end        "for the year ended 31 March 2026"            the financial year that ends on that date
  period_end      "for the nine months ended 31 December 2025"   the months stated, ending on that date
  as_of           "as at 31 March 2026", "as on 30 June 2026"    one day
  range           "01 Apr 2025 to 31 Mar 2026", "from ... to ..."
  financial_year  "FY 2025-26", "Financial Year 2025-26", "FY2025"
  assessment_year "Assessment Year 2025-26", "AY 2025-26"        the previous year: 1 April 2024 to 31 March 2025
  month           "April 2025", "Apr-25", "042025" after a period label, "Period Apr" with "Year 2025-26"
  quarter         "Quarter 1 (Apr-Jun)", "Q1 2025-26", "Apr-Jun 2025"
  columns         a line holding two or more dates that no word joins: a table's year columns; the latest is current
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from ..config.models import KwPeriods

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_SEP = r"[\s\-./,']*"
DATE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?{_SEP}{_MON}\.?{_SEP}(\d{{4}}|\d{{2}})\b"      # 31 March 2026, 31-Mar-26
    r"|\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b"                                     # 31.03.2026, 31/03/2026 (day first)
    r"|\b(\d{4})-(\d{2})-(\d{2})\b", re.I)                                          # 2026-03-31


def _phrase(p: str) -> str:
    """A configured phrase as a pattern: any spacing between words, a "." that may be left out, a "-" that may be a space."""
    out = []
    for ch in p.strip():
        if ch == " ":
            out.append(r"\s+")
        elif ch == ".":
            out.append(r"\.?\s?")
        elif ch == "-" and len(p.strip()) > 1:
            out.append(r"[\s-]*")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def _alt(phrases) -> str:
    return "(?:" + "|".join(sorted((_phrase(x) for x in phrases), key=len, reverse=True)) + ")"


class Vocab:
    """The configured words (keywords.yaml settings.periods), compiled once."""

    def __init__(self, cfg: KwPeriods):
        self.cfg = cfg
        self.joined = re.compile(rf"\s*{_alt(cfg.range_joiners)}\s*")
        self.columns = re.compile(rf"\b{_alt(cfg.column_headings)}\b")
        self.heading = re.compile(rf"\b{_alt(cfg.heading_words)}\b")
        nums = "|".join(sorted(map(re.escape, cfg.number_words), key=len, reverse=True))
        self.count = re.compile(rf"\b(\d{{1,2}}|{nums})\s*(?:-\s*)?({'|'.join(map(_phrase, cfg.count_units))})\s+"
                                rf"{_alt(cfg.count_ended)}\s*(?:on\s*)?$")
        self.units = {k.lower(): v for k, v in cfg.count_units.items()}
        self.year_end = re.compile(rf"\b({_alt(cfg.year_end)})\s*(?:on\s*)?$")
        self.period_end = [(re.compile(rf"\b{_phrase(k)}\s*(?:on\s*)?$"), v) for k, v in cfg.period_end.items()]
        self.as_of = re.compile(rf"\b({_alt(cfg.as_of)})\s*$")
        self.ay = re.compile(rf"\b{_alt(cfg.assessment_year)}\s*:?\s*(20\d{{2}})\s*[-–/]\s*(\d{{2,4}})", re.I)
        self.fy = re.compile(rf"\b{_alt(cfg.financial_year)}\s*:?\s*(20\d{{2}})(?:\s*[-–/]\s*(\d{{2,4}}))?", re.I)
        self.quarter = re.compile(rf"\b{_MON}\w*\s*{_alt(cfg.quarter_joiners)}\s*{_MON}\w*\s*\)?\s*,?\s*(20\d{{2}})?", re.I)
        self.numeric_month = re.compile(rf"\b{_alt(cfg.period_labels)}\s*:?\s*(0[1-9]|1[0-2])\s*[/-]?\s*(20\d{{2}})\b", re.I)
        self.page_year = re.compile(rf"\b{_alt(cfg.year_labels)}\s*:?\s*(20\d{{2}})\s*[-–/]\s*(\d{{2,4}})", re.I)
        self.page_quarter = re.compile(rf"\b{_alt(cfg.quarter_labels)}\s*([1-4])\b", re.I)
        self.page_month = re.compile(rf"\b{_alt(cfg.period_labels)}[ \t]*:?[ \t]*{_MON}\w*\b(?![ \t\-,']*\d)", re.I)


_VOCABS: dict[int, Vocab] = {}


def vocab(cfg: KwPeriods | None = None) -> Vocab:
    cfg = cfg or KwPeriods()
    v = _VOCABS.get(id(cfg))
    if v is None or v.cfg is not cfg:
        v = _VOCABS[id(cfg)] = Vocab(cfg)
    return v


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    kind: str
    text: str            # as printed

    def label(self) -> str:
        return self.text

    def to_json(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "kind": self.kind, "text": self.text}


def _year(y: str) -> int:
    n = int(y)
    return n + 2000 if n < 100 else n


def _date_of(m: re.Match) -> date | None:
    g = m.groups()
    try:
        if g[0]:
            return date(_year(g[2]), _month(g[1]), int(g[0]))
        if g[3]:
            return date(int(g[5]), int(g[4]), int(g[3]))
        if g[6]:
            return date(int(g[6]), int(g[7]), int(g[8]))
    except (ValueError, KeyError):
        return None
    return None


def _month(token: str) -> int:
    t = token.lower().rstrip(".")
    return MONTHS.get(t) or MONTHS[t[:3]]


def _year_before(end: date) -> date:
    """The day after the same date a year earlier: the first day of the year that ends on `end`."""
    try:
        back = end.replace(year=end.year - 1)
    except ValueError:            # 29 February
        back = date(end.year - 1, 2, 28)
    return back + timedelta(days=1)


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _months_back(end: date, n: int) -> date:
    y, m = end.year, end.month - n + 1
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _fy(start_year: int, fy_start: int) -> tuple[date, date]:
    """The financial year that starts in `start_year`: 1 April 2025 to 31 March 2026 with an April start."""
    start = date(start_year, fy_start, 1)
    return start, date(start_year + (1 if fy_start > 1 else 0), fy_start, 1) - timedelta(days=1) if fy_start > 1 \
        else date(start_year, 12, 31)


def _fy_of(d: date, fy_start: int) -> int:
    return d.year if d.month >= fy_start else d.year - 1


def _two_years(a: str, b: str) -> int | None:
    """2025-26, 2025-2026: the first year, when the second follows it."""
    y1, y2 = int(a), _year(b)
    if y2 % 100 == (y1 + 1) % 100 or y2 == y1 + 1:
        return y1
    return None


def _year_end_of(year: int, fy_start: int) -> date:
    """The last day of the financial year that ends in `year`."""
    return date(year, fy_start, 1) - timedelta(days=1) if fy_start > 1 else date(year, 12, 31)


def in_line(line: str, fy_start: int = 4, v: Vocab | None = None) -> list[Period]:
    """Every period the line prints, in the order printed."""
    v = v or vocab()
    t = " ".join(line.split())
    low = t.lower()
    out: list[Period] = []
    dates = [(m, _date_of(m)) for m in DATE.finditer(t)]
    dates = [(m, d) for m, d in dates if d]

    # Two dates joined by "to" or a dash: a range.
    for (m1, d1), (m2, d2) in zip(dates, dates[1:]):
        between = low[m1.end():m2.start()]
        if v.joined.fullmatch(between) and d1 <= d2:
            out.append(Period(d1, d2, "range", t[m1.start():m2.end()]))
    joined = {id(m) for p in out for m, _ in dates if t[m.start():m.end()] in p.text}
    single = [(m, d) for m, d in dates if id(m) not in joined]

    # Column headings printed as a row ("As at 31 March  As at 31 March", the years below): not a heading's period.
    if len(v.columns.findall(low)) >= 2:
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", low)]
        if dates or years:
            d = max([d for _, d in dates] or [_year_end_of(max(years), fy_start)])
            return out + [Period(d, d, "columns", t)]
    # Two or more dates no word joins: a table's year columns.
    if len(single) >= 2 and not v.heading.search(low[: single[0][0].start()][-40:] or ""):
        out.append(Period(max(d for _, d in single), max(d for _, d in single), "columns", t))
        return out

    for m, d in single:
        before = low[max(0, m.start() - 60):m.start()]
        n = v.count.search(before)
        ye = v.year_end.search(before)
        pe = next(((rx.search(before), k) for rx, k in v.period_end if rx.search(before)), (None, 0))
        ao = v.as_of.search(before)
        if n:
            count = v.cfg.number_words.get(n.group(1)) or int(n.group(1))
            unit = next((k for u, k in v.units.items() if re.fullmatch(_phrase(u), n.group(2), re.I)), 1)
            out.append(Period(_months_back(d, count * unit), d, "period_end", t[m.start() - (len(before) - n.start()):m.end()].strip()))
        elif ye:
            out.append(Period(_year_before(d), d, "year_end", t[m.start() - (len(before) - ye.start()):m.end()].strip()))
        elif pe[0]:
            out.append(Period(_months_back(d, pe[1]), d, "period_end", t[m.start() - (len(before) - pe[0].start()):m.end()].strip()))
        elif ao:
            out.append(Period(d, d, "as_of", t[m.start() - (len(before) - ao.start()):m.end()].strip()))

    for m in v.ay.finditer(t):
        y = _two_years(m.group(1), m.group(2))
        if y:
            s, e = _fy(y - 1, fy_start)
            out.append(Period(s, e, "assessment_year", m.group(0)))
    for m in v.fy.finditer(t):
        if m.group(2):
            y = _two_years(m.group(1), m.group(2))
        else:
            y = int(m.group(1)) - 1          # "FY2025": the year that ends in 2025
        if y:
            s, e = _fy(y, fy_start)
            out.append(Period(s, e, "financial_year", m.group(0)))
    # A quarter: Q1 2025-26, Quarter 1 (Apr-Jun), Apr-Jun 2025.
    for m in v.quarter.finditer(t):
        a, b = _month(m.group(1)), _month(m.group(2))
        if a and b and (b - a) % 12 == 2 and m.group(3):
            y = int(m.group(3))
            out.append(Period(date(y, a, 1), _month_end(y + (1 if b < a else 0), b), "quarter", m.group(0)))
    # A month: April 2025, Apr-25, or MMYYYY after a period label.
    for m in re.finditer(rf"(?<![\d\w]){_MON}\w*\.?[\s\-,']*(20\d{{2}}|\d{{2}})(?![\d\w-])", t, re.I):
        if any(m.group(0) in p.text for p in out):
            continue
        if re.search(r"\d\s*$", t[:m.start()]):      # a day before it: a date, read above
            continue
        y, mo = _year(m.group(2)), _month(m.group(1))
        out.append(Period(date(y, mo, 1), _month_end(y, mo), "month", m.group(0)))
    for m in v.numeric_month.finditer(t):
        y, mo = int(m.group(2)), int(m.group(1))
        out.append(Period(date(y, mo, 1), _month_end(y, mo), "month", m.group(0)))
    return out


def page_level(lines: list[str], fy_start: int = 4, v: Vocab | None = None) -> list[Period]:
    """Periods a page prints across lines: a month or quarter named alone after a period label ("Period Apr"), read
    within the financial year the page names ("Year 2025-26")."""
    v = v or vocab()
    text = "\n".join(" ".join(l.split()) for l in lines)       # lines kept apart: a month is not read across them
    fy = v.page_year.search(text)
    if not fy:
        return []
    y0 = _two_years(fy.group(1), fy.group(2))
    if y0 is None:
        return []
    out = []
    q = v.page_quarter.search(text)
    if q:
        n = int(q.group(1))
        first = fy_start + 3 * (n - 1)
        start = date(y0 + (first - 1) // 12, (first - 1) % 12 + 1, 1)
        last = first + 2
        end = _month_end(y0 + (last - 1) // 12, (last - 1) % 12 + 1)
        out.append(Period(start, end, "quarter", q.group(0) + " " + fy.group(0)))
        return out
    m = v.page_month.search(text)
    if m:
        mo = _month(m.group(1))
        y = y0 if mo >= fy_start else y0 + 1
        out.append(Period(date(y, mo, 1), _month_end(y, mo), "month", m.group(0) + " " + fy.group(0)))
    return out
