"""Tables read from where their figures line up (stages/extract/bands.py): the body gives the columns, the header only
names them. Each layout below is one the heading reader misplaces: a heading centred over its column, a heading that
wraps, a column the configuration does not name, a title that holds a date, a label or a figure that wraps, a table that
runs onto the next page."""

from ingestion.config.models import ColumnDef
from ingestion.pageindex import Page, Word, build_lines
from ingestion.stages.extract import kwtables
from ingestion.stages.extract.run import extract_instance

from tests.test_tables_keywords import STMT

AFS = "audited_financial_statements"
W = 5          # width of a character on these pages


def page_at(no: int, items: list[tuple[float, float, str]]) -> Page:
    """A page of words: each item (y, x, text) starts its text at x on the line at y."""
    words = []
    for y, x, text in items:
        cx = x
        for tok in text.split():
            words.append(Word(tok, cx, y, cx + W * len(tok), y + 10, size=10.0))
            cx += W * len(tok) + 3
    return Page(no, "text_layer", 600, 800, words, build_lines(no, words, y_tol=3, column_gap=12, boilerplate=[]))


def right(edge: float, text: str) -> float:
    """Where a single figure starts when it is set right against `edge`."""
    return edge - W * len(text)


def row(y, label, *cells, label_x=60):
    return [(y, label_x, label)] + [(y, right(edge, v), v) for edge, v in cells if v]


def readings(cfg, doc_type, table, defs, pages):
    spec = cfg.fields.types[doc_type].table_keywords[table]
    return kwtables.band_readings(cfg, spec, defs, pages, list(cfg.fields.types[doc_type].table_keywords.values()))


def by_label(res, text):
    return next(r["cells"] for r in res.rows if text in (r["cells"].get("particulars") or r["cells"].get("description") or ""))


NOTE, CUR, PREV = 320, 430, 540


def _profit_and_loss() -> Page:
    """Headings centred over their columns, a serial number before each label, a Notes column, the dates on a second
    header line, and above them a title and a note on the unit that hold a date and words over every column."""
    items = [(40, 60, "PROFIT AND LOSS STATEMENT FOR THE YEAR ENDED ON 31st MARCH 2026"),
             (56, 120, "(All amounts in INR thousands unless otherwise stated)"),
             (80, 30, "Sl. No"), (80, 150, "Particulars"), (80, 300, "Notes"),
             (80, 362, "For the year ended"), (80, 472, "For the year ended"),
             (94, right(CUR, "31.03.2026"), "31.03.2026"), (94, right(PREV, "31.03.2025"), "31.03.2025")]
    y = 118
    for serial, label, note, cur, prev in [
            ("I", "Revenue from operations", "13", "1,000", "900"), ("II", "Other income", "14", "100", "80"),
            ("III", "Total income", "", "1,100", "980"), ("IV", "Expenses:", "", "", ""),
            ("", "Cost of materials consumed", "15", "600", "500"), ("", "Other expenses", "16", "100", "100"),
            ("", "Total expenses", "", "700", "600"), ("V", "Profit before exceptional items and tax", "", "400", "380"),
            ("VI", "Profit before tax", "", "400", "380")]:
        if serial:
            items.append((y, 30, serial))
        items += row(y, label, (NOTE, note), (CUR, cur), (PREV, prev))
        y += 16
    return page_at(1, items)


def test_columns_come_from_the_figures_and_the_header_only_names_them(cfg):
    res = next(r for r in readings(cfg, AFS, "profit_and_loss", STMT, [_profit_and_loss()]) if len(r.rows) > 5)
    revenue = by_label(res, "Revenue from operations")
    assert (revenue["current_period"], revenue["previous_period"]) == (1000, 900)
    assert by_label(res, "Total expenses")["current_period"] == 700
    assert all("13" not in (r["cells"]["particulars"] or "") for r in res.rows)   # the note number is its own column


def test_the_statement_is_extracted_from_its_figures_and_meets_its_contract(cfg):
    pl = extract_instance(cfg, AFS, [_profit_and_loss()], None)["tables"]["profit_and_loss"]
    assert pl["status"] == "found" and pl["contract"]["met"], pl.get("contract")
    revenue = next(r["cells"] for r in pl["rows"] if "Revenue from operations" in r["cells"]["particulars"])
    assert (revenue["current_period"], revenue["previous_period"]) == (1000, 900)


GST = [ColumnDef(name="description"), ColumnDef(name="taxable_value", type="number"), ColumnDef(name="igst", type="number"),
       ColumnDef(name="cgst", type="number"), ColumnDef(name="sgst", type="number")]


def test_wrapped_headings_name_their_columns_and_a_figure_that_wraps_is_joined(cfg):
    items = [(80, 30, "Nature of Supplies"), (80, 268, "Total taxable"), (80, 350, "Integrated"), (80, 430, "Central"),
             (80, 495, "State/UT"),
             (91, 280, "value"), (91, 370, "tax"), (91, 440, "tax"), (91, 505, "tax")]
    items += row(112, "(a) Outward taxable supplies (other than", (330, "153703745.00"), (400, "11066669.64"),
                 (470, "8300002.2"), (540, "8300002.23"), label_x=30)
    items += row(123, "zero rated, nil rated and exempted)", (470, "3"), label_x=30)
    items += row(140, "(b) Outward taxable supplies (zero rated)", (330, "0.00"), (400, "0.00"), (470, "0.00"),
                 (540, "0.00"), label_x=30)
    res = next(iter(readings(cfg, "gstr_3b", "outward_supplies", GST, [page_at(1, items)])))
    a = by_label(res, "(a) Outward taxable supplies")
    assert a["description"].endswith("nil rated and exempted)")
    assert (a["taxable_value"], a["igst"], a["cgst"], a["sgst"]) == (153703745, 11066669.64, 8300002.23, 8300002.23)


def test_years_the_table_does_not_ask_for_are_read_and_left_out_never_merged_into_another_column(cfg):
    edges = [260, 330, 400, 470, 540]
    years = ["2021 - 2022", "2022 - 2023", "2023 - 2024", "2024 - 2025", "2025 - 2026"]
    items = [(80, 40, "Element Name")] + [(80, e - W * 9 - 6, y) for e, y in zip(edges, years)]
    items += row(100, "Revenue from operations", *zip(edges, ["17,920.43", "18,902.85", "18,322.87", "20,741.76", "17,434.19"]), label_x=40)
    items += row(116, "Other income", *zip(edges, ["171.41", "406.11", "361.67", "1,131.22", "714.52"]), label_x=40)
    items += row(132, "Total income", *zip(edges, ["18,091.84", "19,308.96", "18,684.54", "21,872.98", "18,148.71"]), label_x=40)
    res = next(iter(readings(cfg, AFS, "profit_and_loss", STMT, [page_at(1, items)])))
    revenue = by_label(res, "Revenue from operations")
    assert revenue == {"particulars": "Revenue from operations", "current_period": 17434.19, "previous_period": 20741.76}


def test_a_label_set_flush_under_its_row_is_part_of_that_row(cfg):
    items = [(80, 60, "Particulars"), (80, right(CUR, "2026") - 10, "Year 2026"), (80, right(PREV, "2025") - 10, "Year 2025")]
    items += row(100, "Net cash flows from / (used in)", (CUR, "2,443.03"), (PREV, "5,820.66"))
    items += [(110, 60, "Operating Activities")]                        # flush: no space between it and the line above
    items += row(126, "Cash flows from investing", (CUR, "-1,356.80"), (PREV, "-1,165.39"))
    items += row(142, "Cash flows from financing", (CUR, "-1,011.76"), (PREV, "-4,309.25"))
    res = next(iter(readings(cfg, AFS, "cash_flow", STMT, [page_at(1, items)])))
    assert by_label(res, "Net cash flows")["particulars"] == "Net cash flows from / (used in) Operating Activities"
    assert len(res.rows) == 3


def _balance_sheet_half(no, rows, header=True):
    items = [(80, 60, "Particulars"), (80, 372, "As at 31.03.2026"), (80, 482, "As at 31.03.2025")] if header else []
    y = 100
    for label, cur, prev in rows:
        items += row(y, label, (CUR, cur), (PREV, prev))
        y += 16
    return page_at(no, items)


def test_a_table_that_runs_onto_the_next_page_with_no_header_there_is_one_table(cfg):
    first = _balance_sheet_half(1, [("Share capital", "500", "400"), ("Trade payables", "1,500", "1,390")])
    second = _balance_sheet_half(2, [("Inventories", "800", "700"), ("Trade receivables", "1,200", "1,090"),
                                     ("Total assets", "2,000", "1,790")], header=False)
    res = next(r for r in readings(cfg, AFS, "balance_sheet", STMT, [first, second]) if r.page_start == 1)
    assert (res.page_start, res.page_end) == (1, 2)
    assert by_label(res, "Total assets")["current_period"] == 2000


def test_a_page_that_opens_with_its_own_header_starts_a_new_table(cfg):
    first = _balance_sheet_half(1, [("Share capital", "500", "400"), ("Total assets", "2,000", "1,790")])
    second = _balance_sheet_half(2, [("Revenue from operations", "800", "700"), ("Other income", "1,200", "1,090")])
    res = next(r for r in readings(cfg, AFS, "balance_sheet", STMT, [first, second]) if r.page_start == 1)
    assert res.page_end == 1


def test_a_figure_whose_decimals_wrap_onto_the_next_line_is_read_whole(cfg):
    items = [(80, 30, "Nature of Supplies"), (80, 268, "Total taxable"), (80, 350, "Integrated"), (80, 430, "Central"),
             (80, 495, "State/UT"), (91, 280, "value"), (91, 370, "tax"), (91, 440, "tax"), (91, 505, "tax")]
    items += row(112, "(a) Outward taxable supplies (other than", (330, "193861553.00"), (400, "13958031.82"),
                 (470, "10468523."), (540, "10468523.8"), label_x=30)
    items += row(123, "zero rated, nil rated and exempted)", (470, "86"), (540, "6"), label_x=30)
    items += row(140, "(b) Outward taxable supplies (zero rated)", (330, "0.00"), (400, "0.00"), (470, "-"), (540, "-"), label_x=30)
    res = next(iter(readings(cfg, "gstr_3b", "outward_supplies", GST, [page_at(1, items)])))
    a = by_label(res, "(a) Outward taxable supplies")
    assert (a["taxable_value"], a["cgst"], a["sgst"]) == (193861553, 10468523.86, 10468523.86)
