"""Arithmetic over figures the host returned, done here and never by the model.

A tool with a `compute` block fetches its source as any read tool does, then works out one configured formula for
each period in it: the model only chooses which formula. Formulas are + - * / and brackets over the source's line
keys and numbers; anything else is refused when the configuration loads. Each period's result carries its inputs and
the working with the figures put in, so the answer shows how it was reached. A missing input or a zero divisor gives
no number, and says which.
"""

from __future__ import annotations

import ast
import operator
import re
from typing import Any

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_SIGN = {"+": "+", "-": "−", "*": "×", "/": "÷"}
_NAME = re.compile(r"[A-Za-z_]\w*")


class FormulaError(ValueError):
    pass


def parse(expression: str) -> ast.expr:
    """The expression's tree, or FormulaError if it is anything but arithmetic over names and numbers."""
    try:
        tree = ast.parse(expression, mode="eval").body
    except SyntaxError as e:
        raise FormulaError(f"{expression!r}: {e.msg}") from None
    for node in ast.walk(tree):
        ok = isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.USub, ast.UAdd, *_OPS)) or (
            isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool))
        if not ok:
            raise FormulaError(f"{expression!r}: only + - * / and brackets over line names and numbers are allowed")
    return tree


def names(expression: str) -> list[str]:
    """The line keys an expression reads, in the order they first appear."""
    found = {n.id for n in ast.walk(parse(expression)) if isinstance(n, ast.Name)}
    return [n for n in dict.fromkeys(_NAME.findall(expression)) if n in found]


def _eval(node: ast.expr, values: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, values)
        return -v if isinstance(node.op, ast.USub) else v
    assert isinstance(node, ast.BinOp)
    left, right = _eval(node.left, values), _eval(node.right, values)
    if isinstance(node.op, ast.Div) and right == 0:
        raise ZeroDivisionError
    return _OPS[type(node.op)](left, right)


def _divisors(node: ast.expr) -> list[ast.expr]:
    return [n.right for n in ast.walk(node) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)]


def _amount(v: float, spec) -> str:
    return f"{v / spec.divisor:,.{spec.decimals}f}"


def _result(v: float, f) -> str:
    return f"{v:,.{f.decimals}f}{f.suffix}"


def _working(expression: str, shown: dict[str, str]) -> str:
    # Operators first, so a sign in a figure or a hyphen in a label is left as it is.
    text = re.sub(r"\s*([+\-*/])\s*", lambda m: f" {_SIGN[m.group(1)]} ", expression)
    text = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", text)).strip()
    return _NAME.sub(lambda m: shown.get(m.group(0), m.group(0)), text)


def _rows(data: Any, path: str) -> list:
    v = data.get(path) if isinstance(data, dict) else None
    return v if isinstance(v, list) else []


def run(spec, selected: str, data: Any) -> dict:
    """Work out formula `selected` for every period in the host's answer `data`."""
    f = spec.formulas[selected]
    tree = parse(f.expression)
    keys = names(f.expression)
    L, P = spec.lines, spec.periods
    lines = {r.get(L.key): r for r in _rows(data, L.list) if isinstance(r, dict)}
    periods = [p for p in _rows(data, P.list) if isinstance(p, dict)]
    label = {k: str((lines.get(k) or {}).get(L.label) or k.replace("_", " ").capitalize()) for k in keys}
    results = []
    for i, period in enumerate(periods):
        try:
            name = P.label.format(**period)
        except (KeyError, IndexError, ValueError):
            name = f"Period {i + 1}"
        values: dict[str, float] = {}
        for k in keys:
            cells = (lines.get(k) or {}).get(L.values) or []
            cell = cells[i] if i < len(cells) else None
            v = cell.get(L.value) if isinstance(cell, dict) else cell
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                values[k] = float(v)
        missing = [label[k] for k in keys if k not in values]
        inputs = "; ".join(f"{label[k]} {_amount(values[k], spec.amount)}{spec.amount.suffix}" for k in keys if k in values)
        row = {"period": name, "inputs": inputs}
        if missing:
            row |= {"working": f"Not worked out: {', '.join(missing)} not on file", "value": ""}
        else:
            row["working"] = _working(f.expression, {k: _amount(values[k], spec.amount) for k in keys})
            try:
                row["value"] = _result(_eval(tree, values), f)
            except ZeroDivisionError:
                zero = [_working(ast.unparse(d), label) for d in _divisors(tree) if _safe(d, values) == 0]
                row |= {"working": f"Not worked out: {' and '.join(zero) or 'the divisor'} is zero", "value": ""}
        results.append(row)
    return {"ratio": f.label, "formula": f.formula, "results": results}


def _safe(node: ast.expr, values: dict[str, float]) -> float | None:
    try:
        return _eval(node, values)
    except ZeroDivisionError:
        return None
