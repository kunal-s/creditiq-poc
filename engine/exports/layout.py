"""The draft CAM and the PD note as files: the layout the Word and the PDF writer share (F-23.5, F-24.3).

`cam_document` and `pd_note_document` turn the memo or the note, as the screen has it, into one
ordered list of blocks: headings, paragraphs, tables and room left to write in. Both writers render
the same blocks, so the two files carry the same text. A statement's citations become a marker after
it, such as [3 p.4], numbered as the sources listed at the end. The words of the headings and labels
come with the memo or the note (its labels, from configuration), today's wording where none is set.
The Word file keeps every character; the PDF, drawn with the standard fonts, writes those outside
Windows-1252 in other characters (`winansi`).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date
from functools import lru_cache
from typing import Literal

from reportlab.pdfbase.pdfmetrics import stringWidth

from ..contracts import Cam, CamBlock, CamSummaryItem, CamText, Evidence, OutputSource, PdNote, PdQuestion
from ..util import display_date, parse_date

SEVERITY = {"serious": "Serious", "moderate": "Moderate", "mild": "Mild"}
# The words printed inside the files, by key, where the memo's or the note's labels do not give them.
LABELS = {
    "borrower": "Borrower", "case_id": "Case ID", "drafted_as_of": "Drafted from the data on file as of",
    "data_as_of": "Data as of", "configuration": "Configuration version", "run": "Cross-check run",
    "summary_findings": "Findings", "summary_no_findings": "No discrepancy in cross-check run {run}.",
    "summary_incomplete": "Checks not completed", "summary_deviations": "Deviations from policy norms",
    "summary_unassessed": "Norms not assessed", "summary_queries": "Open queries",
    "people_to_meet": "People to meet", "record": "Record of the discussion", "why_we_ask": "Why we ask",
    "evidence": "Evidence", "also_covers": "Also covers", "response": "Response", "follow_up": "Follow-up",
    "observation": "Observation",
    "documents_to_collect": "Documents to collect at the discussion",
    "sign_name": "Name", "sign_designation": "Designation", "sign_signature": "Signature", "sign_date": "Date",
    "sources": "Sources", "source_no": "No.", "source_document": "Document", "source_file": "File",
    "source_pages": "Pages",
}
# The groups of the query list, in its order.
QUERY_GROUPS = {"documents_needed": "Documents needed", "documents_to_redo": "Documents to redo",
                "clarifications": "Clarifications"}
FACTS = (0.34, 0.66)
SIGN_OFF = ("sign_name", "sign_designation", "sign_signature", "sign_date")
SIGN_OFF_WIDTHS = (0.2, 0.24, 0.2, 0.22, 0.14)
TEXT_WIDTH = 481.9
"""Points across the text: A4 less margins of 2 cm, in both files."""
BODY_HEIGHT = 720.0
"""Points down the text: A4 less a top margin of 2.3 cm and a bottom margin of 2 cm, in both files."""
WHOLE = BODY_HEIGHT / 6
"""Points: a table this short, with the headings over it, is kept on one page."""
FACTS_WHOLE = 12
"""Rows: a table of facts this long or shorter is kept on one page, with the headings over it."""
RESPONSE_LINES, FOLLOW_UP_LINES = 4, 2
"""Ruled lines under each question of the note, for the response and the follow-up."""
HOLD = 2
"""Response lines kept with their question: the page may turn after these, rather than the question
move whole to the next page."""
SOURCE_ROWS = 3
"""Rows of a list of sources kept together at either end where it runs over a page."""
INDENT = 18.4
"""Points: the indent under a question's number (0.65 cm)."""
BODY_SIZE = 9.5
"""The size of body text, in points."""
TABLE_SIZE = 8.5
"""The size of table text, in points."""
LEADING = 10.5
"""Points from one line of table text to the next."""
PADDING = 8.0
"""A cell's left and right padding together, in points."""
ROW_PADDING = 6.0
"""A cell's top and bottom padding together, in points."""
SHORT = 64.0
"""Points: a line of text this short is kept whole where the width allows."""
TOLERANCE = 0.5
"""Points: widths that overrun the room by this little still fit."""


@dataclass(frozen=True)
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    cite: bool = False
    """A citation marker, set smaller."""


Spans = tuple[Span, ...]


@dataclass(frozen=True)
class Title:
    text: str
    facts: tuple[tuple[str, Spans], ...]
    note: str | None = None


@dataclass(frozen=True)
class Heading:
    text: str
    new_page: bool = False


@dataclass(frozen=True)
class Paragraph:
    spans: Spans
    style: Literal["body", "note", "subheading", "label", "question", "meta"] = "body"
    indent: bool = False
    """Under a question's number."""
    keep: bool = False
    """Kept on the page of what follows it: a short line leading into a table."""


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    """The header row, repeated on every page; none for a facts or a form table."""
    rows: tuple[tuple[Spans, ...], ...]
    widths: tuple[float, ...]
    """Each column's share of the text width."""
    numeric: frozenset[int] = frozenset()
    kind: Literal["grid", "facts", "form"] = "grid"
    title: str | None = None
    note: str | None = None
    row_height: float = 0
    """The least height of a body row, in points: room to write in."""
    tail: tuple[Paragraph, ...] = ()
    """A short paragraph straight after the table, kept with its last rows."""
    whole: float = WHOLE
    """Points: a table this short is kept on one page with the headings over it and the lines under it."""
    least: int = 1
    """Body rows kept together at either end where the table runs over a page: a table with fewer than
    twice as many goes to the next page whole."""


@dataclass(frozen=True)
class Space:
    """Room left blank to write in: ruled lines, or a box."""

    lines: int
    box: bool = False
    indent: bool = False
    hold: int | None = None
    """In a group that may turn: the lines kept with what is above them; the page may turn after any
    line from this one on. None keeps every line with the rest of the group."""


@dataclass(frozen=True)
class Group:
    """Blocks kept on one page where they fit."""

    blocks: tuple[Block, ...]
    turns: bool = False
    """Where the group does not fit whole, the page may turn between its ruled lines (after a Space's
    `hold` lines) rather than the group move to the next page."""


Block = Title | Heading | Paragraph | Table | Space | Group


@dataclass(frozen=True)
class Document:
    title: str
    subject: str
    header: str
    """The running header."""
    footer: str
    """The running footer, before "page X of Y", which each writer adds."""
    as_of: date | None
    """The date the case's data is read as of: the files carry it as their date, never the clock."""
    blocks: tuple[Block, ...]
    version: str = ""
    """The configuration version in full, for the file's properties (the title block names it shortly)."""
    keywords: str = ""


# --- Text ---

_SUBSTITUTES = str.maketrans({
    "→": "->", "←": "<-", "⇒": "=>",  # arrows
    "✓": "Yes", "✔": "Yes", "✗": "No", "✘": "No",  # ticks and crosses
    "≥": ">=", "≤": "<=", "≠": "!=", "≈": "~",  # comparison signs
    "−": "-", "‐": "-", "‑": "-", "‒": "-", "―": "-",  # the minus sign, hyphens and dashes
    "₹": "INR ", "′": "'", "″": '"',  # the rupee sign, primes
    " ": " ", " ": " ", " ": " ",  # figure and narrow spaces
})


@lru_cache(maxsize=4096)
def _winansi(ch: str) -> bool:
    try:
        ch.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return ch in "\n " or ch.isprintable()


@lru_cache(maxsize=4096)
def _control(ch: str) -> bool:
    return unicodedata.category(ch) in ("Cc", "Cs") or ch in "￾￿"


def clean(text: str | None) -> str:
    """The text as both files carry it: lines ended by a line feed, tabs as spaces, runs of spaces as
    one, and no control characters, which a Word file cannot hold. Every other character is kept."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    return re.sub(r" {2,}", " ", "".join(ch for ch in text if ch == "\n" or not _control(ch))).strip()


def winansi(text: str) -> str:
    """The text in characters the PDF standard fonts can show (Windows-1252), for the PDF only: arrows,
    ticks and comparison signs in words or ASCII, the rupee sign as INR, a letter without a
    Windows-1252 form without its accent, format characters left out and anything else as "?"."""
    out = []
    for ch in text.translate(_SUBSTITUTES):
        if _winansi(ch):
            out.append(ch)
        elif unicodedata.category(ch)[0] != "C":
            parts = unicodedata.normalize("NFKD", ch)
            # Not a negated sign (≮ is < with a stroke): without its stroke it would say the opposite.
            folded = "" if "̸" in parts else "".join(
                c for c in parts if _winansi(c) and not unicodedata.combining(c))
            out.append(folded or "?")
    return "".join(out)


def fit(text: str, size: float, least: float = 6.5) -> tuple[str, float]:
    """A running line in the width, in both files: a smaller size first, down to the least, then shortened."""
    def across(t: str, s: float) -> float:
        return stringWidth(winansi(t), "Helvetica", s)

    while across(text, size) > TEXT_WIDTH and size > least:
        size -= 0.5
    while across(text, size) > TEXT_WIDTH and len(text) > 1:
        text = text[:-2] + "…"
    return text, size


def _date(value: str) -> str:
    d = parse_date(value)
    return display_date(d) if d else clean(value)


def _version(label: str, version: str) -> str:
    """The configuration version as people know it ("Version 15 (published 13 Oct 2026)"); without a
    label, the start of the version's hash."""
    version = clean(version)
    return clean(label) or (version[:8] if len(version) > 12 else version)


def _words(labels: dict[str, str]) -> Callable[[str], str]:
    """The words for each label key: the memo's or the note's own, else today's."""
    return lambda key: clean(labels.get(key)) or LABELS[key]


def _lead_in(label: str) -> str:
    """A label that leads into its text: "Why we ask: ", whether or not it was written with its colon."""
    return f"{label.rstrip(': ')}: "


def _runs(pages: Iterable[int]) -> str:
    """"4", "4-6", "1, 4-6": pages in ascending order, consecutive ones as a range."""
    runs: list[list[int]] = []
    for p in sorted(set(pages)):
        if runs and p == runs[-1][1] + 1:
            runs[-1][1] = p
        else:
            runs.append([p, p])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


class _Sources:
    """The citation markers, numbered as the sources the memo or note lists. A document cited but not
    listed is added after the list, so that no citation is lost."""

    def __init__(self, sources: list[OutputSource]) -> None:
        self.listed = sorted(sources, key=lambda s: s.number)
        self.numbers = {s.document_id: s.number for s in self.listed}
        self.added: dict[str, OutputSource] = {}

    def marker(self, citations: Iterable[Evidence]) -> str:
        pages: dict[int, set[int]] = {}
        for c in citations:
            number = self.numbers.get(c.document_id)
            if number is None:
                number = self._add(c.document_id)
            if c.document_id in self.added:
                self.added[c.document_id].pages.append(c.page)
            pages.setdefault(number, set()).add(c.page)
        # Three or more sources in a row cited at the same pages read as a range, such as the twelve
        # monthly returns behind a year's GST figure: [13-24 p.1].
        runs: list[list] = []
        for n, p in sorted(pages.items()):
            if runs and n == runs[-1][1] + 1 and p == runs[-1][2]:
                runs[-1][1] = n
            else:
                runs.append([n, n, p])
        cited = []
        for first, last, p in runs:
            # A no-break space keeps a source's number with its page.
            at = f" {'p.' if len(p) == 1 else 'pp.'}{_runs(p)}"
            cited += [f"{first}-{last}{at}"] if last - first >= 2 else [f"{n}{at}" for n in range(first, last + 1)]
        return f"[{'; '.join(cited)}]" if cited else ""

    def _add(self, document_id: str) -> int:
        number = max(self.numbers.values(), default=0) + 1
        self.numbers[document_id] = number
        self.added[document_id] = OutputSource(number=number, document_id=document_id, label="Document", pages=[])
        return number

    def all(self) -> list[OutputSource]:
        return self.listed + [s.model_copy(update={"pages": sorted(set(s.pages))}) for s in self.added.values()]


def _cited(text: CamText, sources: _Sources) -> Spans:
    words = clean(text.text)
    marker = sources.marker(text.citations)
    spans = [Span(words)] if words else []
    if marker:
        spans.append(Span(f" {marker}" if words else marker, cite=True))
    return tuple(spans)


def _spans(text: str | None, **style) -> Spans:
    text = clean(text)
    return (Span(text, **style),) if text else ()


# --- Tables ---

def _measure(text: str, span: Span) -> float:
    """Points across, in table text, as the PDF draws it. Helvetica and Arial have the same widths, so
    both files agree."""
    size = TABLE_SIZE - 1.5 if span.cite else TABLE_SIZE
    return stringWidth(winansi(text), "Helvetica-Bold" if span.bold else "Helvetica", size)


def _lines(spans: Spans, cites: bool = True) -> list[float]:
    """The width of each line of a cell, with or without its citation marker."""
    widths = [0.0]
    for s in spans:
        if s.cite and not cites:
            continue
        for k, part in enumerate(s.text.split("\n")):
            if k:
                widths.append(0.0)
            widths[-1] += _measure(part, s)
    return widths


def _figure(spans: Spans) -> float:
    """What a cell of figures keeps on one line: each line's figure, up to a qualifier that may wrap under
    it ("INR 2.50 lakh (12 months)", "INR 95.00 lakh; outstanding INR 60.00 lakh")."""
    widths = [0.0]
    for line in "".join(s.text for s in spans if not s.cite).split("\n"):
        cut = re.search(r";\s|\s\(", line)
        head = line if cut is None else line[:cut.start() + (1 if line[cut.start()] == ";" else 0)]
        widths.append(_measure(head, Span(head)))
    return max(widths)


def row_lines(row: tuple[Spans, ...], widths: tuple[float, ...]) -> int:
    """About how many lines the row's fullest cell wraps to."""
    rooms = [max(w * TEXT_WIDTH - PADDING, 1.0) for w in widths]
    return max((sum(max(1, math.ceil(w / room)) for w in _lines(cell)) for cell, room in zip(row, rooms)),
               default=1)


def table_height(t: Table) -> float:
    """About how tall the table is drawn, in points: its header row and its rows."""
    rows = ([tuple((Span(c, bold=True),) for c in t.columns)] if t.columns else []) + list(t.rows)
    return sum(max(row_lines(r, t.widths) * LEADING + ROW_PADDING, t.row_height) for r in rows)


def _fill(room: float, *tiers: list[float], short: list[bool]) -> list[float]:
    """Widths that reach each tier in turn while the tier fits the room; the first tier that does not fit
    shares out what room is left, by how much more each column needs to reach it. Short of room for the
    second tier, the figures and short lines it keeps whole come first: the columns that wrap anyway
    give up the room."""
    widths = list(tiers[0])
    if sum(widths) > room + TOLERANCE:
        return [w * room / sum(widths) for w in widths]
    for k, tier in enumerate(tiers[1:], start=1):
        if k == 1:
            first = [t if s else w for w, t, s in zip(widths, tier, short)]
            if sum(first) <= room + TOLERANCE:
                widths = first
        need, spare = sum(tier) - sum(widths), max(room - sum(widths), 0.0)
        if need <= spare + TOLERANCE:
            widths = list(tier)
        else:
            return [w + (t - w) * spare / need for w, t in zip(widths, tier)]
    return widths


def _widths(columns: tuple[str, ...], rows: list[tuple[Spans, ...]], numeric: frozenset[int]) -> tuple[float, ...]:
    """Each column's share of the width, from what it holds, in tiers as far as the width allows: room
    for its longest word; then room to keep a figure (up to any qualifier after it) or a short line, such
    as a year or a name, on one line; then room for each line of words on one line; then for each figure
    with its citation, and each heading, on one line. What is left over is shared by width."""
    count = max([len(columns), *(len(r) for r in rows)], default=1)
    room = TEXT_WIDTH - PADDING * count
    words, whole, text, lines, short = [], [], [], [], []
    for j in range(count):
        head = (Span(columns[j], bold=True),) if j < len(columns) else ()
        cells = [r[j] for r in rows if j < len(r)]
        word = max((_measure(w, s) for spans in (head, *cells) for s in spans for w in s.text.split()), default=0)
        words.append(min(word + 2, room / 3))  # a longer word is broken
        if j in numeric:
            one, cap = max((_figure(spans) for spans in cells), default=0) + 2, room / 4
        else:
            one, cap = max((w for spans in cells for w in _lines(spans, cites=False)), default=0) + 2, SHORT
        short.append(one <= cap + TOLERANCE)
        whole.append(max(words[-1], min(one, cap)))
        longest = min(max((w for spans in cells for w in _lines(spans)), default=0) + 2, room * 0.6)
        text.append(whole[-1] if j in numeric else max(whole[-1], longest))
        lines.append(max(text[-1], longest, min(max(_lines(head)) + 2, room / 4)))
    widths = _fill(room, words, whole, text, lines, short=short)
    return tuple((w + PADDING) / (sum(widths) + PADDING * count) for w in widths)


def _table(columns: Iterable[str], rows: Iterable[Iterable[Spans]], *, numeric: Iterable[int] = (),
           title: str | None = None, note: str | None = None, whole: float = WHOLE) -> Table:
    columns = tuple(clean(c) for c in columns)
    body = [tuple(r) for r in rows]
    count = max(len(columns), *(len(r) for r in body), 1)
    columns = columns + ("",) * (count - len(columns)) if columns else ()
    body = [r + ((),) * (count - len(r)) for r in body]
    numeric = frozenset(j for j in numeric if 0 <= j < count)
    return Table(columns=columns, rows=tuple(body), widths=_widths(columns, body, numeric), numeric=numeric,
                 title=clean(title) or None, note=clean(note) or None, whole=whole)


def _facts(pairs: Iterable[tuple[str, Spans]], kind: Literal["facts", "form"] = "facts",
           row_height: float = 0) -> Table:
    """Label and value, row by row; up to FACTS_WHOLE rows are kept on one page, rather than leave a
    few of them alone at the top of the next."""
    rows = tuple(((Span(clean(label)),), value) for label, value in pairs)
    return Table(columns=(), rows=rows, widths=FACTS, kind=kind, row_height=row_height,
                 whole=BODY_HEIGHT if len(rows) <= FACTS_WHOLE else WHOLE)


def _sign_off(roles: Iterable[str], words: Callable[[str], str]) -> Table:
    return Table(columns=("", *(words(k) for k in SIGN_OFF)),
                 rows=tuple(((Span(clean(r)),), (), (), (), ()) for r in roles),
                 widths=SIGN_OFF_WIDTHS, kind="form", row_height=30)


def _sources_appendix(sources: _Sources, words: Callable[[str], str], new_page: bool = False) -> list[Block]:
    heading = Heading(words("sources"), new_page)
    rows = sources.all()
    if not rows:
        return [heading, Paragraph(_spans("No document is cited.", italic=True), "note")]
    # The list starts under what is before it, rather than go alone onto a page of its own; where it
    # runs over, its first and its last rows go in threes, so that none is left alone on a page.
    return [heading, replace(_table(
        (words("source_no"), words("source_document"), words("source_file"), words("source_pages")),
        [((Span(str(s.number)),), _spans(s.label), _spans(s.file_name or "—"), _spans(_runs(s.pages) or "—"))
         for s in rows],
        numeric=(0,), whole=0), least=SOURCE_ROWS)]


# --- Keeping lines with their tables (F-22) ---

def _line_count(p: Paragraph) -> int:
    """About how many lines the paragraph takes, in body text."""
    room = TEXT_WIDTH - (INDENT if p.indent else 0)
    space = stringWidth(" ", "Helvetica", BODY_SIZE)
    count, width = 1, 0.0
    for s in p.spans:
        size = BODY_SIZE - 1.5 if s.cite else BODY_SIZE
        font = "Helvetica-Bold" if s.bold else "Helvetica"
        for k, part in enumerate(s.text.split("\n")):
            if k:
                count, width = count + 1, 0.0
            for word in part.split(" "):
                w = stringWidth(winansi(word), font, size)
                if width and width + space + w > room:
                    count, width = count + 1, w
                else:
                    width += (space if width else 0) + w
    return count


def _kept(blocks: list[Block]) -> list[Block]:
    """The short lines either side of a table kept with it: a paragraph of up to three lines straight
    before a table goes with the table's start, and one of up to two lines straight after a table (not
    leading into another) stays with the table's last rows."""
    out: list[Block] = []
    for k, b in enumerate(blocks):
        after = blocks[k + 1] if k + 1 < len(blocks) else None
        plain = isinstance(b, Paragraph) and b.style in ("body", "note")
        if plain and isinstance(after, Table) and _line_count(b) <= 3:
            b = replace(b, keep=True)
        elif plain and out and isinstance(out[-1], Table) and not out[-1].tail and _line_count(b) <= 2:
            out[-1] = replace(out[-1], tail=(b,))
            continue
        out.append(b)
    return out


# --- The memo ---

def _cam_block(block: CamBlock, sources: _Sources) -> list[Block]:
    if block.kind == "paragraph" and block.paragraph:
        spans = _cited(block.paragraph, sources)
        return [Paragraph(spans)] if spans else []
    if block.kind == "facts" and block.facts:
        return [_facts((f.label, _cited(f.value, sources)) for f in block.facts)]
    if block.kind == "table" and block.table:
        t = block.table
        if t.rows:
            rows = [[_cited(cell, sources) for cell in row] for row in t.rows]
            return [_table(t.columns, rows, numeric=t.numeric, title=t.title, note=t.note)]
        # A table with nothing in it yet: its title and its note, which says why.
        out: list[Block] = []
        if clean(t.title):
            out.append(Paragraph(_spans(t.title, bold=True), "subheading"))
        if clean(t.note):
            out.append(Paragraph(_spans(t.note, italic=True), "note"))
        return out
    if block.kind == "subheading" and clean(block.text):
        return [Paragraph(_spans(block.text, bold=True), "subheading")]
    if block.kind == "note" and clean(block.text):
        return [Paragraph(_spans(block.text, italic=True), "note")]
    return []


def _ref(i: CamSummaryItem) -> Spans:
    return _spans("\n".join(r for r in (clean(i.ref), clean(i.rule) if i.rule and i.rule != i.ref else "") if r))


def _findings(items: list[CamSummaryItem], sources: _Sources) -> Table:
    """The findings as a register: each with its reference and rule, its severity, what is wrong (cited)
    and where it stands. What each one says is in the cross-verification section."""
    return _table(("Ref", "Severity", "Finding", "Status"), [
        (_ref(i), _spans(SEVERITY.get(i.severity or "", "")),
         _cited(CamText(text=i.title or i.text, citations=i.citations), sources),
         _spans("\n".join(s for s in (clean(i.status), "Blocks submission" if i.blocking else "") if s)))
        for i in items])


def _incomplete(items: list[CamSummaryItem], sources: _Sources) -> Table:
    """The checks that could not be completed, each with what would complete it."""
    severity = any(i.severity for i in items)
    rows = []
    for i in items:
        row = [_ref(i), _cited(CamText(text=i.title or i.text, citations=i.citations), sources),
               _spans(i.request or "—")]
        if severity:
            row.insert(1, _spans(SEVERITY.get(i.severity or "", "")))
        rows.append(row)
    return _table(["Ref", *(["Severity"] if severity else []), "Check", "What would complete it"], rows)


def _summary(items: list[CamSummaryItem], column: str, sources: _Sources) -> Table:
    """Deviations or norms not assessed: each with its reference (and rule), its severity and status
    where it has them, its title and what it says."""
    severity = any(i.severity for i in items)
    status = any(i.status or i.blocking for i in items)
    columns = ["Ref", *(["Severity"] if severity else []), column, *(["Status"] if status else [])]
    rows = []
    for i in items:
        body = [Span(clean(i.title), bold=True), Span("\n")] if clean(i.title) else []
        row = [_ref(i), tuple(body + list(_cited(CamText(text=i.text, citations=i.citations), sources)))]
        if severity:
            row.insert(1, _spans(SEVERITY.get(i.severity or "", "")))
        if status:
            row.append(_spans("\n".join(s for s in (clean(i.status), "Blocks submission" if i.blocking else "") if s)))
        rows.append(row)
    return _table(columns, rows)


def _group(i: CamSummaryItem) -> str:
    """The heading a query sits under: its group in the query list (or its title, which carried the
    group before the group had its own field)."""
    return QUERY_GROUPS.get(i.group or "", "") or clean(i.title)


def _queries(items: list[CamSummaryItem], sources: _Sources) -> list[Block]:
    """The open queries numbered, under the groups the query list puts them in."""
    out: list[Block] = []
    number = 0
    for group in dict.fromkeys(_group(i) for i in items):
        members = [i for i in items if _group(i) == group]
        if group:
            out.append(Paragraph(_spans(group, bold=True), "label"))
        out.append(_table(("No.", "Query"), [
            ((Span(str(n)),), _cited(CamText(text=i.text, citations=i.citations), sources))
            for n, i in enumerate(members, start=number + 1)], numeric=(0,)))
        number += len(members)
    return out


def _summary_blocks(cam: Cam, sources: _Sources, words: Callable[[str], str]) -> list[Block]:
    """Findings (a register), checks not completed, deviations, norms not assessed and open queries,
    each under its heading; with a cross-check run and no finding, a line that says so."""
    def heading(key: str) -> Paragraph:
        return Paragraph(_spans(words(key), bold=True), "subheading")

    kinds = {kind: [i for i in cam.summary if i.kind == kind]
             for kind in ("finding", "incomplete", "deviation", "unassessed", "query")}
    out: list[Block] = []
    if kinds["finding"]:
        out += [heading("summary_findings"), _findings(kinds["finding"], sources)]
    elif cam.run_id:
        out += [heading("summary_findings"),
                Paragraph(_spans(words("summary_no_findings").replace("{run}", clean(cam.run_id)), italic=True),
                          "note")]
    if kinds["incomplete"]:
        out += [heading("summary_incomplete"), _incomplete(kinds["incomplete"], sources)]
    if kinds["deviation"]:
        out += [heading("summary_deviations"), _summary(kinds["deviation"], "Deviation", sources)]
    if kinds["unassessed"]:
        out += [heading("summary_unassessed"), _summary(kinds["unassessed"], "Norm", sources)]
    if kinds["query"]:
        out += [heading("summary_queries"), *_queries(kinds["query"], sources)]
    if not out:
        out.append(Paragraph(_spans("No findings, deviations or open queries.", italic=True), "note"))
    return out


def cam_document(cam: Cam) -> Document:
    """The draft CAM as blocks: the title block, the numbered sections, the summary, the recommendation
    left blank for credit with its sign-off, and the sources."""
    words = _words(cam.labels)
    sources = _Sources(cam.sources)
    facts = [(words("borrower"), cam.borrower), (words("case_id"), cam.case_id),
             (words("drafted_as_of"), _date(cam.as_of)),
             (words("configuration"), _version(cam.config_label, cam.config_version)),
             (words("run"), cam.run_id or "")]
    blocks: list[Block] = [Title(clean(cam.title), tuple((k, _spans(v)) for k, v in facts if clean(v)),
                                 clean(cam.template_note) or None)]
    for section in cam.sections:
        blocks.append(Heading(f"{section.number}. {clean(section.title)}"))
        drafted = [b for block in section.blocks for b in _cam_block(block, sources)]
        if not drafted and clean(section.empty):
            drafted = [Paragraph(_spans(section.empty, italic=True), "note")]
        blocks += drafted

    blocks.append(Heading(f"{cam.summary_number}. {clean(cam.summary_title)}"))
    blocks += _summary_blocks(cam, sources, words)

    recommendation: list[Block] = [Heading(f"{cam.recommendation_number}. {clean(cam.recommendation_title)}")]
    if clean(cam.recommendation):
        recommendation.append(Paragraph(_spans(cam.recommendation)))
    for prompt in cam.recommendation_prompts:
        recommendation.append(Group((Paragraph(_spans(prompt, bold=True), "label"), Space(lines=5, box=True))))
    if not cam.recommendation_prompts and not clean(cam.recommendation):
        recommendation.append(Space(lines=8, box=True))
    if cam.sign_off:
        recommendation.append(Group((_sign_off((s.role for s in cam.sign_off), words),)))
    # The recommendation is left to credit on one page with its sign-off: a page of its own, or under the
    # last lines of the summary where it fits whole there, rather than leave those lines alone on a page.
    # The sources start on the next.
    blocks.append(Group(tuple(recommendation)))
    blocks += _sources_appendix(sources, words, new_page=True)
    return _document(cam.title, cam.borrower, cam.case_id, cam.as_of, blocks, cam.config_version)


# --- The PD note ---

def _at(xv_ref: str | None, rule: str | None, ref: str) -> str:
    return f"{xv_ref} ({rule})" if xv_ref and rule and rule != xv_ref else xv_ref or rule or ref


def _about(q: PdQuestion, words: Callable[[str], str]) -> str:
    """What the question comes from, in a line: its severity, the finding, norm or observation and its
    status; then the other findings it also covers, each with its status. An observation, a fact the
    memo states, goes by its word alone and its status, the memo section that states it ("section 9"):
    its key and its rule (OBS) mean nothing to a reader."""
    ref = _at(q.xv_ref, q.rule, q.ref)
    if q.source == "finding":
        what = f"Finding {ref}"
    elif q.source == "deviation":
        what = f"Deviation from {ref}"
    elif q.source == "observation":
        what = words("observation")
    else:
        what = f"{'Check not completed' if q.target == 'cross_verification' else 'Norm not assessed'}: {ref}"
    line = " · ".join(p for p in (SEVERITY.get(q.severity, ""), clean(what), clean(q.status)) if p)
    also = "; ".join(" · ".join(p for p in (clean(_at(a.xv_ref, a.rule, a.ref)), clean(a.status)) if p)
                     for a in q.also)
    return f"{line}\n{_lead_in(words('also_covers'))}{also}" if also else line


def _question(q: PdQuestion, sources: _Sources, words: Callable[[str], str]) -> Group:
    blocks: list[Block] = [
        Paragraph((Span(f"{q.number}. {clean(q.question)}", bold=True),), "question"),
        Paragraph(_spans(_about(q, words)), "meta", indent=True),
    ]
    if clean(q.context):
        blocks.append(Paragraph((Span(_lead_in(words("why_we_ask")), bold=True), *_spans(q.context)), indent=True))
    # The question's evidence, and that of the other findings it covers.
    marker = sources.marker([*q.evidence, *(e for a in q.also for e in a.evidence)])
    if marker:
        blocks.append(Paragraph((Span(_lead_in(words("evidence")), bold=True), Span(marker)), indent=True))
    # Kept on one page where it fits; where it nearly does, the page turns between the response lines
    # (after the first two) or before the follow-up, rather than the question leave a page part blank.
    blocks += [Paragraph(_spans(words("response"), bold=True), "label", indent=True),
               Space(lines=RESPONSE_LINES, indent=True, hold=HOLD),
               Paragraph(_spans(words("follow_up"), bold=True), "label", indent=True),
               Space(lines=FOLLOW_UP_LINES, indent=True)]
    return Group(tuple(blocks), turns=True)


def pd_note_document(note: PdNote) -> Document:
    """The PD question note as blocks: the header facts, the people to meet (cited), the record of the
    discussion left blank, the questions by topic with room for the response and the follow-up, the
    documents to collect, the sign-off and the sources."""
    words = _words(note.labels)
    sources = _Sources(note.sources)
    if note.header:
        facts = [(clean(f.label), _cited(f.value, sources)) for f in note.header]
    else:
        facts = [(words("borrower"), _spans(note.borrower)), (words("case_id"), _spans(note.case_id)),
                 (words("data_as_of"), _spans(_date(note.as_of))),
                 (words("configuration"), _spans(_version(note.config_label, note.config_version)))]
    blocks: list[Block] = [Title(clean(note.title), tuple((k, v) for k, v in facts if k and v))]
    if note.people:
        blocks += [Heading(words("people_to_meet")), _table(
            ("Name", "Role", "DIN", "Named in"),
            [(_spans(p.name), _spans(p.role or "—"), _spans(p.din or "—"),
              _cited(CamText(text=", ".join(p.sources) or "—", citations=p.evidence), sources))
             for p in note.people])]
    if note.record_fields:
        blocks += [Heading(words("record")), _facts(((f, ()) for f in note.record_fields), "form", 24)]

    questions = {q.id: q for q in note.questions}
    topics = [(t.title, [questions[i] for i in t.question_ids if i in questions]) for t in note.topics]
    asked = {q.id for _, qs in topics for q in qs}
    topics.append(("Other questions", [q for q in note.questions if q.id not in asked]))
    for title, qs in topics:
        if qs:
            blocks.append(Heading(clean(title)))
            blocks += [_question(q, sources, words) for q in qs]
    if not note.questions:
        blocks += [Heading("Questions"), Paragraph(_spans("No question arises from the data on file.", italic=True),
                                                   "note")]

    if note.documents_to_collect:
        blocks += [Heading(words("documents_to_collect")), _table(
            ("No.", "Document"), [((Span(str(n)),), _cited(d, sources)) for n, d in
                                  enumerate(note.documents_to_collect, start=1)], numeric=(0,))]
    if note.sign_off:
        blocks.append(Group((_sign_off((s.role for s in note.sign_off), words),)))
    blocks += _sources_appendix(sources, words)
    return _document(note.title, note.borrower, note.case_id, note.as_of, blocks, note.config_version)


def _document(title: str, borrower: str, case_id: str, as_of: str, blocks: list[Block], version: str) -> Document:
    title, borrower, case_id, version = clean(title), clean(borrower), clean(case_id), clean(version)
    return Document(title=title, subject=f"{borrower} · {case_id}",
                    header=f"{title} — Draft · {borrower} · {case_id}",
                    footer=f"CreditIQ draft · data as of {_date(as_of)}", as_of=parse_date(as_of),
                    blocks=tuple(_kept(blocks)), version=version,
                    keywords=f"Configuration version {version}" if version else "")
