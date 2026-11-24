"""Canonical financial lines from the statement tables (FRD F-18, F-20, F-22).

The document-processing service returns an audited statement as tables of printed rows
(balance_sheet, profit_and_loss, cash_flow). Where each line is printed is configuration
(config/statements.yaml): a row found by its label, then derived lines summed from those. Policy
norms, the spread and the turnover facts all read through here, so the three never disagree.
Every line keeps the field value it came from, so its evidence is one click away (F-16).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from datetime import date

from .configstore.schema import StatementsSection
from .contracts import Evidence
from .util import fy_end_of


@dataclass
class LinePart:
    """One line a derived figure was summed from, with the sign it carried (F-20.2)."""

    name: str
    sign: int
    value: float
    evidence: list[Evidence] = field(default_factory=list)
    not_printed: bool = False
    line: "Line | None" = None
    """The line itself, for the screens to follow a sum down to the printed figures."""


@dataclass
class Line:
    value: float
    evidence: list[Evidence] = field(default_factory=list)
    manual: bool = False
    field_ids: list[str] = field(default_factory=list)
    pending: bool = False
    """A cell it was read from is still waiting for review (F-17.2)."""
    not_printed: bool = False
    """The statement does not print this line; it stands as nil because the configuration allows that
    (absent_is_nil), and the screens say so."""
    parts: list[LinePart] = field(default_factory=list)
    """For a derived line, the lines it was summed from, in the order configured; empty for a
    line the statement prints itself. The screens show the arithmetic from these."""
    state: str = "printed"
    """printed, nil (the statement prints a dash), not_printed, edited or derived."""
    key: str | None = None
    label: str | None = None
    """The row's label as the statement prints it."""
    raw: str | None = None
    """The amount as printed, in the statement's own unit ("3,586", "-")."""
    printed: float | None = None
    """The amount in the statement's own unit, before it is scaled to rupees."""
    scale: float = 1.0
    column: str | None = None
    document_id: str | None = None
    edit: object | None = None
    """The live edit behind this figure (facts.StatementEdit), when a person set it."""


def _number(v) -> float | None:
    if v is None or v.value in (None, ""):
        return None
    try:
        return float(str(v.value).replace(",", ""))
    except ValueError:
        return None


UNIT_SCALE = {"thousand": 1e3, "lakh": 1e5, "lac": 1e5, "crore": 1e7, "million": 1e6}


def unit_scale(doc) -> float:
    """The multiplier from the statement's printed unit ("All Amounts are in INR Thousands") to
    rupees; 1 when it prints none."""
    unit = doc.get("amount_unit")
    if unit is None:
        return 1.0
    word = str(unit.value).strip().lower().rstrip("s")
    return UNIT_SCALE.get(word, 1.0)


def _find_all(doc, table: str, row_pattern, column: str, label_column: str = "particulars") -> list[tuple[float, object]]:
    """Every row a line spec (or a row pattern) matches that has an amount in the column."""
    scale = unit_scale(doc)
    out = []
    for row in doc.rows(table):
        label = row.get(label_column)
        if label is None:
            continue
        text = str(label.value or "").strip()
        if isinstance(row_pattern, str):
            if not re.search(row_pattern, text, re.IGNORECASE):
                continue
        elif _match_rank(fold_label(text) if row_pattern.wordings else text, row_pattern) is None:
            continue
        cell = row.get(column)
        number = _number(cell)
        if number is not None:
            out.append((number * scale, cell))
    return out


_NUMBERING = re.compile(r"^\s*(?:\(?(?:[ivxlc]{1,6}|[a-z]|\d{1,2})[.)]|\((?:[ivxlc]{1,6}|[a-z]|\d{1,2})\))\s+", re.IGNORECASE)


def fold_label(text: str) -> str:
    """A printed label as it is matched: its numbering ("(a)", "1.", "II.", "A.", "i)") removed, in lower case, "&" as
    "and", hyphens, punctuation and apostrophes as nothing or a space."""
    t = str(text or "").strip()
    while True:
        cut = _NUMBERING.sub("", t, count=1)
        if cut == t:
            break
        t = cut
    t = t.lower().replace("&", " and ").replace("'", "").replace("’", "")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def _match_rank(label: str, spec) -> int | None:
    """How well a folded label is the line: 0 it is a wording, 1 it begins with one, 2 it holds one; None not at all."""
    if spec.row:
        return 0 if re.search(spec.row, label, re.IGNORECASE) else None
    best = None
    for w in spec.wordings:
        f = fold_label(w)
        if not f:
            continue
        rank = 0 if label == f else 1 if label.startswith(f + " ") else 2 if f" {f} " in f" {label} " else None
        if rank is not None and (best is None or rank < best):
            best = rank
    return best


def matches(spec, label: str) -> bool:
    """Whether a printed label is the line (or GST row) the spec names."""
    return _match_rank(fold_label(label) if spec.wordings else str(label or "").strip(), spec) is not None


def row_sections(doc, table: str, cfg, label_column: str = "particulars") -> list[str | None]:
    """Each row's section (statements.yaml sections), by the section headings the table prints above it; all None
    when it prints none."""
    secs = (cfg.sections or {}).get(table, {}) if cfg is not None else {}
    heads = {fold_label(h): name for name, s in secs.items() for h in s.headings}
    out, current = [], None
    for row in doc.rows(table):
        cell = row.get(label_column)
        label = fold_label(cell.value if cell is not None else "")
        if label in heads:
            current = heads[label]
        out.append(current)
    return out

def row_groups(doc, table: str, cfg, label_column: str = "particulars") -> list[str | None]:
    """Each row's top-level group (statements.yaml groups), by the group headings printed above it."""
    groups = (cfg.groups or {}).get(table, {}) if cfg is not None else {}
    heads = {fold_label(h): name for name, hs in groups.items() for h in hs}
    out, current = [], None
    for row in doc.rows(table):
        cell = row.get(label_column)
        label = fold_label(cell.value if cell is not None else "")
        if label in heads:
            current = heads[label]
        out.append(current)
    return out


def _find_row(doc, spec, column: str, cfg=None):
    """The row that is the line, with an amount in the column: (rupees, cell, label). Of the rows in its section (where
    the table prints section headings), a label that is a wording wins over one that begins with it, which wins over
    one that holds it; then the first printed."""
    scale = unit_scale(doc)
    rows = doc.rows(spec.table)
    sections = row_sections(doc, spec.table, cfg, spec.label) if spec.section else [None] * len(rows)
    sectioned = spec.section and any(sections)
    groups = row_groups(doc, spec.table, cfg, spec.label) if getattr(spec, "group", None) else [None] * len(rows)
    grouped = getattr(spec, "group", None) and any(groups)
    best = None
    for i, row in enumerate(rows):
        label = row.get(spec.label)
        if label is None:
            continue
        if sectioned and sections[i] != spec.section:
            continue
        if grouped and groups[i] != spec.group:
            continue
        text = str(label.value or "").strip()
        rank = _match_rank(fold_label(text) if spec.wordings else text, spec)
        if rank is None:
            continue
        cell = row.get(column)
        number = _number(cell)
        if number is not None and (best is None or rank < best[0]):
            best = (rank, number * scale, cell, text)
            if rank == 0:
                break
    return best[1:] if best else None


def _find(doc, table: str, row_pattern: str, column: str, label_column: str = "particulars") -> tuple[float, object] | None:
    found = _find_all(doc, table, row_pattern, column, label_column)
    return found[0] if found else None


def _line(doc, number: float, cell) -> Line:
    return Line(number, doc.evidence(cell), cell.manual, [cell.field_id], getattr(cell, "pending", False))


def _terms(expression: str) -> list[tuple[int, str]]:
    """The names of a sum or difference with their signs."""
    tree = ast.parse(expression, mode="eval").body
    out: list[tuple[int, str]] = []

    def walk(node: ast.AST, sign: int) -> None:
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            walk(node.left, sign)
            walk(node.right, sign if isinstance(node.op, ast.Add) else -sign)
        elif isinstance(node, ast.Name):
            out.append((sign, node.id))
        else:
            raise ValueError(f"statements.derived allows only sums and differences of lines: {expression!r}")

    walk(tree, 1)
    return out


def lines(doc, cfg: StatementsSection, *, column: str | None = None) -> dict[str, Line]:
    """Every canonical line the statement prints, and every derived line whose parts are all on it. A line the statement
    does not print is nil where the section (or group) it belongs to ties out to its printed total: the statement's
    own figures show nothing is missing there (TC-09)."""
    col = column or cfg.column
    out = _printed_lines(doc, cfg, col)
    tied = {name for t in _tie_outs(doc, cfg, col, out) if t.agrees for name in t.section.split(", ")}
    scale = unit_scale(doc)
    for key, spec in cfg.lines.items():
        if key not in out and spec.section in tied:
            out[key] = Line(0.0, [], not_printed=True, state="not_printed", key=key, column=col, document_id=doc.id, scale=scale)
    return _derive(doc, cfg, col, out)


def _printed_lines(doc, cfg: StatementsSection, col: str) -> dict[str, Line]:
    """The canonical lines the statement prints, the configured nils and a person's edits; nothing derived.

    A person's edit of a line (statement_edits) stands in place of what the statement prints; the
    printed figure stays on the line beside it."""
    scale = unit_scale(doc)
    edits = getattr(doc, "edits", {}) or {}
    out: dict[str, Line] = {}
    for key, spec in cfg.lines.items():
        use = spec.column or col
        found = _find_row(doc, spec, use, cfg)
        if found:
            number, cell, label = found
            line = _line(doc, number, cell)
            line.key, line.label, line.column, line.document_id = key, label, use, doc.id
            line.raw, line.scale = cell.raw, scale
            line.printed = number / scale if scale else number
            line.state = "nil" if (cell.raw or "").strip() in ("-", "–", "—") else "printed"
            out[key] = line
    for key in cfg.absent_is_nil:
        spec = cfg.lines.get(key)
        if key in out or not spec:
            continue
        rows = doc.rows(spec.table)
        listed = any(_match_rank(fold_label(r[spec.label].value) if spec.wordings else str(r[spec.label].value or "").strip(),
                                 spec) is not None for r in rows if spec.label in r)
        if rows and not listed:   # a row that is there but unread is not absent
            out[key] = Line(0.0, [], not_printed=True, state="not_printed", key=key, column=col,
                            document_id=doc.id, scale=scale)
    for key, spec in cfg.lines.items():
        edit = edits.get((key, spec.column or col))
        if edit is None:
            continue
        was = out.get(key)
        line = Line(edit.value * scale, was.evidence if was else doc.evidence(), True, was.field_ids if was else [],
                    False, state="edited", key=key, label=was.label if was else None, raw=was.raw if was else None,
                    printed=edit.value, scale=scale, column=spec.column or col, document_id=doc.id, edit=edit)
        out[key] = line
    return out


def _derive(doc, cfg: StatementsSection, col: str, out: dict[str, Line]) -> dict[str, Line]:
    scale = unit_scale(doc)
    for key, expression in cfg.derived.items():
        terms = _terms(expression)
        if all(name in out for _, name in terms):
            out[key] = Line(
                sum(sign * out[name].value for sign, name in terms),
                [e for _, name in terms for e in out[name].evidence[:1]],
                any(out[name].manual for _, name in terms),
                [i for _, name in terms for i in out[name].field_ids],
                any(out[name].pending for _, name in terms),
                parts=[LinePart(name, sign, out[name].value, out[name].evidence[:1], out[name].not_printed, out[name])
                       for sign, name in terms],
                state="derived", key=key, column=col, document_id=doc.id, scale=scale,
            )
    return out


def gst_outward(doc, cfg: StatementsSection) -> Line | None:
    """The return's outward supplies: the sum of every configured row of its table."""
    spec = cfg.gst_outward
    found = _find_all(doc, spec.table, spec if spec.wordings else spec.row, spec.column, spec.label)
    if not found:
        return None
    cells = [cell for _, cell in found]
    return Line(
        sum(number for number, _ in found),
        doc.evidence(*cells[:1]),
        any(c.manual for c in cells),
        [c.field_id for c in cells],
        any(getattr(c, "pending", False) for c in cells),
    )


def itr_lines(doc, cfg: StatementsSection) -> dict[str, Line]:
    """The configured lines of an income tax return's computation (TX-02, TX-03)."""
    out: dict[str, Line] = {}
    for key, spec in cfg.itr_lines.items():
        found = _find(doc, spec.table, spec if spec.wordings else spec.row, spec.column or "amount", spec.label)
        if found:
            out[key] = _line(doc, *found)
    return out


def period_end(doc) -> date | None:
    """The year end a financial statement is for, from its printed financial year, or the end of the period
    a provisional statement covers."""
    v = doc.get("financial_year") or doc.get("period_to")
    return fy_end_of(v.value) if v else None


@dataclass
class TieOut:
    """A section's mapped lines against its printed total (Story 5.13)."""

    table: str
    section: str
    total_label: str
    printed: float
    mapped: float
    lines: list[str]
    unmapped: list[str]
    tolerance: float
    evidence: list = field(default_factory=list)

    @property
    def difference(self) -> float:
        return self.printed - self.mapped

    @property
    def agrees(self) -> bool:
        return abs(self.difference) <= self.tolerance + 1e-6


def tie_outs(doc, cfg: StatementsSection, *, column: str | None = None) -> list[TieOut]:
    """Each section the statement prints a total for, and each configured grand total, with the sum of the canonical
    lines mapped in it: they must agree within the rounding of the unit printed. A difference names the rows printed
    there with an amount that map to no line, for a person to look at."""
    col = column or cfg.column
    return _tie_outs(doc, cfg, col, _printed_lines(doc, cfg, col))


def _tie_outs(doc, cfg: StatementsSection, col: str, mapped: dict[str, Line]) -> list[TieOut]:
    scale = unit_scale(doc)
    out: list[TieOut] = []
    for table, secs in (cfg.sections or {}).items():
        rows = doc.rows(table)
        if not rows:
            continue
        sections = row_sections(doc, table, cfg)
        totals = {fold_label(t): name for name, s in secs.items() for t in s.total}
        heads = {fold_label(h) for s in secs.values() for h in s.headings}
        specs = {k: s for k, s in cfg.lines.items() if s.table == table and s.section}
        for i, row in enumerate(rows):
            cell = row.get("particulars")
            label = fold_label(cell.value if cell is not None else "")
            name = totals.get(label)
            amount = _number(row.get(col))
            if name is None or amount is None:
                continue
            keys = [k for k, s in specs.items() if s.section == name and k in mapped and mapped[k].state in ("printed", "nil", "edited")]
            known = {fold_label(w) for s in specs.values() for w in s.wordings} | set(totals) | heads
            # The rows printed between the section's heading and its total.
            stray = [str(r["particulars"].value) for j, r in enumerate(rows)
                     if j < i and sections[j] == name and r.get("particulars") is not None and _number(r.get(col)) is not None
                     and all(_match_rank(fold_label(r["particulars"].value), s) is None for s in specs.values() if s.section == name)
                     and fold_label(r["particulars"].value) not in known]
            out.append(TieOut(table, name, str(cell.value), amount * scale, sum(mapped[k].value for k in keys), keys, stray,
                              cfg.tie_out_rounding * scale * max(1, len(keys)), doc.evidence(row.get(col))))
    # A grand total (total assets) against the lines mapped in the sections that make it up, whether or not the
    # statement prints those sections' own totals.
    for total_key, section_names in (cfg.grand_totals or {}).items():
        total = mapped.get(total_key)
        spec = cfg.lines.get(total_key)
        if total is None or spec is None or total.state not in ("printed", "edited"):
            continue
        keys = [k for k, s in cfg.lines.items() if s.table == spec.table and s.section in section_names and k in mapped
                and mapped[k].state in ("printed", "nil", "edited")]
        rows = doc.rows(spec.table)
        sections = row_sections(doc, spec.table, cfg)
        sectioned = any(sections)
        known = {fold_label(w) for s in cfg.lines.values() if s.table == spec.table for w in s.wordings}
        known |= {fold_label(t) for s in (cfg.sections or {}).get(spec.table, {}).values() for t in s.total + s.headings}
        stray = [str(r["particulars"].value) for j, r in enumerate(rows)
                 if r.get("particulars") is not None and _number(r.get(col)) is not None
                 and (not sectioned or sections[j] in section_names)
                 and all(_match_rank(fold_label(r["particulars"].value), s) is None for s in cfg.lines.values() if s.table == spec.table)
                 and fold_label(r["particulars"].value) not in known]
        out.append(TieOut(spec.table, ", ".join(section_names), total.label or total_key, total.value,
                          sum(mapped[k].value for k in keys), keys, stray,
                          cfg.tie_out_rounding * scale * max(1, len(keys)), total.evidence[:1]))
    return out
