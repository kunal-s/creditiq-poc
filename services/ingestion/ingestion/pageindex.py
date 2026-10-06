"""The page index: every later stage reads this, never the file (FRD F-07.1).

Coordinates are PDF points with the origin at the top left. Spreadsheet cells use a
virtual grid (100 points per column, 20 per row) so the same table code reads them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float = 1.0
    cell: str | None = None  # "B7" for spreadsheet cells

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


def union_bbox(boxes: Iterable[tuple[float, float, float, float]]) -> list[float] | None:
    bs = list(boxes)
    if not bs:
        return None
    return [round(min(b[0] for b in bs), 2), round(min(b[1] for b in bs), 2),
            round(max(b[2] for b in bs), 2), round(max(b[3] for b in bs), 2)]


@dataclass
class Line:
    page: int
    idx: int
    text: str
    words: list[Word]
    spans: list[tuple[int, int]]  # char span of each word inside `text`
    boilerplate: bool = False

    @property
    def id(self) -> str:
        return f"p{self.page}.l{self.idx}"

    @property
    def y0(self) -> float:
        return min(w.y0 for w in self.words)

    @property
    def y1(self) -> float:
        return max(w.y1 for w in self.words)

    def bbox(self) -> list[float] | None:
        return union_bbox((w.x0, w.y0, w.x1, w.y1) for w in self.words)

    def bbox_for(self, start: int, end: int) -> list[float] | None:
        """Box of the words overlapping text[start:end]."""
        hit = [w for w, (a, b) in zip(self.words, self.spans) if a < end and b > start]
        return union_bbox((w.x0, w.y0, w.x1, w.y1) for w in hit) or self.bbox()

    def cells(self) -> list[str]:
        """The line split into column segments (two or more spaces)."""
        return [c for c in re.split(r"\s{2,}", self.text) if c]


@dataclass
class Page:
    no: int
    source: str  # text_layer | ocr | sheet
    width: float = 0.0
    height: float = 0.0
    words: list[Word] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    grade: str = "A"
    reasons: list[str] = field(default_factory=list)
    reading_trust: float = 1.0
    ocr_conf: float | None = None
    sheet: str | None = None
    blank: bool = False

    def content_lines(self) -> list[Line]:
        return [l for l in self.lines if not l.boilerplate]

    def text(self) -> str:
        return "\n".join(l.text for l in self.content_lines())

    def summary(self) -> dict:
        return {"page": self.no, "source": self.source, "width": round(self.width, 2), "height": round(self.height, 2), "grade": self.grade, "reasons": list(self.reasons),
                "reading_trust": round(self.reading_trust, 4), "ocr_conf": None if self.ocr_conf is None else round(self.ocr_conf, 2),
                "sheet": self.sheet, "blank": self.blank, "words": len(self.words)}

    def to_json(self) -> dict:
        return {**self.summary(),
                "lines": [{"id": l.id, "text": l.text, "boilerplate": l.boilerplate,
                           "words": [[w.text, round(w.x0, 2), round(w.y0, 2), round(w.x1, 2), round(w.y1, 2), round(w.conf, 3), w.cell] for w in l.words]}
                          for l in self.lines]}


def build_lines(page_no: int, words: list[Word], *, y_tol: float, column_gap: float, boilerplate: list[re.Pattern]) -> list[Line]:
    """Group words into lines by vertical position; a wide gap inside a line becomes two spaces."""
    ws = sorted(words, key=lambda w: (w.yc, w.x0))
    groups: list[list[Word]] = []
    for w in ws:
        if groups:
            g = groups[-1]
            mean = sum(x.yc for x in g) / len(g)
            if abs(w.yc - mean) <= y_tol:
                g.append(w)
                continue
        groups.append([w])
    lines: list[Line] = []
    for i, g in enumerate(groups):
        g.sort(key=lambda w: w.x0)
        parts: list[str] = []
        spans: list[tuple[int, int]] = []
        pos = 0
        for j, w in enumerate(g):
            if j:
                sep = "  " if (w.x0 - g[j - 1].x1) > column_gap else " "
                parts.append(sep)
                pos += len(sep)
            parts.append(w.text)
            spans.append((pos, pos + len(w.text)))
            pos += len(w.text)
        text = "".join(parts)
        line = Line(page=page_no, idx=i + 1, text=text, words=g, spans=spans)
        line.boilerplate = any(rx.search(text.strip()) for rx in boilerplate)
        lines.append(line)
    return lines
