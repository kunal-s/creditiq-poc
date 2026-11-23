"""Identifier formats and checksums (FRD F-15.2). Masked identifiers are valid as masked and are
never expanded."""

from __future__ import annotations

import re

PATTERNS: dict[str, str] = {
    "pan": r"\b[A-Z]{5}\d{4}[A-Z]\b",
    "gstin": r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
    "cin": r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b",
    "ifsc": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "din": r"\b\d{8}\b",
    "tan": r"\b[A-Z]{4}\d{5}[A-Z]\b",
    "udin": r"\b\d{8}[A-Z0-9]{10}\b",
    "masked_pan": r"\b[A-Z][X*]{4}\d{4}[A-Z]\b",
    "masked_aadhaar": r"(?:\b[X*]{4}\s?){2}\d{4}\b",
}

_ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum_ok(g: str) -> bool:
    if len(g) != 15:
        return False
    total = 0
    for i, ch in enumerate(g[:14]):
        if ch not in _ALPHA:
            return False
        v = _ALPHA.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return _ALPHA[(36 - total % 36) % 36] == g[14]


def check(kind: str, value: str) -> tuple[bool, str]:
    """(ok, detail). `checksum_fail` is True only for a well-formed value whose check digit is wrong."""
    rx = PATTERNS.get(kind)
    if rx is None:
        return True, f"no format defined for {kind}"
    v = value.strip()
    if not re.fullmatch(rx.replace(r"\b", ""), v):
        return False, f'"{v}" is not in the {kind.upper()} format'
    if kind == "gstin" and not gstin_checksum_ok(v):
        return False, f'"{v}" has the GSTIN format but its check digit is wrong'
    return True, f'"{v}" matches the {kind.upper()} format'


def find(kind: str, text: str) -> re.Match | None:
    return re.search(PATTERNS[kind], text)


# What each position of an identifier holds: A a letter, 9 a digit, ? either. A scan's confusion is undone only where
# the position says which it must be (a 0 where a letter belongs is an O).
SHAPES = {"pan": "AAAAA9999A", "gstin": "99AAAAA9999A?Z?"}


def corrected(kind: str, text: str, digit_as_letter: dict[str, str], letter_as_digit: dict[str, str],
              max_corrections: int, gstin_pans: set[str] | None = None) -> list[tuple[str, str]]:
    """(as printed, as corrected) for each value in `text` that is not in the format of `kind` as printed, but is once
    at most `max_corrections` characters a scan confuses are read as the position requires, and that a check then
    confirms: a GSTIN by its check digit, a PAN by being the PAN inside a GSTIN of the same document (`gstin_pans`).
    The map is used to find a value only; the value printed is what is kept (Story 2.6)."""
    shape = SHAPES.get(kind)
    if not shape:
        return []
    out = []
    for m in re.finditer(r"(?<![A-Za-z0-9])[A-Za-z0-9]{%d}(?![A-Za-z0-9])" % len(shape), text):
        printed = m.group(0)
        up = printed.upper()
        if re.fullmatch(PATTERNS[kind].replace(r"\b", ""), up):
            continue                     # in the format as printed: the ordinary scan reads it
        fixed, n = [], 0
        for ch, want in zip(up, shape):
            if want == "A" and ch.isdigit():
                ch, n = digit_as_letter.get(ch, ch), n + 1
            elif want == "9" and ch.isalpha():
                ch, n = letter_as_digit.get(ch, ch), n + 1
            elif want == "Z" and ch != "Z":
                ch, n = ("Z" if ch in letter_as_digit or ch == "2" else ch), n + 1
            fixed.append(ch)
        value = "".join(fixed)
        if n == 0 or n > max_corrections or not re.fullmatch(PATTERNS[kind].replace(r"\b", ""), value):
            continue
        if kind == "gstin" and not gstin_checksum_ok(value):
            continue
        if kind == "pan" and value not in (gstin_pans or set()):
            continue
        out.append((printed, value))
    return out
