"""Where a model's value is printed on a line (Story 6.6): the model may write a value in another form than the page
does ("123456" for "1,23,456", "2024-03-31" for "31 March 2024", a dropped hyphen in a name), so a value is matched
to its line by what it is (the same number with the same sign, the same date, or the same text within the configured
fuzzy ratio) and the text the page prints is what is kept. A value with no such match on the lines named is
rejected; nothing is matched against any other document."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from .normalise import _DATE_TOKENS, to_date, to_number

_FIGURE = re.compile(r"(?<![\w,.])\(?(?:[-−–]\s?)?(?:₹|Rs\.?\s?|INR\s?)?\d[\d,]*(?:\.\d+)?\)?(?:\s?(?:Dr|Cr)\.?\b)?", re.IGNORECASE)
_NUMERIC = re.compile(r"^\s*\(?[-−–]?\s?(?:₹|Rs\.?\s?|INR\s?)?\d[\d,\s]*(?:\.\d+)?\)?\s*(?:Dr|Cr)?\.?\s*$", re.IGNORECASE)


def find(raw: str, text: str, text_ratio: float) -> tuple[int, int] | None:
    """The span of `text` that prints `raw`, or None."""
    raw = str(raw or "").strip()
    if not raw or not text:
        return None
    low, needle = text.casefold(), re.sub(r"\s+", " ", raw).casefold()
    # As printed, whatever the spacing between its words.
    exact = re.search(r"\s+".join(map(re.escape, needle.split())), text, re.IGNORECASE)
    if exact:
        return exact.start(), exact.end()
    if _NUMERIC.match(raw):
        want = to_number(raw)
        if want is not None:
            for m in _FIGURE.finditer(text):
                if to_number(m.group(0).strip()) == want:
                    return m.start(), m.end()
        return None
    day = to_date(raw)
    if day is not None:
        for rx in _DATE_TOKENS:
            for m in re.finditer(rx, low):
                if to_date(m.group(0)) == day:
                    return m.start(), m.end()
        return (0, len(text)) if to_date(text) == day else None
    if len(needle) < 4:
        return None          # too short to tell a near match from a coincidence
    al = fuzz.partial_ratio_alignment(needle, low)
    if al is not None and al.score >= text_ratio:
        a, b = al.dest_start, al.dest_end
        while a > 0 and text[a - 1].isalnum():          # widen to whole words: the text as printed
            a -= 1
        while b < len(text) and text[b].isalnum():
            b += 1
        return a, b
    return None
