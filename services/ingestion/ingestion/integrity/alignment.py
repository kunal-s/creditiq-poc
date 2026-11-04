"""Values on a scan that sit off their line (F-07A, use case 2: IMG_VALUE_IN_LINE).

A form prints its values in line with their labels, and a statement prints each
row's cells on one line. A value pasted in as a picture of new digits is placed
by hand, and is rarely placed exactly: the reviewer's own test edit of a
registration number sat 36 pixels lower than its label where every other value
sat on its row (31 times the spread of the genuine rows). Rows can drift down a
page, so each value is measured against the trend of the others (Theil-Sen),
not against perfect alignment, and only on a tidy form or ledger.

Boxes are in points with the origin at the bottom left (top > bottom), as the
source measured them. `runs` are anything with `.text` and `.box`.

Ported unchanged from RBL/fault_detection `raster.py` (`misplaced_on_form`,
`misplaced_in_rows` and their helpers and constants; PROVENANCE.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Misplaced", "LayoutResult", "misplaced_on_form", "misplaced_in_rows"]


@dataclass(slots=True)
class Misplaced:
    """A value — a form field, or a cell of a statement's row — out of line
    with where the rest of the page puts such values."""

    page_index: int
    box: Any                     # the value's rectangle, in PDF points
    label_box: Any | None        # what it should be in line with
    offset_pt: float             # how far off, after the page's own trend
    spread_pt: float             # the genuine rows' spread
    kind: str                    # "form" | "row"
    pitch_ratio: float | None = None

    @property
    def strength(self) -> float:
        return abs(self.offset_pt) / max(self.spread_pt, 1e-6)


def _centre(box) -> float:
    return (box.bottom + box.top) / 2


def _theil_sen(xs: list[float], ys: list[float]) -> tuple[float, float]:
    slopes = sorted((ys[j] - ys[i]) / (xs[j] - xs[i]) for i in range(len(xs)) for j in range(i + 1, len(xs))
                    if xs[j] != xs[i])
    slope = slopes[len(slopes) // 2] if slopes else 0.0
    intercepts = sorted(y - slope * x for x, y in zip(xs, ys))
    return slope, intercepts[len(intercepts) // 2]


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    return (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2) if n else 0.0


def _columns(runs, *, min_members: int = 5, tolerance: float = 4.0) -> list[list]:
    """Runs grouped by where they start: the columns a form lines things up in."""
    groups: list[list] = []
    for run in sorted(runs, key=lambda r: r.box.left):
        if groups and run.box.left - groups[-1][0].box.left <= tolerance:
            groups[-1].append(run)
        else:
            groups.append([run])
    return [g for g in groups if len(g) >= min_members]


#: A value counts as out of line when it is this many of the genuine rows'
#: spreads off the trend, and this share of a line's height. Both, so neither
#: a tidy form's tiny spread nor a messy one's large spread decides alone.
FORM_MIN_STRENGTH = 6.0
FORM_MIN_SHARE_OF_LINE = 0.35
#: The genuine rows' spread is never taken as less than this share of a line:
#: rows a renderer places exactly would otherwise make any difference "large".
FORM_MIN_SPREAD_SHARE = 0.06
FORM_MIN_ROWS = 6
#: A value moved this far or more of a row's pitch is as near the next row as
#: its own: it cannot be told from a value that belongs to the next row, so it
#: is not judged.
FORM_MAX_SHARE_OF_PITCH = 0.75
#: A page is a tidy form only when its values line up with their labels: at
#: most this share of its pairs (and at least one) may sit off their line. A
#: page with more is laid out some other way — a table, wrapped text, columns
#: of figures — and alignment says nothing about it.
FORM_MAX_OUTLIER_SHARE = 0.10
#: Two label lines closer than this share of the page's row pitch are one
#: label printed on two lines.
FORM_WRAPPED_LABEL_SHARE = 0.75
#: A value taller than this many times the page's median value is set in
#: larger type, and its centre is not comparable with its label's.
FORM_MAX_VALUE_HEIGHT_SHARE = 1.4
#: A form pairs most of the lines in its label column with a value. A page of
#: prose whose margin happens to hold a few short words pairs few of them, and
#: is not a form however its words line up.
FORM_MIN_PAIRED_SHARE = 0.6
#: A value has at least this many letters or digits: two-character marks in a
#: margin ("NA", a page's section letter) are not what a form is read for.
FORM_MIN_VALUE_CHARS = 3

_LEADING = re.compile(r"^[\s:;\-–—.]+")


@dataclass(slots=True)
class LayoutResult:
    """What the alignment check could say about a page. `applicable` is False
    when the page is not laid out the way the check measures — then silence
    means nothing, and the check is reported as not run, never as passed."""

    applicable: bool
    findings: list[Misplaced] = field(default_factory=list)
    pairs: int = 0
    reason: str = ""


def _content(text: str) -> str:
    return _LEADING.sub("", text or "").strip()


def _alnum(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def misplaced_on_form(page_index: int, runs) -> LayoutResult:
    """Values on a two-column form — labels in one column, values in another —
    that sit out of line with their labels where the other rows do not.

    Precision comes before reach. A value is judged only on a tidy form (its
    other values line up with their labels), only against the label it is
    mutually nearest, only when its row prints one line of value, and only
    when it sits between rows rather than on another row's line."""
    runs = [r for r in runs if _content(r.text)]
    columns = _columns(runs)
    if len(columns) < 2:
        return LayoutResult(False, reason="no labels and values in columns")
    labels = [r for r in columns[0] if sum(ch.isalpha() for ch in r.text) >= 2]
    left = columns[0][0].box.left
    later = [c for c in columns[1:] if c[0].box.left - left >= 60]
    if not later or len(labels) < FORM_MIN_ROWS:
        return LayoutResult(False, reason="no labels and values in columns")
    # The value column is the one that holds the most values — runs that say
    # something once a leading colon or dash is taken off — not the one with
    # the most members, which can be a column of colons.
    values = max(later, key=lambda c: sum(1 for r in c if _alnum(_content(r.text)) >= FORM_MIN_VALUE_CHARS))
    values = [r for r in values if _alnum(_content(r.text)) >= FORM_MIN_VALUE_CHARS]
    height = _median([r.box.top - r.box.bottom for r in values] or [0.0])
    if height <= 0 or len(values) < FORM_MIN_ROWS:
        return LayoutResult(False, reason="no labels and values in columns")
    labels.sort(key=lambda r: -_centre(r.box))
    centres = [_centre(r.box) for r in labels]
    pitch = _median([a - b for a, b in zip(centres, centres[1:])])
    if pitch <= 0:
        return LayoutResult(False, reason="no labels and values in columns")
    # A label printed on two lines is two runs closer together than rows are:
    # where its value sits against either line says nothing, so both lines'
    # rows are left out.
    wrapped_label = set()
    for k in range(1, len(labels)):
        if centres[k - 1] - centres[k] < FORM_WRAPPED_LABEL_SHARE * pitch:
            wrapped_label.update((k - 1, k))

    def nearest_label(y: float) -> int:
        return min(range(len(labels)), key=lambda k: abs(centres[k] - y))

    # Each label with the value nearest it, if that value is nearest this label
    # too; each value used once. A row whose value runs to a second line, or
    # whose label does, is left out: where its centre falls says nothing.
    pairs = []
    used: set[int] = set()
    for k, label in enumerate(labels):
        top = (centres[k - 1] + centres[k]) / 2 if k else centres[k] + pitch / 2
        bottom = (centres[k] + centres[k + 1]) / 2 if k + 1 < len(labels) else centres[k] - pitch / 2
        in_band = [i for i, v in enumerate(values) if bottom < _centre(v.box) <= top]
        choices = sorted((abs(_centre(v.box) - centres[k]), i) for i, v in enumerate(values) if i not in used)
        if not choices or choices[0][0] > FORM_MAX_SHARE_OF_PITCH * pitch:
            continue
        i = choices[0][1]
        if nearest_label(_centre(values[i].box)) != k:
            continue
        used.add(i)
        value = values[i]
        wrapped = (len(in_band) > 1 or label.box.top - label.box.bottom > 1.6 * height or k in wrapped_label
                   # A value set in larger type than the rest sits on its
                   # label's baseline with its centre higher: not comparable.
                   or value.box.top - value.box.bottom > FORM_MAX_VALUE_HEIGHT_SHARE * height)
        if not wrapped:
            pairs.append((label, value))
    if len(pairs) < FORM_MIN_ROWS:
        return LayoutResult(False, pairs=len(pairs),
                            reason=f"only {len(pairs)} single-line label and value pairs; "
                                   f"{FORM_MIN_ROWS} are needed to measure alignment")
    if len(used) < FORM_MIN_PAIRED_SHARE * len(labels):
        return LayoutResult(False, pairs=len(pairs),
                            reason=f"only {len(used)} of the {len(labels)} lines in the label column have a value "
                                   f"beside them, so the page is not laid out as a form")

    ys = [_centre(label.box) for label, _ in pairs]
    offsets = [_centre(value.box) - _centre(label.box) for label, value in pairs]
    measured = []
    for i in range(len(pairs)):
        others = [k for k in range(len(pairs)) if k != i]
        slope, intercept = _theil_sen([ys[k] for k in others], [offsets[k] for k in others])
        residuals = [offsets[k] - (intercept + slope * ys[k]) for k in others]
        spread = max(1.4826 * _median([abs(r) for r in residuals]), FORM_MIN_SPREAD_SHARE * height)
        measured.append((offsets[i] - (intercept + slope * ys[i]), spread))
    # A row taller than the others — a remark beside it wraps — with its label
    # at the top and its value centred: the value sits below its label by half
    # the extra height, and the gap to the next label shows the extra height.
    # Off by no more than that, the value is where it belongs.
    index_of = {id(label): n for n, label in enumerate(labels)}
    in_taller_row = set()
    for i, ((label, _value), (off, _spread)) in enumerate(zip(pairs, measured)):
        k = index_of[id(label)]
        neighbour = k + 1 if off < 0 else k - 1
        if 0 <= neighbour < len(labels) and abs(centres[k] - centres[neighbour]) - pitch >= 1.5 * abs(off):
            in_taller_row.add(i)
    off_line = sum(1 for i, (off, _) in enumerate(measured)
                   if abs(off) >= FORM_MIN_SHARE_OF_LINE * height and i not in in_taller_row)
    if off_line > max(1, int(FORM_MAX_OUTLIER_SHARE * len(pairs))):
        return LayoutResult(False, pairs=len(pairs),
                            reason=f"{off_line} of {len(pairs)} values sit off their labels' lines, so the page "
                                   f"is not laid out as a form whose values line up")

    out = []
    other_labels = [label for label in labels]
    for i, ((label, value), (off, spread)) in enumerate(zip(pairs, measured)):
        if abs(off) < FORM_MIN_SHARE_OF_LINE * height or abs(off) / spread < FORM_MIN_STRENGTH:
            continue
        if abs(off) >= FORM_MAX_SHARE_OF_PITCH * pitch:
            continue
        # Between rows, not on another row's line: overlapping another label's
        # line, it would be that row's value as much as this one's.
        if any(o is not label and min(o.box.top, value.box.top) - max(o.box.bottom, value.box.bottom)
               > 0.3 * height for o in other_labels):
            continue
        # And the gap to a neighbouring row disagrees between the two columns:
        # a value moved off its row, not a page whose rows all slope.
        ratio = None
        for j in (i - 1, i + 1):
            if 0 <= j < len(pairs):
                label_gap = _centre(pairs[j][0].box) - _centre(label.box)
                value_gap = _centre(pairs[j][1].box) - _centre(value.box)
                if label_gap:
                    r = value_gap / label_gap
                    if ratio is None or abs(r - 1) > abs(ratio - 1):
                        ratio = r
        if ratio is not None and abs(ratio - 1) < 0.2:
            continue
        if i in in_taller_row:
            continue
        out.append(Misplaced(page_index, value.box, label.box, round(off, 2), round(spread, 3), "form",
                             round(ratio, 3) if ratio is not None else None))
    return LayoutResult(True, out, pairs=len(pairs))


ROW_MIN_SHARE_OF_LINE = 0.35
ROW_MIN_STRENGTH = 6.0


def misplaced_in_rows(page_index: int, rows) -> LayoutResult:
    """Amounts of a statement's rows that sit off their row's line.

    `rows` holds each row's cells on one page, as {column: box} (a list of
    boxes is taken left to right). Each row's balance — its rightmost cell —
    is the row's line, and every other cell's offset from it is measured
    against the trend of the same column down the page, as a form's values are
    against their labels: a row of two cells is measured too. A page with too
    few rows, or whose cells do not keep to their lines, is not judged."""
    norm: list[dict] = []
    for row in rows:
        if isinstance(row, dict):
            cells = dict(row)
        else:
            ordered = sorted(row, key=lambda b: b.left)
            cells = {f"c{n}": b for n, b in enumerate(ordered[:-1])}
            if ordered:
                cells["balance"] = ordered[-1]
        if "balance" not in cells and cells:
            key = max(cells, key=lambda k: cells[k].left)
            cells["balance"] = cells.pop(key)
        if len(cells) >= 2:
            norm.append(cells)
    heights = [b.top - b.bottom for cells in norm for b in cells.values()]
    height = _median(heights)
    columns = sorted({k for cells in norm for k in cells if k != "balance"})
    out, measured_rows = [], 0
    for column in columns:
        series = [(cells[column], cells["balance"]) for cells in norm if column in cells]
        if len(series) < FORM_MIN_ROWS or height <= 0:
            continue
        ys = [_centre(b) for _, b in series]
        offsets = [_centre(a) - _centre(b) for a, b in series]
        measured = []
        for i in range(len(series)):
            others = [k for k in range(len(series)) if k != i]
            slope, intercept = _theil_sen([ys[k] for k in others], [offsets[k] for k in others])
            residuals = [offsets[k] - (intercept + slope * ys[k]) for k in others]
            spread = max(1.4826 * _median([abs(r) for r in residuals]), FORM_MIN_SPREAD_SHARE * height)
            measured.append((offsets[i] - (intercept + slope * ys[i]), spread))
        off_line = sum(1 for off, _ in measured if abs(off) >= ROW_MIN_SHARE_OF_LINE * height)
        if off_line > max(1, int(FORM_MAX_OUTLIER_SHARE * len(series))):
            continue
        measured_rows = max(measured_rows, len(series))
        for (cell, _), (off, spread) in zip(series, measured):
            if abs(off) >= ROW_MIN_SHARE_OF_LINE * height and abs(off) / spread >= ROW_MIN_STRENGTH:
                out.append(Misplaced(page_index, cell, None, round(off, 2), round(spread, 3), "row"))
    if not measured_rows:
        return LayoutResult(False, reason=f"fewer than {FORM_MIN_ROWS} rows whose cells keep to their lines")
    return LayoutResult(True, out, pairs=measured_rows)
