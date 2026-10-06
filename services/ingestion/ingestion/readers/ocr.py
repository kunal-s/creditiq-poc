"""OCR behind one interface. PaddleOCR is the configured engine; it is imported lazily so the
service runs (and reads digital documents) without it installed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from ..config.models import OcrConfig
from ..pageindex import Word


class OcrUnavailable(RuntimeError):
    pass


@dataclass
class OcrResult:
    words: list[Word]  # in points (pixels / dpi * 72)
    mean_conf: float   # 0-100


class OcrEngine(Protocol):
    name: str

    def recognise(self, img: Image.Image, dpi: int) -> OcrResult: ...


def split_line_box(text: str, x0: float, y0: float, x1: float, y1: float, conf: float) -> list[Word]:
    """OCR engines return text lines; the page index wants words. Split a line box in proportion
    to character counts (positions are therefore approximate within a line)."""
    toks = text.split()
    if not toks:
        return []
    total = sum(len(t) for t in toks) + (len(toks) - 1)
    width = x1 - x0
    out, pos = [], 0
    for t in toks:
        a = x0 + width * pos / total
        b = x0 + width * (pos + len(t)) / total
        out.append(Word(t, a, y0, b, y1, conf))
        pos += len(t) + 1
    return out


class PaddleOcr:
    name = "paddle"

    def __init__(self, cfg: OcrConfig):
        try:
            from paddleocr import PaddleOCR  # noqa: PLC0415
        except ImportError as e:
            raise OcrUnavailable("PaddleOCR is not installed (pip install -r requirements-ocr.in)") from e
        kw = dict(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
                  device="cpu", enable_mkldnn=False, text_det_limit_type="max", text_det_limit_side_len=cfg.det_limit_side)
        if cfg.det_model:
            kw["text_detection_model_name"] = cfg.det_model
        if cfg.rec_model:
            kw["text_recognition_model_name"] = cfg.rec_model
        self._ocr = PaddleOCR(**kw)
        self.cfg = cfg

    def recognise(self, img: Image.Image, dpi: int) -> OcrResult:
        import numpy as np  # noqa: PLC0415

        res = self._ocr.predict(np.array(img.convert("RGB")))[0]
        k = 72.0 / dpi
        words: list[Word] = []
        confs: list[float] = []
        for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
            pts = np.array(poly).reshape(-1, 2)
            x0, y0 = pts.min(axis=0) * k
            x1, y1 = pts.max(axis=0) * k
            words += split_line_box(str(text), float(x0), float(y0), float(x1), float(y1), float(score))
            confs.append(float(score))
        return OcrResult(words, 100.0 * (sum(confs) / len(confs)) if confs else 0.0)


def get_engine(cfg: OcrConfig) -> OcrEngine | None:
    """None when OCR is switched off or not installed; callers then grade the page U with the
    reason `ocr_unavailable` instead of guessing."""
    if cfg.engine == "none":
        return None
    try:
        return PaddleOcr(cfg)
    except OcrUnavailable:
        return None
