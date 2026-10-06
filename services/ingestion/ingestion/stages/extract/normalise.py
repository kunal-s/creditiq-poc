"""Value normalisers. They turn text as printed into a typed value and never guess: anything
that does not parse returns None and the field is reported missing with the raw text kept."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from ...util import collapse_ws

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], start=1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9

_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
        "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17,
        "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "thirtieth": 30}
_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
          "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def _valid(y: int, m: int, d: int) -> str | None:
    import calendar

    if not (1 <= m <= 12) or y < 1000 or y > 2200:
        return None
    if not (1 <= d <= calendar.monthrange(y, m)[1]):
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def _words_to_number(words: list[str]) -> int | None:
    total, cur, seen = 0, 0, False
    for w in words:
        if w in _UNITS:
            cur += _UNITS[w]; seen = True
        elif w in _TENS:
            cur += _TENS[w]; seen = True
        elif w == "hundred":
            cur = (cur or 1) * 100; seen = True
        elif w == "thousand":
            total += (cur or 1) * 1000; cur = 0; seen = True
        elif w in ("and", "-"):
            continue
        else:
            return None
    return total + cur if seen else None


def to_date(raw: str) -> str | None:
    s = collapse_ws(raw).strip(" .,;")
    low = s.casefold()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", low)
    if m:
        return _valid(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", low)
    if m:
        return _valid(int(m[3]), int(m[2]), int(m[1]))
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[\s-]+([a-z]+)\.?,?[\s-]+(\d{4})", low)
    if m and m[2] in MONTHS:
        return _valid(int(m[3]), MONTHS[m[2]], int(m[1]))
    m = re.fullmatch(r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", low)
    if m and m[1] in MONTHS:
        return _valid(int(m[3]), MONTHS[m[1]], int(m[2]))
    m = re.fullmatch(r"([a-z]+)\s+day\s+of\s+([a-z]+),?\s+(.+)", low)  # "Eighteenth day of March Two Thousand Sixteen"
    if m and m[1] in _ORD and m[2] in MONTHS:
        y = _words_to_number(m[3].split())
        return _valid(y, MONTHS[m[2]], _ORD[m[1]]) if y else None
    return None


def to_number(raw: str) -> int | float | None:
    s = collapse_ws(raw)
    if not s or s in ("-", "--", "—"):
        return None
    neg = s.startswith("(") and s.rstrip(" CrDr.").endswith(")") or bool(re.match(r"^[-−–]\s*", s)) or bool(re.search(r"(?<![A-Za-z])Dr\.?$", s))
    digits = re.sub(r"(?i)(?:₹|rs\.?|inr)", "", s)
    digits = re.sub(r"(?i)\b(?:cr|dr)\.?$", "", digits.strip())
    digits = re.sub(r"[^\d.]", "", digits.replace(",", ""))
    if not digits or digits.count(".") > 1:
        return None
    try:
        d = Decimal(digits)
    except InvalidOperation:
        return None
    if neg:
        d = -d
    return int(d) if d == d.to_integral_value() else float(d)


def to_text(raw: str) -> str | None:
    s = collapse_ws(raw).strip()
    return s or None


def normalise(raw: str, kind: str) -> tuple[object | None, str | None]:
    """(value, reason-if-unparseable)."""
    if kind == "date":
        v = to_date(raw)
        return v, None if v else "unparseable_date"
    if kind == "number":
        v = to_number(raw)
        return v, None if v is not None else "unparseable_number"
    v = to_text(raw)
    return v, None if v else "empty"
