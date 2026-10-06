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
class Line:
    value: float
    evidence: list[Evidence] = field(default_factory=list)
    manual: bool = False
    field_ids: list[str] = field(default_factory=list)


def _number(v) -> float | None:
    if v is None or v.value in (None, ""):
        return None
    try:
        return float(str(v.value).replace(",", ""))
    except ValueError:
        return None


def _find(doc, table: str, row_pattern: str, column: str, label_column: str = "particulars") -> tuple[float, object] | None:
    rx = re.compile(row_pattern, re.IGNORECASE)
    for row in doc.rows(table):
        label = row.get(label_column)
        if label is None or not rx.search(str(label.value or "").strip()):
            continue
        cell = row.get(column)
        number = _number(cell)
        if number is not None:
            return number, cell
    return None


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
    """Every canonical line the statement prints, and every derived line whose parts are all on it."""
    col = column or cfg.column
    out: dict[str, Line] = {}
    for key, spec in cfg.lines.items():
        found = _find(doc, spec.table, spec.row, spec.column or col, spec.label)
        if found:
            number, cell = found
            out[key] = Line(number, doc.evidence(cell), cell.manual, [cell.field_id])
    for key, expression in cfg.derived.items():
        terms = _terms(expression)
        if all(name in out for _, name in terms):
            out[key] = Line(
                sum(sign * out[name].value for sign, name in terms),
                [e for _, name in terms for e in out[name].evidence[:1]],
                any(out[name].manual for _, name in terms),
                [i for _, name in terms for i in out[name].field_ids],
            )
    return out


def gst_outward(doc, cfg: StatementsSection) -> Line | None:
    spec = cfg.gst_outward
    found = _find(doc, spec.table, spec.row, spec.column, spec.label)
    if not found:
        return None
    number, cell = found
    return Line(number, doc.evidence(cell), cell.manual, [cell.field_id])


def period_end(doc) -> date | None:
    """The year end a financial statement is for, from its printed financial year."""
    v = doc.get("financial_year")
    return fy_end_of(v.value) if v else None
