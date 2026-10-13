"""The PDF writer (reportlab platypus): A4, the PDF standard fonts, a running header and a footer
with "page X of Y". The text is written in the characters the standard fonts can show
(`layout.winansi`)."""

from __future__ import annotations

import io
from functools import partial
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import FrameBreak, NullActionFlowable
from reportlab.platypus.flowables import HRFlowable, PageBreakIfNotEmpty, _listWrapOn

from . import layout

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm
TOP = MARGIN + 0.3 * cm
WIDTH = PAGE_WIDTH - 2 * MARGIN
INDENT = 0.65 * cm
LINE = 20
"""Points between ruled lines left to write on."""
START = 64
"""Points of a longer table's first rows kept with its headings: its first row, and the next while
they are short (about three lines in all)."""

MUTED_HEX = "#5F6B7A"
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor(MUTED_HEX)
RULE = colors.HexColor("#A7B0BA")
HEAD_FILL = colors.HexColor("#E6EBF1")
LABEL_FILL = colors.HexColor("#F3F5F8")
REGULAR, BOLD, ITALIC = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


def _style(name: str, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **{"fontName": REGULAR, "fontSize": layout.BODY_SIZE, "leading": 12.5,
                                   "textColor": INK, "spaceAfter": 4, **kw})


STYLES = {
    "title": _style("title", fontName=BOLD, fontSize=17, leading=21, spaceAfter=6),
    "heading": _style("heading", fontName=BOLD, fontSize=12, leading=15, spaceBefore=12, spaceAfter=5, keepWithNext=1),
    "body": _style("body"),
    "note": _style("note", fontName=ITALIC, fontSize=9, leading=12, textColor=MUTED),
    "subheading": _style("subheading", fontName=BOLD, fontSize=10, leading=13, spaceBefore=6, spaceAfter=3,
                         keepWithNext=1),
    "label": _style("label", fontName=BOLD, fontSize=9, leading=12, spaceBefore=4, spaceAfter=2, keepWithNext=1),
    "question": _style("question", fontName=BOLD, fontSize=10, leading=13, spaceBefore=10, spaceAfter=2,
                       leftIndent=INDENT, firstLineIndent=-INDENT, keepWithNext=1),
    "meta": _style("meta", fontSize=8.5, leading=11, textColor=MUTED, spaceAfter=3),
    "caption": _style("caption", fontName=BOLD, fontSize=9, leading=12, spaceBefore=4, spaceAfter=3, keepWithNext=1),
    "table_note": _style("table_note", fontName=ITALIC, fontSize=8.5, leading=11, textColor=MUTED, spaceBefore=3,
                         spaceAfter=6),
    "cell": _style("cell", fontSize=layout.TABLE_SIZE, leading=layout.LEADING, spaceAfter=0),
    "cell_right": _style("cell_right", fontSize=layout.TABLE_SIZE, leading=layout.LEADING, spaceAfter=0,
                         alignment=TA_RIGHT),
    "head": _style("head", fontName=BOLD, fontSize=layout.TABLE_SIZE, leading=layout.LEADING, spaceAfter=0),
    "head_right": _style("head_right", fontName=BOLD, fontSize=layout.TABLE_SIZE, leading=layout.LEADING,
                         spaceAfter=0, alignment=TA_RIGHT),
    "title_label": _style("title_label", fontSize=9, leading=12, textColor=MUTED, spaceAfter=0),
    "title_value": _style("title_value", fontName=BOLD, fontSize=9, leading=12, spaceAfter=0),
}


def _plain(text: str) -> str:
    """Text for reportlab's paragraph markup: in the standard fonts' characters, escaped."""
    return escape(layout.winansi(text))


def _markup(spans: layout.Spans, size: float) -> str:
    """Reportlab's paragraph markup for the spans."""
    out = []
    for s in spans:
        text = _plain(s.text).replace("\n", "<br/>")
        if s.cite:
            text = f'<font size="{size - 1.5:g}" color="{MUTED_HEX}">{text}</font>'
        if s.bold:
            text = f"<b>{text}</b>"
        if s.italic:
            text = f"<i>{text}</i>"
        out.append(text)
    return "".join(out)


def _paragraph(spans: layout.Spans, style: str, indent: bool = False) -> Paragraph:
    base = STYLES[style]
    if indent and style != "question":
        base = ParagraphStyle(f"{style}_indented", parent=base, leftIndent=INDENT)
    return Paragraph(_markup(spans, base.fontSize), base)


class _Space(Flowable):
    """Ruled lines, or a box, left blank to write in."""

    def __init__(self, space: layout.Space) -> None:
        super().__init__()
        self.space = space
        self.left = INDENT if space.indent else 0

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        self.width = available_width
        self.height = self.space.lines * LINE
        return self.width, self.height + 6

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        if self.space.box:
            c.rect(self.left, 6, self.width - self.left, self.height)
        else:
            for i in range(self.space.lines):
                y = 6 + i * LINE
                c.line(self.left, y, self.width, y)
        c.restoreState()


class _Table(Table):
    """A table whose rest, once split at the foot of a page, starts on the next page: offered the space
    left under the part before it, reportlab would split it again inside a row and repeat the header
    row mid-page."""

    rest = False

    def split(self, availWidth, availHeight):
        frame = getattr(self, "_frame", None)
        if self.rest and frame is not None and not frame._atTop:
            return []
        parts = super().split(availWidth, availHeight)
        for part in parts[1:]:
            part.rest = True
        return parts


def _at_top(flowable: Flowable) -> bool:
    frame = getattr(flowable, "_frame", None)
    return frame is None or bool(getattr(frame, "_atTop", False))


class _Tail(Flowable):
    """A table and the short lines under it (its note, a line that follows it): where the table ends near
    the foot of a page and the lines do not fit under it, its last row goes over with them rather than
    leave them alone at the top of the next page."""

    def __init__(self, table: _Table, tail: list[Flowable]) -> None:
        super().__init__()
        self.table, self.tail = table, tail

    def wrap(self, aW, aH):
        return aW, 0xffffff  # always split, as KeepTogether does

    def split(self, aW, aH):
        table, tail = self.table, self.tail
        height = table.wrapOn(self.canv, aW, aH)[1]
        under = _listWrapOn(tail, aW, self.canv)[1] + max(table.getSpaceAfter(), tail[0].getSpaceBefore())
        if height + under <= aH:
            return [NullActionFlowable(), table, *tail]
        if height <= aH:
            body = table._rowHeights[table.repeatRows:]
            if len(body) > 1:
                # Between rows (not inside one): every row but the last on this page.
                parts = Table.split(table, aW, height - body[-1] + 0.01)
                if len(parts) == 2:
                    parts[1].rest = True
                    return [NullActionFlowable(), parts[0], FrameBreak(), parts[1], *tail]
            return [NullActionFlowable(), table, *tail]
        parts = table.split(aW, aH)
        if len(parts) < 2:
            # Nothing of it fits here: the next page (or, at the top of one, as it comes).
            return [NullActionFlowable(), table, *tail] if _at_top(self) else []
        return [NullActionFlowable(), parts[0], _Tail(parts[1], tail)]


class _TableBlock(KeepTogether):
    """A table with the headings and the short line over it, and its note and a short line under it
    (F-22): a short table goes onto one page with them all; a longer one keeps only its header and first
    rows with the headings, starting where it is reached, and its last row with the lines under it."""

    def __init__(self, lead: list[Flowable], table: _Table, tail: list[Flowable], whole: float) -> None:
        self.lead, self.table, self.tail, self.whole = lead, table, tail, whole
        super().__init__([*lead, table, *tail])

    def split(self, aW, aH):
        if getattr(self, "_wrapInfo", None) != (aW, aH):
            self.wrap(aW, aH)
        here = NullActionFlowable if _at_top(self) else FrameBreak
        if self._H <= aH:
            return [NullActionFlowable(), *self._content]
        table = self.table
        if sum(table._rowHeights) <= self.whole:
            return [here(), *self._content]
        heads, body = table._rowHeights[:table.repeatRows], table._rowHeights[table.repeatRows:]
        kept = body[:1]
        for height in body[1:]:
            if sum(kept) + height > START:
                break
            kept.append(height)
        over = _listWrapOn(self.lead, aW, self.canv)[1] + self.lead[-1].getSpaceAfter() if self.lead else 0
        start = over + sum(heads + kept)
        rest = [_Tail(table, self.tail)] if self.tail else [table]
        return [(NullActionFlowable if start <= aH else here)(), *self.lead, *rest]


def _table(t: layout.Table) -> tuple[list[Flowable], _Table, list[Flowable]]:
    """The table with its caption over it, and its note and the line that follows it under it."""
    caption = [_paragraph((layout.Span(t.title),), "caption")] if t.title else []
    header = 1 if t.columns else 0
    data = []
    if header:
        data.append([Paragraph(_plain(c), STYLES["head_right" if j in t.numeric else "head"])
                     for j, c in enumerate(t.columns)])
    for row in t.rows:
        data.append([Paragraph(_markup(cell, layout.TABLE_SIZE), STYLES["cell_right" if j in t.numeric else "cell"])
                     for j, cell in enumerate(row)])
    table = _Table(data, colWidths=[w * WIDTH for w in t.widths], repeatRows=header, splitInRow=1, hAlign="LEFT",
                   minRowHeights=[0] * header + [t.row_height] * len(t.rows) if t.row_height else None,
                   spaceAfter=0 if t.note else 6)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), layout.PADDING / 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), layout.PADDING / 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), layout.ROW_PADDING - 2.5),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_FILL))
    if t.kind in ("facts", "form"):
        style.append(("BACKGROUND", (0, header), (0, -1), LABEL_FILL))
    table.setStyle(TableStyle(style))
    under = [_paragraph((layout.Span(t.note, italic=True),), "table_note")] if t.note else []
    under += [_paragraph(p.spans, p.style, p.indent) for p in t.tail]
    return caption, table, under


def _title(t: layout.Title) -> list[Flowable]:
    out: list[Flowable] = [_paragraph((layout.Span(t.text),), "title")]
    if t.facts:
        table = Table([[Paragraph(_plain(k), STYLES["title_label"]), Paragraph(_markup(v, 9), STYLES["title_value"])]
                       for k, v in t.facts], colWidths=[0.36 * WIDTH, 0.64 * WIDTH], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        out.append(table)
    if t.note:
        out += [Spacer(1, 5), _paragraph((layout.Span(t.note, italic=True),), "note")]
    out.append(HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=6, spaceAfter=4))
    return out


def _flowables(blocks: tuple[layout.Block, ...], grouped: bool = False) -> list[Flowable]:
    out: list[Flowable] = []
    for b in blocks:
        if isinstance(b, layout.Title):
            out += _title(b)
        elif isinstance(b, layout.Heading):
            if b.new_page:
                out.append(PageBreakIfNotEmpty())
            out.append(_paragraph((layout.Span(b.text),), "heading"))
        elif isinstance(b, layout.Paragraph):
            paragraph = _paragraph(b.spans, b.style, b.indent)
            if b.keep:
                paragraph.keepWithNext = 1
            out.append(paragraph)
        elif isinstance(b, layout.Table) and grouped:
            lead, table, under = _table(b)
            out += [*lead, table, *under]
        elif isinstance(b, layout.Table):
            # The headings and the short line over the table go with its start, not with all of it as
            # reportlab would keep them.
            lead, table, under = _table(b)
            while out and isinstance(out[-1], Paragraph) and out[-1].getKeepWithNext():
                lead.insert(0, out.pop())
            for f in lead:
                f.keepWithNext = 0
            out.append(_TableBlock(lead, table, under, b.whole))
        elif isinstance(b, layout.Space):
            out.append(_Space(b))
        elif isinstance(b, layout.Group):
            # Reportlab keeps a heading with the next flowable but not with a group: the group takes it in.
            content = _flowables(b.blocks, grouped=True)
            while out and isinstance(out[-1], Paragraph) and out[-1].getKeepWithNext():
                content.insert(0, out.pop())
            out.append(KeepTogether(content))
    return out


class _PagedCanvas(Canvas):
    """Keeps every page until the document is complete, then draws the running header and the footer
    with "page X of Y" on each. The file's date is the case's as_of, never the clock."""

    def __init__(self, *args, document: layout.Document, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._document = document
        self._pages: list[dict] = []
        stamp = document.as_of.strftime("D:%Y%m%d000000+00'00'") if document.as_of else None
        if stamp:
            self.setDateFormatter(lambda *_: stamp)

    def showPage(self) -> None:
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._pages)
        for number, page in enumerate(self._pages, start=1):
            self.__dict__.update(page)
            self._decorate(number, total)
            Canvas.showPage(self)
        Canvas.save(self)

    def _decorate(self, number: int, total: int) -> None:
        self.saveState()
        self.setFillColor(MUTED)
        header, size = layout.fit(self._document.header, 8)
        self.setFont(REGULAR, size)
        self.drawString(MARGIN, PAGE_HEIGHT - 1.3 * cm, layout.winansi(header))
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(MARGIN, PAGE_HEIGHT - 1.45 * cm, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 1.45 * cm)
        footer, size = layout.fit(f"{self._document.footer} · page {number} of {total}", 8)
        self.setFont(REGULAR, size)
        self.drawString(MARGIN, 1.2 * cm, layout.winansi(footer))
        self.restoreState()


def render(document: layout.Document) -> bytes:
    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=TOP,
                          bottomMargin=MARGIN, title=document.title, author="CreditIQ", subject=document.subject,
                          keywords=document.keywords, creator="CreditIQ", invariant=1)
    frame = Frame(MARGIN, MARGIN, WIDTH, PAGE_HEIGHT - TOP - MARGIN, leftPadding=0, rightPadding=0, topPadding=0,
                  bottomPadding=0, id="body")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame])])
    doc.build(_flowables(document.blocks), canvasmaker=partial(_PagedCanvas, document=document))
    return buffer.getvalue()
