"""How heavy and how slanted a scan's type is, from its pixels (use case 2).

A scan has no font names to compare, so a figure retyped in another weight or
slant can only be seen in its strokes. Ported from fault_detection
(`tamper/typestyle.py`, the measurement, and `tamper/typelayout.py`, the
column rule):

* stroke: a low (30th) percentile of the horizontal runs of ink over every row
  of a word, as a share of the word's height, so it does not depend on the
  resolution. fault_detection takes the median; on figures the flat bars of 2,
  3, 5 and 7 make long runs that lift the median (a regular "2,315.75" measured
  1.5 times its column), while the runs across upright strokes, the stroke
  itself, fill the lower part of the distribution;
* slant: the shear that stacks the word's ink into the fewest columns, searched
  from -0.35 to +0.35 in steps of 0.05 (about +/-19 degrees); judged only on a
  word with three or more letters that have an upright stem;
* bold: a stroke of `bold_ratio` times the document's usual or more; italic: a
  slant of `italic_deg` or more to the right;
* a column: three or more figures whose right edges agree within
  `column_tol_pt`, on as many lines; its usual style is the one held by
  `column_majority` of its figures, and a figure set otherwise is named.

fault_detection measures on Tesseract's tight word boxes; PaddleOCR's are padded,
so the right edge of each figure is taken from its ink.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

__all__ = ["Measured", "stroke_and_slant", "measure", "styled", "odd_in_columns"]

#: Letters with an upright stem: a slant is judged only where three of them stand.
STEMS = set("bdfhiklmnprtuBDEFHIKLMNPRTU1")
MIN_STEMS = 3
#: The share of a word's horizontal ink runs at or under its stroke width.
STROKE_PERCENTILE = 30
#: A figure: a token that carries a digit (fault_detection typelayout VALUE).
VALUE = re.compile(r"(?=.*\d)[\w.,/:₹-]{2,}")


@dataclass(slots=True)
class Measured:
    """One word measured on a page picture."""

    page: int
    text: str
    left: float
    right: float
    top: float
    bottom: float
    """The word's box in points, bottom-left origin, its right edge taken from its ink."""
    ratio: float
    slant: float | None
    is_value: bool
    rect: tuple[float, float, float, float] | None = None
    """The word as fractions of its page (left, top, right, bottom), for its mark."""


def stroke_and_slant(ink: np.ndarray) -> tuple[float, float] | None:
    """The stroke width (pixels) and the slant (degrees, + leans
    right) of one word's ink mask; None with too little ink to say."""
    h, w = ink.shape
    if h < 8 or w < 8 or ink.sum() < 20:
        return None
    runs: list[int] = []
    for row in ink:
        edges = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
        runs += (ends - starts).tolist()
    if len(runs) < 5:
        return None
    stroke = float(np.percentile(runs, STROKE_PERCENTILE))
    ys, xs = np.nonzero(ink)
    up = (h - 1 - ys).astype(np.float64)
    best, best_score = 0.0, -1.0
    for k in range(-7, 8):
        shear = k * 0.05
        cols = np.round(xs - shear * up).astype(np.int64)
        cols -= cols.min()
        score = float((np.bincount(cols) ** 2).sum())
        if score > best_score:
            best, best_score = shear, score
    return stroke, math.degrees(math.atan(best))


def measure(grey: np.ndarray, page: int, text: str, box_px: tuple[int, int, int, int],
            to_points) -> Measured | None:
    """One word cut from a page picture (grey, 0-255) at `box_px` (x0, y0, x1, y1,
    top-left origin); `to_points(x_px, y_px)` maps a pixel to page points."""
    x0, y0, x1, y1 = box_px
    crop = grey[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
    if crop.shape[0] < 8 or crop.shape[1] < 8:
        return None
    paper, darkest = np.percentile(crop, 90), np.percentile(crop, 2)
    if paper - darkest < 40:
        return None
    ink = crop < (paper + darkest) / 2
    cols = np.flatnonzero(ink.any(axis=0))
    rows = np.flatnonzero(ink.any(axis=1))
    if cols.size == 0 or rows.size == 0:
        return None
    ink = ink[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    found = stroke_and_slant(ink)
    if found is None:
        return None
    stroke, slant = found
    stems = sum(ch in STEMS for ch in text)
    left, top = to_points(x0 + cols[0], y0 + rows[0])
    right, bottom = to_points(x0 + cols[-1] + 1, y0 + rows[-1] + 1)
    return Measured(page, text, left, right, top, bottom, stroke / max(ink.shape[0], 1),
                    slant if stems >= MIN_STEMS else None, bool(VALUE.fullmatch(text)))


def styled(m: Measured, usual: float, bold_ratio: float, italic_deg: float) -> str:
    """bold, italic, bold italic or regular (a lean to the left is never italic)."""
    bold = m.ratio >= bold_ratio * usual
    italic = m.slant is not None and m.slant >= italic_deg
    return "bold italic" if bold and italic else "bold" if bold else "italic" if italic else "regular"


def odd_in_columns(words: list[Measured], *, bold_ratio: float, italic_deg: float, tol_pt: float,
                   column_min: int, majority: float) -> tuple[float | None, int, list[tuple[Measured, str, str, int]]]:
    """The document's usual stroke, how many columns were compared, and each figure
    set otherwise than its column: (figure, its style, the column's style, the column's size)."""
    if not words:
        return None, 0, []
    usual = float(np.median([w.ratio for w in words]))
    values = sorted((w for w in words if w.is_value), key=lambda w: w.right)
    columns: list[list[Measured]] = []
    for w in values:
        for col in columns:
            if w.page == col[0].page and abs(w.right - float(np.median([c.right for c in col]))) <= tol_pt:
                col.append(w)
                break
        else:
            columns.append([w])
    odd, compared = [], 0
    for col in columns:
        lines = {round((c.top + c.bottom) / 2) for c in col}
        if len(col) < column_min or len(lines) < column_min:
            continue
        compared += 1
        styles = [styled(c, usual, bold_ratio, italic_deg) for c in col]
        top = max(set(styles), key=styles.count)
        if styles.count(top) < majority * len(col):
            continue
        odd += [(c, s, top, len(col)) for c, s in zip(col, styles) if s != top]
    return usual, compared, odd
