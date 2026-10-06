"""Stage 2b: the route profile (FRD F-07.1). Facts about how the document was read, kept so a
reviewer and the confidence step can see them. Thresholds are configuration."""

from __future__ import annotations

from ..pageindex import Page


def profile(pages: list[Page]) -> dict:
    routes = [{"page": p.no, "route": {"text_layer": "text", "ocr": "ocr", "sheet": "sheet"}[p.source]} for p in pages]
    kinds = sorted({r["route"] for r in routes})
    table_pages = 0
    for p in pages:
        lines = p.content_lines()
        multi = sum(1 for l in lines if len(l.cells()) >= 3)
        if lines and multi / len(lines) >= 0.25:
            table_pages += 1
    return {
        "route": kinds[0] if len(kinds) == 1 else "mixed",
        "pages": len(pages),
        "page_routes": routes,
        "table_pages": table_pages,
        "ocr_pages": sum(1 for p in pages if p.source == "ocr"),
        "blank_pages": [p.no for p in pages if p.blank],
        "dropped_rotated_chars": 0,
    }
