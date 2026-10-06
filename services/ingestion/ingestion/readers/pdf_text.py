"""PDF reading: text layer with word boxes (pdfplumber) and page rendering (pypdfium2)."""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

from ..config.models import ReadingConfig
from ..pageindex import Word


@dataclass
class RawPdfPage:
    no: int
    width: float
    height: float
    words: list[Word]
    n_chars: int
    garbage_ratio: float
    has_images: bool
    dropped_rotated: int


class PdfError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def probe_pdf(data: bytes) -> int:
    """Page count, or PdfError('encrypted' | 'corrupt')."""
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        msg = str(e).lower()
        raise PdfError("encrypted" if "password" in msg else "corrupt", str(e)) from e
    try:
        return len(doc)
    finally:
        doc.close()


def _axis_aligned(obj: dict, max_deg: float) -> bool:
    m = obj.get("matrix")
    if not m:
        return True
    a, b = m[0], m[1]
    ang = abs(math.degrees(math.atan2(b, a)))
    return ang <= max_deg or abs(ang - 180) <= max_deg


def read_text_layer(data: bytes, cfg: ReadingConfig) -> list[RawPdfPage]:
    out: list[RawPdfPage] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            chars = page.chars
            kept = chars
            if cfg.drop_rotated_text:
                kept = [c for c in chars if _axis_aligned(c, cfg.max_rotation_deg)]
            view = page.filter(lambda o: o.get("object_type") != "char" or _axis_aligned(o, cfg.max_rotation_deg)) if cfg.drop_rotated_text else page
            raw_words = view.extract_words(x_tolerance=cfg.x_tolerance, y_tolerance=cfg.y_tolerance, keep_blank_chars=False, use_text_flow=False)
            words = [Word(w["text"], float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"])) for w in raw_words]
            n = len(kept)
            bad = sum(1 for c in kept if c.get("text") in ("�",) or str(c.get("text", "")).startswith("(cid:"))
            out.append(RawPdfPage(i, float(page.width), float(page.height), words, n, (bad / n) if n else 0.0,
                                  bool(page.images), len(chars) - len(kept)))
    return out


def render_page(data: bytes, page_no: int, dpi: int) -> Image.Image:
    doc = pdfium.PdfDocument(data)
    try:
        return doc[page_no - 1].render(scale=dpi / 72).to_pil().convert("RGB")
    finally:
        doc.close()
