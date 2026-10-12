"""Name normalisation and similarity for duplicate cases (F-04.5) and party
attribution (F-10.3). Standard library only (difflib): python-Levenshtein
is excluded on licence grounds (CLAUDE.md rule 10)."""

from __future__ import annotations

import re
from dataclasses import dataclass
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



# --- A person's name in its parts (ID-09) ---

_PERSON_HONORIFICS = re.compile(r"\b(?:mr|mrs|ms|miss|shri|sri|smt|kumari|dr|late)\b\.?\s*", re.IGNORECASE)


@dataclass(frozen=True)
class NameParts:
    """A person's name as written, honorifics removed: the first word, the words between and the
    last word. A single word is a first name only."""

    first: str | None
    middle: tuple[str, ...]
    last: str | None

    def words(self) -> list[str]:
        return [w for w in (self.first, *self.middle, self.last) if w]


def name_parts(name: str | None) -> NameParts:
    """"Shri Tarun S. Velankar" -> first "Tarun", middle ("S.",), last "Velankar"."""
    words = [w.strip(",;") for w in _PERSON_HONORIFICS.sub(" ", name or "").split()]
    words = [w for w in words if _key(w)]
    if not words:
        return NameParts(None, (), None)
    if len(words) == 1:
        return NameParts(words[0], (), None)
    return NameParts(words[0], tuple(words[1:-1]), words[-1])


def _key(word: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def _word_status(a: str | None, b: str | None) -> str | None:
    """One part of two names: same, missing (in one), initial (one gives only the other's first
    letter) or different; None where neither has it."""
    ka, kb = _key(a), _key(b)
    if not ka and not kb:
        return None
    if not ka or not kb:
        return "missing"
    if ka == kb:
        return "same"
    if (len(ka) == 1 and kb.startswith(ka)) or (len(kb) == 1 and ka.startswith(kb)):
        return "initial"
    return "different"


def _middle_status(a: tuple[str, ...], b: tuple[str, ...]) -> str | None:
    if not a and not b:
        return None
    if not a or not b:
        return "missing"
    if len(a) != len(b):
        return "different"
    statuses = [_word_status(x, y) for x, y in zip(a, b)]
    if all(s == "same" for s in statuses):
        return "same"
    return "initial" if all(s in ("same", "initial") for s in statuses) else "different"


def compare_name_parts(a: str | None, b: str | None) -> dict[str, str | None]:
    """How name b's first, middle and last names stand against name a's: same, missing, initial or
    different, None where neither has the part. The order of the words is not a difference
    ("Velankar Tarun" is "Tarun Velankar"), and a surname written first is read as the surname."""
    pa, pb = name_parts(a), name_parts(b)
    words_a, words_b = sorted(_key(w) for w in pa.words()), sorted(_key(w) for w in pb.words())
    if words_a and words_a == words_b:
        return {"first": "same", "middle": "same" if pa.middle else None, "last": "same" if pa.last else None}
    first_b, last_b = pb.first, pb.last
    if (pa.last and pb.last and _word_status(pa.last, pb.first) == "same"
            and _word_status(pa.first, pb.last) in ("same", "initial")):
        first_b, last_b = pb.last, pb.first
    return {"first": _word_status(pa.first, first_b), "middle": _middle_status(pa.middle, pb.middle),
            "last": _word_status(pa.last, last_b)}


def same_by_parts(a: str | None, b: str | None) -> bool:
    """Whether two names can be one person by their parts, where similarity alone may not say so:
    the same surname and a first name that is the same or the other's initial ("T. Velankar" and
    "Tarun Velankar")."""
    pa, pb = name_parts(a), name_parts(b)
    if not (pa.first and pa.last and pb.first and pb.last):
        return False
    return _word_status(pa.last, pb.last) == "same" and _word_status(pa.first, pb.first) in ("same", "initial")
