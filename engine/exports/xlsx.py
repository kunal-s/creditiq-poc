"""The draft CAM as an Excel workbook (F-23.5): a worksheet a section, in the memo's order, each a
sheet a person can read, print or work in.

Each sheet opens with the bank's mark (the logo, else its name), the memo's title and its facts, then
the section: its paragraphs as merged rows, its key facts as Field | Value | Source, its tables with
their own columns. Citation markers are the downloads' own ([3 p.2]), and each sheet ends with the
sources it cites. A figure a person overrode shows the value they gave, the cell marked and noted
with the value drafted, who, when and why; the overrides table stays in the section, as in the other
files. The content is laid out by `layout`, as Word and PDF are, so the three files never differ in
what they say. Every string is written as text (never a formula), and the file is dated as of the
case, never the clock, so the same memo always gives the same file.
"""

from __future__ import annotations

import io
import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime

import xlsxwriter

from ..contracts import Cam, CamOverride, CamText
from ..util import parse_date
from .layout import (
    Group, Paragraph, Space, Span, Spans, Table, _cam_block, _date, _runs, _Sources, _summary_blocks, _version,
    _words, clean,
)

SHEET_NAME = 31
"""Excel's limit on a worksheet's name."""
FORBIDDEN = re.compile(r"[\[\]:*?/\\]")
WIDTH = {"min": 10, "max": 48, "label": 26, "value": 46, "source": 16}
"""Column widths, in characters."""
LINE = 15.0
"""Points a line of body text takes."""
CITED = re.compile(r"(\d+)(?:-(\d+))?\s")


def sheet_name(number: int, title: str, taken: set[str]) -> str:
    """"1. Borrower and Group Profile": within Excel's 31 characters ("and" as "&" first, then cut
    short), without the characters a sheet name may not hold, and unique in the workbook."""
    name = FORBIDDEN.sub("", f"{number}. {clean(title)}").strip()
    if len(name) > SHEET_NAME:
        name = name.replace(" and ", " & ")
    if len(name) > SHEET_NAME:
        name = name[: SHEET_NAME - 1].rstrip() + "…"
    base, n = name, 2
    while name.lower() in taken:
        suffix = f" ({n})"
        name, n = base[: SHEET_NAME - len(suffix)] + suffix, n + 1
    taken.add(name.lower())
    return name


def figure_key(owner: str, row_name: str, column: str) -> str:
    """The name an override gives a table's cell, as the screen's sheet names it: the table (or its
    section), the row and the column. A fact's figure is its label."""
    return " · ".join(clean(p) for p in (owner, row_name, column))


def _latest(overrides: Iterable[CamOverride]) -> dict[str, CamOverride]:
    """The override in force for each figure: the last one made."""
    out: dict[str, CamOverride] = {}
    for o in sorted(overrides, key=lambda o: o.at):
        out[clean(o.figure)] = o
    return out


def _overridden(text: CamText, o: CamOverride | None) -> CamText:
    return text.model_copy(update={"text": o.value}) if o else text


def _apply_overrides(cam: Cam) -> tuple[Cam, dict[tuple[str, str], CamOverride]]:
    """The memo with each overridden fact and table cell showing the value a person gave, and those
    overrides by section and figure for the cells' notes."""
    cam = cam.model_copy(deep=True)
    applied: dict[tuple[str, str], CamOverride] = {}
    for s in cam.sections:
        latest = _latest(s.review.overrides)
        if not latest:
            continue
        for b in s.blocks:
            for f in b.facts:
                o = latest.get(clean(f.label))
                if o:
                    f.value = _overridden(f.value, o)
                    applied[(s.id, clean(f.label))] = o
            t = b.table
            if t and t.rows and t.title != OVERRIDES_TITLE:
                owner = t.title or s.title
                for row in t.rows:
                    name = row[0].text if row else ""
                    for i, cell in enumerate(row):
                        key = figure_key(owner, name, t.columns[i] if i < len(t.columns) else "")
                        o = latest.get(key)
                        if o:
                            row[i] = _overridden(cell, o)
                            applied[(s.id, key)] = o
    return cam, applied


OVERRIDES_TITLE = "Figures overridden by the analyst"
"""The record of overrides the review adds to a section (cam_review): never itself overridden."""


def _text(spans: Spans) -> str:
    return "".join(s.text for s in spans if not s.cite).strip()


def _cites(spans: Spans) -> str:
    return " ".join(s.text.strip() for s in spans if s.cite).strip()


def _all(spans: Spans) -> str:
    return "".join(s.text for s in spans).strip()


def _numbers(marker: str) -> set[int]:
    """The source numbers a marker cites: "[1 p.1; 13-15 p.2]" → {1, 13, 14, 15}."""
    out: set[int] = set()
    for first, last in CITED.findall(marker.replace(" ", " ") + " "):
        out.update(range(int(first), int(last or first) + 1))
    return out


@dataclass
class _Sheet:
    """A worksheet being written: the next row, and what it cites."""

    ws: object
    columns: int
    widths: list[float]
    row: int = 0
    cited: set[int] = field(default_factory=set)

    def need(self, column: int, chars: float) -> None:
        self.widths[column] = max(self.widths[column], min(WIDTH["max"], max(WIDTH["min"], chars + 2)))


class _Formats:
    def __init__(self, wb: xlsxwriter.Workbook) -> None:
        base = {"font_name": "Calibri", "font_size": 10, "valign": "top"}
        line = {"border": 1, "border_color": "#D0D5DD"}

        def f(**kw) -> object:
            return wb.add_format({**base, **kw})

        self.bank = f(bold=True, font_size=12, font_color="#1F3B4D", valign="vcenter")
        self.title = f(bold=True, font_size=14, font_color="#111827")
        self.meta = f(font_color="#4B5563", text_wrap=True)
        self.template = f(italic=True, font_color="#1D4E89", bg_color="#EAF2FB", text_wrap=True)
        self.heading = f(bold=True, font_size=13, font_color="#FFFFFF", bg_color="#1F4E5F", valign="vcenter")
        self.purpose = f(italic=True, font_color="#4B5563", text_wrap=True)
        self.subheading = f(bold=True, font_size=11, font_color="#1F4E5F", bottom=1, bottom_color="#1F4E5F")
        self.body = f(text_wrap=True, **line)
        self.note = f(italic=True, font_color="#4B5563", text_wrap=True)
        self.head = f(bold=True, bg_color="#F2F4F7", text_wrap=True, **line)
        self.cell = f(text_wrap=True, **line)
        self.zebra = f(text_wrap=True, bg_color="#F9FAFB", **line)
        self.number = f(text_wrap=True, align="right", **line)
        self.number_zebra = f(text_wrap=True, align="right", bg_color="#F9FAFB", **line)
        self.label = f(bold=True, bg_color="#F9FAFB", text_wrap=True, **line)
        self.cite = f(font_size=9, font_color="#1D4E89", text_wrap=True, **line)
        self.override = f(text_wrap=True, bg_color="#FFF6DA", **line)
        self.box = f(**line)
        self.prompt = f(bold=True)


def _height(texts: Iterable[tuple[str, float]]) -> float:
    """Points a row needs for its wrapped cells: the most lines any cell takes at its width."""
    lines = 1
    for text, width in texts:
        per_line = max(1.0, width * 1.1)
        lines = max(lines, sum(max(1, math.ceil(len(part) / per_line)) for part in (text or " ").split("\n")))
    return LINE * lines + 3


def _paragraph(sh: _Sheet, fm: _Formats, p: Paragraph) -> None:
    text = _all(p.spans)
    if not text:
        return
    style = {"subheading": fm.subheading, "note": fm.note, "label": fm.prompt}.get(p.style, fm.body)
    sh.cited |= _numbers(_cites(p.spans))
    last = sh.columns - 1
    width = sum(sh.widths)
    if last:
        sh.ws.merge_range(sh.row, 0, sh.row, last, text, style)
    else:
        sh.ws.write_string(sh.row, 0, text, style)
    sh.ws.set_row(sh.row, _height([(text, width)]) if style is fm.body or style is fm.note else None)
    sh.row += 1


def _facts(sh: _Sheet, fm: _Formats, t: Table, words: Callable[[str], str],
           notes: dict[str, CamOverride]) -> None:
    for i, heading in enumerate((words("field"), words("value"), words("source"))):
        sh.ws.write_string(sh.row, i, heading, fm.head)
    sh.row += 1
    for label_spans, value_spans in t.rows:
        label, value, cites = _all(label_spans), _text(value_spans), _cites(value_spans)
        o = notes.get(label)
        sh.ws.write_string(sh.row, 0, label, fm.label)
        sh.ws.write_string(sh.row, 1, value, fm.override if o else fm.cell)
        sh.ws.write_string(sh.row, 2, cites, fm.cite)
        if o:
            sh.ws.write_comment(sh.row, 1, _note(o, words), {"x_scale": 2, "y_scale": 1.4})
        sh.cited |= _numbers(cites)
        sh.need(0, len(label))
        sh.need(1, min(len(value), WIDTH["value"]))
        sh.need(2, len(cites))
        sh.ws.set_row(sh.row, _height([(label, sh.widths[0]), (value, sh.widths[1])]))
        sh.row += 1


def _grid(sh: _Sheet, fm: _Formats, t: Table, owner: str, words: Callable[[str], str],
          notes: dict[str, CamOverride]) -> None:
    if clean(t.title):
        _paragraph(sh, fm, Paragraph((_span(t.title),), "subheading"))
    for i, column in enumerate(t.columns):
        sh.ws.write_string(sh.row, i, clean(column), fm.head)
        sh.need(i, len(clean(column)))
    sh.ws.set_row(sh.row, _height((clean(c), sh.widths[i]) for i, c in enumerate(t.columns)))
    sh.row += 1
    for n, row in enumerate(t.rows):
        zebra = n % 2 == 1
        name = _text(row[0]) if row else ""
        texts = []
        for i, spans in enumerate(row):
            text = _all(spans)
            sh.cited |= _numbers(_cites(spans))
            column = clean(t.columns[i]) if i < len(t.columns) else ""
            o = notes.get(figure_key(t.title or owner, name, column))
            style = fm.override if o else (
                (fm.number_zebra if zebra else fm.number) if i in t.numeric else (fm.zebra if zebra else fm.cell))
            sh.ws.write_string(sh.row, i, text, style)
            if o:
                sh.ws.write_comment(sh.row, i, _note(o, words), {"x_scale": 2, "y_scale": 1.4})
            sh.need(i, min(len(text), WIDTH["max"]))
            texts.append((text, sh.widths[i]))
        sh.ws.set_row(sh.row, _height(texts))
        sh.row += 1
    if clean(t.note):
        _paragraph(sh, fm, Paragraph((_span(t.note, italic=True),), "note"))
    for p in t.tail:
        _paragraph(sh, fm, p)


def _span(text: str | None, **style) -> Span:
    return Span(clean(text), **style)


def _space(sh: _Sheet, fm: _Formats, s: Space) -> None:
    """Room to write in: bordered rows across the sheet."""
    for _ in range(max(1, s.lines // 2 if s.box else s.lines)):
        last = sh.columns - 1
        if last:
            sh.ws.merge_range(sh.row, 0, sh.row, last, "", fm.box)
        else:
            sh.ws.write_blank(sh.row, 0, None, fm.box)
        sh.ws.set_row(sh.row, LINE * 1.6)
        sh.row += 1


def _note(o: CamOverride, words: Callable[[str], str]) -> str:
    return (f"{words('as_drafted')}: {clean(o.original)}\n"
            f"{words('overridden_by')} {clean(o.by_name or o.by)}, {_date(o.at[:10])}: {clean(o.reason)}")


def _blocks(sh: _Sheet, fm: _Formats, blocks: Iterable, owner: str, words: Callable[[str], str],
            notes: dict[str, CamOverride]) -> None:
    for b in blocks:
        if isinstance(b, Paragraph):
            _paragraph(sh, fm, b)
        elif isinstance(b, Table):
            if b.kind == "grid":
                _grid(sh, fm, b, owner, words, notes)
            else:
                _facts(sh, fm, b, words, notes)
            sh.row += 1
        elif isinstance(b, Space):
            _space(sh, fm, b)
        elif isinstance(b, Group):
            _blocks(sh, fm, b.blocks, owner, words, notes)


def _has_facts(blocks: Iterable) -> bool:
    return any((isinstance(b, Table) and b.kind != "grid") or (isinstance(b, Group) and _has_facts(b.blocks))
               for b in blocks)


def _columns(blocks: Iterable) -> int:
    most = 4  # the sources at the foot of every sheet take four
    for b in blocks:
        if isinstance(b, Table) and b.kind == "grid":
            most = max(most, len(b.columns))
        elif isinstance(b, Group):
            most = max(most, _columns(b.blocks))
    return most


def cam_workbook(cam: Cam, logo: bytes | None = None) -> bytes:
    """The memo as an .xlsx file: a sheet a section, the logo (where given) at the head of each."""
    words = _words({**cam.labels})
    cam, applied = _apply_overrides(cam)
    sources = _Sources(cam.sources)

    # The sheets' content first, so that every citation is numbered before any sheet lists its sources.
    sheets: list[tuple[str, str, str | None, list, str]] = []
    for s in cam.sections:
        drafted = [b for block in s.blocks for b in _cam_block(block, sources)]
        if not drafted and clean(s.empty):
            drafted = [Paragraph((_span(s.empty, italic=True),), "note")]
        sheets.append((s.id, f"{s.number}. {clean(s.title)}", s.purpose, drafted, s.title))
    summary: list = []
    if cam.summary_review.paragraphs:
        summary += [Paragraph((_span(p),)) for p in cam.summary_review.paragraphs]
    if clean(cam.rating_note):
        summary.append(Paragraph((_span(cam.rating_note, italic=True),), "note"))
    summary += _summary_blocks(cam, sources, words)
    sheets.append(("summary", f"{cam.summary_number}. {clean(cam.summary_title)}", cam.summary_purpose, summary,
                   cam.summary_title))
    recommendation: list = []
    if clean(cam.recommendation):
        recommendation += [Paragraph((_span(p),)) for p in cam.recommendation.split("\n\n") if clean(p)]
    for prompt in cam.recommendation_prompts:
        recommendation += [Paragraph((_span(prompt, bold=True),), "label"), Space(lines=4)]
    if not cam.recommendation_prompts and not clean(cam.recommendation):
        recommendation.append(Space(lines=8))
    if cam.sign_off:
        recommendation.append(Table(
            columns=tuple(words(k) for k in ("sign_role", "sign_name", "sign_designation", "sign_signature",
                                             "sign_date")),
            rows=tuple(((_span(s.role),), (), (), (), ()) for s in cam.sign_off), widths=(0.2,) * 5))
    sheets.append(("recommendation", f"{cam.recommendation_number}. {clean(cam.recommendation_title)}",
                   cam.recommendation_purpose, recommendation, cam.recommendation_title))

    listed = {s.number: s for s in sources.all()}
    as_of = parse_date(cam.as_of)
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "strings_to_numbers": False, "strings_to_formulas": False,
                                   "strings_to_urls": False})
    wb.set_properties({
        "title": f"{clean(cam.title)} · {clean(cam.borrower)}", "subject": clean(cam.case_id),
        "author": "CreditIQ", "company": words("bank"),
        "keywords": f"Configuration version {clean(cam.config_version)}",
        "created": datetime(as_of.year, as_of.month, as_of.day) if as_of else datetime(2026, 1, 1),
    })
    fm = _Formats(wb)
    taken: set[str] = set()
    facts = " · ".join(p for p in (
        f"{words('case_id')}: {clean(cam.case_id)}",
        f"{words('drafted_as_of')} {_date(cam.as_of)}",
        f"{words('configuration')}: {_version(cam.config_label, cam.config_version)}",
        f"{words('run')}: {clean(cam.run_id)}" if clean(cam.run_id) else "",
    ) if p)

    for section_id, heading, purpose, blocks, owner in sheets:
        number = heading.split(".", 1)[0]
        ws = wb.add_worksheet(sheet_name(int(number) if number.isdigit() else 0, heading.split(". ", 1)[-1], taken))
        columns = _columns(blocks)
        first = [WIDTH["label"], WIDTH["value"], WIDTH["source"]] if _has_facts(blocks) else [WIDTH["min"]] * 3
        sh = _Sheet(ws=ws, columns=columns, widths=first + [WIDTH["min"]] * (columns - 3))
        notes = {key: o for (sid, key), o in applied.items() if sid == section_id}
        last = columns - 1

        # The head of every sheet: the bank's mark, the memo, its facts and, while the layout is assumed,
        # the note that says so; then the section's heading, held in view as the sheet scrolls.
        top = 0
        if logo or words("bank"):
            ws.set_row(0, 42)
            if logo:
                ws.insert_image(0, 0, "logo.png", {"image_data": io.BytesIO(logo), "x_offset": 4, "y_offset": 4,
                                                    "object_position": 3, "decorative": False,
                                                    "description": words("bank") or "Logo"})
            if words("bank"):
                ws.merge_range(0, 1 if logo else 0, 0, last, words("bank"), fm.bank)
            top = 1
        ws.merge_range(top, 0, top, last, f"{clean(cam.title)} · {clean(cam.borrower)}", fm.title)
        ws.set_row(top, 20)
        ws.merge_range(top + 1, 0, top + 1, last, facts, fm.meta)
        sh.row = top + 2
        if clean(cam.template_note):
            ws.merge_range(sh.row, 0, sh.row, last, clean(cam.template_note), fm.template)
            sh.row += 1
        sh.row += 1
        ws.merge_range(sh.row, 0, sh.row, last, heading, fm.heading)
        ws.set_row(sh.row, 24)
        sh.row += 1
        ws.freeze_panes(sh.row, 0)
        if clean(purpose):
            ws.merge_range(sh.row, 0, sh.row, last, clean(purpose), fm.purpose)
            sh.row += 1
        sh.row += 1

        _blocks(sh, fm, blocks, owner, words, notes)

        # The sources this sheet cites, so that a sheet printed alone still says where its figures are from.
        rows = [listed[n] for n in sorted(sh.cited) if n in listed]
        if rows:
            sh.row += 1
            _paragraph(sh, fm, Paragraph((_span(words("sources_cited"), bold=True),), "subheading"))
            _grid(sh, fm, Table(
                columns=(words("source_no"), words("source_document"), words("source_file"), words("source_pages")),
                rows=tuple(((_span(str(s.number)),), (_span(s.label),), (_span(s.file_name or "—"),),
                            (_span(_runs(s.pages) or "—"),)) for s in rows),
                widths=(0.1, 0.4, 0.35, 0.15), numeric=frozenset({0})), owner, words, {})

        for i, width in enumerate(sh.widths):
            ws.set_column(i, i, width)
        ws.set_landscape()
        ws.set_paper(9)
        ws.fit_to_pages(1, 0)
        ws.set_margins(left=0.5, right=0.5, top=0.6, bottom=0.6)
        ws.repeat_rows(0, top + 1)
        ws.set_footer(f"&L{clean(cam.case_id)} · {_date(cam.as_of)}&RPage &P of &N")
        ws.hide_gridlines(1)  # on screen, not on paper

    wb.close()
    return buf.getvalue()
