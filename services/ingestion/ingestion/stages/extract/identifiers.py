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
