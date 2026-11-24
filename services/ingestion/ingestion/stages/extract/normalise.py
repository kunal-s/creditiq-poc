"""Value normalisers. They turn text as printed into a typed value and never guess: anything
that does not parse returns None and the field is reported missing with the raw text kept."""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation

from ...config.models import NumberForms
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


_MON = "|".join(sorted((k for k in MONTHS), key=len, reverse=True))
_DATE_TOKENS = (
    r"\b\d{4}-\d{1,2}-\d{1,2}\b",
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b",
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?[\s-]+(?:{_MON})\.?,?[\s-]+\d{{4}}\b",
    rf"\b(?:{_MON})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b",
)


def to_date(raw: str) -> str | None:
    """The whole text is a date, or it holds exactly one (a filing date followed by a time or a note).
    Two different dates in one value is a range or a sentence, not a date: that is left unparsed."""
    s = collapse_ws(raw).strip(" .,;")
    v = _date_exact(s.casefold())
    if v:
        return v
    found = {_date_exact(m.group(0)) for rx in _DATE_TOKENS for m in re.finditer(rx, s.casefold())}
    found.discard(None)
    return found.pop() if len(found) == 1 else None


def _date_exact(low: str) -> str | None:
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
    # A certificate's date in words: "this Seventh day of February Two thousand seventeen", "Twenty-first day of
    # June Two thousand twenty-four", "the 7th day of March 2015".
    m = re.fullmatch(r"(?:(?:this|on|the|dated)\s+)*(.+?)\s+day\s+of\s+([a-z]+),?\s+(?:in\s+the\s+year\s+)?(.+)", low)
    if m and m[2] in MONTHS:
        d, y = _day_number(m[1]), _year_number(m[3])
        return _valid(y, MONTHS[m[2]], d) if d and y else None
    return None


def _day_number(s: str) -> int | None:
    """An ordinal day: "seventh", "twenty-first", "twenty first", "7th", "21"."""
    if re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)?", s):
        return int(re.match(r"\d+", s)[0])
    words = [w for w in re.split(r"[\s-]+", s) if w]
    if len(words) == 1:
        return _ORD.get(words[0])
    if len(words) == 2 and words[0] in ("twenty", "thirty") and _ORD.get(words[1], 10) < 10:
        return _TENS[words[0]] + _ORD[words[1]]
    return None


def _year_number(s: str) -> int | None:
    """A year in figures or in words ("Two thousand twenty-four", "Two Thousand and Sixteen"). The year is the
    words that are numbers at the start; text after them ("under the Companies Act") is not part of it."""
    m = re.match(r"(\d{4})\b", s)
    if m:
        return int(m[1])
    words = [w for w in re.split(r"[\s,-]+", s.strip(" .")) if w]
    number = list(words)
    for i, w in enumerate(words):
        if w not in _UNITS and w not in _TENS and w not in ("hundred", "thousand", "and"):
            number = words[:i]
            break
    while number and number[-1] == "and":
        number.pop()
    return _words_to_number(number) if number else None


def _two_quantities(s: str) -> bool:
    """Digits, then anything that is not part of a number, then more digits ("4,027,498 as on 31 March
    2025", "75,00,000 (90,00,000)"): joining them would invent a number, so the value is left unparsed."""
    body = re.sub(r"(?i)(?:₹|rs\.?|inr)", "", s)
    body = re.sub(r"(?i)\b(?:cr|dr)\.?\s*$", "", body.strip())
    return re.search(r"\d[\d,.\s]*[^\d,.\s][^\d]*\d", body) is not None


_FORMS: ContextVar[NumberForms] = ContextVar("number_forms", default=NumberForms())


@contextmanager
def number_forms(forms: NumberForms):
    """The configured number forms (fields.yaml numbers) for the extraction inside the block."""
    token = _FORMS.set(forms)
    try:
        yield
    finally:
        _FORMS.reset(token)


def _markers(words: list[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) or r"(?!x)x"


def _split_figure(s: str, forms: NumberForms) -> str | None:
    """A figure a scan broke with spaces, put back when the pieces form a grouping; None when they do not."""
    m = re.fullmatch(r"(\d+(?: \d+)+)(\.\d+)?", s)
    if not m:
        return s
    if not forms.space_grouping:
        return None
    parts = m.group(1).split(" ")
    indian = len(parts[-1]) == 3 and 1 <= len(parts[0]) <= 2 and all(len(p) == 2 for p in parts[1:-1])
    western = len(parts[0]) <= 3 and all(len(p) == 3 for p in parts[1:])
    return "".join(parts) + (m.group(2) or "") if indian or western else None


def to_number(raw: str) -> int | float | None:
    forms = _FORMS.get()
    s = collapse_ws(raw)
    if not s or s in ("-", "--", "—"):
        return None
    if s.lower().rstrip(".") in [w.lower().rstrip(".") for w in forms.nil_words]:
        return 0
    dr, cr = _markers(forms.debit_markers), _markers(forms.credit_markers)
    marked_debit = bool(re.search(rf"(?i)(?:^(?:{dr})\.?\s+(?=[\d(₹R])|(?<![A-Za-z])(?:{dr})\.?$)", s))
    s = re.sub(rf"(?i)^(?:{dr}|{cr})\.?\s+(?=[\d(₹R])", "", s)
    s = re.sub(rf"(?i)(?<![A-Za-z])(?:{dr}|{cr})\.?$", "", s).strip()
    trailing = forms.trailing_minus and bool(re.search(r"\d\s*[-−–]$", s))
    if trailing:
        s = re.sub(r"\s*[-−–]$", "", s)
    # "(AO) -20.43": a footnote reference in front of the figure is not part of it (and is not a negative's brackets).
    s = re.sub(r"^\([A-Z]{1,2}\)\s+(?=[-−–(]?\s?(?:₹|Rs\.?|INR)?\s?\d)", "", s)
    # "4,027,498 (illustrative)", "Rs. 75,00,000 (previous year Rs. 90,00,000).": a trailing note in words
    s = re.sub(r"(?<=\d)\s*\([^)]*[A-Za-z][^)]*\)\s*[.,;]?\s*$", "", s)
    if _two_quantities(s):
        return None
    neg = (s.startswith("(") and s.endswith(")")) or bool(re.match(r"^[-−–]\s*", s)) or marked_debit or trailing
    digits = re.sub(r"(?i)(?:₹|rs\.?|inr)", "", s).strip().strip("()").strip()
    digits = re.sub(r"^[-−–]\s*", "", digits)
    if "," not in digits:
        digits = _split_figure(digits, forms)
        if digits is None:
            return None
    elif re.search(r"\d\s+\d", digits):
        return None          # with commas printed, a space between digits parts two figures: never join them
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
    if kind == "present":
        # A yes/no fact read from the wording that states it ("Material Uncertainty Related to Going
        # Concern"): verified wording on the page means true. Nothing found stays missing, never false.
        return (True, None) if to_text(raw) else (None, "empty")
    if kind == "date":
        v = to_date(raw)
        return v, None if v else "unparseable_date"
    if kind == "number":
        v = to_number(raw)
        return v, None if v is not None else "unparseable_number"
    v = to_text(raw)
    return v, None if v else "empty"
