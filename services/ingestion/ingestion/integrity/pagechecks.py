"""The integrity checks that read the page (F-07A, phase 2).

The phase-1 checks answer from the file's records. These answer from what each
page draws: a block painted over printed text, a picture pasted over it, text
too small or drawn invisibly, text placed off the page, a figure set in two
typefaces, a figure off its line. Every finding points at a place on a page, so
a reader is shown the spot rather than told about it.

A page read by OCR is a picture of a page: it has no text of its own to compare,
so these checks say so for it rather than pass it.

Deterministic; thresholds in `config/ingestion/integrity.yaml` under `page`.
Ported from RBL/fault_detection `pdfdoc.py` (covered text, images),
`integrity.py` (hidden text), `pipeline._hidden_text` (outside the page),
`typography.py` and `inventory._positions` (PROVENANCE.md).
"""

from __future__ import annotations

import re
from statistics import median
from typing import Any

from dataclasses import dataclass, field

from ..contracts import IntegrityEvidence, IntegrityFigure, IntegrityFinding
from .pagedoc import PICTURE_PAGE_COVERAGE, Box, Char, PageDoc, union
from .spec import method

__all__ = ["PAGE_CHECKS", "PageReading", "page_checks", "read_pages"]

#: The page checks, in the order they are listed.
PAGE_CHECKS = ("PDF_COVERED_TEXT", "PDF_PICTURE_OVER_TEXT", "HIDDEN_TEXT", "PDF_TEXT_OUTSIDE_VISIBLE_AREA",
               "FONT_WITHIN_VALUE", "PDF_FIGURE_TYPESET_DIFFERENTLY", "LAYOUT_OFF_LINE")

#: The most figures kept for a file, for a reader to see where each was read.
MAX_FIGURES = 4000

#: An amount as a column of figures prints it: 1,23,456.00, (450.00), 12,345.
_AMOUNT = re.compile(r"^\(?-?\d[\d,]*\.\d{1,2}\)?$|^\(?-?\d{1,3}(?:,\d{2,3})+\)?$")

#: The most marks one check puts on the pages: past this, the page is set that way.
MAX_EVIDENCE = 20

#: A value: a token of three or more characters with a digit in it.
_VALUE = re.compile(r"(?=.*\d)[\w.,/:-]{3,}")

#: Characters whose glyphs reach below the baseline, left out of a baseline.
_DESCENDERS = set("gjpqyQ,;()[]{}|_/\\$@")

#: Font names a PDF writer makes up (F1, CIDFont+F2, TT3, T1_0): they name a font
#: object, not a typeface, so two of them say nothing about two typefaces.
_GENERIC = re.compile(r"^(cidfont\+)?(f|tt|t|c|font)\d+(_\d+)?$")


def _family(font: str) -> str | None:
    """The typeface family a font name gives, or None for a writer's placeholder."""
    name = re.sub(r"^[A-Z]{6}\+", "", font or "")
    if _GENERIC.match(name.lower()):
        return None
    name = re.split(r"[-,]", name)[0]
    return re.sub(r"(PSMT|MT|PS)$", "", name).lower() or None


def _short(text: str, n: int = 40) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


#: Stands in for a check the published configuration does not name, so the
#: result can be built and then left out (see read_pages).
_UNCONFIGURED = {"family": "layout", "tier": "T1", "impact": "low"}


def _result(cfg: dict, code: str, status: str, finding: str,
            evidence: list[IntegrityEvidence] | None = None, failed: bool = False) -> IntegrityFinding:
    spec = cfg["checks"].get(code, _UNCONFIGURED)
    return IntegrityFinding(
        code=code, family=spec["family"], status=status, finding=finding, evidence=evidence or [],
        tier=spec["tier"], impact=spec["impact"], context=bool(spec.get("context", False)),
        method=method(spec, cfg["version"], failed=failed),
        reads=["pages"])


def _ev(doc: PageDoc, index: int, box, observed: str, threshold: str) -> IntegrityEvidence:
    return IntegrityEvidence(page=index + 1, rect=doc.to_fractions(index, box), observed=observed,
                             threshold=threshold)


# --- each check over the pages of text ------------------------------------

def _tokens(chars: list[Char], word_gap_em: float) -> list[list[Char]]:
    """Tokens in reading order, split at white space and at a gap wider than
    `word_gap_em` of the type size beside a letter: many files draw the space
    between words by position and store no space character."""
    out: list[list[Char]] = []
    token: list[Char] = []
    for c in sorted(chars, key=lambda c: c.box.left) + [None]:  # type: ignore[list-item]
        gap = (c is not None and token and not c.text.isspace()
               and (c.text.isalpha() or token[-1].text.isalpha())
               and c.box.left - token[-1].box.right > word_gap_em * max(c.size or 0, token[-1].size or 0, 1.0))
        if c is None or c.text.isspace() or gap:
            if token:
                out.append(token)
            token = [c] if gap and c is not None else []
        else:
            token.append(c)
    return out


def _two_faces(doc: PageDoc, index: int, page, shown: list[Char], word_gap_em: float) -> list[tuple]:
    found = []
    for run in page.runs(shown):
        for token in _tokens(list(run.chars), word_gap_em):
            text = "".join(c.text for c in token)
            if not _VALUE.fullmatch(text):
                continue
            families = {_family(c.font) for c in token if c.text.isalnum()}
            if None not in families and len(families) > 1:
                found.append((index, union([c.box for c in token]), text, sorted(families)))  # type: ignore[arg-type]
    return found


def _is_credit(text: str, credits: list[str]) -> bool:
    """Whether invisible text is only a writing program's credit line, such as
    TCPDF's "Powered by TCPDF (www.tcpdf.org)" on every file it makes."""
    flat = re.sub(r"[^a-z0-9]", "", text.lower())
    return bool(flat) and any(c in flat for c in credits)


def _font_name(font: str) -> str:
    """A font's name as a reader would say it: without the subset prefix."""
    return re.sub(r"^[A-Z]{6}\+", "", font or "") or "unnamed"


def _figures(doc: PageDoc, index: int, page, shown: list[Char], word_gap_em: float) -> list[IntegrityFigure]:
    """Every value the page prints, with its box, font and size; amounts are
    grouped into columns by their right edge (figures are set right-aligned)."""
    out: list[IntegrityFigure] = []
    for run in page.runs(shown):
        for token in _tokens(list(run.chars), word_gap_em):
            text = "".join(c.text for c in token)
            if not _VALUE.fullmatch(text):
                continue
            box = union([c.box for c in token])
            digits = [c for c in token if c.text.isdigit()] or token
            fonts = [c.font for c in digits]
            font = max(set(fonts), key=fonts.count)
            out.append(IntegrityFigure(page=index + 1, rect=doc.to_fractions(index, box), text=text,
                                       font=_font_name(font), size=round(median(c.size for c in digits), 1),
                                       right=round(box.right, 1)))
    return out


def _columns(figures: list[IntegrityFigure], tolerance_pt: float) -> list[IntegrityFigure]:
    """The same figures with each amount given the column it is set in: the
    amounts on one page whose right edges line up within `tolerance_pt`."""
    by_page: dict[int, list[int]] = {}
    for i, f in enumerate(figures):
        if _AMOUNT.match(f.text):
            by_page.setdefault(f.page, []).append(i)
    column: dict[int, int] = {}
    for page, idx in by_page.items():
        idx.sort(key=lambda i: figures[i].right)
        n, start = 0, None
        for i in idx:
            if start is None or figures[i].right - start > tolerance_pt:
                n, start = n + 1, figures[i].right
            column[i] = n
    return [f.model_copy(update={"column": column.get(i)}) for i, f in enumerate(figures)]


def _typeset_apart(figures: list[IntegrityFigure], t: dict) -> list[tuple[IntegrityFigure, str, float, int]]:
    """Amounts set in another typeface or size from the rest of their column:
    (the figure, the column's family, its size, how many it holds)."""
    columns: dict[tuple[int, int], list[IntegrityFigure]] = {}
    for f in figures:
        if f.column is not None:
            columns.setdefault((f.page, f.column), []).append(f)
    out = []
    for members in columns.values():
        if len(members) < t["column_min_values"]:
            continue
        styles = [(_family(f.font), f.size) for f in members]
        common = max(set(styles), key=styles.count)
        if styles.count(common) / len(styles) < t["column_majority"]:
            continue                    # a column set two ways throughout is its design
        family, size = common
        for f, (fam, sz) in zip(members, styles):
            other_face = fam is not None and family is not None and fam != family
            other_size = abs(sz - size) > t["column_size_tol_pt"]
            if other_face or other_size:
                out.append((f, next(m.font for m, st in zip(members, styles) if st == common), size, len(members)))
    return out


def _off_line(page, index: int, shown: list[Char], t: dict) -> tuple[list[tuple], int, int]:
    """Values whose baseline is off their line's, and how many lines were
    measured. A line is the runs that overlap vertically and share a type size;
    its baseline is the median of its runs'. A superscript (smaller type raised)
    and a run on another line are left out."""
    measured = []
    for run in page.runs(shown):
        base = [c.box.bottom for c in run.chars if c.text not in _DESCENDERS and c.text.isalnum()]
        if not base:
            continue
        measured.append({"run": run, "base": median(base), "size": median(c.size for c in run.chars),
                         "mid": (run.box.bottom + run.box.top) / 2})
    measured.sort(key=lambda m: -m["mid"])
    lines: list[list[dict]] = []
    for m in measured:
        for line in lines:
            ref = line[0]
            if abs(m["mid"] - ref["mid"]) <= 0.45 * max(ref["size"], m["size"]) and abs(m["size"] - ref["size"]) <= 0.6:
                line.append(m)
                break
        else:
            lines.append([m])
    off, words, count = [], 0, 0
    for line in lines:
        if len(line) < 2 or sum(sum(c.isalnum() for c in m["run"].text) == 1 for m in line) > len(line) / 2:
            continue
        count += 1
        centre = median(m["base"] for m in line)
        line_size = median(m["size"] for m in line)
        for m in line:
            text = m["run"].text.strip()
            if sum(c.isalnum() for c in text) < 2:
                continue
            delta = m["base"] - centre
            if abs(delta) < t["baseline_tol_pt"] or abs(delta) > t["max_offset_line_ratio"] * line_size:
                continue
            if line_size and m["size"] / line_size <= t["superscript_size_ratio"]:
                continue
            if _VALUE.fullmatch(text):
                off.append((index, m["run"].box, text, round(delta, 2)))
            else:
                words += 1
    return off, words, count


@dataclass
class PageReading:
    """The page checks' results, and every figure the pages print."""

    findings: list[IntegrityFinding]
    figures: list[IntegrityFigure] = field(default_factory=list)


def page_checks(data: bytes, cfg: dict[str, Any], scanned: set[int] | None = None) -> list[IntegrityFinding]:
    """Every page check, over the pages that carry their own text."""
    return read_pages(data, cfg, scanned).findings


def read_pages(data: bytes, cfg: dict[str, Any], scanned: set[int] | None = None) -> PageReading:
    """Every page check the configuration names, over the pages that carry
    their own text, and the figures those pages print.

    `scanned` is the 1-based pages read by OCR: a picture of a page has no text
    of its own, so it is left out and the finding says so. A check the published
    configuration does not name is not run: configuration governs what runs, and
    a configuration published before a check existed must not fail the file.
    """
    reading = _read_pages(data, cfg, scanned)
    # Not run, and said so: a check this code has but the published configuration
    # does not name is reported as not run, so the file is never taken as fully
    # checked when it was checked against an older configuration.
    reading.findings = [f if f.code in cfg["checks"] else _not_configured(cfg, f.code) for f in reading.findings]
    return reading


def _not_configured(cfg: dict, code: str) -> IntegrityFinding:
    return IntegrityFinding(
        code=code, family="layout", status="unable_to_determine", tier="T1", impact="low", context=True,
        finding="Not run: this check is not in the published configuration. Publish the configuration, "
                "then run the remaining checks.",
        method={**method({}, cfg["version"]), "not_configured": "true"}, reads=["pages"])


def _read_pages(data: bytes, cfg: dict[str, Any], scanned: set[int] | None) -> PageReading:
    t = cfg["page"]
    figures: list[IntegrityFigure] = []
    scanned = scanned or set()
    covered, pictures, tiny, invisible, outside, faces, off = [], [], [], [], [], [], []
    marks: list[tuple[int, Box]] = []
    words_off = lines = credits = 0
    looked = 0
    fonts_seen = False
    try:
        with PageDoc(data) as doc:
            for index in range(min(len(doc), t["max_pages"])):
                page = doc.page(index)
                # A scanner draws the text it recognised invisibly over its picture so the
                # file can be searched: on a picture page that is the scan's reading.
                picture_page = min(1.0, sum(f for _, _, f in page.pictures)) >= PICTURE_PAGE_COVERAGE
                if index + 1 in scanned or not page.chars or picture_page:
                    # A page with no text of its own can still have something drawn over its picture.
                    marks += [(index, box) for box in doc.dark_marks(index, page)]
                if index + 1 in scanned or not page.chars:
                    continue
                looked += 1
                fonts_seen = fonts_seen or any(c.font for c in page.chars)
                for c in [*page.covered(), *page.annotations_over_text()]:
                    covered.append((index, c))
                for p in page.pictures_over_text():
                    if p.under and p.fraction <= t["picture_max_page_fraction"] and \
                            sum(ch.isalnum() for ch in p.under) >= t["picture_min_chars_under"]:
                        pictures.append((index, p))
                small = [c for c in page.chars if c.visible and c.text.strip() and 0 < c.size < t["tiny_pt"]]
                if small:
                    tiny.append((index, union([c.box for c in small]), "".join(c.text for c in small)))
                unseen = [] if picture_page else [c for c in page.chars if not c.visible and c.text.strip()]
                for run in page.runs(unseen) if unseen else []:
                    if _is_credit(run.text, t["writer_credits"]):
                        credits += 1            # the writing program signing its own work
                    else:
                        invisible.append((index, run.box, run.text))
                shown = page.shown_chars()
                for run in page.runs(shown):
                    x0, y0, x1, y1 = doc.to_fractions(index, run.box)
                    if x1 < 0 or y1 < 0 or x0 > 1 or y0 > 1:
                        outside.append((index, run.box, run.text))
                faces += _two_faces(doc, index, page, shown, t["word_gap_em"])
                if len(figures) < MAX_FIGURES:
                    figures += _figures(doc, index, page, shown, t["word_gap_em"])[: MAX_FIGURES - len(figures)]
                o, w, n = _off_line(page, index, shown, t)
                off += o
                words_off += w
                lines += n

            figures = _columns(figures, t["column_tolerance_pt"])
            apart = _typeset_apart(figures, t)
            evidence = {
                "covered": [_ev(doc, i, c.cover, f"{'a block' if c.by == 'block' else f'an annotation ({c.by})'} "
                                f"lies over “{_short(c.hidden)}”"
                                + (f"; “{_short(c.shown)}” is printed on it" if c.shown else ""),
                                "nothing laid over printed text") for i, c in covered[:MAX_EVIDENCE]]
                + [_ev(doc, i, b, f"a solid dark mark ({b.width:.0f} × {b.height:.0f} pt) is drawn over the page's "
                                  f"picture", "nothing drawn over the page's picture")
                   for i, b in marks[:MAX_EVIDENCE]],
                "pictures": [_ev(doc, i, p.box, f"a picture ({p.fraction:.2%} of the page) lies over "
                                 f"“{_short(p.under or '')}”", "a picture painted over printed text")
                             for i, p in pictures[:MAX_EVIDENCE]],
                "hidden": [_ev(doc, i, b, f"type under {t['tiny_pt']} pt: “{_short(x)}”", f"type of {t['tiny_pt']} pt or more")
                           for i, b, x in tiny[:MAX_EVIDENCE]]
                + [_ev(doc, i, b, f"drawn invisibly: “{_short(x)}”", "text drawn so that it shows")
                   for i, b, x in invisible[:MAX_EVIDENCE]],
                "outside": [IntegrityEvidence(page=i + 1, rect=None, observed=f"off the page: “{_short(x)}”",
                                              threshold="text inside the page's visible area")
                            for i, _, x in outside[:MAX_EVIDENCE]],
                "faces": [_ev(doc, i, b, f"“{x}” in {' and '.join(f)}", "one typeface within a value")
                          for i, b, x, f in faces[:MAX_EVIDENCE]],
                "off": [_ev(doc, i, b, f"“{x}” {d:+.2f} pt off its line", f"within {t['baseline_tol_pt']} pt of its line")
                        for i, b, x, d in off[:MAX_EVIDENCE]],
                "apart": [IntegrityEvidence(page=f.page, rect=f.rect,
                                            observed=f"“{f.text}” is set in {f.font} {f.size:g} pt; the other {n - 1} "
                                                     f"figures in its column in {font} {size:g} pt",
                                            threshold=f"the typeface and size of its column, within "
                                                      f"{t['column_size_tol_pt']} pt")
                          for f, font, size, n in apart[:MAX_EVIDENCE]],
            }
    except Exception as e:  # noqa: BLE001 - a page that cannot be read is said so, never passed
        return PageReading([_result(cfg, code, "unable_to_determine", f"The pages could not be read: {type(e).__name__}.",
                                    failed=True) for code in PAGE_CHECKS])

    marked = (f"{len(marks)} solid dark mark{'s are' if len(marks) != 1 else ' is'} drawn over the page's picture: "
              f"what lies beneath cannot be read from the file.")
    if not looked:
        why = ("Every page is a picture of the page, read by OCR: it has no text of its own to check."
               if scanned else "No page carries text to check.")
        return PageReading([_result(cfg, code, "review_required", marked, evidence["covered"])
                            if code == "PDF_COVERED_TEXT" and marks else _result(cfg, code, "not_applicable", why)
                            for code in PAGE_CHECKS])

    pages_note = f"{looked} page{'s' if looked != 1 else ''} of text"
    out = []
    if covered or marks:
        out.append(_result(cfg, "PDF_COVERED_TEXT", "review_required",
                           (f"{len(covered)} block{'s' if len(covered) != 1 else ''} or annotation"
                            f"{'s' if len(covered) != 1 else ''} laid over printed text "
                            f"hide{'s' if len(covered) == 1 else ''} it from a reader; the file still holds the text "
                            f"underneath." if covered else "") + (" " if covered and marks else "")
                           + (marked if marks else ""), evidence["covered"]))
    else:
        out.append(_result(cfg, "PDF_COVERED_TEXT", "pass",
                           f"No opaque block is painted over printed text on the {pages_note}."))
    if pictures:
        out.append(_result(cfg, "PDF_PICTURE_OVER_TEXT", "warning",
                           f"{len(pictures)} picture{'s lie' if len(pictures) != 1 else ' lies'} over printed text: what a "
                           f"reader sees there is the picture, not the text the file holds.", evidence["pictures"]))
    else:
        out.append(_result(cfg, "PDF_PICTURE_OVER_TEXT", "pass",
                           f"No small picture lies over printed text on the {pages_note}."))
    if tiny or invisible:
        out.append(_result(cfg, "HIDDEN_TEXT", "warning",
                           "The file holds text a machine reads and a person cannot see: "
                           + "; ".join(([f"type under {t['tiny_pt']} pt"] if tiny else [])
                                       + (["text drawn invisibly on a page of text"] if invisible else [])) + ".",
                           evidence["hidden"]))
    else:
        credit = (f" ({credits} invisible line{'s' if credits != 1 else ''} the writing program adds to every file "
                  f"it makes, naming itself, left out)") if credits else ""
        out.append(_result(cfg, "HIDDEN_TEXT", "pass", f"No tiny or invisible text on the {pages_note}{credit}."))
    if outside:
        out.append(_result(cfg, "PDF_TEXT_OUTSIDE_VISIBLE_AREA", "warning",
                           f"{len(outside)} run{'s' if len(outside) != 1 else ''} of text sit outside the area the "
                           f"page shows: in the file, but not on the page as it is read or printed.",
                           evidence["outside"]))
    else:
        out.append(_result(cfg, "PDF_TEXT_OUTSIDE_VISIBLE_AREA", "pass",
                           "Every run of text falls inside the area its page shows."))
    if not fonts_seen:
        out.append(_result(cfg, "FONT_WITHIN_VALUE", "not_applicable", "The file names no font to compare."))
    elif faces:
        out.append(_result(cfg, "FONT_WITHIN_VALUE", "warning",
                           f"{len(faces)} value{'s are' if len(faces) != 1 else ' is'} set in two typefaces at once.",
                           evidence["faces"]))
    else:
        out.append(_result(cfg, "FONT_WITHIN_VALUE", "pass", "Every value is set in one typeface throughout."))
    columns = {(f.page, f.column) for f in figures if f.column is not None}
    measured = [c for c in columns if sum(1 for f in figures if (f.page, f.column) == c) >= t["column_min_values"]]
    if not measured:
        out.append(_result(cfg, "PDF_FIGURE_TYPESET_DIFFERENTLY", "not_applicable",
                           f"No column of {t['column_min_values']} or more figures to compare."))
    elif apart:
        out.append(_result(cfg, "PDF_FIGURE_TYPESET_DIFFERENTLY", "warning",
                           f"{len(apart)} figure{'s are' if len(apart) != 1 else ' is'} set in another typeface or "
                           f"size from the rest of {'their columns' if len(apart) != 1 else 'its column'}.",
                           evidence["apart"]))
    else:
        out.append(_result(cfg, "PDF_FIGURE_TYPESET_DIFFERENTLY", "pass",
                           f"{len(measured)} column{'s' if len(measured) != 1 else ''} of figures measured; every "
                           f"figure is set in its column's typeface and size."))
    if not lines:
        out.append(_result(cfg, "LAYOUT_OFF_LINE", "not_applicable", "No line with more than one run to measure."))
    elif off and words_off > max(t["layout_style_min"], t["layout_style_ratio"] * len(off)):
        out.append(_result(cfg, "LAYOUT_OFF_LINE", "pass",
                           f"{len(off)} value(s) and {words_off} other run(s) sit off their lines: the document is "
                           f"set off its baselines throughout, so no value stands out."))
    elif off:
        out.append(_result(cfg, "LAYOUT_OFF_LINE", "warning",
                           f"{len(off)} value{'s sit' if len(off) != 1 else ' sits'} off {'their' if len(off) != 1 else 'its'} "
                           f"line by {t['baseline_tol_pt']} pt or more.", evidence["off"]))
    else:
        out.append(_result(cfg, "LAYOUT_OFF_LINE", "pass",
                           f"{lines} line(s) measured; no value sits off its line by {t['baseline_tol_pt']} pt or more."))
    return PageReading(out, figures)
