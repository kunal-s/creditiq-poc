"""Small shared helpers: timestamps for records (never for rules, CLAUDE.md
rule 5), stable ids, and date parsing for completeness rules."""

from __future__ import annotations

import calendar
import hashlib
import json
import re
from datetime import date, datetime, timezone


def now_iso() -> str:
    """A record timestamp. Rules never read it: ages use the case's as_of."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def stable_id(prefix: str, *parts: object) -> str:
    """A deterministic id, so re-running a step writes the same rows."""
    digest = hashlib.sha1("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
_MONTHS["sept"] = 9


def parse_date(value: object) -> date | None:
    """A calendar date from the formats documents use: ISO, dd-mm-yyyy,
    dd/mm/yyyy, dd.mm.yyyy, "31 Jan 2026", "31st January, 2026"."""
    if value is None:
        return None
    text = str(value).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ].*)?", text)
    if m:
        return _safe_date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", text)
    if m:
        return _safe_date(int(m[3]), int(m[2]), int(m[1]))
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[\s-]+([A-Za-z]+)[\s,.-]+(\d{4})", text)
    if m and m[2].lower() in _MONTHS:
        return _safe_date(int(m[3]), _MONTHS[m[2].lower()], int(m[1]))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if m and m[1].lower() in _MONTHS:
        return _safe_date(int(m[3]), _MONTHS[m[1].lower()], int(m[2]))
    return None


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_period(value: object) -> tuple[int, int] | None:
    """A (year, month) tax period: "2025-09", "09-2025", "092025" (the GST
    portal's MMYYYY), "Sep 2025", "September-2025", or a full date."""
    if value is None:
        return None
    text = str(value).strip()
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})", text)
    if m and 1 <= int(m[2]) <= 12:
        return int(m[1]), int(m[2])
    m = re.fullmatch(r"(\d{1,2})[-/](\d{4})", text)
    if m and 1 <= int(m[1]) <= 12:
        return int(m[2]), int(m[1])
    m = re.fullmatch(r"(\d{2})(\d{4})", text)
    if m and 1 <= int(m[1]) <= 12:
        return int(m[2]), int(m[1])
    m = re.fullmatch(r"([A-Za-z]+)[\s,'-]+(\d{2}|\d{4})", text)
    if m and m[1].lower() in _MONTHS:
        year = int(m[2]) + (2000 if len(m[2]) == 2 else 0)
        return year, _MONTHS[m[1].lower()]
    d = parse_date(text)
    return (d.year, d.month) if d else None


def month_add(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def month_label(period: tuple[int, int]) -> str:
    return f"{calendar.month_abbr[period[1]]} {period[0]}"


def months_before(as_of: date, count: int) -> list[tuple[int, int]]:
    """The `count` complete calendar months before as_of's month, oldest first."""
    return [month_add(as_of.year, as_of.month, -k) for k in range(count, 0, -1)]


def ranges_label(periods: list[tuple[int, int]]) -> str:
    """"Sep 2025 to Dec 2025, Mar 2026" for a sorted list of months."""
    if not periods:
        return ""
    periods = sorted(periods)
    runs: list[list[tuple[int, int]]] = [[periods[0]]]
    for p in periods[1:]:
        if month_add(*runs[-1][-1], 1) == p:
            runs[-1].append(p)
        else:
            runs.append([p])
    return ", ".join(
        month_label(r[0]) if len(r) == 1 else f"{month_label(r[0])} to {month_label(r[-1])}" for r in runs
    )


def fy_end(as_of: date, offset: int) -> date:
    """The end (31 March) of financial year `offset`: 1 is the latest
    financial year ended before as_of, 2 the one before it."""
    latest = as_of.year if as_of > date(as_of.year, 3, 31) else as_of.year - 1
    return date(latest - (offset - 1), 3, 31)


def fy_label(end: date) -> str:
    return f"FY {end.year - 1}-{str(end.year)[2:]} (year ended 31 Mar {end.year})"


def fy_end_of(value: object) -> date | None:
    """The 31 March a financial-statement period or year label points to:
    a date ("2026-03-31"), "FY2025-26", "FY26", "2025-26" or "2026"."""
    d = parse_date(value)
    if d:
        return date(d.year if d.month <= 3 else d.year + 1, 3, 31)
    if value is None:
        return None
    text = str(value).strip().upper().replace(" ", "")
    m = re.fullmatch(r"(?:FY)?(\d{4})-(\d{2}|\d{4})", text)
    if m:
        return date(int(m[1]) + 1, 3, 31)
    m = re.fullmatch(r"FY(\d{2}|\d{4})", text)
    if m:
        year = int(m[1]) + (2000 if len(m[1]) == 2 else 0)
        return date(year, 3, 31)
    m = re.fullmatch(r"(\d{4})", text)
    if m:
        return date(int(m[1]), 3, 31)
    return None


def assessment_year_start(value: object) -> int | None:
    """The first calendar year of an assessment year: "2026-27", "AY 2026-27" -> 2026."""
    if value is None:
        return None
    text = str(value).strip().upper().replace(" ", "")
    m = re.fullmatch(r"(?:AY)?(\d{4})-?(\d{2}|\d{4})?", text)
    return int(m[1]) if m else None


def format_inr(amount: float | int) -> str:
    """Indian digit grouping: 30000000 -> "3,00,00,000"."""
    negative = amount < 0
    whole = str(int(round(abs(amount))))
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return ("-" if negative else "") + whole


def display_date(d: date) -> str:
    return f"{d.day} {calendar.month_abbr[d.month]} {d.year}"
