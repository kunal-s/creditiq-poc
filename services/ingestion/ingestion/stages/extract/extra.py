"""A document's extra data (Story 6.4): what is printed on its pages that no field and no table claimed. A line that
pairs a label with a value is kept as a pair; a run of such lines is kept as a table, described by the heading printed
above it (or, with none, by its column headings, or by the model). Each item keeps its page. Nothing here is shown on
screen: the case summary and the assistant read it (Story 6.5), and the leftover fill reads its pages (Story 6.2)."""

from __future__ import annotations

import re

from ...config.models import ExtraDataConfig
from ...llm.provider import ModelError, ModelRequest
from ...llm.recorder import ModelClient
from ...pageindex import Line, Page
from .normalise import to_date
from .tables import NUM_RX, segments

_LETTERS = re.compile(r"[A-Za-z]{3,}")
_IDENT = re.compile(r"^[A-Z0-9][A-Z0-9/-]{5,}$")


def _is_value(text: str) -> bool:
    t = text.strip()
    return bool(NUM_RX.match(t)) or to_date(t) is not None or bool(_IDENT.match(t) and re.search(r"\d", t))


def _pair(line: Line, gap: float, cfg: ExtraDataConfig) -> tuple[str, list[str]] | None:
    """(label, values) when the line pairs a label with values, else None."""
    segs = [s.text.strip() for s in segments(line, gap) if s.text.strip()]
    if len(segs) >= 2 and _LETTERS.search(segs[0]) and all(_is_value(s) for s in segs[1:]):
        label, values = segs[0].rstrip(" :"), segs[1:]
    else:
        m = re.match(r"^\s*([^:]{3,}?)\s*:\s*(.+?)\s*$", line.text)
        if not m or not _LETTERS.search(m[1]):
            return None
        label, values = m[1], [m[2]]
    if len(label) > cfg.max_label_chars or any(len(v) > cfg.max_value_chars for v in values):
        return None
    if any(re.search(r"_{3,}", v) for v in values):
        return None          # a blank on a form, left to be filled in
    return label, values


def _heading(line: Line, gap: float) -> bool:
    segs = [s.text for s in segments(line, gap)]
    return len(segs) == 1 and bool(_LETTERS.search(segs[0])) and not any(_is_value(w) for w in segs[0].split())


def _columns(line: Line, gap: float) -> list[str] | None:
    segs = [s.text.strip() for s in segments(line, gap)]
    return segs if len(segs) >= 2 and all(_LETTERS.search(s) or to_date(s) for s in segs) else None


def collect(pages: list[Page], claimed: set[str], gap: float, cfg: ExtraDataConfig, model: ModelClient | None = None,
            describe_prompt=None) -> tuple[dict, list[dict]]:
    """{"pairs": [...], "tables": [...]} for the lines of `pages` not in `claimed`, and any model trace."""
    pairs: list[dict] = []
    tables: list[dict] = []
    trace: list[dict] = []
    for p in pages:
        lines = p.content_lines()
        free = [l.id not in claimed for l in lines]
        found = [(_pair(l, gap, cfg) if free[i] else None) for i, l in enumerate(lines)]
        i = 0
        while i < len(lines):
            if found[i] is None:
                i += 1
                continue
            j = i
            while j + 1 < len(lines) and found[j + 1] is not None and len(found[j + 1][1]) >= 1:
                j += 1
            run = list(range(i, j + 1))
            # A first line whose values are all dates heads the columns ("Particulars  31 March 2024  31 March 2023").
            heads_columns = (len(run) > cfg.min_table_rows and all(to_date(v) for v in found[i][1])
                             and not all(to_date(v) for v in found[i + 1][1]))
            if len(run) >= cfg.min_table_rows + (1 if heads_columns else 0):
                if heads_columns:
                    cols = [found[i][0], *found[i][1]]
                    run, top = run[1:], i - 1
                else:
                    cols = _columns(lines[i - 1], gap) if i >= 1 and free[i - 1] else None
                    top = i - 1 - (1 if cols else 0)
                heading = next((lines[k].text.strip() for k in range(top, max(-1, top - cfg.heading_reach), -1)
                                if k >= 0 and free[k] and _heading(lines[k], gap)), None)
                table = {"page": p.no, "rows": [[found[k][0], *found[k][1]] for k in run],
                         "columns": cols or [], "line_ids": [lines[k].id for k in ([i] if heads_columns else []) + run]}
                if heading:
                    table.update(description=heading, described_by="heading")
                elif cols:
                    table.update(description="Table of " + ", ".join(cols), described_by="columns")
                else:
                    table.update(description=None, described_by="none")
                    if model is not None and describe_prompt is not None:
                        text = "\n".join(" | ".join(r) for r in table["rows"][:12])
                        try:
                            ans = model.call(ModelRequest("describe_table", describe_prompt.system.strip(),
                                                          describe_prompt.user.replace("{{rows}}", text).strip(),
                                                          {"type": "object", "properties": {"description": {"type": "string"}},
                                                           "required": ["description"], "additionalProperties": False}))
                            got = str((ans or {}).get("description") or "").strip()
                            if got:
                                table.update(description=got[:200], described_by="model")
                        except ModelError as e:
                            trace.append({"call": "describe_table", "error": e.code})
                tables.append(table)
            else:
                for k in run:
                    pairs.append({"label": found[k][0], "values": found[k][1], "page": p.no, "line_id": lines[k].id})
            i = j + 1
    return {"pairs": pairs, "tables": tables}, trace
