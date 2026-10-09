"""Stage 2: read every page into the page index and grade it (FRD F-07.1 to F-07.4).

Route per page: the text layer when it is trustworthy, OCR for scans and photos, cells for
spreadsheets. Grades A (clean) B (degraded) C (poor) U (unreadable) follow quality.yaml."""

from __future__ import annotations

import io
import re
from typing import Protocol

from PIL import Image, ImageSequence

from ..config.models import QualityConfig, RoutingConfig
from ..pageindex import Line, Page, Word, build_lines
from ..readers import imagequal
from ..readers import pdf_text
from ..readers import sheet as sheet_reader
from ..readers.ocr import OcrEngine
from ..util import sha256_hex

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "U": 3}


class OcrCache(Protocol):
    def get(self, key: str) -> dict | None: ...
    def put(self, key: str, value: dict) -> None: ...


def _boilerplate(r: RoutingConfig) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in r.reading.boilerplate]


def worst(grades: list[str]) -> str:
    return max(grades, key=lambda g: GRADE_ORDER[g]) if grades else "U"


def document_grade(pages: list[Page]) -> str:
    """Worst grade among non-blank pages (F-07.3); a file of blank pages is U."""
    real = [p.grade for p in pages if not p.blank]
    return worst(real) if real else "U"


def read_document(data: bytes, kind: str, q: QualityConfig, r: RoutingConfig, ocr: OcrEngine | None,
                  cache: OcrCache | None = None, image_dpi: int | None = None) -> list[Page]:
    bp = _boilerplate(r)
    if kind == "pdf":
        return _read_pdf(data, q, r, ocr, cache, bp)
    if kind in ("xlsx", "csv"):
        return _read_sheets(data, kind, q, r, bp)
    return _read_image(data, q, r, ocr, cache, bp, image_dpi)


def _lines(no: int, words: list[Word], r: RoutingConfig, bp: list[re.Pattern]) -> list[Line]:
    return build_lines(no, words, y_tol=r.reading.line_y_tol, column_gap=r.reading.column_gap, boilerplate=bp,
                       min_overlap=r.reading.line_overlap)


def _read_pdf(data, q, r, ocr, cache, bp) -> list[Page]:
    raw = pdf_text.read_text_layer(data, r.reading)
    pages: list[Page] = []
    for rp in raw:
        trusted = rp.n_chars >= q.min_chars_text_layer and rp.garbage_ratio <= q.garbage_ratio_max
        if trusted:
            p = Page(rp.no, "text_layer", rp.width, rp.height, rp.words, _lines(rp.no, rp.words, r, bp), "A", [], 1.0)
        elif rp.has_images or rp.n_chars > 0:
            img = pdf_text.render_page(data, rp.no, r.ocr.dpi)
            p = _ocr_page(rp.no, img, r.ocr.dpi, q, r, ocr, cache, bp)
        else:
            p = Page(rp.no, "text_layer", rp.width, rp.height, [], [], "U", ["blank"], 0.0, blank=True)
        pages.append(p)
    return pages


def _read_image(data, q, r, ocr, cache, bp, image_dpi) -> list[Page]:
    pages = []
    with Image.open(io.BytesIO(data)) as im:
        dpi = image_dpi or int(round(float((im.info.get("dpi") or (0,))[0] or 0))) or None
        for i, frame in enumerate(ImageSequence.Iterator(im), start=1):
            img = frame.convert("RGB")
            eff = dpi or r.ocr.dpi
            p = _ocr_page(i, img, eff, q, r, ocr, cache, bp)
            if dpi and dpi < q.min_dpi and "resolution" not in p.reasons:
                p.reasons.append("resolution")
                if p.grade == "A":
                    p.grade = "B"
            pages.append(p)
    return pages


def _ocr_page(no: int, img: Image.Image, dpi: int, q: QualityConfig, r: RoutingConfig, ocr: OcrEngine | None,
              cache: OcrCache | None, bp) -> Page:
    w_pt, h_pt = img.width * 72 / dpi, img.height * 72 / dpi
    if ocr is None:
        return Page(no, "ocr", w_pt, h_pt, [], [], "U", ["ocr_unavailable"], 0.0)
    ink = imagequal.ink_ratio(img)
    if ink < q.blank_ink_max:
        return Page(no, "ocr", w_pt, h_pt, [], [], "U", ["blank"], 0.0, blank=True)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    key = sha256_hex(f"{ocr.name}|{dpi}|{r.ocr.det_limit_side}|".encode() + buf.getvalue())
    hit = cache.get(key) if cache else None
    if hit:
        words = [Word(*w) for w in hit["words"]]
        conf = hit["mean_conf"]
    else:
        res = ocr.recognise(img, dpi)
        words, conf = res.words, res.mean_conf
        if cache:
            cache.put(key, {"words": [[w.text, w.x0, w.y0, w.x1, w.y1, w.conf, None] for w in words], "mean_conf": conf})
    reasons: list[str] = []
    grade = "A"
    if not words:
        return Page(no, "ocr", w_pt, h_pt, [], [], "U", ["ocr_floor"], 0.0, ocr_conf=0.0)
    if conf < q.ocr_confidence_floor:
        grade, reasons = "C", ["ocr_floor"]
    elif conf < q.ocr_confidence_degraded:
        grade = "B"
    if imagequal.sharpness(img) < q.blur_sharpness_min:
        reasons.append("blur")
    if imagequal.skew_degrees(img) > q.skew_degrees_max:
        reasons.append("skew")
    if imagequal.shadow_spread(img) > q.shadow_spread_max:
        reasons.append("shadow")
    if reasons and grade == "A":
        grade = "B"
    return Page(no, "ocr", w_pt, h_pt, words, _lines(no, words, r, bp), grade, reasons, conf / 100.0, ocr_conf=conf)


def _read_sheets(data, kind, q, r, bp) -> list[Page]:
    sheets = sheet_reader.read_xlsx(data, q.max_sheet_cells) if kind == "xlsx" else sheet_reader.read_csv(data, q.max_sheet_cells)
    pages = []
    for i, (name, rows) in enumerate(sheets, start=1):
        words = [w for row in rows for w in row]
        blank = not words
        pages.append(Page(i, "sheet", 0.0, 0.0, words, _lines(i, words, r, bp), "U" if blank else "A", ["blank"] if blank else [], 1.0, sheet=name, blank=blank))
    return pages
