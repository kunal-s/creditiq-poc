"""A statement checked against itself and against the next year's report (FRD F-22.3).

The balance sheet's two totals must agree. A figure a year's statements give as the year's own must agree
with what the following year's statements give as their comparative. Both are only as exact as the unit the
statements print in: a report in thousands rounds each figure, so the comparative of a year first reported in
rupees can differ by up to half a thousand and still agree. Nothing here changes a figure; it says where two
statements disagree so a person looks at the page.
"""

from __future__ import annotations

from . import facts as facts_module
from . import statements
from .configstore.schema import StatementsSection
from .contracts import Evidence, SpreadCheck, SpreadColumn
from .policy import INPUT_LABELS

LABELS = {**INPUT_LABELS, "total_assets": "Total assets", "total_equity_and_liabilities": "Total equity and liabilities"}
BALANCE = ("total_assets", "total_equity_and_liabilities")
READ = ("printed", "nil", "edited")


def _first(copies: list[dict[str, statements.Line]], name: str) -> tuple[statements.Line, int] | None:
    for i, lines in enumerate(copies):
        if name in lines and lines[name].state in READ:
            return lines[name], i
    return None


def _agree(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance + 1e-6


def _fmt(v: float) -> str:
    return f"{v:,.0f}"


def checks(columns: list[SpreadColumn], groups: list[list[facts_module.Doc]], cfg: StatementsSection) -> list[SpreadCheck]:
    out: list[SpreadCheck] = []
    current = [[statements.lines(d, cfg) for d in docs] for docs in groups]
    for i, col in enumerate(columns):
        a, b = _first(current[i], BALANCE[0]), _first(current[i], BALANCE[1])
        if a and b:
            tolerance = a[0].scale
            diff = a[0].value - b[0].value
            ok = _agree(a[0].value, b[0].value, tolerance)
            out.append(SpreadCheck(
                id=f"balance:{col.key}", kind="balance", fy=col.fy, label=f"Balance sheet totals, {col.fy}",
                outcome="agrees" if ok else "differs", left_label=LABELS[BALANCE[0]], left=a[0].value,
                right_label=LABELS[BALANCE[1]], right=b[0].value, difference=diff, tolerance=tolerance,
                detail=(f"Total assets {_fmt(a[0].value)} and total equity and liabilities {_fmt(b[0].value)} "
                        + ("agree." if ok else f"differ by {_fmt(abs(diff))}.")),
                evidence=a[0].evidence[:1] + b[0].evidence[:1], lines=list(BALANCE)))
    # Each year's figures against the comparative the next audited year's statements print.
    for i in range(len(columns) - 1):
        earlier, later = columns[i], columns[i + 1]
        if (earlier.basis, later.basis) != ("audited", "audited"):
            continue
        comparatives = [statements.lines(d, cfg, column="previous_period") for d in groups[i + 1]]
        for key in cfg.lines:
            own, comp = _first(current[i], key), _first(comparatives, key)
            if not (own and comp) or key in BALANCE:
                continue
            tolerance = max(own[0].scale, comp[0].scale) / 2
            diff = own[0].value - comp[0].value
            ok = _agree(own[0].value, comp[0].value, tolerance)
            label = LABELS.get(key, key.replace("_", " ").capitalize())
            out.append(SpreadCheck(
                id=f"comparative:{earlier.key}:{key}", kind="comparative", fy=earlier.fy,
                label=f"{label}, {earlier.fy}", outcome="agrees" if ok else "differs",
                left_label=f"As the {earlier.fy} statements give it", left=own[0].value,
                right_label=f"As the {later.fy} statements give it", right=comp[0].value, difference=diff,
                tolerance=tolerance,
                detail=(f"{label} for {earlier.fy} is {_fmt(own[0].value)} in the {earlier.fy} statements and "
                        f"{_fmt(comp[0].value)} in the {later.fy} statements"
                        + (", which agree to the rounding of the unit they print in." if ok else f"; they differ by {_fmt(abs(diff))}.")),
                evidence=own[0].evidence[:1] + comp[0].evidence[:1], lines=[key]))
    _offsets(out)
    return out


def _offsets(found: list[SpreadCheck]) -> None:
    """Two differences that cancel (one line over by what another is under) are most likely one amount moved
    between the lines in the later statements; say so, so the person looks there rather than at each."""
    differing = [c for c in found if c.kind == "comparative" and c.outcome == "differs"]
    for c in differing:
        for other in differing:
            if other is not c and other.fy == c.fy and abs(c.difference + other.difference) <= max(c.tolerance, other.tolerance) * 2:
                c.detail += f" The difference is offset by {other.label.rsplit(',', 1)[0].lower()}, so the amount may have been reclassified in the later statements."
                break
