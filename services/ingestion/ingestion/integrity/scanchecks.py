"""The integrity checks that read a scan (F-07A, use case 2).

Use case 1 reads a file's records and the text it draws. A scan or a photo keeps
neither: what it says is in its pixels and in where its words sit. These checks
read those, on every page that is a picture of a page — a PDF page read by OCR,
a searchable scan (a picture with a text layer), and every frame of an image
upload:

  VISUAL_REGIONS_INCONSISTENT  a text region with another grain or sharpness (listed only)
  IMG_VALUE_IN_LINE            a value off its label's or row's line
  TEXT_LAYER_MATCHES_PAGE      a searchable scan whose text says another number than its picture
  PDF_FIGURE_IS_PICTURE        a small picture carrying a figure, pasted over a scan or in place of text
  PAGES_SAME_ORIGIN            a page made differently from the rest
  IMG_PAGE_ORIGIN              how each page picture was made (listed only)

Every check answers on every file, so the engine never takes a missing answer for
a pass. Thresholds in `config/ingestion/integrity.yaml` under `scan`. OCR runs only
where the read stage did not already read the pixels (a searchable scan, a small
picture), through the service's engine and cache, so a replay reads the same.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

from ..contracts import IntegrityEvidence, IntegrityFinding
from ..pageindex import Page
from ..util import sha256_hex
from . import capture as cap
from . import typestyle as ts
from .alignment import misplaced_in_rows, misplaced_on_form
from .pagedoc import PICTURE_PAGE_COVERAGE, Box, PageDoc
from .regions import odd_regions, page_has_grain
from .spec import method
from .textlayer import text_layer_versus_scan

__all__ = ["SCAN_CHECKS", "scan_checks", "scan_reading"]

SCAN_CHECKS = ("VISUAL_REGIONS_INCONSISTENT", "IMG_VALUE_IN_LINE", "TEXT_LAYER_MATCHES_PAGE",
               "PDF_FIGURE_IS_PICTURE", "PAGES_SAME_ORIGIN", "IMG_TYPE_IN_COLUMN", "IMG_PAGE_ORIGIN")

#: Regions are measured at the resolution the source calibrated them at (2x a 72 dpi page).
REGIONS_DPI = 144.0
#: The most marks one check puts on the pages.
MAX_EVIDENCE = 20
#: A figure as a pasted picture shows: an amount with paise, or a date.
_AMOUNT_OR_DATE = re.compile(r"\d[\d,]*\.\d{2}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}")
_AMOUNTISH = re.compile(r"\d[\d,.]*\d")


@dataclass(slots=True)
class _Placed:
    """A word or run with a box in points, origin at the bottom left (the source's frame)."""

    text: str
    box: Box
    confidence: float = 1.0


@dataclass(slots=True)
class _Picture:
    """One picture page: its pixels, where they lie, how they were drawn, its words."""

    no: int
    image: Any
    placed: Box
    dpi: float
    width: float
    height: float
    words: list
    searchable: bool


def _result(cfg: dict, code: str, status: str, finding: str,
            evidence: list[IntegrityEvidence] | None = None, failed: bool = False) -> IntegrityFinding:
    spec = cfg["checks"][code]
    return IntegrityFinding(code=code, family=spec["family"], status=status, finding=finding,
                            evidence=evidence or [], tier=spec["tier"], impact=spec["impact"],
                            context=bool(spec.get("context", False)),
                            method=method(spec, cfg["version"], failed=failed), reads=["pages"])


def _frac(p: _Picture, box: Box) -> tuple[float, float, float, float]:
    """A box in points (bottom-left origin) as fractions of the page, top-left origin."""
    clamp = lambda v: round(min(max(v, 0.0), 1.0), 4)  # noqa: E731
    return (clamp(box.left / p.width), clamp((p.height - box.top) / p.height),
            clamp(box.right / p.width), clamp((p.height - box.bottom) / p.height))


def _image_frac(p: _Picture, rect) -> tuple[float, float, float, float]:
    """A rectangle in fractions of the picture as fractions of the page."""
    l, t, r, b = rect
    pw, ph = p.placed.width, p.placed.height
    left, top = p.placed.left, p.height - p.placed.top
    return (round((left + l * pw) / p.width, 4), round((top + t * ph) / p.height, 4),
            round((left + r * pw) / p.width, 4), round((top + b * ph) / p.height, 4))


def _up(word, height: float) -> Box:
    """A word box (points, top-left origin) in the bottom-left frame."""
    return Box(word.x0, height - word.y1, word.x1, height - word.y0)


def _runs(page: Page) -> list[_Placed]:
    """The page's words grouped into runs: words of a line closer than a word height apart."""
    out: list[_Placed] = []
    for line in page.lines:
        words = sorted(line.words, key=lambda w: w.x0)
        group: list = []
        for w in words + [None]:  # type: ignore[list-item]
            gap = w is not None and group and (w.x0 - group[-1].x1) > max(4.0, 0.8 * (w.y1 - w.y0))
            if (w is None or gap) and group:
                box = _up(group[0], page.height)
                for g in group[1:]:
                    box = box.union(_up(g, page.height))
                out.append(_Placed(" ".join(g.text for g in group), box,
                                   min(g.conf for g in group)))
                group = []
            if w is not None:
                group.append(w)
    return out


def _tighten(p: _Picture, placed: list[_Placed], grey, paper: float) -> list[_Placed]:
    """Each box shrunk vertically to the rows of print inside it.

    An OCR engine returns a padded box around a line of text, its height varying
    with descenders and the detector's margin; where a value sits against its
    label is a few points, so it is measured on the print itself (what the source
    got from Tesseract's tight word boxes). A box with no print in it is kept."""
    px = p.dpi / 72.0
    ox, oy = p.placed.left, p.height - p.placed.top
    out = []
    for r in placed:
        top_px = (p.height - r.box.top - oy) * px
        bot_px = (p.height - r.box.bottom - oy) * px
        l_px, r_px = (r.box.left - ox) * px, (r.box.right - ox) * px
        y0, y1 = max(0, int(top_px)), min(grey.shape[0], int(bot_px) + 1)
        x0, x1 = max(0, int(l_px)), min(grey.shape[1], int(r_px) + 1)
        if y1 - y0 < 2 or x1 - x0 < 2:
            out.append(r)
            continue
        rows = (grey[y0:y1, x0:x1] < paper - 60).any(axis=1).nonzero()[0]
        if rows.size == 0:
            out.append(r)
            continue
        top = p.height - oy - (y0 + rows[0]) / px
        bottom = p.height - oy - (y0 + rows[-1] + 1) / px
        out.append(_Placed(r.text, Box(r.box.left, bottom, r.box.right, top), r.confidence))
    return out


def _ocr(image, dpi: float, ocr, cache) -> list:
    """The engine's reading of an image (cached by its pixels), words in points from its top left."""
    from ..pageindex import Word  # noqa: PLC0415

    buf = io.BytesIO()
    image.save(buf, "PNG")
    key = sha256_hex(f"integrity|{ocr.name}|{round(dpi)}|".encode() + buf.getvalue())
    hit = cache.get(key) if cache else None
    if hit:
        return [Word(*w) for w in hit["words"]]
    res = ocr.recognise(image, int(round(dpi)))
    if cache:
        cache.put(key, {"words": [[w.text, w.x0, w.y0, w.x1, w.y1, w.conf, None] for w in res.words],
                        "mean_conf": res.mean_conf})
    return res.words


def _pdf_pictures(data: bytes, pages: list[Page], t: dict) -> tuple[list[_Picture], dict[int, str], list[tuple]]:
    """The picture pages of a PDF (at most `max_pages`), every page's kind, and each
    picture page's small pictures (for PDF_FIGURE_IS_PICTURE)."""
    by_no = {p.no: p for p in pages}
    out, kinds, small = [], {}, []
    with PageDoc(data) as doc:
        for index in range(len(doc)):
            no = index + 1
            page = by_no.get(no)
            if page is not None and page.blank:
                continue
            share = doc.picture_share(index)
            is_picture = (page is not None and page.source == "ocr") or share >= PICTURE_PAGE_COVERAGE
            kinds[no] = "picture" if is_picture else "text"
            if not is_picture:
                # A page of text: a small picture with no text under it may stand in
                # place of a printed figure (what it shows is read below).
                if index < t["max_pages"]:
                    for pic in doc.page(index).pictures_over_text():
                        if pic.under is None and pic.fraction <= t["figure_picture"]["max_page_fraction"]:
                            small.append((no, index, pic.box, "text", doc.to_fractions(index, pic.box)))
                continue
            if len(out) >= t["max_pages"]:
                continue
            pic = doc.page_picture(index, t["render_dpi_max"])
            if pic is None:
                continue
            w, h = doc._doc[index].get_size()
            out.append(_Picture(no, pic.image, pic.placed, pic.dpi, w, h,
                                page.words if page else [], bool(page and page.source == "text_layer")))
            extent_w = pic.placed.width
            for box, fraction, dpi in doc.pictures(index):
                # Small, and narrower than the page picture: not one of a scan's strips.
                if fraction <= t["figure_picture"]["max_page_fraction"] and box.width < 0.6 * extent_w \
                        and dpi >= 40:
                    small.append((no, index, box, "picture", doc.to_fractions(index, box)))
    return out, kinds, small


def _image_pictures(data: bytes, pages: list[Page]) -> tuple[list[_Picture], dict[int, str]]:
    from PIL import Image, ImageSequence  # noqa: PLC0415

    by_no = {p.no: p for p in pages}
    out, kinds = [], {}
    with Image.open(io.BytesIO(data)) as im:
        for i, frame in enumerate(ImageSequence.Iterator(im), start=1):
            page = by_no.get(i)
            if page is None or page.blank or not page.width:
                continue
            img = frame.convert("RGB")
            dpi = img.width / (page.width / 72.0)
            kinds[i] = "picture"
            out.append(_Picture(i, img, Box(0.0, 0.0, page.width, page.height), dpi, page.width, page.height,
                                page.words, False))
    return out, kinds


def _read_figures(data: bytes, small: list[tuple], t: dict, ocr, cache) -> list[tuple]:
    """Small pictures that show a figure: on a scan, any number or identifier; on a
    page of text, an amount or a date (a logo carrying a phone number is not a
    figure the page prints). (page, rect, text read, where)."""
    figures: list[tuple] = []
    if not small or ocr is None:
        return figures
    with PageDoc(data) as doc:
        for no, index, box, where, rect in small[:MAX_EVIDENCE]:
            page = doc._doc[index]
            left, bottom, right, top = page.get_bbox()
            crop = (box.left - left, box.bottom - bottom, right - box.right, top - box.top)
            try:
                img = page.render(scale=300 / 72.0, crop=crop, draw_annots=False).to_pil().convert("RGB")
            except Exception:  # noqa: BLE001 - a picture that cannot be drawn is not read
                continue
            text = " ".join(w.text for w in _ocr(img, 300.0, ocr, cache))
            # One value, not a stamp or a seal with a sentence and a date in it: a
            # pasted figure reads as a few words at most, one carrying the digits.
            short = 0 < len(text.split()) <= t["figure_picture"]["max_words"]
            digits = any(sum(ch.isdigit() for ch in tok) >= t["figure_picture"]["min_digits"] for tok in text.split())
            if short and digits and (where == "picture" or _AMOUNT_OR_DATE.search(text)):
                figures.append((no, rect, text, where))
    return figures


def _figure_result(cfg: dict, kind: str, small: list[tuple], ocr, figures: list[tuple]) -> IntegrityFinding:
    code = "PDF_FIGURE_IS_PICTURE"
    if kind != "pdf":
        return _result(cfg, code, "not_applicable", "An image file is one picture; nothing is laid on it apart.")
    if not small:
        return _result(cfg, code, "pass", "No small picture lies on the pages apart from what they print.")
    if ocr is None:
        return _result(cfg, code, "not_applicable", "Optical reading is not set up, so the pictures could not be read.")
    if figures:
        return _result(cfg, code, "review_required",
                       f"{len(figures)} small picture(s) carry a figure the file holds no text for: pasted on a "
                       f"scan, or standing in place of printed text.",
                       [IntegrityEvidence(page=no, rect=rect,
                                          observed=(f"a separate picture on the scan showing “{text[:40]}”"
                                                    if where == "picture" else
                                                    f"a picture standing in place of printed text, showing "
                                                    f"“{text[:40]}”"),
                                          threshold="a figure is printed as text, or is part of the page's own picture")
                        for no, rect, text, where in figures[:MAX_EVIDENCE]])
    return _result(cfg, code, "pass", f"{len(small)} small picture(s) lie on the pages; none carries a figure.")


def _measure_words(p: _Picture, page: Page, grey, style: dict) -> list[ts.Measured]:
    """The page's legible words measured for weight and slant on its picture."""
    px = p.dpi / 72.0
    oy = p.height - p.placed.top
    to_points = lambda x, y: (p.placed.left + x / px, p.height - (oy + y / px))  # noqa: E731
    out: list[ts.Measured] = []
    for line in page.lines:
        for w in line.words:
            if len(out) >= style["max_words"]:
                return out
            if w.conf < style["min_confidence"] or sum(ch.isalnum() for ch in w.text) < 3:
                continue
            box = (int((w.x0 - p.placed.left) * px), int((w.y0 - oy) * px),
                   int((w.x1 - p.placed.left) * px) + 1, int((w.y1 - oy) * px) + 1)
            m = ts.measure(grey, p.no, w.text, box, to_points)
            if m is not None:
                m.rect = _frac(p, Box(m.left, m.bottom, m.right, m.top))
                out.append(m)
    return out


def _type_result(cfg: dict, measured: list[ts.Measured], style: dict) -> IntegrityFinding:
    code = "IMG_TYPE_IN_COLUMN"
    if not measured:
        return _result(cfg, code, "not_applicable", "No scanned page has enough legible words to measure its type.")
    usual, compared, odd = ts.odd_in_columns(
        measured, bold_ratio=style["bold_ratio"], italic_deg=style["italic_deg"], tol_pt=style["column_tol_pt"],
        column_min=style["column_min"], majority=style["column_majority"])
    if not compared:
        return _result(cfg, code, "not_applicable",
                       f"{len(measured)} words measured; no column of {style['column_min']} or more figures to compare.")
    if not odd:
        return _result(cfg, code, "pass", f"Every figure in the {compared} column(s) of figures on the scan is set "
                                          f"in its column's weight and slant.")
    threshold = (f"its column's weight and slant (bold at {style['bold_ratio']}× the usual stroke, italic at "
                 f"{style['italic_deg']:g}° or more)")
    return _result(cfg, code, "warning",
                   f"{len(odd)} figure(s) on the scan are set in another weight or slant than the rest of their column.",
                   [IntegrityEvidence(page=m.page, rect=m.rect,
                                      observed=f"“{m.text}” is {mine} where the other {n - 1} figures in its column "
                                               f"are {theirs} (stroke {m.ratio / usual:.2f}× the usual)",
                                      threshold=threshold)
                    for m, mine, theirs, n in odd[:MAX_EVIDENCE]])


def scan_checks(data: bytes, kind: str, pages: list[Page], cfg: dict[str, Any], ocr=None,
                cache=None) -> list[IntegrityFinding]:
    """Every scan check, over the file's picture pages."""
    return scan_reading(data, kind, pages, cfg, ocr, cache)[0]


def scan_reading(data: bytes, kind: str, pages: list[Page], cfg: dict[str, Any], ocr=None,
                 cache=None) -> tuple[list[IntegrityFinding], dict[int, str], list[str]]:
    """Every scan check, with what they read on the way: each page's kind ("text"
    or "picture") and how each picture page measured as made (`capture.Capture.kind`)."""
    import numpy as np  # noqa: PLC0415

    t = cfg["scan"]
    try:
        if kind == "pdf":
            pictures, kinds, small = _pdf_pictures(data, pages, t)
        else:
            (pictures, kinds), small = _image_pictures(data, pages), []
    except Exception as e:  # noqa: BLE001 - said on each check, never passed
        return [_result(cfg, c, "unable_to_determine", f"The page pictures could not be read: {type(e).__name__}.",
                        failed=True) for c in SCAN_CHECKS], {}, []
    if not pictures and not small:
        why = "No page is a picture of a page; the checks on what its pages draw apply instead."
        return [_result(cfg, c, "not_applicable", why) for c in SCAN_CHECKS], kinds, []

    if not pictures:
        # Pages of text only: just the pictures standing in place of figures were looked at.
        none = "No page is a picture of a page; the checks on what its pages draw apply instead."
        pictures_only = [c for c in SCAN_CHECKS if c != "PDF_FIGURE_IS_PICTURE"]
        return [_result(cfg, c, "not_applicable", none) for c in pictures_only] + \
            [_figure_result(cfg, kind, small, ocr, _read_figures(data, small, t, ocr, cache))], kinds, []

    captures, regions, varied, grainy, misplaced, laid_out = [], [], 0, 0, [], 0
    measured: list[ts.Measured] = []
    style = t["type_style"]
    tl_pages, tl_found, tl_said = 0, [], []
    for p in pictures:
        coverage = (p.placed.width * p.placed.height) / max(p.width * p.height, 1.0)
        captures.append(cap.capture_of(p.no, p.image, coverage, dpi=p.dpi))

        # Grain and sharpness, at the resolution the source measured them at.
        scale = REGIONS_DPI / p.dpi
        img = p.image.resize((max(1, round(p.image.width * scale)), max(1, round(p.image.height * scale))))
        grey = np.asarray(img.convert("L"), dtype=np.float64)
        if page_has_grain(grey, t["regions"]):
            grainy += 1
            found = odd_regions(grey, t["regions"])
            if len(found) > t["regions"]["max_regions_per_page"]:
                varied += 1
            else:
                regions += [(p, r) for r in found]

        # Values off their lines, on a form or in rows of figures, measured on the
        # print inside each box.
        page = next((pg for pg in pages if pg.no == p.no), None)
        if page is not None and page.lines:
            measured += _measure_words(p, page, np.asarray(p.image.convert("L"), dtype=np.float64), style)
        if page is not None and page.lines:
            full = np.asarray(p.image.convert("L"), dtype=np.float64)
            paper = float(np.percentile(full, 90))
            runs = _tighten(p, _runs(page), full, paper)
            results = [misplaced_on_form(p.no, runs)]
            rows = []
            for line in page.lines:
                cells = [_Placed(w.text, _up(w, page.height)) for w in line.words
                         if _AMOUNTISH.fullmatch(w.text.strip("()-"))]
                if len(cells) >= 2:
                    rows.append([c.box for c in _tighten(p, cells, full, paper)])
            results.append(misplaced_in_rows(p.no, rows))
            if any(r.applicable for r in results):
                laid_out += 1
            for r in results:
                misplaced += [(p, m) for m in r.findings]

        # A searchable scan: its text layer against its picture, read twice.
        if p.searchable and ocr is not None:
            if p.dpi < t["text_layer"]["min_dpi"]:
                tl_said.append(f"page {p.no} is {round(p.dpi)} dpi, below {t['text_layer']['min_dpi']:g}")
                continue
            px = 72.0 / p.dpi
            ox, oy = p.placed.left, p.height - p.placed.top
            read = [_Placed(w.text, Box(ox + w.x0, p.height - (oy + w.y1), ox + w.x1, p.height - (oy + w.y0)),
                            w.conf) for w in _ocr(p.image, p.dpi, ocr, cache)]

            def reread(box: Box, p=p, ox=ox, oy=oy, px=px) -> tuple[str, float]:
                pad = 3.0
                l, top = (box.left - ox - pad) / px, (p.height - box.top - oy - pad) / px
                r, bottom = (box.right - ox + pad) / px, (p.height - box.bottom - oy + pad) / px
                crop = p.image.crop((max(0, round(l)), max(0, round(top)), min(p.image.width, round(r)),
                                     min(p.image.height, round(bottom))))
                words = _ocr(crop, p.dpi, ocr, cache)
                if not words:
                    return "", 0.0
                return "".join(w.text for w in sorted(words, key=lambda w: w.x0)), min(w.conf for w in words)

            tokens = [_Placed(w.text, _up(w, p.height)) for w in p.words]
            res = text_layer_versus_scan(p.no, tokens, read, reread, confirm=t["text_layer"]["confirm_confidence"],
                                         min_agreement=t["text_layer"]["min_agreement"])
            if res.applicable:
                tl_pages += 1
                tl_found += [(p, d) for d in res.disagreements if not d.misreading]
            else:
                tl_said.append(f"page {p.no}: {res.reason}")

    figures = _read_figures(data, small, t, ocr, cache)

    out = []
    # VISUAL_REGIONS_INCONSISTENT
    r_cfg = t["regions"]
    if not grainy:
        out.append(_result(cfg, "VISUAL_REGIONS_INCONSISTENT", "not_applicable",
                           f"None of the {len(pictures)} picture page(s) has a paper grain to compare: they are "
                           f"pictures made from a digital page, not scans or photographs."))
    elif regions:
        out.append(_result(cfg, "VISUAL_REGIONS_INCONSISTENT", "warning",
                           f"{len(regions)} region(s) have another grain or sharpness than the rest of their page.",
                           [IntegrityEvidence(page=p.no, rect=_image_frac(p, r["rect"]),
                                              observed=f"{r['tiles']} tiles whose grain is {r['grain_z']:+g} and "
                                                       f"sharpness {r['sharp_z']:+g} robust deviations from the page's",
                                              threshold=f"cleaner than the page by {r_cfg['noise_z']:g} deviations, or "
                                                        f"by half that and sharper by {r_cfg['sharpness_z']:g}")
                            for p, r in regions[:MAX_EVIDENCE]]))
    elif varied == grainy:
        out.append(_result(cfg, "VISUAL_REGIONS_INCONSISTENT", "not_applicable",
                           f"The {grainy} scanned page(s) vary too much by nature to compare regions."))
    else:
        out.append(_result(cfg, "VISUAL_REGIONS_INCONSISTENT", "pass",
                           f"Every text region of the {grainy - varied} scanned page(s) has its page's grain and "
                           f"sharpness."))
    # IMG_VALUE_IN_LINE
    if misplaced:
        out.append(_result(cfg, "IMG_VALUE_IN_LINE", "warning",
                           f"{len(misplaced)} value(s) on the scan sit off their line where the page's other values "
                           f"do not.",
                           [IntegrityEvidence(page=p.no, rect=_frac(p, m.box),
                                              observed=f"{abs(m.offset_pt):.1f} pt {'below' if m.offset_pt < 0 else 'above'} "
                                                       f"its {'label' if m.kind == 'form' else 'row'}'s line, where the "
                                                       f"others sit within {m.spread_pt:.1f} pt "
                                                       f"({abs(m.offset_pt) / max(m.spread_pt, 1e-6):.0f} times as far)",
                                              threshold="within 6 times the page's own spread of its line")
                            for p, m in sorted(misplaced, key=lambda pm: -pm[1].strength)[:MAX_EVIDENCE]]))
    elif laid_out:
        out.append(_result(cfg, "IMG_VALUE_IN_LINE", "pass",
                           f"On {laid_out} scanned page(s) laid out as labels and values or rows of figures, every "
                           f"value sits on its line as the others do."))
    else:
        out.append(_result(cfg, "IMG_VALUE_IN_LINE", "not_applicable",
                           "No scanned page is laid out as labels and values in columns, or as rows of figures, so "
                           "alignment could not be measured."))
    # TEXT_LAYER_MATCHES_PAGE
    searchable = [p for p in pictures if p.searchable]
    if not searchable:
        out.append(_result(cfg, "TEXT_LAYER_MATCHES_PAGE", "not_applicable",
                           "No scanned page carries a text layer of its own to compare with its picture."))
    elif ocr is None:
        out.append(_result(cfg, "TEXT_LAYER_MATCHES_PAGE", "not_applicable",
                           "Optical reading is not set up, so the text layer could not be compared with the picture."))
    elif tl_found:
        out.append(_result(cfg, "TEXT_LAYER_MATCHES_PAGE", "review_required",
                           f"{len(tl_found)} number(s) in the scan's text layer differ from what its picture shows, "
                           f"read twice.",
                           [IntegrityEvidence(page=p.no, rect=_frac(p, d.box),
                                              observed=f"the text layer says “{d.text_says}”, the picture shows "
                                                       f"“{d.page_shows}”",
                                              threshold="the text layer says what the picture shows")
                            for p, d in tl_found[:MAX_EVIDENCE]]))
    elif tl_pages:
        out.append(_result(cfg, "TEXT_LAYER_MATCHES_PAGE", "pass",
                           f"On {tl_pages} searchable scanned page(s), every number the text layer prints is what "
                           f"the picture shows."))
    else:
        out.append(_result(cfg, "TEXT_LAYER_MATCHES_PAGE", "not_applicable",
                           "The text layer could not be compared: " + "; ".join(tl_said[:3]) + "."))
    # PDF_FIGURE_IS_PICTURE
    out.append(_figure_result(cfg, kind, small, ocr, figures))
    # PAGES_SAME_ORIGIN
    o_cfg = t["origin"]
    odd = cap.mixed_origins(kinds, captures, dpi_differ=o_cfg["dpi_differ"], dpi_agree=o_cfg["dpi_agree"])
    if len(kinds) < 2:
        out.append(_result(cfg, "PAGES_SAME_ORIGIN", "not_applicable", "The file has one page."))
    elif odd:
        # One or two pages made differently is a page swapped in; many is a file put
        # together from several documents (a compiled set): listed, not counted.
        many = len(odd) > o_cfg["max_odd_pages"]
        hit = _result(cfg, "PAGES_SAME_ORIGIN", "warning",
                      f"{len(odd)} pages were made differently from the rest: the file reads as several documents "
                      f"put together." if many else
                      f"{len(odd)} page(s) were made differently from the rest; pages issued together are made alike.",
                      [IntegrityEvidence(page=no, rect=None, observed=f"page {no}: {why}",
                                         threshold="every page made the same way") for no, why in odd])
        out.append(hit.model_copy(update={"context": True}) if many else hit)
    else:
        out.append(_result(cfg, "PAGES_SAME_ORIGIN", "pass", f"The file's {len(kinds)} pages were made alike."))
    # IMG_TYPE_IN_COLUMN
    out.append(_type_result(cfg, measured, style))
    # IMG_PAGE_ORIGIN (listed only)
    said = [cap.describe(c) for c in captures]
    digital = [c for c in captures if c.kind in cap.DIGITAL]
    out.append(_result(cfg, "IMG_PAGE_ORIGIN", "warning" if digital else "pass",
                       ("; ".join(said[:4]) + ". A picture of a computer-drawn page keeps none of its file's history."
                        if digital else f"{len(captures)} picture page(s): " + "; ".join(said[:4]) + "."),
                       [IntegrityEvidence(page=c.page, rect=None, observed=cap.describe(c),
                                          threshold="the issuer's own file, not a picture of it")
                        for c in captures[:MAX_EVIDENCE]]))
    return out, kinds, [c.kind for c in captures]
