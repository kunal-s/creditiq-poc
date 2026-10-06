"""Where a value was read: page, line, text and box (FRD principle 2, F-15.4)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...pageindex import Line, Page, union_bbox
from ...util import collapse_ws


@dataclass
class Evidence:
    page: int
    line_ids: list[str]
    text: str
    bbox: list[float] | None
    sheet: str | None = None
    cells: list[str] = field(default_factory=list)

    def source(self) -> dict:
        if self.sheet is not None:
            rng = self.cells[0] if len(self.cells) == 1 else f"{self.cells[0]}:{self.cells[-1]}" if self.cells else None
            return {"kind": "cell", "page": self.page, "sheet": self.sheet, "range": rng, "text": self.text}
        return {"kind": "page", "page": self.page, "text": self.text, "bbox": self.bbox}


def evidence_for_lines(page: Page, parts: list[tuple[Line, int, int]]) -> Evidence:
    """Evidence from (line, char_start, char_end) parts; the box covers exactly those characters."""
    boxes, texts, ids, cells = [], [], [], []
    for line, a, b in parts:
        bb = line.bbox_for(a, b)
        if bb:
            boxes.append(tuple(bb))
        texts.append(line.text[a:b] if (a, b) != (0, len(line.text)) else line.text)
        ids.append(line.id)
        if page.source == "sheet":
            cells += [w.cell for w, (x, y) in zip(line.words, line.spans) if x < b and y > a and w.cell]
    text = collapse_ws(" ".join(texts))[:400]
    return Evidence(page.no, ids, text, union_bbox(boxes), page.sheet if page.source == "sheet" else None, cells)


def lines_overlapping(page: Page, start: int, end: int) -> list[tuple[Line, int, int]]:
    """Map a character range in page.text() back to (line, a, b) parts."""
    parts, pos = [], 0
    for line in page.content_lines():
        ls, le = pos, pos + len(line.text)
        if ls < end and le > start:
            parts.append((line, max(start, ls) - ls, min(end, le) - ls))
        pos = le + 1  # the joining newline
    return parts
