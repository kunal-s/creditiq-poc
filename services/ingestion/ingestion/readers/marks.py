"""Dash marks the OCR engine does not return. A statement prints nil as a lone "-" in the amount
column; the detector skips glyphs that small, so the cell comes back empty and cannot be told
from a cell that was never read. A mark is taken as a dash only when it is a short, thin, solid
horizontal stroke on its own: nothing else inked around it and no recognised word over it.
Deterministic image analysis, no model."""

from __future__ import annotations

import numpy as np
from PIL import Image

from ..pageindex import Word

INK = 140       # grey level below which a pixel is ink
ISOLATION = 4   # pixels around the stroke that must be clear of ink
SPECKLE = 4     # ...bar a few stray pixels of scan noise


def _runs(row: np.ndarray) -> list[tuple[int, int]]:
    edges = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


def find_dashes(img: Image.Image, dpi: int, taken: list[tuple[float, float, float, float]]) -> list[Word]:
    """Dashes on the page image as words in points. `taken` are the boxes (points) of the words
    already read; a mark inside one is part of that word."""
    ink = np.asarray(img.convert("L")) < INK
    h, w = ink.shape
    scale = dpi / 72.0
    min_w, max_w = round(0.025 * dpi), round(0.12 * dpi)   # about 2 to 9 points wide
    max_h = max(2, round(0.02 * dpi))                      # and about 1.5 points thick at most
    # Stack the runs of consecutive rows that overlap into one stroke.
    open_strokes: list[list[int]] = []   # [x0, x1, y0, y1]
    strokes: list[list[int]] = []
    for y in range(h):
        runs = _runs(ink[y]) if ink[y].any() else []
        nxt: list[list[int]] = []
        used = set()
        for s in open_strokes:
            hit = next((i for i, (a, b) in enumerate(runs) if i not in used and a < s[1] and b > s[0]), None)
            if hit is None:
                strokes.append(s)
            else:
                a, b = runs[hit]
                used.add(hit)
                if y - s[2] < max_h:   # a taller mark is a glyph or a rule, not a dash
                    nxt.append([min(s[0], a), max(s[1], b), s[2], y])
        nxt += [[a, b, y, y] for i, (a, b) in enumerate(runs) if i not in used and b - a <= 4 * max_w]
        open_strokes = nxt
    strokes += open_strokes
    out: list[Word] = []
    for x0, x1, y0, y1 in strokes:
        sw, sh = x1 - x0, y1 - y0 + 1
        if not (min_w <= sw <= max_w and sh <= max_h and sw >= 2 * sh):
            continue
        if ink[y0:y1 + 1, x0:x1].mean() < 0.65:
            continue
        a, b, c, d = max(0, x0 - ISOLATION), min(w, x1 + ISOLATION), max(0, y0 - ISOLATION), min(h, y1 + 1 + ISOLATION)
        ring = ink[c:d, a:b].copy()
        ring[y0 - c:y1 + 1 - c, x0 - a:x1 - a] = False
        if ring.sum() > SPECKLE:
            continue
        box = (x0 / scale, y0 / scale, x1 / scale, (y1 + 1) / scale)
        if any(box[0] < t[2] and box[2] > t[0] and box[1] < t[3] and box[3] > t[1] for t in taken):
            continue
        out.append(Word("-", *box, 0.9))
    return out
