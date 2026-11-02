"""A scan's text layer against the scan itself (F-07A, use case 2: TEXT_LAYER_MATCHES_PAGE).

A scanner, or the app that made the PDF, draws the text it recognised over the
page's picture — usually invisibly — so the file can be searched and copied. A
machine reads that text; a person reads the picture. When the two say different
things about the same number, the file states two values for it, and which one
a reader gets depends on how they read. Editing the picture after the text was
recognised does this, and so does editing the text layer of a genuine scan.

Every number and identifier the text layer prints is compared with what the
pixels show in the same place. Optical reading misreads, so nothing is said on
one reading, on a reading that is only the usual confusions (O for 0, I for 1,
S for 5), or on a page whose reading does not mostly agree with its text — then
it is not a reading of this page. A difference counts when a second reading of
that place alone agrees with the first.

Ported from RBL/fault_detection `textlayer.py` (PROVENANCE.md). Not ported: the
identifier-rule branch of `misread_by_form` (it needs the identifier rules) and
the ledger arithmetic (CreditIQ checks that after extraction). Confidence is
0–1 here (PaddleOCR), 0–100 in the source (Tesseract).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

__all__ = ["Disagreement", "TextLayerResult", "text_layer_versus_scan", "misread_by_form"]

_IDENTIFIER = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]{3}|[A-Z]{5}\d{4}[A-Z]|[A-Z]{4}0[A-Z0-9]{6}")
_CONFUSABLE = str.maketrans("OQDIL|SBZG", "0001115826")
_AMOUNT = re.compile(r"^-?\(?(?:\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\)?$")
_AMOUNTISH = re.compile(r"^-?\(?[\d,]+\.\d{1,2}\)?$")
_DATE = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2}|\d{4})$")


@dataclass(frozen=True, slots=True)
class Disagreement:
    """A place where the text layer gives one value and the scan shows another.
    `misreading` says why it is the scanner's own misreading of a genuine page,
    when its form alone can tell ("" when it cannot)."""

    page: int
    box: Any
    text_says: str
    page_shows: str
    misreading: str = ""


@dataclass(slots=True)
class TextLayerResult:
    """What comparing one page found. `applicable` is False when nothing could be
    compared, or the reading did not mostly agree with the text."""

    applicable: bool
    disagreements: list[Disagreement]
    compared: int = 0
    agreed: int = 0
    reason: str = ""


def _norm(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def _worth_comparing(text: str) -> bool:
    n = _norm(text)
    return sum(ch.isdigit() for ch in n) >= 4 or bool(_IDENTIFIER.fullmatch(n))


def _same(a: str, b: str) -> bool:
    return _norm(a) == _norm(b) or _norm(a).translate(_CONFUSABLE) == _norm(b).translate(_CONFUSABLE)


def _cut_short(a: str, b: str) -> bool:
    x, y = _norm(a), _norm(b)
    return bool(x) and bool(y) and x != y and (x in y or y in x)


def _beside(a, b) -> bool:
    ay, by = (a.bottom + a.top) / 2, (b.bottom + b.top) / 2
    return (abs(ay - by) <= 0.6 * max(a.top - a.bottom, b.top - b.bottom, 1.0)
            and a.left < b.right + 1.0 and b.left < a.right + 1.0)


def _well_formed_amount(text: str) -> bool:
    t = (text or "").strip()
    if not _AMOUNT.match(t):
        return False
    digits = t.lstrip("-(").split(".")[0].replace(",", "")
    return not (len(digits) > 1 and digits.startswith("0"))


def _valid_date(text: str) -> bool:
    m = _DATE.match((text or "").strip())
    if not m:
        return False
    day, month = int(m.group(1)), int(m.group(2))
    return 1 <= day <= 31 and 1 <= month <= 12


def misread_by_form(text_says: str, page_shows: str) -> str:
    """Why the text layer's value is a misreading by its form alone: not a
    well-formed value of the kind the page's value is. "" when its form cannot tell."""
    says, shows = (text_says or "").strip(), (page_shows or "").strip()
    if _AMOUNTISH.match(shows) and _well_formed_amount(shows) and not _well_formed_amount(says):
        return "the text layer's figure is not a well-formed amount where the page's is"
    if _DATE.match(shows) and _valid_date(shows) and not _valid_date(says):
        return "the text layer's date is not a date where the page's is"
    return ""


def text_layer_versus_scan(page: int, text_tokens, ocr_words, reread: Callable[[Any], tuple[str, float]], *,
                           confirm: float, min_agreement: float) -> TextLayerResult:
    """Tokens of the text layer the scan, read twice, shows differently. `text_tokens`
    and `ocr_words` have `.text`, `.box` (points, bottom-left origin) and, for the
    reading, `.confidence` (0–1); `reread(box)` reads one place again on its own."""
    candidates = [t for t in text_tokens if _worth_comparing(t.text)]
    if not candidates:
        return TextLayerResult(False, [], reason="its text layer gives no number or identifier to compare")
    agree, differ = 0, []
    for token in candidates:
        seen = sorted((w for w in ocr_words if _beside(w.box, token.box)), key=lambda w: w.box.left)
        if not seen:
            continue                      # nothing read there: say nothing, a reading can miss
        shown = "".join(w.text for w in seen)
        if _same(shown, token.text):
            agree += 1
            continue
        if _cut_short(shown, token.text) or min(w.confidence for w in seen) < confirm:
            continue
        place = token.box
        for w in seen:
            place = place.union(w.box)
        differ.append((token, shown, place))
    compared = agree + len(differ)
    if not compared:
        return TextLayerResult(False, [], reason="the scan could not be read where its text layer prints numbers")
    if agree / compared < min_agreement:
        return TextLayerResult(False, [], compared=compared, agreed=agree,
                               reason=f"the scan's reading agrees with only {agree} of {compared} of its text "
                                      f"layer's numbers, too few to compare them")
    out = []
    for token, shown, place in differ:
        again, sure = reread(place)
        if sure >= confirm and _same(again, shown) and not _same(again, token.text):
            out.append(Disagreement(page, place, token.text.strip(), shown.strip(),
                                    misread_by_form(token.text, shown)))
    return TextLayerResult(True, out, compared=compared, agreed=agree)
