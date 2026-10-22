"""A statement's printed unit scales its amounts to rupees; the printed year end reads in the forms filed accounts use."""

from types import SimpleNamespace

import pytest

from engine import statements
from engine.util import fy_end_of


def _doc(unit):
    return SimpleNamespace(get=lambda name: SimpleNamespace(value=unit) if unit and name == "amount_unit" else None)


@pytest.mark.parametrize("unit,scale", [(None, 1), ("Thousands", 1e3), ("thousand", 1e3), ("Lakhs", 1e5), ("Crores", 1e7), ("Millions", 1e6), ("furlongs", 1)])
def test_the_scale_follows_the_printed_unit(unit, scale):
    assert statements.unit_scale(_doc(unit)) == scale


@pytest.mark.parametrize("printed", ["31ST MARCH, 2024", "31st March, 2024", "31 March 2024", "31.03.2024"])
def test_the_year_end_reads_in_filed_accounts_forms(printed):
    assert str(fy_end_of(printed)) == "2024-03-31"


def _statement(rows):
    cells = {f"balance_sheet[{i}].{k}": SimpleNamespace(value=v, manual=False, field_id=f"F{i}{k}", pending=False, raw=str(v))
             for i, (label, amount) in enumerate(rows) for k, v in (("particulars", label), ("current_period", amount)) if v is not None}
    doc = SimpleNamespace(id="DOC-1", edits={}, get=lambda name: None, evidence=lambda *a: [])
    import re
    def table_rows(table):
        out = {}
        for name, v in cells.items():
            m = re.match(rf"{table}\[(\d+)\]\.(.+)", name)
            if m:
                out.setdefault(int(m[1]), {})[m[2]] = v
        return [out[i] for i in sorted(out)]
    doc.rows = table_rows
    return doc


def _cfg(absent):
    from engine.configstore.schema import StatementsSection
    return StatementsSection.model_validate({
        "lines": {"inventories": {"table": "balance_sheet", "row": r"^\(\w\)\s*inventories"},
                  "trade_receivables": {"table": "balance_sheet", "row": r"^\(\w\)\s*trade receivables"}},
        "derived": {"current_assets": "inventories + trade_receivables"},
        "absent_is_nil": absent, "gst_outward": {"table": "t", "row": "x", "column": "c"}})


def test_a_listed_row_the_statement_does_not_print_is_nil_and_marked():
    lines = statements.lines(_statement([("(b) Trade receivables", 100)]), _cfg(["inventories"]))
    assert lines["inventories"].value == 0 and lines["inventories"].not_printed
    assert lines["current_assets"].value == 100 and lines["current_assets"].parts[0].not_printed


def test_a_row_that_is_printed_but_unread_is_not_absent():
    lines = statements.lines(_statement([("(a) Inventories", None), ("(b) Trade receivables", 100)]), _cfg(["inventories"]))
    assert "inventories" not in lines and "current_assets" not in lines


def test_an_unlisted_missing_line_still_blocks_what_is_derived_from_it():
    lines = statements.lines(_statement([("(b) Trade receivables", 100)]), _cfg([]))
    assert "current_assets" not in lines
