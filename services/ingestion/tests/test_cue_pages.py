"""Story 6.7, scenario 31: a bank statement with no "Statement Summary" page; the model reads the pages that score
highest for the fields still to read."""

from pathlib import Path

from ingestion.config.loader import load_dir
from ingestion.pageindex import Line, Page, Word
from ingestion.stages.extract.run import cue_pages

CFG = load_dir(Path(__file__).resolve().parents[3] / "config" / "ingestion")


def page(no: int, texts: list[str]) -> Page:
    lines = [Line(no, i, t, [Word(t, 10, 10 + 12 * i, 200, 20 + 12 * i)], [(0, len(t))]) for i, t in enumerate(texts)]
    return Page(no, "text_layer", 600, 800, [w for l in lines for w in l.words], lines)


STATEMENT = [page(1, ["Account Statement", "Account Name  Southgate Textiles", "Statement 01 April 2025 to 31 March 2026"])]
STATEMENT += [page(n, ["Date  Narration  Debit  Credit  Balance", "02-04-2025  NEFT  10,000  5,40,000"]) for n in range(2, 12)]
STATEMENT += [page(12, ["Opening Balance (01 Apr 2025)  4,50,000", "Closing Balance (31 Mar 2026)  6,10,000"])]


def test_scenario_31_the_page_that_prints_the_balances_is_read_without_a_summary_page_pattern():
    rules = CFG.fields.types["bank_statement"].fields
    chosen = [p.no for p in cue_pages(rules, ["opening_balance", "closing_balance"], STATEMENT, CFG.llm.fill_pages)]
    assert chosen == [1, 12]


def test_a_short_document_is_read_whole():
    rules = CFG.fields.types["bank_statement"].fields
    assert [p.no for p in cue_pages(rules, ["closing_balance"], STATEMENT[:3], CFG.llm.fill_pages)] == [1, 2, 3]
