"""Indian identifier formats: validation and construction.

Only GSTIN has a public checksum (implemented and enforced here). PAN, CIN,
Udyam, DIN, IFSC, TAN and UDIN have no public check algorithm — format and
internal-consistency checks are as far as code can go. Invalid identifiers
are flagged, never corrected (docs/functional-requirements.md F-04.4, F-15).
"""

from __future__ import annotations

import re

_GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# PAN 4th character by constitution/holder type.
PAN_FOURTH_CHAR = {
    "individual": "P",
    "company": "C",
    "huf": "H",
    "firm": "F",
    "llp": "F",
    "aop": "A",
    "trust": "T",
    "boi": "B",
    "local_authority": "L",
    "artificial_juridical_person": "J",
    "government": "G",
}

_PAN_RE = re.compile(r"^[A-Z]{3}[ABCFGHJLPT][A-Z][0-9]{4}[A-Z]$")
_CIN_RE = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
_UDYAM_RE = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$")
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_TAN_RE = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
_DIN_RE = re.compile(r"^[0-9]{8}$")
_ITR_ACK_RE = re.compile(r"^[0-9]{15}$")
_UDIN_RE = re.compile(r"^[0-9]{8}[A-Z0-9]{10}$")


class IdentifierError(ValueError):
    pass


def gstin_check_digit(first14: str) -> str:
    """The GSTIN check character (position 15), computed over positions 1-14."""
    if len(first14) != 14:
        raise IdentifierError(f"expected 14 characters, got {len(first14)!r}")
    total = 0
    for i, ch in enumerate(first14):
        if ch not in _GSTIN_ALPHABET:
            raise IdentifierError(f"character {ch!r} is not valid in a GSTIN")
        p = _GSTIN_ALPHABET.index(ch) * (1 + i % 2)
        total += p // 36 + p % 36
    return _GSTIN_ALPHABET[(36 - total % 36) % 36]


def build_gstin(state_code: str, pan: str, entity_number: str = "1") -> str:
    """Construct a checksum-valid GSTIN. Does not check PAN/state-code existence."""
    if not validate_pan_format(pan):
        raise IdentifierError(f"{pan!r} is not a validly formatted PAN")
    if not re.fullmatch(r"[0-9]{2}", state_code):
        raise IdentifierError(f"state_code must be two digits, got {state_code!r}")
    if entity_number not in _GSTIN_ALPHABET or entity_number == "0":
        raise IdentifierError(f"entity_number must be one of {_GSTIN_ALPHABET[1:]!r}")
    first14 = f"{state_code}{pan}{entity_number}Z"
    return first14 + gstin_check_digit(first14)


def validate_gstin(gstin: str) -> bool:
    if not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", gstin):
        return False
    return gstin_check_digit(gstin[:14]) == gstin[14]


def validate_pan_format(pan: str) -> bool:
    return bool(_PAN_RE.fullmatch(pan))


def validate_pan(pan: str, holder_type: str | None = None) -> bool:
    if not validate_pan_format(pan):
        return False
    if holder_type is not None:
        expected = PAN_FOURTH_CHAR.get(holder_type)
        if expected is None:
            raise IdentifierError(f"unknown holder_type {holder_type!r}")
        if pan[3] != expected:
            return False
    return True


def validate_cin(cin: str, *, formed_year: int | None = None, roc: str | None = None) -> bool:
    # U 17291 TZ 2016 PTC 027431 -> [0]=U/L, [1:6]=NIC, [6:8]=ROC, [8:12]=year, [12:15]=type, [15:21]=serial
    if not _CIN_RE.fullmatch(cin):
        return False
    if formed_year is not None and cin[8:12] != str(formed_year):
        return False
    if roc is not None and cin[6:8] != roc:
        return False
    return True


def validate_udyam(udyam: str) -> bool:
    return bool(_UDYAM_RE.fullmatch(udyam))


def validate_ifsc(ifsc: str) -> bool:
    return bool(_IFSC_RE.fullmatch(ifsc))


def validate_tan(tan: str) -> bool:
    return bool(_TAN_RE.fullmatch(tan))


def validate_din(din: str) -> bool:
    return bool(_DIN_RE.fullmatch(din))


def validate_itr_ack(ack: str) -> bool:
    return bool(_ITR_ACK_RE.fullmatch(ack))


def validate_udin(udin: str) -> bool:
    return bool(_UDIN_RE.fullmatch(udin))
