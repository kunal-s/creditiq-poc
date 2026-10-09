"""Tables from word positions (FRD F-15.3). One builder serves digital PDFs, OCR pages and
spreadsheets, because all three are a page of positioned words.

How a table is read:
  1. find the header line (rule.start) and anchor each configured column to the header segment
     whose word matches the column's header pattern;
  2. split every data line into segments (a wide gap is a column break) and give each segment to
     the column whose edge it sits nearest (left edge for text columns, right edge for numbers);
  3. start a row on a line that qualifies (row_start, or a label with values); every other line
     joins the nearest row, so wrapped labels and vertically centred values stay together;
  4. normalise cells by the schema's column types; unparseable numbers stay null with the raw text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...config.models import ColRule, ColumnDef, ReadingConfig, TableRule
from ...pageindex import Line, Page, Word, union_bbox
from ...util import collapse_ws
from .normalise import to_date, to_number

NUM_RX = re.compile(r"^[(\-−–]?\s?(?:₹|Rs\.?)?\s?[\d,]*\d(?:\.\d+)?\)?(?:\s?(?:Cr|Dr)\.?)?$|^-$", re.I)


@dataclass
class Seg:
    text: str
    x0: float
    x1: float
    words: list[Word]


@dataclass
class TableResult:
    columns: list[str]
    rows: list[dict]
    page_start: int
    page_end: int
    bbox: list[float] | None
    sheet: str | None = None
    repairs: list[dict] = field(default_factory=list)
    unparsed: int = 0


def segments(line: Line, gap: float) -> list[Seg]:
    out: list[list[Word]] = []
    for w in line.words:
        if out and w.x0 - out[-1][-1].x1 <= gap:
            out[-1].append(w)
        else:
            out.append([w])
    return [Seg(" ".join(w.text for w in g), g[0].x0, g[-1].x1, g) for g in out]


def _anchor(cols: list[ColRule], block: list[Line], gap: float) -> dict[str, tuple[float, float]]:
    found: dict[str, tuple[float, float]] = {}
    for c in cols:
        rx, n = re.compile(c.header, re.I), 0
        hit = None
        for line in block:
            for seg in segments(line, gap):
                for w in seg.words:
                    if rx.search(w.text):
                        if n == c.nth:
                            hit = (seg.x0, seg.x1)
                            break
                        n += 1
                if hit:
                    break
            if hit:
                break
        if hit:
            found[c.name] = hit
    return found


def split_at_numeric_columns(segs: list[Seg], cols: list[ColRule], anchors: dict[str, tuple[float, float]]) -> list[Seg]:
    """A number that sits on a value column's edge (right edge for right-aligned columns, left edge
    otherwise) is that column's cell, even when wrapped text ends just before it and the gap alone
    would glue them into one segment."""
    edges = [(anchors[c.name][1], True) if c.align == "right" else (anchors[c.name][0], False) for c in cols[1:] if c.name in anchors]
    if not edges:
        return _split_adjacent_numbers(segs, cols, anchors)
    out: list[Seg] = []
    for seg in segs:
        cur: list[Word] = []
        for w in seg.words:
            if cur and NUM_RX.match(w.text) and any(abs((w.x1 if right else w.x0) - e) <= 3 for e, right in edges):
                out.append(Seg(" ".join(x.text for x in cur), cur[0].x0, cur[-1].x1, cur))
                cur = []
            cur.append(w)
        out.append(Seg(" ".join(x.text for x in cur), cur[0].x0, cur[-1].x1, cur))
    return _split_adjacent_numbers(out, cols, anchors)


def _split_adjacent_numbers(segs: list[Seg], cols: list[ColRule], anchors: dict[str, tuple[float, float]]) -> list[Seg]:
    """Two numbers closer together than the column gap are still two cells when each one's nearest
    column differs (tightly set statements run a figure into the next column's)."""
    out: list[Seg] = []
    for seg in segs:
        cur: list[Word] = []
        col = None
        for w in seg.words:
            wc = _assign(Seg(w.text, w.x0, w.x1, [w]), cols, anchors) if NUM_RX.match(w.text) else None
            if cur and wc and col and wc != col:
                out.append(Seg(" ".join(x.text for x in cur), cur[0].x0, cur[-1].x1, cur))
                cur = []
            cur.append(w)
            col = wc
        out.append(Seg(" ".join(x.text for x in cur), cur[0].x0, cur[-1].x1, cur))
    return out


def _assign(seg: Seg, cols: list[ColRule], anchors: dict[str, tuple[float, float]]) -> str | None:
    best, best_d = None, 1e9
    for c in cols:
        a = anchors.get(c.name)
        if not a:
            continue
        d = abs(seg.x1 - a[1]) if c.align == "right" else abs(seg.x0 - a[0])
        if d < best_d:
            best, best_d = c.name, d
    return best


def _find_header(pages: list[Page], rule: TableRule, from_page: int = 0) -> tuple[int, int] | None:
    rx = re.compile(rule.start, re.I)
    pm = re.compile(rule.page_match, re.I | re.M) if rule.page_match else None
    for pi in range(from_page, len(pages)):
        p = pages[pi]
        if pm and not pm.search(p.text()):
            continue
        for li, line in enumerate(p.content_lines()):
            if rx.search(line.text):
                return pi, li
    return None


@dataclass
class _DL:
    page: Page
    line: Line
    cells: dict[str, list[Seg]]
    y_abs: float
    is_start: bool = False


def build_table(rule: TableRule, defs: list[ColumnDef], pages: list[Page], reading: ReadingConfig) -> TableResult | None:
    found = _find_header(pages, rule)
    if not found:
        return None
    pi0, li0 = found
    gap = reading.column_gap
    cols = rule.columns
    end_rx = re.compile(rule.end, re.I) if rule.end else None
    start_rx = re.compile(rule.start, re.I)
    row_rx = re.compile(rule.row_start, re.I) if rule.row_start else None
    label_col = cols[0].name

    dls: list[_DL] = []
    anchors: dict[str, tuple[float, float]] = {}
    stop = False
    last_page = pi0
    for pi in range(pi0, len(pages) if rule.multi_page else pi0 + 1):
        p = pages[pi]
        lines = p.content_lines()
        if pi == pi0:
            block = lines[li0:li0 + 1 + rule.header_lines]
            data = lines[li0 + 1 + rule.header_lines:]
            anchors = _anchor(cols, block, gap)
        else:
            hdr = next((i for i, l in enumerate(lines) if start_rx.search(l.text)), None)
            if hdr is not None:
                block = lines[hdr:hdr + 1 + rule.header_lines]
                anchors = _anchor(cols, block, gap) or anchors
                data = lines[hdr + 1 + rule.header_lines:]
            else:
                data = lines
        if not anchors.get(label_col):
            return None
        for line in data:
            if end_rx and end_rx.search(line.text):
                stop = True
                break
            cells: dict[str, list[Seg]] = {}
            segs = split_at_numeric_columns(segments(line, gap), cols, anchors)
            if rule.attach == "heading" and not any(NUM_RX.match(sg.text) for sg in segs):
                cells[label_col] = segs  # a heading may run across the columns: all of it is the label
            else:
                for seg in segs:
                    col = _assign(seg, cols, anchors)
                    if col:
                        cells.setdefault(col, []).append(seg)
            if cells:
                dls.append(_DL(p, line, cells, pi * 100000 + line.words[0].yc))
        last_page = pi
        if stop:
            break

    def text_of(dl: _DL, col: str) -> str:
        return " ".join(s.text for s in dl.cells.get(col, []))

    for dl in dls:
        has_label = bool(dl.cells.get(label_col))
        has_values = any(c != label_col for c in dl.cells)
        if row_rx:
            dl.is_start = bool(row_rx.search(text_of(dl, rule.row_start_col or label_col).strip()))
        else:
            dl.is_start = (has_label and has_values) or (has_label and rule.text_only == "row")
    starts = [d for d in dls if d.is_start]
    if not starts:
        return None
    groups: dict[int, list[_DL]] = {id(s): [s] for s in starts}
    dropped = 0
    for d in dls:
        if d.is_start:
            continue
        label_only = bool(d.cells.get(label_col)) and not any(c != label_col for c in d.cells)
        prior = [s for s in starts if s.y_abs <= d.y_abs]
        if rule.attach == "heading":
            following = [s for s in starts if s.y_abs > d.y_abs]
            if label_only and following:
                groups[id(following[0])].append(d)
            else:
                dropped += 1
            continue
        if not row_rx and rule.text_only == "continuation" and label_only and prior:
            near = prior[-1]  # a wrapped label belongs to the row above it
        else:
            near = min(starts, key=lambda s: (abs(s.y_abs - d.y_abs), s.y_abs > d.y_abs))  # a tie goes to the earlier row
        if abs(near.y_abs - d.y_abs) > rule.max_attach and not (d.page is not near.page):
            dropped += 1
            continue
        groups[id(near)].append(d)

    skip = [re.compile(x, re.I) for x in rule.skip_rows]
    by_name = {c.name: c for c in cols}
    types = {c.name: c.type for c in defs}
    rows, unparsed = [], 0
    for s in starts:
        members = sorted(groups[id(s)], key=lambda d: d.y_abs)
        raw: dict[str, str] = {}
        for c in cols:
            parts = [" ".join(sg.text for sg in d.cells[c.name]) for d in members if d.cells.get(c.name)]
            if parts:
                raw[c.name] = collapse_ws(c.join.join(parts) if c.join != " " else " ".join(parts))
        if any(rx.search(raw.get(label_col, "")) for rx in skip):
            continue
        if not any(raw.values()):
            continue
        cells_out: dict[str, object] = {}
        for d in defs:
            c = by_name.get(d.name)
            if c is None or not c.emit:
                if c is None:
                    cells_out[d.name] = None
                continue
            r = raw.get(d.name)
            if r is None:
                cells_out[d.name] = None
            elif d.type == "number":
                v = to_number(r)
                unparsed += v is None and r.strip() not in ("", "-")
                cells_out[d.name] = v
            elif d.type == "date":
                v = to_date(r)
                unparsed += v is None
                cells_out[d.name] = v
            else:
                cells_out[d.name] = r
        boxes = [tuple(b) for d in members if (b := d.line.bbox())]
        pg = members[0].page
        src: dict = {"page": s.page.no, "bbox": union_bbox(boxes), "line_ids": [d.line.id for d in members]}
        if pg.source == "sheet":
            cells = [w.cell for d in members for w in d.line.words if w.cell]
            src = {"sheet": pg.sheet, "range": f"{cells[0]}:{cells[-1]}" if len(cells) > 1 else cells[0] if cells else None, "line_ids": src["line_ids"]}
        rows.append({"cells": cells_out, "raw": {k: v for k, v in raw.items() if by_name[k].emit}, "source": src})
    if not rows:
        return None
    first, last = pages[pi0], pages[last_page]
    allbox = union_bbox(tuple(r["source"]["bbox"]) for r in rows if r["source"].get("bbox"))
    res = TableResult([d.name for d in defs], rows, first.no, last.no, allbox, first.sheet if first.source == "sheet" else None, [], unparsed)
    if rule.repair and rule.repair.get("kind") == "running_balance":
        repair_running_balance(res, rule.repair, types)
    return res


def repair_running_balance(t: TableResult, cfg: dict, types: dict) -> None:
    """A bank statement's running balance is its own check (F-15.3). A row that breaks it is
    repaired arithmetically when exactly one single-cell explanation fits and the next row
    continues from the result. Never by a model; every repair is recorded."""
    d, c, b = cfg["debit"], cfg["credit"], cfg["balance"]
    rows = t.rows

    def num(r, k):
        v = r["cells"].get(k)
        return v if isinstance(v, (int, float)) else None

    def holds(pb, cur):
        cb = num(cur, b)
        return pb is not None and cb is not None and abs(pb + (num(cur, c) or 0) - (num(cur, d) or 0) - cb) < 0.005

    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        pb = num(prev, b)
        if pb is None or num(cur, b) is None or holds(pb, cur):
            continue
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        cb, cd, cc = num(cur, b), num(cur, d), num(cur, c)
        options: list[tuple[str, float]] = []
        expected = pb + (cc or 0) - (cd or 0)
        if nxt is None or holds(expected, nxt):
            options.append((b, expected))
        if cc is not None and cd is None and cb - pb >= 0 and (nxt is None or holds(cb, nxt)):
            options.append((c, cb - pb))
        if cd is not None and cc is None and pb - cb >= 0 and (nxt is None or holds(cb, nxt)):
            options.append((d, pb - cb))
        if len(options) == 1:
            col, new = options[0]
            t.repairs.append({"row": i, "column": col, "from": cur["cells"].get(col), "to": new, "page": cur["source"].get("page")})
            cur["cells"][col] = new
