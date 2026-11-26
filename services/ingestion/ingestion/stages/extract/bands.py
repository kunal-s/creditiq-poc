"""Tables read from where their figures line up (the body first, the header to name what the body shows).

The heading reader (kwtables.py) places each column where its heading is printed and puts every piece of a row in the
nearest column it has a name for. A heading centred over its figures, a heading that wraps over two lines, a column the
configuration does not name (a serial number, more years than it asks for) or a title that holds a date then moves the
columns, and the pieces land in the wrong ones without anything showing it.

This reader takes the table's geometry from the body instead, and words only name what the body shows:

1. A body is a run of lines that print figures, read without any vocabulary. Lines without figures inside it are
   headings or the parts of wrapped labels.
2. The figures of a body line up in vertical bands; each band is a column, named or not. Figures are set right, so a
   band's region runs from the right edge of the band before it to its own right edge. The text to the left of the
   first band is the row's label.
3. The header is the text above the body that sits within those regions: a line whose text runs across a band's edge (a
   title, a running page heading, a note on the unit) is not a column heading and ends the header. All the header text
   over a band, over every line of the header, is that band's heading ("Integrated" over "tax"; "For the Period ended"
   over "31.03.2026"). A band is a year column by the date its heading holds, or the column its heading names among the
   configured headings; a band nothing names is read and left out, never merged into another.
4. Each figure goes to the band whose region holds it; one outside every band is not read. A label that is visibly
   unfinished carries on onto the next line, a line that starts in lower case carries on the label above it, and a cell
   whose figure wraps onto the next line is joined.

The readings are proposed to the table's contract (contract.py), which keeps the one that meets it best."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...config.models import ColumnDef, IngestionConfig, KwTable
from ...pageindex import Line, Page, Word, union_bbox
from ...util import collapse_ws
from .normalise import to_number
from .tables import NUM_RX, TableResult, figure_words, segments

_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_DASH = ("-", "–", "—")
MAX_GAP_LINES = 3          # lines without figures a body may hold in a row (headings, wrapped labels)
HEADER_LINES = 6           # lines above a body looked at for its header
EDGE_TOL = 6.0             # how far past a band's right edge a figure or a heading may still end


@dataclass
class _Band:
    x0: float
    x1: float
    lines: set = field(default_factory=set)


@dataclass
class _Row:
    label: list[str]
    cells: dict[int, str]
    lines: list[Line]
    page: Page
    unread: int = 0
    open_cells: set = field(default_factory=set)


_CUT = re.compile(r"^-?[\d,]*\d\.$")     # a figure whose decimals wrapped onto the next line ("10468523." over "86")


def _is_figure(w: Word) -> bool:
    return bool(NUM_RX.match(w.text) or _CUT.match(w.text))


def _value_token(w: Word) -> bool:
    """A figure that is a value: not a bare year (a heading's "2021 - 2022") and not a dash."""
    return _is_figure(w) and w.text not in _DASH and not _YEAR.match(w.text)


def _split(line: Line, gap: float) -> tuple[list[Word], list[Word]]:
    """A line's label words and its figures. Figures before the first word of text (a row's serial number) are part
    of the label; footnote references in front of figures are not read."""
    words = figure_words(line.words, gap)
    first_text = next((i for i, w in enumerate(words) if not _is_figure(w)), len(words))
    label = words[:first_text] if first_text < len(words) else []
    figs: list[Word] = []
    for w in words[first_text:]:
        (figs if _is_figure(w) else label).append(w)
    if first_text == len(words):          # a line of figures only
        figs = words
    return label, figs


def _is_data(line: Line, gap: float) -> bool:
    _, figs = _split(line, gap)
    if any(_value_token(w) for w in figs):
        return True
    # A row of dashes only ("Exceptional items  -  -") is a row; a heading of years and dashes is not.
    return bool(figs) and all(w.text in _DASH for w in figs) and bool(_split(line, gap)[0])


def _bodies(lines: list[Line], gap: float, breaks) -> list[list[int]]:
    """Runs of lines with figures, with up to MAX_GAP_LINES lines without figures inside; a line `breaks` names (the
    header of another table, a title) ends a run."""
    out: list[list[int]] = []
    cur: list[int] = []
    quiet: list[int] = []
    for i, line in enumerate(lines):
        if _is_data(line, gap):
            if cur and quiet:
                cur += quiet
            quiet = []
            cur.append(i)
            continue
        if not cur:
            continue
        if breaks(lines, i) or len(quiet) >= MAX_GAP_LINES:
            out.append(cur)
            cur, quiet = [], []
            continue
        quiet.append(i)
    if cur:
        out.append(cur)
    return out


def _bands(lines: list[Line], body: list[int], gap: float) -> list[_Band]:
    """The body's columns: figures whose spans overlap are one column; a column printed on too few lines is not one."""
    toks = [(w.x0, w.x1, i) for i in body for w in _split(lines[i], gap)[1]]
    toks.sort()
    bands: list[_Band] = []
    for x0, x1, i in toks:
        if bands and x0 <= bands[-1].x1 + 1:
            b = bands[-1]
            b.x1 = max(b.x1, x1)
            b.lines.add(i)
        else:
            bands.append(_Band(x0, x1, {i}))
    data = [i for i in body if _is_data(lines[i], gap)]
    need = max(2, int(0.15 * len(data) + 0.999)) if len(data) > 2 else 1
    return [b for b in bands if len(b.lines) >= need]


def _regions(bands: list[_Band], label_right: float) -> list[tuple[float, float]]:
    """Region 0 is the label's; region k is band k's: from the right edge of the band before it to its own."""
    first = bands[0]
    start = (label_right + first.x0) / 2 if label_right < first.x0 else first.x0 - 2
    regions = [(-1e9, start)]
    prev = start
    for b in bands:
        regions.append((prev, b.x1 + EDGE_TOL))
        prev = b.x1 + EDGE_TOL
    regions[-1] = (regions[-1][0], 1e9)
    return regions


def _region_of(x0: float, x1: float, regions: list[tuple[float, float]]) -> int | None:
    """The region a piece of header text belongs to: the one its middle falls in (a heading over a narrow column is
    wider than the figures under it)."""
    mid = (x0 + x1) / 2
    for k, (a, b) in enumerate(regions):
        if a <= mid <= b:
            return k
    return None


def _spans_columns(x0: float, x1: float, bands: list[_Band]) -> bool:
    """A piece of text over the figures of two columns or more: a sentence (a title, a running page heading, a note on
    the unit), not a column heading."""
    return sum(1 for b in bands if x0 < b.x1 and b.x0 < x1) >= 2


_UNFINISHED = re.compile(r"(?:[,&/\-–(]|\b(?:and|or|of|the|for|to|in|on|with|by|from|at))\s*$", re.I)


def _unfinished(text: str) -> bool:
    """A label that visibly carries on onto the next line (a bracket left open, a comma, a joining word). A heading
    that ends with a colon opens a section; it is not unfinished."""
    t = text.strip()
    return bool(t) and (t.count("(") > t.count(")") or bool(_UNFINISHED.search(t)))


def _carries_on(previous: str, text: str) -> bool:
    """Whether `text` carries on the label `previous`: the previous one is unfinished, or this one starts in lower case."""
    return _unfinished(previous) or text.strip()[:1].islower()


def _figure_region(w: Word, regions: list[tuple[float, float]]) -> int | None:
    """A figure's band: the region its right edge falls in (figures are set right)."""
    for k, (a, b) in enumerate(regions[1:], start=1):
        if a < w.x1 <= b:
            return k
    return None


@dataclass
class Reading:
    page_index: int
    body: list[int]
    bands: list[_Band]
    regions: list[tuple[float, float]]
    names: dict[int, str]           # region -> column name (label 0 included)


def _name(header: list[Line], gap: float, regions, bands, spec: KwTable, h) -> dict[int, str] | None:
    """Each band's name from the header text over it: a date makes it a year column (latest first), else the
    configured heading its text names. None when the header names no value column."""
    texts: dict[int, list[str]] = {}
    for line in header:
        for sg in segments(line, gap):
            k = _region_of(sg.x0, sg.x1, regions)
            if k is not None:
                texts.setdefault(k, []).append(sg.text)
    names: dict[int, str] = {0: spec.label}
    dated: list[tuple] = []
    scored: dict[str, tuple[int, int]] = {}
    for k in range(1, len(regions)):
        text = " ".join(texts.get(k, []))
        if not text:
            continue
        d = h._period_date(text) if spec.periods else None
        if d is not None:
            dated.append((d, bands[k - 1].x0, k))
            continue
        for col, phrases in spec.headings.items():
            if col == spec.label:
                continue
            s = h._matched(phrases, text, spec.heading_cover)
            if s and (col not in scored or s > scored[col][0]):
                scored[col] = (s, k)
    for col, (_, k) in scored.items():
        if k not in names:
            names[k] = col
    dated.sort(key=lambda t: (-t[0].toordinal(), t[1]))
    for col, (_, _, k) in zip(spec.periods, dated):
        names.setdefault(k, col)
    value_cols = [n for k, n in names.items() if k and n not in spec.ignore]
    return names if value_cols else None


def _header(lines: list[Line], first: int, gap: float, bands: list[_Band]) -> list[Line]:
    """The lines above a body that are its header. A line with a piece of text over the figures of two columns or more
    (a title, a running page heading, a note on the unit) is not a column heading and ends it, as does a line of
    figures."""
    out: list[Line] = []
    for i in range(first - 1, max(-1, first - 1 - HEADER_LINES), -1):
        line = lines[i]
        if _is_data(line, gap):
            break
        if any(_spans_columns(sg.x0, sg.x1, bands) for sg in segments(line, gap)):
            break
        out.insert(0, line)
    return out


def readings(cfg: IngestionConfig, spec: KwTable, defs: list[ColumnDef], pages: list[Page], h) -> list[TableResult]:
    """Every table the bodies of these pages hold that its header names, each read as the table `defs` describes.
    `h` is the table's heading reader (kwtables.KwHeader): its vocabulary names the columns and its headers end a body.
    Only for a table whose columns other than its label are figures."""
    types = {d.name: d.type for d in defs}
    if any(t != "number" for n, t in types.items() if n != spec.label and n not in spec.ignore):
        return []
    gap = cfg.routing.reading.column_gap

    def breaks(lines: list[Line], i: int) -> bool:
        return bool(h._block(lines, i)) or id(lines[i]) in h.titles and _part_title(h, lines[i])

    per_page = []
    for pi, p in enumerate(pages):
        lines = p.content_lines()
        per_page.append((lines, _bodies(lines, gap, breaks)))
    out: list[TableResult] = []
    for pi, (lines, bodies) in enumerate(per_page):
        for bi, body in enumerate(bodies):
            bands = _bands(lines, body, gap)
            if not bands:
                continue
            label_right = max((w.x1 for i in body for w in _split(lines[i], gap)[0] if w.x1 < bands[0].x0), default=bands[0].x0)
            regions = _regions(bands, label_right)
            first = next(i for i in body if _is_data(lines[i], gap))
            header = _header(lines, first, gap, bands)
            names = _name(header, gap, regions, bands, spec, h)
            if names is None:
                continue
            parts = [(pi, body, regions)]
            # A body that ends its page carries on at the top of the next when its figures line up the same way and
            # nothing between (a title of another part, another header) says a new table begins.
            npi, nbi = pi, bi
            while nbi == len(per_page[npi][1]) - 1 and npi + 1 < len(per_page):
                nlines, nbodies = per_page[npi + 1]
                if not nbodies:
                    break
                nb = nbodies[0]
                nbands = _bands(nlines, nb, gap)
                if len(nbands) != len(bands) or any(abs(a.x1 - b.x1) > EDGE_TOL for a, b in zip(nbands, bands)):
                    break
                if any(breaks(nlines, i) for i in range(0, nb[0])):
                    break
                nlabel = max((w.x1 for i in nb for w in _split(nlines[i], gap)[0] if w.x1 < nbands[0].x0), default=nbands[0].x0)
                parts.append((npi + 1, nb, _regions(nbands, nlabel)))
                npi, nbi = npi + 1, 0
            res = _build(parts, per_page, pages, names, spec, defs, h, gap)
            if res is not None:
                out.append(res)
    return out


def _gap(above: Line, below: Line) -> float:
    a, b = above.bbox(), below.bbox()
    return (b[1] - a[3]) if a and b else 1e9


def _row_gap(lines: list[Line], body: list[int], gap: float) -> float:
    """The usual space between two rows of the body: between consecutive lines that both print figures."""
    gaps = sorted(_gap(lines[a], lines[b]) for a, b in zip(body, body[1:])
                  if b == a + 1 and _is_data(lines[a], gap) and _is_data(lines[b], gap))
    return gaps[len(gaps) // 2] if gaps else 0.0


def _part_title(h, line: Line) -> bool:
    from ..pages import _titles_of
    return bool(h.kw and _titles_of(h.kw, line.text))


def _build(parts, per_page, pages, names, spec: KwTable, defs: list[ColumnDef], h, gap: float) -> TableResult | None:
    rows: list[_Row] = []
    pending: list[str] = []
    used: list[str] = []
    for pi, body, regions in parts:
        lines = per_page[pi][0]
        page = pages[pi]
        pitch = _row_gap(lines, body, gap)
        prev_line: Line | None = None
        for i in body:
            line = lines[i]
            used.append(line.id)
            tight = prev_line is not None and _gap(prev_line, line) < 0.5 * pitch
            prev_line = line
            label_words, figs = _split(line, gap)
            edge = regions[0][1]
            # A figure in the label's region is part of the label ("Final dividend of Rs. 6.75 per share").
            label_words = sorted([w for w in label_words if w.x0 < edge] + [w for w in figs if w.x1 <= edge], key=lambda w: w.x0)
            figs = [w for w in figs if w.x1 > edge]
            text = collapse_ws(" ".join(w.text for w in label_words))
            if not _is_data(line, gap):
                if not text:
                    continue
                if tight and rows and not pending:
                    rows[-1].label.append(text)          # set flush under the row above: its label wrapped
                    rows[-1].lines.append(line)
                elif pending:
                    pending.append(text)
                elif rows and _carries_on(" ".join(rows[-1].label), text):
                    rows[-1].label.append(text)          # a label wrapped onto the next line
                    rows[-1].lines.append(line)
                elif _unfinished(text):
                    pending.append(text)                 # unfinished: it carries on into the row below
                else:
                    rows.append(_Row([text], {}, [line], page))   # a heading inside the table
                continue
            cells: dict[int, list[str]] = {}
            unread = 0
            for w in figs:
                k = _figure_region(w, regions)
                if k is None:
                    unread += 1
                    continue
                cells.setdefault(k, []).append(w.text)
            if pending:
                rows.append(_Row(pending + ([text] if text else []), {k: " ".join(v) for k, v in cells.items()}, [line], page, unread))
                pending = []
                continue
            if rows and text and _carries_on(" ".join(rows[-1].label), text) and rows[-1].cells:
                # The row above wraps onto this line: its label goes on, and a figure that wrapped joins its first part.
                prev = rows[-1]
                prev.label.append(text)
                prev.lines.append(line)
                for k, v in cells.items():
                    piece = " ".join(v)
                    if k in prev.cells and re.search(r"[\d.]$", prev.cells[k]) and re.fullmatch(r"\d+", piece):
                        prev.cells[k] += piece
                    elif k in prev.cells:
                        prev.unread += 1
                    else:
                        prev.cells[k] = piece
                prev.unread += unread
                continue
            rows.append(_Row([text] if text else [], {k: " ".join(v) for k, v in cells.items()}, [line], page, unread))
    if pending:
        rows.append(_Row(pending, {}, [], pages[parts[-1][0]]))
    # A table ends with its last row that prints a figure: label-only lines after it are notes printed under it.
    while rows and not rows[-1].cells:
        rows.pop()
    if not rows:
        return None
    out_rows, unparsed = [], 0
    for r in rows:
        cells_out: dict[str, object] = {d.name: None for d in defs}
        raw: dict[str, str] = {}
        label = collapse_ws(" ".join(r.label))
        cells_out[spec.label] = label or None
        if label:
            raw[spec.label] = label
        for k, text in r.cells.items():
            col = names.get(k)
            if col is None or col in spec.ignore or col not in cells_out:
                continue
            v = 0 if spec.dash_is_zero and text.strip() in _DASH else to_number(text)
            if v is None and text.strip() not in ("", *_DASH):
                unparsed += 1
            cells_out[col] = v
            raw[col] = text
        unparsed += r.unread
        boxes = [tuple(b) for line in r.lines if (b := line.bbox())]
        out_rows.append({"cells": cells_out, "raw": raw,
                         "source": {"page": r.page.no, "bbox": union_bbox(boxes) if boxes else None,
                                    "line_ids": [line.id for line in r.lines],
                                    "line": collapse_ws(" ".join(line.text for line in r.lines))[:400]}})
    first, last = pages[parts[0][0]], pages[parts[-1][0]]
    allbox = union_bbox(tuple(r["source"]["bbox"]) for r in out_rows if r["source"].get("bbox"))
    return TableResult([d.name for d in defs], out_rows, first.no, last.no, allbox, None, [], unparsed,
                       method="keywords", claimed=used)
