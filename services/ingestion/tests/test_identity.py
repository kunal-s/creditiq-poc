"""Document identity (Epic 4 of the classification restructure; FRD F-08.1, F-08.1a, F-08.3): periods read as date
ranges from a document's own pages, and documents split where the period, account or person changes."""

from datetime import date

import pytest

from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.stages import identity as I
from ingestion.stages.periods import in_line, page_level
from ingestion.store import Store

from .test_keywords import page

B = 14.0


def title(text):
    return (text, B, True)


def span(p):
    return (p.kind, p.start, p.end)


@pytest.mark.parametrize("line, want", [
    ("STATEMENT OF PROFIT AND LOSS FOR THE YEAR ENDED 31 MARCH 2026", ("year_end", date(2025, 4, 1), date(2026, 3, 31))),
    ("Balance Sheet as at 31st March, 2026", ("as_of", date(2026, 3, 31), date(2026, 3, 31))),
    ("For the nine months ended 31 December 2025", ("period_end", date(2025, 4, 1), date(2025, 12, 31))),
    ("Statement 01 Apr 2025 to 30 Sep 2026", ("range", date(2025, 4, 1), date(2026, 9, 30))),
    ("Statement period 01/04/2025 - 31/03/2026", ("range", date(2025, 4, 1), date(2026, 3, 31))),
    ("FY 2025-26", ("financial_year", date(2025, 4, 1), date(2026, 3, 31))),
    ("Financial Year FY2025", ("financial_year", date(2024, 4, 1), date(2025, 3, 31))),
    ("Assessment Year 2025-26", ("assessment_year", date(2024, 4, 1), date(2025, 3, 31))),
    ("Return Period 12/2025", ("month", date(2025, 12, 1), date(2025, 12, 31))),
    ("Tax period 042025", ("month", date(2025, 4, 1), date(2025, 4, 30))),          # TC-05
    ("Tax Period December 2025", ("month", date(2025, 12, 1), date(2025, 12, 31))),
    ("Quarter 1 (Apr-Jun) 2025", ("quarter", date(2025, 4, 1), date(2025, 6, 30))),  # TC-05
    ("As at 31 March  As at 31 March 2026 2025", ("columns", date(2026, 3, 31), date(2026, 3, 31))),
])
def test_a_period_is_read_as_a_date_range(line, want):
    assert span(in_line(line)[0]) == want


@pytest.mark.parametrize("lines, want", [
    (["FORM GSTR-3B", "Year 2025-26", "Period Apr"], ("month", date(2025, 4, 1), date(2025, 4, 30))),     # TC-05 "April"
    (["FORM GSTR-3B", "Year 2025-26", "Period Jan"], ("month", date(2026, 1, 1), date(2026, 1, 31))),
    (["GSTR-3B", "Year 2025-26", "Q1"], ("quarter", date(2025, 4, 1), date(2025, 6, 30))),                 # TC-05 "Q1"
    (["GSTR-3B", "Financial Year 2025-26", "Quarter 4"], ("quarter", date(2026, 1, 1), date(2026, 3, 31))),
])
def test_a_month_or_quarter_named_alone_is_read_within_the_year_the_page_names(lines, want):
    assert span(page_level(lines)[0]) == want


def test_a_date_that_is_not_a_period_is_not_read():
    assert in_line("Date: 06 August 2026") == [] and in_line("Place: Mumbai") == []


AUD = lambda no, y, *rest: page(no, title(f"Statement of Profit and Loss for the year ended 31 March {y}"),
                                 f"Revenue from operations 23,60,00,000", *rest)


def test_scenario_12_two_years_of_statements_in_one_file_are_two_documents(cfg):
    pages = [page(1, title("Independent Auditor's Report"), "We have audited the financial statements"), AUD(2, 2026),
             page(3, "Notes 1,00,000 31 March 2025"), page(4, title("Independent Auditor's Report"), "We have audited"), AUD(5, 2025)]
    front, groups = I.split(cfg, "audited_financial_statements", pages)
    assert front == [] and [[p.no for p in g] for g in groups] == [[1, 2, 3], [4, 5]]
    assert [I.identify(cfg, "audited_financial_statements", g, None).key for g in groups] == ["2026-03-31", "2025-03-31"]


def test_scenario_12_twelve_returns_in_one_file_are_twelve_documents(cfg):
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    pages = [page(n + 1, title("FORM GSTR-3B"), "Year 2025-26", f"Period {m}", "3.1 Details of outward supplies")
             for n, m in enumerate(months)]
    _, groups = I.split(cfg, "gstr_3b", pages)
    keys = [I.identify(cfg, "gstr_3b", g, None).key for g in groups]
    assert len(groups) == 12 and keys[0] == "Apr 2025" and keys[-1] == "Mar 2026"


def test_tc_04_two_accounts_in_one_file_and_a_statement_with_no_printed_period(cfg):
    ca = [page(1, title("Statement of Account"), "Account Number 602010345567", "Statement 01 Apr 2025 to 30 Sep 2025",
               "03 Apr 2025 NEFT CR 64,40,000 3,14,40,000")]
    cc = [page(2, title("Statement of Account"), "Account Number 602010999981", "03 Apr 2025 NEFT CR 10,00,000 10,00,000"),
          page(3, "28 Sep 2025 RTGS DR 1,00,000 9,00,000")]
    _, groups = I.split(cfg, "bank_statement", ca + cc)
    assert [[p.no for p in g] for g in groups] == [[1], [2, 3]]
    first, second = (I.identify(cfg, "bank_statement", g, None) for g in groups)
    assert (first.key, first.status, span(first.period)) == ("602010345567", "found", ("range", date(2025, 4, 1), date(2025, 9, 30)))
    assert (second.key, second.status, second.source) == ("602010999981", "derived", "rows")
    assert (second.period.start, second.period.end) == (date(2025, 4, 3), date(2025, 9, 28))


def test_scenario_13_a_year_printed_only_in_the_column_headings_is_taken_from_them(cfg):
    p = page(1, title("Balance Sheet"), "Particulars 31 March 2026 31 March 2025", "Share capital 50,00,000 50,00,000")
    ident = I.identify(cfg, "audited_financial_statements", [p], None)
    assert (ident.status, ident.source, ident.key) == ("found", "columns", "2026-03-31")


def test_scenario_14_no_year_anywhere_is_kept_as_period_not_found(cfg):
    ident = I.identify(cfg, "audited_financial_statements", [page(1, title("Balance Sheet"), "Share capital 50,00,000")], None)
    assert ident.period is None and ident.status == "not_found" and ident.key is None and "a person sets it" in ident.note


def test_scenario_15_a_title_that_disagrees_with_the_columns_is_flagged(cfg):
    p = page(1, title("Balance Sheet as at 31 March 2026"), "Particulars 31 March 2025 31 March 2024", "Share capital 50,00,000 50,00,000")
    ident = I.identify(cfg, "audited_financial_statements", [p], None)
    assert ident.status == "conflict" and ident.key == "2026-03-31" and "2025-03-31" in ident.note


def test_a_cover_listing_many_periods_is_front_matter_not_the_first_return(cfg):
    cover = page(1, title("GSTR-3B returns: compilation"), "Tax Period December 2025", "Tax Period January 2026", "Tax Period February 2026")
    returns = [page(2, title("FORM GSTR-3B"), "Return Period 12/2025"), page(3, title("FORM GSTR-3B"), "Return Period 01/2026")]
    front, groups = I.split(cfg, "gstr_3b", [cover, *returns])
    assert front == [1] and [[p.no for p in g] for g in groups] == [[2], [3]]


def test_persons_are_told_apart_by_din_or_an_individuals_pan(cfg):
    pages = [page(1, title("Director KYC"), "Director Identification Number 07421683"),
             page(2, title("Director KYC"), "Director Identification Number 07421684"), page(3, "Residential address Mumbai")]
    _, groups = I.split(cfg, "director_kyc", pages)
    assert [[p.no for p in g] for g in groups] == [[1], [2, 3]]


def test_the_model_names_the_period_and_it_counts_only_on_its_own_line(cfg):
    p = page(1, title("Balance Sheet"), "Figures relate to the twelve months ended 31 March 2026", "Share capital 50,00,000")
    p.lines[1].text  # noqa: B018 - the line the model must cite
    line_id = p.lines[1].id

    def answer(req):
        return {"text": "twelve months ended 31 March 2026", "line_id": line_id}

    def wrong(req):
        return {"text": "twelve months ended 31 March 2027", "line_id": line_id}

    rule_cfg = cfg.model_copy(deep=True)
    rule_cfg.keywords.types["audited_financial_statements"].identity.period = ["period_end"]
    rule_cfg.keywords.types["audited_financial_statements"].identity.columns = False
    # The reader finds this on its own; with the title zone emptied, only the model can.
    q = page(1, "Figures relate to the twelve months ended 31 March 2026", "Share capital 50,00,000")
    q.lines[0]  # noqa: B018
    lid = q.lines[0].id
    got = I.identify(rule_cfg, "audited_financial_statements", [q],
                     ModelClient(FixtureProvider(cfg.llm, lambda r: {"text": "twelve months ended 31 March 2026", "line_id": lid}), "record", Store()))
    assert (got.source, got.status, got.key) == ("model", "found", "2026-03-31")
    bad = I.identify(rule_cfg, "audited_financial_statements", [q],
                     ModelClient(FixtureProvider(cfg.llm, lambda r: {"text": "twelve months ended 31 March 2027", "line_id": lid}), "record", Store()))
    assert bad.status == "not_found"
