"""The model pass for a table no configured layout found (FRD F-15.2, F-15.3, F-15.4).

The layouts in tables.py run first. For a table they cannot find, and that the type's configuration lets the
model map (`model_tables`), the model is shown the candidate pages as numbered lines and returns the table's rows:
for each row, the line(s) its label is printed on and, for each figure column, the line its figure sits on and
which figure on that line it is (1 for the first from the left). The model never writes a figure or a label: code
reads both from the lines it named, and a line that is not there, or a figure that is not on its line, is
rejected (F-15.4). The table is marked as mapped by the model, and the document goes to a person once for it."""

from __future__ import annotations

import re

from ...config.models import ColumnDef, IngestionConfig, ModelTable
from ...llm.provider import ModelError, ModelRequest
from ...llm.recorder import ModelClient
from ...pageindex import Line, Page, Word, union_bbox
from ...util import collapse_ws
from .normalise import to_date, to_number
from .tables import FOOTNOTE_RX, NUM_RX, TableResult, figure_words, segments

DASHES = ("-", "–", "—")


def candidate_pages(pages: list[Page], spec: ModelTable) -> list[Page]:
    """The pages whose opening lines name the table, and the pages after each, up to the configured number."""
    rxs = [re.compile(rx, re.I) for rx in spec.pages]
    keep: list[int] = []
    for i, p in enumerate(pages):
        head = " ".join(l.text for l in p.content_lines()[:spec.head_lines])
        if any(rx.search(head) for rx in rxs):
            keep += [j for j in range(i, min(i + spec.span, len(pages))) if j not in keep]
    return [pages[j] for j in sorted(keep)[:spec.max_pages]]


def figures(line: Line, gap: float) -> list[Word]:
    """The figures printed on a line, left to right, without the footnote references in front of them."""
    return [w for w in figure_words(line.words, gap) if NUM_RX.match(w.text)]


def label_text(lines: list[Line], gap: float) -> str:
    """A row's label: the words of its label lines that are neither figures nor footnote references."""
    words = [w.text for line in lines for w in figure_words(line.words, gap)
             if not NUM_RX.match(w.text) and not FOOTNOTE_RX.match(w.text)]
    return collapse_ws(" ".join(words))


def text_segments(line: Line, gap: float) -> list[str]:
    """The pieces of text a line prints apart from its figures, left to right (a narration, a reference, a name)."""
    return [sg.text for sg in segments(line, gap, figure_words(line.words, gap)) if not NUM_RX.match(sg.text)]


def table_schema(columns: list[str], text_columns: list[str] | None = None) -> dict:
    """Each figure column is named by its line and which figure on it; each text column by its line and which piece
    of text on it (counting the label's own piece), so the model points at a value and never writes one."""
    cell = {"type": "object", "properties": {"line_id": {"type": ["string", "null"]}, "figure": {"type": ["integer", "null"]}},
            "required": ["line_id", "figure"], "additionalProperties": False}
    text = {"type": "object", "properties": {"line_id": {"type": ["string", "null"]}, "segment": {"type": ["integer", "null"]}},
            "required": ["line_id", "segment"], "additionalProperties": False}
    texts = text_columns or []
    every = columns + texts
    row = {"type": "object",
           "properties": {"label_line_ids": {"type": "array", "items": {"type": "string"}},
                          "cells": {"type": "object", "properties": {**{c: cell for c in columns}, **{c: text for c in texts}},
                                    "required": every, "additionalProperties": False}},
           "required": ["label_line_ids", "cells"], "additionalProperties": False}
    return {"type": "object", "properties": {"rows": {"type": "array", "items": row}}, "required": ["rows"],
            "additionalProperties": False}


def _column_line(c: ColumnDef, hint: str | None) -> str:
    return f"- {c.name}: {hint}" if hint else f"- {c.name}"


def map_table(cfg: IngestionConfig, type_name: str, name: str, title: str, defs: list[ColumnDef], spec: ModelTable,
              pages: list[Page], model: ModelClient, dash_is_zero: bool = True,
              shown: list[Page] | None = None) -> tuple[TableResult | None, list[dict]]:
    """The table as the model maps it and the page gives it, or None; with trace entries for what was rejected.
    `shown`: the pages to show the model, when chosen by the keyword scorer instead of `spec.pages`."""
    trace: list[dict] = []
    shown = shown if shown is not None else candidate_pages(pages, spec)
    if not shown:
        return None, [{"call": "table", "table": name, "skipped": "no_candidate_page"}]
    gap = cfg.routing.reading.column_gap
    budget, by_id = cfg.llm.window_chars, {}
    for p in shown:
        for line in p.content_lines():
            row = f"{line.id}: {line.text}"
            if budget - len(row) < 0:
                break
            budget -= len(row) + 1
            by_id[line.id] = (p, line)
    figure_cols = [c.name for c in defs if c.type == "number"]
    text_cols = [c.name for c in defs if c.type != "number" and c.name != spec.label_column] if spec.text_columns else []
    pr = cfg.llm.prompts["table"]
    user = (pr.user.replace("{{table}}", title)
            .replace("{{columns}}", "\n".join(_column_line(c, spec.hints.get(c.name)) for c in defs
                                              if c.name in figure_cols or c.name in text_cols))
            .replace("{{lines}}", "\n".join(f"{i}: {pl[1].text}" for i, pl in by_id.items())).strip())
    system = pr.system.replace("{{type_name}}", type_name).replace("{{table}}", title).strip()
    try:
        ans = model.call(ModelRequest("table", system, user, table_schema(figure_cols, text_cols)))
    except ModelError as e:
        return None, [{"call": "table", "table": name, "error": e.code, "message": str(e)[:200]}]

    rows, unparsed = [], 0
    for k, r in enumerate((ans or {}).get("rows") or []):
        ids = [i for i in r.get("label_line_ids") or []]
        if not ids or any(i not in by_id for i in ids):
            trace.append({"table": name, "row": k, "rejected": "bad_label_line"})
            continue
        # A text table's label is the first piece of text on each label line; the other pieces are its text columns'.
        label = (collapse_ws(" ".join((text_segments(by_id[i][1], gap) or [""])[0] for i in ids)) if text_cols
                 else label_text([by_id[i][1] for i in ids], gap))
        if not label:
            trace.append({"table": name, "row": k, "rejected": "no_label_on_line"})
            continue
        cells: dict[str, object] = {d.name: None for d in defs}
        cells[spec.label_column] = label
        raw: dict[str, str] = {spec.label_column: label}
        used = list(ids)
        for col in figure_cols:
            ent = (r.get("cells") or {}).get(col) or {}
            lid, n = ent.get("line_id"), ent.get("figure")
            if lid is None or n is None:
                continue
            figs = figures(by_id[lid][1], gap) if lid in by_id else []
            if not isinstance(n, int) or not 1 <= n <= len(figs):
                trace.append({"table": name, "row": k, "column": col, "rejected": "figure_not_on_line"})
                unparsed += 1
                continue
            token = figs[n - 1].text
            value = 0 if dash_is_zero and token in DASHES else to_number(token)
            if value is None:
                unparsed += 1
                continue
            cells[col], raw[col] = value, token
            if lid not in used:
                used.append(lid)
        for col in text_cols:
            ent = (r.get("cells") or {}).get(col) or {}
            lid, n = ent.get("line_id"), ent.get("segment")
            if lid is None or n is None:
                continue
            parts = text_segments(by_id[lid][1], gap) if lid in by_id else []
            if not isinstance(n, int) or not 1 <= n <= len(parts):
                trace.append({"table": name, "row": k, "column": col, "rejected": "text_not_on_line"})
                continue
            token = parts[n - 1]
            kind = next((d.type for d in defs if d.name == col), "string")
            cells[col] = to_date(token) if kind == "date" else token
            raw[col] = token
            if lid not in used:
                used.append(lid)
        if all(cells[c] is None for c in figure_cols + text_cols):
            trace.append({"table": name, "row": k, "rejected": "no_value"})
            continue
        page = by_id[ids[0]][0]
        lines = [by_id[i][1] for i in used]
        boxes = [tuple(b) for line in lines if (b := line.bbox())]
        rows.append({"cells": cells, "raw": raw,
                     "source": {"page": page.no, "bbox": union_bbox(boxes), "line_ids": used,
                                "line": collapse_ws(" ".join(line.text for line in lines))[:400], "method": "model"}})
    if not rows:
        return None, trace + [{"call": "table", "table": name, "rejected": "no_rows"}]
    nos = [r["source"]["page"] for r in rows]
    allbox = union_bbox(tuple(r["source"]["bbox"]) for r in rows if r["source"].get("bbox"))
    claimed = [i for r in rows for i in (r["source"].get("line_ids") or [])]
    return TableResult([d.name for d in defs], rows, min(nos), max(nos), allbox, None, [], unparsed, method="model",
                       claimed=claimed), trace
