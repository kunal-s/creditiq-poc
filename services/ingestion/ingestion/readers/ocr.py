"""OCR behind one interface. PaddleOCR is the configured engine; it is imported lazily so the
service runs (and reads digital documents) without it installed."""

from __future__ import annotations

import functools
import os
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


def _python_bidi_not_needed() -> None:
    """PaddleX lists python-bidi (LGPL, kept out by CLAUDE.md rule 10) among its OCR dependencies and refuses to build
    the text recogniser without it, although it calls it only to reorder right-to-left text after the two Arabic
    recognition models. The models this service configures read left-to-right scripts, so when python-bidi is absent,
    PaddleX's dependency check is told that requirement is met. Configuring an Arabic model would need python-bidi."""
    import importlib.util  # noqa: PLC0415

    if importlib.util.find_spec("bidi") is not None:
        return
    from paddlex.utils import deps  # noqa: PLC0415

    if getattr(deps.is_dep_available, "_bidi_waived", False):
        return
    original = deps.is_dep_available

    def is_dep_available(dep, /, check_version=False):
        return True if dep == "python-bidi" else original(dep, check_version=check_version)

    is_dep_available._bidi_waived = True
    deps.is_dep_available = is_dep_available


class PaddleOcr:
    name = "paddle"

    def __init__(self, cfg: OcrConfig, cpu_threads: int | None = None):
        try:
            from paddleocr import PaddleOCR  # noqa: PLC0415
        except ImportError as e:
            raise OcrUnavailable("PaddleOCR is not installed (pip install -r requirements-ocr.txt, without python-bidi)") from e
        if cfg.rec_model and cfg.rec_model.startswith("arabic_"):
            raise OcrUnavailable("an Arabic recognition model needs python-bidi, which is not installed")
        _python_bidi_not_needed()
        kw = dict(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
                  device="cpu", enable_mkldnn=False, text_det_limit_type="max", text_det_limit_side_len=cfg.det_limit_side)
        if cpu_threads:
            kw["cpu_threads"] = cpu_threads
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


# --- OCR in worker processes -----------------------------------------------------------------------------------
# One engine keeps about eight cores busy, and two engines in one process take turns (the engine holds the
# interpreter while it reads), so pages are read side by side only in separate processes.

_WORKER_ENGINE: OcrEngine | None = None


def _start_worker(factory) -> None:
    global _WORKER_ENGINE
    _WORKER_ENGINE = factory()


def _read_in_worker(mode: str, size: tuple[int, int], pixels: bytes, dpi: int) -> tuple[list[tuple], float]:
    assert _WORKER_ENGINE is not None
    res = _WORKER_ENGINE.recognise(Image.frombytes(mode, size, pixels), dpi)
    return [(w.text, w.x0, w.y0, w.x1, w.y1, w.conf) for w in res.words], res.mean_conf


class OcrProcessPool:
    """Pages read in at most `workers` processes at once, each with its own engine (loaded in that process on its
    first page; a second process starts only when two pages wait at the same time). Any further page waits for a
    free process. The same page gives the same words whichever process reads it."""

    def __init__(self, factory, workers: int, name: str = "paddle"):
        from concurrent.futures import ProcessPoolExecutor  # noqa: PLC0415
        import multiprocessing  # noqa: PLC0415

        self.name = name
        self.workers = max(1, workers)
        self._pool = ProcessPoolExecutor(max_workers=self.workers, mp_context=multiprocessing.get_context("spawn"),
                                         initializer=_start_worker, initargs=(factory,))

    def recognise(self, img: Image.Image, dpi: int) -> OcrResult:
        img = img.convert("RGB")
        words, conf = self._pool.submit(_read_in_worker, img.mode, img.size, img.tobytes(), dpi).result()
        return OcrResult([Word(*w) for w in words], conf)

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


def _paddle_available(cfg: OcrConfig) -> bool:
    import importlib.util  # noqa: PLC0415

    if cfg.rec_model and cfg.rec_model.startswith("arabic_"):
        return False
    return importlib.util.find_spec("paddleocr") is not None


def get_engine(cfg: OcrConfig, workers: int = 1) -> OcrEngine | None:
    """None when OCR is switched off or not installed; callers then grade the page U with the
    reason `ocr_unavailable` instead of guessing. With `workers` above one, up to that many pages
    are read at once, each in its own process with its share of the machine's cores."""
    if cfg.engine == "none":
        return None
    if workers > 1:
        if not _paddle_available(cfg):
            return None
        threads = max(1, (os.cpu_count() or 2) // workers)
        return OcrProcessPool(functools.partial(PaddleOcr, cfg, threads), workers)
    try:
        return PaddleOcr(cfg)
    except OcrUnavailable:
        return None
