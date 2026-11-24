"""Tables found by their column headings (Epic 5a of the classification restructure; FRD F-15.13): scenarios 16, 17,
24, 25 and 27 of the plan, units (TC-06) and a table running onto a second page (TC-07)."""

import pytest

from ingestion.config.models import ColumnDef, Units
from ingestion.pageindex import Page, Word, build_lines
from ingestion.stages.extract import kwtables, units
from ingestion.stages.extract.normalise import to_number

STMT = [ColumnDef(name="particulars"), ColumnDef(name="current_period", type="number"), ColumnDef(name="previous_period", type="number")]


def grid(no: int, rows: list[list[tuple[float, str]]], *, title: str | None = None, top: float = 120.0) -> Page:
    """A page of positioned cells: each row a list of (x, text); an optional bold title above."""
    words, y = [], top
    if title:
        x = 40.0
        for tok in title.split():
            words.append(Word(tok, x, 60, x + 8 * len(tok), 74, size=14.0, bold=True))
            x += 8 * len(tok) + 4
    for row in rows:
        for x, text in row:
            cx = x
            for tok in text.split():
                words.append(Word(tok, cx, y, cx + 5 * len(tok), y + 10, size=10.0))
                cx += 5 * len(tok) + 3
        y += 16
    return Page(no, "text_layer", 600, 800, words, build_lines(no, words, y_tol=3, column_gap=12, boilerplate=[]))


def read(cfg, doc_type, table, defs, pages):
    spec = cfg.fields.types[doc_type].table_keywords[table]
    return kwtables.read(cfg, spec, defs, pages, list(cfg.fields.types[doc_type].table_keywords.values()))


def cells(res, *cols):
    return [tuple(r["cells"][c] for c in cols) for r in res.rows]


def test_scenario_16_year_columns_headed_by_financial_year_are_read_latest_first(cfg):
    p = grid(1, [[(40, "Particulars"), (300, "FY 2024-25"), (420, "FY 2025-26")],     # the older year printed first
                 [(40, "Share capital"), (300, "40,00,000"), (420, "50,00,000")],
                 [(40, "Trade payables"), (300, "1,39,00,000"), (420, "1,48,00,000")]], title="Balance Sheet")
    res = read(cfg, "audited_financial_statements", "balance_sheet", STMT, [p])
    assert cells(res, "particulars", "current_period", "previous_period") == [
        ("Share capital", 5000000, 4000000), ("Trade payables", 14800000, 13900000)]


def test_scenario_17_renamed_reordered_columns_and_a_notes_column_read_the_same_figures(cfg):
    p = grid(1, [[(40, "Description"), (250, "Note No."), (320, "As at 31.03.2026"), (440, "As at 31.03.2025")],
                 [(40, "Share capital"), (260, "3"), (320, "50,00,000"), (440, "40,00,000")],
                 [(40, "Inventories"), (260, "7"), (320, "2,16,00,000"), (440, "2,01,00,000")]],
             title="Statement of Financial Position")
    res = read(cfg, "audited_financial_statements", "balance_sheet", STMT, [p])
    assert cells(res, "particulars", "current_period", "previous_period") == [
        ("Share capital", 5000000, 4000000), ("Inventories", 21600000, 20100000)]
    assert "notes" not in res.rows[0]["raw"]


BANK = [ColumnDef(name="date", type="date"), ColumnDef(name="description"), ColumnDef(name="reference_number"),
        ColumnDef(name="debit", type="number"), ColumnDef(name="credit", type="number"), ColumnDef(name="balance", type="number"),
        ColumnDef(name="value_date", type="date")]


def test_scenario_24_one_amount_column_with_a_dr_cr_marker(cfg):
    p = grid(1, [[(40, "Txn Date"), (110, "Narration"), (330, "Amount"), (420, "Dr/Cr"), (480, "Balance")],
                 [(40, "01/04/2025"), (110, "OPENING BALANCE"), (480, "1,00,000.00")],
                 [(40, "03/04/2025"), (110, "NEFT CR BHARAT PUMPS"), (330, "50,000.00"), (420, "Cr"), (480, "1,50,000.00")],
                 [(40, "05/04/2025"), (110, "RTGS DR SUPPLIER"), (330, "20,000.00"), (420, "Dr"), (480, "1,30,000.00")]],
             title="Statement of Account")
    res = read(cfg, "bank_statement", "transactions", BANK, [p])
    assert cells(res, "debit", "credit", "balance")[1:] == [(None, 50000, 150000), (20000, None, 130000)]
    assert res.repairs == [] and "amount" not in res.rows[1]["raw"]


def test_scenario_25_a_gstr_3b_exported_from_accounting_software(cfg):
    defs = [ColumnDef(name="description"), ColumnDef(name="taxable_value", type="number"), ColumnDef(name="igst", type="number"),
            ColumnDef(name="cgst", type="number"), ColumnDef(name="sgst", type="number")]
    p = grid(1, [[(40, "3.1 Details of Outward Supplies")],
                 [(40, "Nature of Supply"), (250, "Taxable Value"), (340, "IGST"), (400, "CGST"), (460, "SGST")],
                 [(40, "(a) Outward taxable supplies"), (250, "1,96,00,000"), (340, "0"), (400, "17,64,000"), (460, "17,64,000")],
                 [(40, "(b) Zero rated supplies"), (250, "0"), (340, "0"), (400, "0"), (460, "0")]])
    res = read(cfg, "gstr_3b", "outward_supplies", defs, [p])
    assert cells(res, "taxable_value", "cgst") == [(19600000, 1764000), (0, 0)]


@pytest.mark.parametrize("printed, value", [
    ("1,234-", -1234), ("(12,345)", -12345), ("Nil", 0), ("1 23 456", 123456), ("1,234 Dr.", -1234), ("Dr 1,234", -1234),
    ("1,234 Cr", 1234), ("75,000 90,000", None), ("2025 2024", None)])
def test_scenario_27_amounts_in_their_printed_forms(printed, value):
    assert to_number(printed) == value


@pytest.mark.parametrize("text, unit", [
    ("(Rs. '000)", "thousand"), ("₹ in 000s", "thousand"), ("Amount in Rs. Lacs", "lakh"), ("Rs. in Crore", "crore"),
    ("All amounts in Indian Rupees unless otherwise stated", "rupee"), ("Sanctioned amount Rs. 2,50,000", None)])
def test_tc_06_the_unit_as_printed(text, unit):
    assert units.in_line(text, Units()) == unit


def test_tc_07_a_table_running_onto_a_second_page_with_its_header_repeated(cfg):
    head = [(40, "Particulars"), (320, "31 March 2026"), (440, "31 March 2025")]
    p1 = grid(1, [head, [(40, "Share capital"), (320, "50,00,000"), (440, "40,00,000")]], title="Balance Sheet")
    p2 = grid(2, [head, [(40, "Inventories"), (320, "2,16,00,000"), (440, "2,01,00,000")]])
    spec = cfg.fields.types["audited_financial_statements"].table_keywords["balance_sheet"].model_copy(update={"multi_page": True})
    res = kwtables.read(cfg, spec, STMT, [p1, p2])
    assert cells(res, "particulars", "current_period") == [("Share capital", 5000000), ("Inventories", 21600000)]
    assert (res.page_start, res.page_end) == (1, 2)
