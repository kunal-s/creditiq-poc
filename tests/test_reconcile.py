"""The spread checks a statement against itself and against the following year's comparative (F-22.3)."""

import re
from types import SimpleNamespace

from engine import reconcile
from engine.configstore.schema import StatementsSection
from engine.contracts import SpreadColumn

CFG = StatementsSection.model_validate({
    "lines": {
        "short_term_borrowings": {"table": "balance_sheet", "row": r"^\(\w\)\s*short-term borrowings"},
        "long_term_borrowings": {"table": "balance_sheet", "row": r"^\(\w\)\s*long-term borrowings"},
        "trade_receivables": {"table": "balance_sheet", "row": r"^\(\w\)\s*trade receivables"},
        "total_assets": {"table": "balance_sheet", "row": r"^total assets"},
        "total_equity_and_liabilities": {"table": "balance_sheet", "row": r"^total equity"},
    },
    "gst_outward": {"table": "t", "row": "x", "column": "c"},
})
COLUMNS = [SpreadColumn(key="audited-2024", fy="FY 2023-24", period_end="2024-03-31", basis="audited"),
           SpreadColumn(key="audited-2025", fy="FY 2024-25", period_end="2025-03-31", basis="audited")]


def _doc(doc_id, rows, unit=None):
    """rows: (label, current, previous)."""
    cells = {}
    for i, (label, cur, prev) in enumerate(rows):
        for col, v in (("particulars", label), ("current_period", cur), ("previous_period", prev)):
            if v is not None:
                cells[f"balance_sheet[{i}].{col}"] = SimpleNamespace(value=v, manual=False, field_id=f"{doc_id}{i}{col}", pending=False, raw=str(v))

    def rows_of(table):
        out = {}
        for name, v in cells.items():
            m = re.match(rf"{table}\[(\d+)\]\.(.+)", name)
            if m:
                out.setdefault(int(m[1]), {})[m[2]] = v
        return [out[i] for i in sorted(out)]

    return SimpleNamespace(id=doc_id, edits={}, rows=rows_of, evidence=lambda *a: [],
                           get=lambda n: SimpleNamespace(value=unit) if unit and n == "amount_unit" else None)


def _run(first, second):
    return {c.id: c for c in reconcile.checks(COLUMNS, [[first], [second]], CFG)}


def test_a_balance_sheet_that_balances_agrees_and_one_that_does_not_differs():
    ok = _doc("A", [("Total Assets", 100, None), ("Total Equity & Liabilities", 100, None)])
    bad = _doc("B", [("Total Assets", 100, None), ("Total Equity & Liabilities", 90, None)])
    found = _run(ok, bad)
    assert found["balance:audited-2024"].outcome == "agrees"
    assert found["balance:audited-2025"].outcome == "differs" and found["balance:audited-2025"].difference == 10


def test_a_comparative_agrees_to_the_rounding_of_the_unit_it_is_printed_in():
    first = _doc("A", [("(b) Trade receivables", 849_129, None)])
    second = _doc("B", [("(b) Trade receivables", 2_810, 849)], unit="Thousands")
    check = _run(first, second)["comparative:audited-2024:trade_receivables"]
    assert check.outcome == "agrees" and check.tolerance == 500 and check.difference == 129


def test_an_amount_moved_between_lines_is_flagged_on_both_and_named_as_a_reclassification():
    first = _doc("A", [("(a) Short-term borrowings", 503_800, None), ("(a) Long-term borrowings", 0, None)])
    second = _doc("B", [("(a) Short-term borrowings", 0, 0), ("(a) Long-term borrowings", 504, 504)], unit="Thousands")
    found = _run(first, second)
    short, long = found["comparative:audited-2024:short_term_borrowings"], found["comparative:audited-2024:long_term_borrowings"]
    assert short.outcome == long.outcome == "differs"
    assert "reclassified" in short.detail and "reclassified" in long.detail
