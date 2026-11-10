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
    return [Word(text, x1 - 4 * len(text), y, x1, y + 8)]


def _page(no: int, rows: list[tuple]) -> Page:
    words: list[Word] = []
    for y, label, *figs in rows:
        if label:
            words += _w(label, LABEL_X if not label.startswith(("[", "BMW", "Unless")) else 20.0, y)
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
        (20, "BMW SAMPLE PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "[210000] Statement of profit and loss"),
        (60, "Unless otherwise specified, all monetary values are in Millions of INR"),
        *_dates(80, "01/04/2025", "01/04/2024"), (91, None, "to", "to"), *_dates(102, "31/03/2026", "31/03/2025"),
        (113, "Statement of profit and loss [Abstract]"),
        (124, "Basic earnings per share [INR/shares]", "13.17", "3.86"),
        (800, None, "1", None),   # page number
    ])
    p2 = _page(2, [
        (20, "BMW SAMPLE PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
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
        (20, "BMW SAMPLE PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
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
