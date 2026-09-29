"""Name normalisation and similarity for duplicate cases (F-04.5) and party
attribution (F-10.3). Standard library only (difflib): python-Levenshtein
is excluded on licence grounds (CLAUDE.md rule 10)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_HONORIFICS = r"\b(?:mr|mrs|ms|miss|shri|sri|smt|kumari|dr|m/s|messrs)\b\.?"
_SUFFIXES = [
    (r"\bprivate\s+limited\b", "pvt ltd"),
    (r"\bpvt\.?\s*ltd\.?", "pvt ltd"),
    (r"\(p\)\s*ltd\.?", "pvt ltd"),
    (r"\blimited\b", "ltd"),
    (r"\bltd\.", "ltd"),
    (r"\s&\s", " and "),
]


def normalise_name(name: str | None) -> str:
    """Lower case, honorifics and punctuation removed, company suffixes in
    one form: "M/s. Kestrel Fabricators Private Limited" -> "kestrel fabricators pvt ltd"."""
    if not name:
        return ""
    text = name.lower()
    text = re.sub(_HONORIFICS, " ", text)
    for pattern, repl in _SUFFIXES:
        text = re.sub(pattern, repl, text)
    text = re.sub(r"[^a-z0-9& ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str | None, b: str | None) -> float:
    """0 to 1: the better of the character ratio and the ratio with the
    words sorted (so "Velankar Tarun" matches "Tarun Velankar")."""
    na, nb = normalise_name(a), normalise_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    direct = SequenceMatcher(None, na, nb).ratio()
    tokens = SequenceMatcher(None, " ".join(sorted(na.split())), " ".join(sorted(nb.split()))).ratio()
    return max(direct, tokens)


def tokens(text: str | None) -> list[str]:
    return normalise_name(text).split()
