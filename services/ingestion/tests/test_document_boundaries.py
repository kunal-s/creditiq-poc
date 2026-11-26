"""Where one document ends and the next begins, and the facts a document states once for all its pages.

A file's running header and footer (stages/furniture.py) are found from its own pages. A period the running header
states is the document's: a year a sentence near the top of a page mentions does not open another document. A run of
pages that carry the same running header is one document's, however many of them say too little to be typed. A page
with no title or identity of its own stays with the document before it. The unit is the one the statements' own
captions print; a different unit stated elsewhere goes to a person."""

from ingestion.stages import furniture, identity
from ingestion.stages import pages as pages_stage
from ingestion.stages.extract.run import extract_instance

from tests.test_table_bands import CUR, PREV, page_at, right, row

AFS = "audited_financial_statements"
HEADER = "SAMPLE TRADERS LIMITED Standalone Financial Statements for period 01/04/2023 to 31/03/2024"


def _mark(cfg, pages):
    furniture.mark(pages, cfg.keywords.settings.zones.furniture)
    return pages


def _narrative(no, header=HEADER, top_sentence=None):
    items = [(20, 30, header)] if header else []
    if top_sentence:
        items.append((40, 30, top_sentence))
    words = ["education", "water", "health", "skills", "farming", "energy", "housing", "sanitation", "forestry", "nutrition"]
    items += [(200 + 16 * i, 30, f"The Company supported {words[(no + i) % 10]} work with partners in {words[(no * 3 + i) % 10]} areas.")
              for i in range(6)]
    items.append((760, 280, f"Page {no}"))
    return page_at(no, items)


def test_a_line_repeated_at_the_top_of_most_pages_is_the_running_header(cfg):
    pages = _mark(cfg, [_narrative(n) for n in range(1, 6)])
    assert [l.text for l in furniture.lines(pages[2], "top")] == [HEADER]
    assert [l.text for l in furniture.lines(pages[2], "bottom")] == ["Page 3"]    # numbers differ, the line is the same
    assert not furniture.lines(_mark(cfg, [_narrative(1), _narrative(2)])[0])    # two pages are too few to tell


def test_a_year_a_sentence_mentions_does_not_open_another_document_when_the_running_header_states_the_period(cfg):
    pages = _mark(cfg, [_narrative(1), _narrative(2), _narrative(3, top_sentence="Spent in financial year 2021-22 on education"),
                        _narrative(4), _narrative(5, top_sentence="FY 2022-23 was a year of recovery")])
    _, docs = identity.split(cfg, AFS, pages)
    assert [(d[0].no, d[-1].no) for d in docs] == [(1, 5)]
    ident = identity.identify(cfg, AFS, docs[0], None)
    assert (ident.key, ident.status) == ("2024-03-31", "found")


def test_running_headers_that_state_different_years_are_different_documents(cfg):
    other = HEADER.replace("01/04/2023 to 31/03/2024", "01/04/2022 to 31/03/2023")
    pages = _mark(cfg, [_narrative(1), _narrative(2), _narrative(3), _narrative(4, other), _narrative(5, other), _narrative(6, other)])
    _, docs = identity.split(cfg, AFS, pages)
    assert [(d[0].no, d[-1].no) for d in docs] == [(1, 3), (4, 6)]


def _balance_sheet(no, header=HEADER):
    items = ([(20, 30, header)] if header else []) + [(60, 30, "BALANCE SHEET AS AT 31ST MARCH 2024")]
    items += [(80, 60, "Particulars"), (80, 372, "As at 31.03.2024"), (80, 482, "As at 31.03.2023")]
    y = 100
    for label, cur, prev in [("Share capital", "500", "400"), ("Reserves and surplus", "900", "800"),
                             ("Long-term borrowings", "300", "250"), ("Trade payables", "1,500", "1,390"),
                             ("Total equity and liabilities", "3,200", "2,840"), ("Inventories", "800", "700"),
                             ("Trade receivables", "1,200", "1,090"), ("Cash and cash equivalents", "1,200", "1,050"),
                             ("Total assets", "3,200", "2,840")]:
        items += row(y, label, (CUR, cur), (PREV, prev))
        y += 16
    items.append((760, 280, f"Page {no}"))
    return page_at(no, items)


def test_pages_too_plain_to_type_between_two_of_one_document_are_that_document_when_they_share_its_running_header(cfg):
    pages = _mark(cfg, [_balance_sheet(1), _narrative(2), _narrative(3), _narrative(4), _balance_sheet(5)])
    typing = pages_stage.type_pages(cfg, pages, None)
    assert typing.types_of(1) == [AFS] and typing.types_of(5) == [AFS]
    assert all(typing.types_of(n) == [AFS] for n in (2, 3, 4)), {n: typing.types_of(n) for n in range(1, 6)}


def test_an_untitled_page_whose_only_words_are_shared_with_another_type_stays_with_the_document_before_it(cfg):
    first = page_at(1, [(20, 30, "FORM GSTR-1"), (40, 30, "Details of outward supplies of goods or services"),
                        (60, 30, "GSTIN 27AAACS1234F1Z5"), (76, 30, "Tax period Sep"), (92, 30, "Financial year 2026-27"),
                        (120, 30, "B2B invoices  44  1,53,70,374  11,06,666  83,000  83,000"),
                        (136, 30, "Taxable outward supplies  1,53,70,374")])
    second = page_at(2, [(120, 30, "Integrated tax  Central tax  State/UT tax  Cess"),
                         (136, 30, "Nil rated  0.00  0.00  0.00"), (152, 30, "Zero rated  0.00  0.00  0.00"),
                         (168, 30, "Outward taxable supplies  0.00  0.00  0.00")])
    typing = pages_stage.type_pages(cfg, _mark(cfg, [first, second]), None)
    assert typing.types_of(1) == ["gstr_1"]
    assert typing.types_of(2) == ["gstr_1"], typing.page_info(2)


def test_the_unit_the_statements_print_stands_and_a_different_unit_stated_elsewhere_goes_to_a_person(cfg):
    note = page_at(1, [(120, 30, "Expenditure on research (Rs. in lakhs)"), (140, 30, "Capital 12.5 Recurring 40.2")])
    items = [(40, 30, "STATEMENT OF PROFIT AND LOSS FOR THE YEAR ENDED 31ST MARCH 2024"),
             (60, 30, "All amounts in INR crores"),
             (80, 60, "Particulars"), (80, 362, "Year ended 31.03.2024"), (80, 472, "Year ended 31.03.2023")]
    y = 100
    for label, cur, prev in [("Revenue from operations", "70,105", "70,251"), ("Other income", "3,538", "2,437"),
                             ("Total income", "73,643", "72,688"), ("Cost of materials consumed", "21,309", "19,809"),
                             ("Other expenses", "26,011", "28,202"), ("Total expenses", "47,320", "48,011"),
                             ("Profit before exceptional items and tax", "26,323", "24,677"),
                             ("Profit before tax", "26,323", "24,677")]:
        items += row(y, label, (CUR, cur), (PREV, prev))
        y += 16
    out = extract_instance(cfg, AFS, [note, page_at(2, items)], None)
    unit = out["fields"]["amount_unit"]
    assert unit["value"] == "crore"
    assert "lakhs" in unit.get("correction", "") and "please confirm" in unit["correction"]
