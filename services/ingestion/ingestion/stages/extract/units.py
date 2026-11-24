"""The unit a document's amounts are printed in (FRD F-15.13; Story 5.3 of the classification restructure).

A unit statement is a unit word close after "in" ("Rs. in Crore", "Amount in Rs. Lacs", "All amounts in Indian Rupees",
"₹ in 000s"), or a bracket holding only a currency and a unit ("(Rs. '000)"). An amount ("Rs. 2,50,000") is never one.
Where a scale and the rupee are both named, the scale is the unit. The words are configuration (fields.yaml units);
the unit's name is what the engine scales by (thousand, lakh, crore, million; rupee is 1)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ...config.models import Units
from ...pageindex import Line, Page


@dataclass
class Unit:
    name: str
    text: str
    page: int
    line_id: str


def _tokens(text: str) -> list[str]:
    return re.findall(r"₹|'000|000's|000s|[a-z0-9]+", text.lower().replace("’", "'"))


def _unit_of(tokens: list[str], units: Units) -> str | None:
    named = {name for name, forms in units.words.items() for f in forms if f.lower().rstrip(".") in tokens}
    scales = sorted(named - {"rupee"})
    return scales[0] if len(scales) == 1 else ("rupee" if named == {"rupee"} else None)


def in_line(text: str, units: Units) -> str | None:
    """The unit the line states, or None."""
    low = text.lower()
    for m in re.finditer(r"\(([^()]{1,30})\)", low):          # (Rs. '000), (₹ in lakhs)
        toks = _tokens(m.group(1))
        cur = {c.lower().rstrip(".") for c in units.currency}
        rest = [t for t in toks if t not in cur and t != "in"]
        if rest and len(rest) <= 2:
            u = _unit_of(rest, units)
            if u:
                return u
    toks = _tokens(low)
    for i, t in enumerate(toks):
        if t == "in":
            u = _unit_of(toks[i + 1:i + 1 + units.reach], units)
            if u:
                return u
    return None


def find(pages: list[Page], units: Units, before: dict[int, int] | None = None,
         zones: dict[int, list[Line]] | None = None) -> Unit | None:
    """The document's unit: the first stated in a table's caption (the lines above its header, `before`: page -> line
    index), then in a page's title lines (`zones`), page by page."""
    for p in pages:
        lines = p.content_lines()
        scan = lines[:before[p.no] + 1] if before and p.no in before else []
        scan += [l for l in (zones or {}).get(p.no, []) if l not in scan]
        for l in scan:
            u = in_line(l.text, units)
            if u:
                return Unit(u, l.text.strip(), p.no, l.id)
    return None
