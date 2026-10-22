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


def _find_all(doc, table: str, row_pattern: str, column: str, label_column: str = "particulars") -> list[tuple[float, object]]:
    rx = re.compile(row_pattern, re.IGNORECASE)
    scale = unit_scale(doc)
    out = []
    for row in doc.rows(table):
        label = row.get(label_column)
        if label is None or not rx.search(str(label.value or "").strip()):
            continue
        cell = row.get(column)
        number = _number(cell)
        if number is not None:
            out.append((number * scale, cell))
    return out


def _find_row(doc, spec, column: str):
    """The first row the line's label matches that has an amount in the column: (rupees, cell, label)."""
    rx = re.compile(spec.row, re.IGNORECASE)
    scale = unit_scale(doc)
    for row in doc.rows(spec.table):
        label = row.get(spec.label)
        if label is None or not rx.search(str(label.value or "").strip()):
            continue
        cell = row.get(column)
        number = _number(cell)
        if number is not None:
            return number * scale, cell, str(label.value or "").strip()
    return None


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
    """Every canonical line the statement prints, and every derived line whose parts are all on it.

    A person's edit of a line (statement_edits) stands in place of what the statement prints; the
    printed figure stays on the line beside it."""
    col = column or cfg.column
    scale = unit_scale(doc)
    edits = getattr(doc, "edits", {}) or {}
    out: dict[str, Line] = {}
    for key, spec in cfg.lines.items():
        use = spec.column or col
        found = _find_row(doc, spec, use)
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
        listed = any(re.search(spec.row, str(r[spec.label].value or "").strip(), re.IGNORECASE) for r in rows if spec.label in r)
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
    found = _find_all(doc, spec.table, spec.row, spec.column, spec.label)
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
        found = _find(doc, spec.table, spec.row, spec.column or "amount", spec.label)
        if found:
            out[key] = _line(doc, *found)
    return out


def period_end(doc) -> date | None:
    """The year end a financial statement is for, from its printed financial year."""
    v = doc.get("financial_year")
    return fy_end_of(v.value) if v else None
