"""A file's running header and footer: the lines printed again on its pages (keywords.yaml settings.zones.furniture).

A line near a page's top or bottom whose text repeats on enough of the file's pages, its digits read as one mark so
that "Page 3 of 6" and "Page 4 of 6" are the same line, is furniture. It is found from the file's own pages, with no
words configured. Furniture is the strongest statement of what a document is and which period it covers (it is on
every page of it), and it is not a title of the page it sits on: a document's identity is read from it first
(identity.py), and a run of pages that carry the same furniture is one document's (pages.py)."""

from __future__ import annotations

import math
import re
from collections import Counter

from ..config.models import KwFurniture
from ..pageindex import Line, Page


def norm(text: str) -> str:
    """A line's text compared across pages: case and spacing folded, every run of digits one mark."""
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text).strip().casefold())


def _edge(lines: list[Line], n: int) -> list[tuple[Line, str]]:
    top = [(l, "top") for l in lines[:n]]
    bottom = [(l, "bottom") for l in lines[-n:] if l not in lines[:n]]
    return top + bottom


def mark(pages: list[Page], rules: KwFurniture) -> None:
    """Mark each page's furniture lines (`page._furniture`: line id -> "top" | "bottom") and the furniture it shares
    with the file (`page._furniture_keys`: the lines' compared text)."""
    edges = {p.no: _edge(p.content_lines(), rules.edge_lines) for p in pages}
    seen: Counter = Counter()
    for p in pages:
        seen.update({norm(l.text) for l, _ in edges[p.no] if l.text.strip()})
    counted = [p for p in pages if p.content_lines()]
    need = max(rules.min_pages, math.ceil(rules.min_share * len(counted)))
    for p in pages:
        mine = {l.id: where for l, where in edges[p.no] if l.text.strip() and seen[norm(l.text)] >= need}
        p._furniture = mine                                          # type: ignore[attr-defined]
        p._furniture_keys = {norm(l.text) for l, _ in edges[p.no] if l.id in mine}   # type: ignore[attr-defined]


def lines(page: Page, where: str | None = None) -> list[Line]:
    """The page's furniture lines (top, bottom or both), in page order."""
    marked = getattr(page, "_furniture", {}) or {}
    return [l for l in page.content_lines() if l.id in marked and (where is None or marked[l.id] == where)]


def keys(page: Page) -> set[str]:
    return getattr(page, "_furniture_keys", set()) or set()


def is_furniture(page: Page, line: Line) -> bool:
    return line.id in (getattr(page, "_furniture", {}) or {})
