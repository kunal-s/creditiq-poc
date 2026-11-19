"""Statements filed in XBRL and rendered to PDF: the configured layout reads them (fields.yaml, the XBRL variants).

The pages are laid out as the registrar's rendering prints them: a taxonomy code opens each statement, the period dates
head the columns, "[Abstract]" lines announce groups, and a wrapped label prints its figures between its two halves."""

from __future__ import annotations

from ingestion.pageindex import Page, Word, build_lines
from ingestion.stages.extract.tables import build_table

LABEL_X, CUR_X1, PREV_X1 = 69.0, 497.0, 570.0   # the period columns sit well over a column gap apart


def _w(text: str, x0: float, y: float) -> list[Word]:
    out, x = [], x0
    for t in text.split():
        out.append(Word(t, x, y, x + 5 * len(t), y + 8))
        x += 5 * len(t) + 3
    return out


def _right(text: str, x1: float, y: float) -> list[Word]:
    """A right-aligned figure; a footnote reference in front of it ("(A) 22,737.19") is a word of its own."""
    mark, _, fig = text.rpartition(" ") if text.startswith("(") and " " in text else ("", "", text)
    out = [Word(fig, x1 - 4 * len(fig), y, x1, y + 8)]
    if mark:
        out.insert(0, Word(mark, x1 - 4 * len(fig) - 4 - 5 * len(mark), y, x1 - 4 * len(fig) - 4, y + 8))
    return out


def _page(no: int, rows: list[tuple]) -> Page:
    words: list[Word] = []
    for y, label, *figs in rows:
        if label:
            words += _w(label, LABEL_X if not label.startswith(("[", "SAMPLE", "Unless")) else 20.0, y)
        for fig, x1 in zip(figs, (CUR_X1, PREV_X1)):
            if fig is not None:
                words += _right(fig, x1, y)
    return Page(no, "text_layer", 595, 842, words, build_lines(no, words, y_tol=3, column_gap=12, boilerplate=[]))


def _dates(y: float, a: str, b: str) -> list[tuple]:
    return [(y, None, a, b)]


def _rule(cfg, table: str):
    return next(v for v in cfg.fields.types["audited_financial_statements"].tables[table] if v.page_match and "[" in v.page_match)


def _defs(cfg, table: str):
    td = cfg.document_types.by_id()["audited_financial_statements"]
    return next(t.columns for t in td.schema_.tables if t.name == table)


def _pl_pages() -> list[Page]:
    p1 = _page(1, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "[210000] Statement of profit and loss"),
        (60, "Unless otherwise specified, all monetary values are in Millions of INR"),
        *_dates(80, "01/04/2025", "01/04/2024"), (91, None, "to", "to"), *_dates(102, "31/03/2026", "31/03/2025"),
        (113, "Statement of profit and loss [Abstract]"),
        (124, "Basic earnings per share [INR/shares]", "13.17", "3.86"),
        (800, None, "1", None),   # page number
    ])
    p2 = _page(2, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (60, "Unless otherwise specified, all monetary values are in Millions of INR"),
        *_dates(80, "01/04/2025", "01/04/2024"), (91, None, "to", "to"), *_dates(102, "31/03/2026", "31/03/2025"),
        (113, "Statement of profit and loss [Abstract]"),
        (124, "Income [Abstract]"),
        (135, "Revenue from operations", "60,167.77", "43,518.01"),
        (146, "Changes in inventories of finished goods and"),
        (150.5, None, "-4,261.19", "1,650.66"),
        (155, "stock-in-trade"),
        (166, "Employee benefit expense", "1,716.09", "1,601.59"),
        (177, "Whether company has other comprehensive income"),
        (181.5, None, "Yes", "Yes"),
        (186, "presented net of tax"),
        (197, "Total profit (loss) for period", "2,050.69", "600.62"),
        (220, "[210000a] Statement of profit and loss"),
        (240, "Other comprehensive income others", "-1.65", "0"),
    ])
    return [p1, p2]


def test_profit_and_loss_rows_from_an_xbrl_filing(cfg):
    t = build_table(_rule(cfg, "profit_and_loss"), _defs(cfg, "profit_and_loss"), _pl_pages(), cfg.routing.reading)
    rows = [(r["cells"]["particulars"], r["cells"]["current_period"], r["cells"]["previous_period"]) for r in t.rows]
    assert rows == [
        ("Revenue from operations", 60167.77, 43518.01),
        ("Changes in inventories of finished goods and stock-in-trade", -4261.19, 1650.66),
        ("Employee benefit expense", 1716.09, 1601.59),
        ("Total profit (loss) for period", 2050.69, 600.62),
    ]
    assert t.unparsed == 0


def test_a_multi_page_table_stops_at_the_next_statement_above_a_repeated_header(cfg):
    bs = _page(1, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "[110000] Balance sheet"),
        *_dates(80, "31/03/2026", "31/03/2025"),
        (91, "Balance sheet [Abstract]"),
        (102, "Total assets", "45,853.06", "36,250.8"),
        (113, "Total equity and liabilities", "45,853.06", "36,250.8"),
    ])
    nxt = _pl_pages()[0]
    nxt.no = 2
    t = build_table(_rule(cfg, "balance_sheet"), _defs(cfg, "balance_sheet"), [bs, nxt], cfg.routing.reading)
    assert [r["cells"]["particulars"] for r in t.rows] == ["Total assets", "Total equity and liabilities"]
    assert t.page_end == 1


def test_footnote_letters_before_figures_are_not_part_of_them(cfg):
    """The registrar's rendering prints a footnote reference in front of a figure ("(A) 22,737.19"): the row is
    still read, and a reference in front of a negative figure keeps its sign."""
    bs = _page(1, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "[110000] Balance sheet"),
        *_dates(80, "31/03/2026", "31/03/2025"),
        (91, "Balance sheet [Abstract]"),
        (102, "Property, plant and equipment", "(A) 22,737.19", "(B) 21,207.23"),
        (113, "Inventories", "12,631.51", "10,593.9"),
        (124, "Other current financial liabilities", "(K) 1,706.07", "(AB) -20.43"),
        (135, "Total assets", "45,853.06", "36,250.8"),
    ])
    t = build_table(_rule(cfg, "balance_sheet"), _defs(cfg, "balance_sheet"), [bs], cfg.routing.reading)
    rows = [(r["cells"]["particulars"], r["cells"]["current_period"], r["cells"]["previous_period"]) for r in t.rows]
    assert rows == [
        ("Property, plant and equipment", 22737.19, 21207.23),
        ("Inventories", 12631.51, 10593.9),
        ("Other current financial liabilities", 1706.07, -20.43),
        ("Total assets", 45853.06, 36250.8),
    ]


def test_a_statement_ending_on_the_next_statements_page_keeps_its_last_rows(cfg):
    """A balance sheet runs onto the page where the next statement opens: the rows above that statement's code
    are the balance sheet's last rows, read with the columns it already has."""
    bs = _page(1, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "[110000] Balance sheet"),
        *_dates(80, "31/03/2026", "31/03/2025"),
        (91, "Balance sheet [Abstract]"),
        (102, "Total assets", "45,853.06", "36,250.8"),
        (113, "Other current liabilities", "5,389.75", "5,446.16"),
    ])
    nxt = _page(2, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "Provisions, current", "68.72", "63.59"),
        (51, "Total equity and liabilities", "45,853.06", "36,250.8"),
        (80, "[210000] Statement of profit and loss"),
        *_dates(100, "01/04/2025", "01/04/2024"),
        (120, "Basic earnings per share [INR/shares]", "13.17", "3.86"),
    ])
    t = build_table(_rule(cfg, "balance_sheet"), _defs(cfg, "balance_sheet"), [bs, nxt], cfg.routing.reading)
    assert [r["cells"]["particulars"] for r in t.rows] == [
        "Total assets", "Other current liabilities", "Provisions, current", "Total equity and liabilities"]
    assert t.page_end == 2


def test_the_profit_and_loss_after_an_earnings_per_share_breakdown(cfg):
    """The "[210000]" code heads an earnings-per-share breakdown with a pair of period columns per class of share;
    the statement itself follows on a later page under its "[Abstract]" line alone, and ends where its
    earnings-per-share text block begins."""
    eps = _page(1, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "[210000] Statement of profit and loss"),
        (80, None, "01/04/2025  01/04/2024  01/04/2025  01/04/2024", None),
        (113, "Statement of profit and loss [Abstract]"),
        (124, "Basic earnings per share [INR/shares]", "13.17", "3.86"),
    ])
    pl = _page(2, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        *_dates(80, "01/04/2025", "01/04/2024"), (91, None, "to", "to"), *_dates(102, "31/03/2026", "31/03/2025"),
        (113, "Statement of profit and loss [Abstract]"),
        (135, "Revenue from operations", "70,105.29", "70,251.28"),
        (146, "Total profit before tax", "26,315.77", "24,750.41"),
        (157, "Total profit (loss) for period", "20,421.97", "18,753.31"),
        (180, None, "Textual information (21)", None),
        (191, "Profit for the year (Rs. in Crores)", "20421.97", "18753.31"),
    ])
    t = build_table(_rule(cfg, "profit_and_loss"), _defs(cfg, "profit_and_loss"), [eps, pl], cfg.routing.reading)
    rows = [(r["cells"]["particulars"], r["cells"]["current_period"]) for r in t.rows]
    assert rows == [("Revenue from operations", 70105.29), ("Total profit before tax", 26315.77),
                    ("Total profit (loss) for period", 20421.97)]
    assert (t.page_start, t.page_end) == (2, 2)


def test_a_footnote_reference_in_a_figure_keeps_its_sign():
    from ingestion.stages.extract.normalise import to_number

    assert to_number("(AO) -20.43") == -20.43
    assert to_number("(A) 22,737.19") == 22737.19
    assert to_number("(22,737.19)") == -22737.19   # brackets round a figure still mean a negative
    assert to_number("(a) 12") == 12


def test_a_letter_that_runs_on_from_a_label_stays_in_the_label(cfg):
    """"Total (A)" names a row: its letter follows the label's words, not a figure's column, and is kept."""
    bs = _page(1, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "[110000] Balance sheet"),
        *_dates(80, "31/03/2026", "31/03/2025"),
        (91, "Balance sheet [Abstract]"),
        (102, "Total (A)", "45,853.06", "36,250.8"),
    ])
    t = build_table(_rule(cfg, "balance_sheet"), _defs(cfg, "balance_sheet"), [bs], cfg.routing.reading)
    assert [(r["cells"]["particulars"], r["cells"]["current_period"]) for r in t.rows] == [("Total (A)", 45853.06)]
