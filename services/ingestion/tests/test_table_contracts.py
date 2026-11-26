"""Table contracts (fields.yaml table_contracts): every reader proposes a table and the reading that meets the table's
contract best is kept; a reading that does not meet it is reported with what failed, and one that holds none of the
rows the table must have is not the table."""

import pytest
from pydantic import ValidationError

from ingestion.config.models import TableContract, parse_identity
from ingestion.stages.extract import contract as C
from ingestion.stages.extract import kwtables
from ingestion.stages.extract.run import extract_instance
from tests.test_tables_keywords import STMT, grid

AFS = "audited_financial_statements"


def rows(*pairs):
    return [{"cells": {"particulars": label, "current_period": cur, "previous_period": prev}} for label, cur, prev in pairs]


PL = TableContract(
    label="particulars", columns=["current_period", "previous_period"],
    rows={"revenue": ["revenue from operations"], "other_income": ["other income"], "total_income": ["total income", "total revenue"],
          "total_expenses": ["total expenses"], "pbt": ["profit before tax"]},
    must_have=["revenue", "total_expenses", "pbt"], identities=["total_income = revenue + other_income"], min_rows=3)


def test_an_identity_is_read_as_a_row_and_signed_terms():
    assert parse_identity("a = b + c - d") == ("a", [(1, "b"), (1, "c"), (-1, "d")])
    assert parse_identity("a = - b") == ("a", [(-1, "b")])
    assert parse_identity("a + b = c") is None
    assert parse_identity("a = b c") is None


def test_a_contract_naming_a_row_it_does_not_define_does_not_load():
    with pytest.raises(ValidationError, match="unknown row"):
        TableContract(label="particulars", columns=["current_period"], rows={"a": ["x"]}, must_have=["b"])
    with pytest.raises(ValidationError, match="cannot read"):
        TableContract(label="particulars", columns=["current_period"], rows={"a": ["x"]}, identities=["a == a"])


def test_a_label_is_compared_without_its_list_marker_case_punctuation_or_ampersand():
    assert C.label_key("I Revenue from Operations") == "revenue from operations"
    assert C.label_key("(a) Outward taxable supplies (other than zero rated") == "outward taxable supplies other than zero rated"
    assert C.label_key("Total Equity & Liabilities") == "total equity and liabilities"
    assert C.label_key("IX Profit before tax (VII - VIII)") == "profit before tax vii viii"
    assert C.label_key("civil works") == "civil works"          # a word, not a roman numeral


def test_a_reading_whose_rows_hold_and_add_up_meets_the_contract():
    v = C.evaluate(PL, rows(("I Revenue from Operations", 1743419, 2074176), ("II Other Income", 71452, 113122),
                            ("III Total Revenue (I +II)", 1814871, 2187298), ("Total Expenses (IV)", 1717676, 1941689),
                            ("IX Profit before tax", 97195, 245609)))
    assert v["met"] and v["passed"] == 2 and not v["missing"] and not v["failed"]


def test_a_note_number_read_as_revenue_fails_the_sum_and_says_so():
    v = C.evaluate(PL, rows(("I Revenue from Operations", 13, 1743419), ("II Other Income", 14, 71452),
                            ("III Total Revenue (I +II)", 1814871, 2187298), ("Total Expenses (IV)", 1717676, 1941689),
                            ("IX Profit before tax", 97195, 245609)))
    assert not v["met"]
    assert {f["column"] for f in v["failed"]} == {"current_period", "previous_period"}
    assert "total_income = revenue + other_income does not hold in current period" in C.summary(v)


def test_a_sum_whose_rows_are_not_printed_is_not_checked():
    v = C.evaluate(PL, rows(("Revenue from operations", 100, 90), ("Total expenses", 80, 70), ("Profit before tax", 20, 20)))
    assert v["met"] and v["passed"] == 0


def test_a_reading_without_a_row_the_table_must_have_does_not_meet_it():
    v = C.evaluate(PL, rows(("Basic earnings per share", 16.39, 15.15), ("Diluted earnings per share", 16.35, 15.1),
                            ("Profit before tax", 1, 1)))
    assert not v["met"] and v["missing"] == ["revenue", "total_expenses"]


def _statement_pages():
    """A profit and loss whose first header is a per-share sub-table (as a filed statement prints it), then the
    statement itself on the next page under its own dated header."""
    eps = grid(1, [[(40, "Particulars"), (320, "31.03.2026"), (440, "31.03.2025")],
                   [(40, "Basic earnings per share"), (320, "16.39"), (440, "15.15")],
                   [(40, "Diluted earnings per share"), (320, "16.35"), (440, "15.10")]],
               title="Statement of Profit and Loss")
    pl = grid(2, [[(40, "Particulars"), (320, "31.03.2026"), (440, "31.03.2025")],
                  [(40, "Revenue from operations"), (320, "70,105.29"), (440, "70,251.28")],
                  [(40, "Other income"), (320, "3,538.28"), (440, "2,437.61")],
                  [(40, "Total income"), (320, "73,643.57"), (440, "72,688.89")],
                  [(40, "Cost of materials consumed"), (320, "21,309.84"), (440, "19,809.83")],
                  [(40, "Employee benefit expense"), (320, "3,732.23"), (440, "3,569.46")],
                  [(40, "Finance costs"), (320, "45.73"), (440, "41.81")],
                  [(40, "Other expenses"), (320, "22,232.16"), (440, "24,621.18")],
                  [(40, "Total expenses"), (320, "47,320.23"), (440, "48,011.35")],
                  [(40, "Profit before exceptional items and tax"), (320, "26,323.34"), (440, "24,677.54")],
                  [(40, "Profit before tax"), (320, "26,315.77"), (440, "24,750.41")]])
    return [eps, pl]


def test_every_header_the_headings_name_is_proposed_and_the_contract_keeps_the_statement(cfg):
    pages = _statement_pages()
    spec = cfg.fields.types[AFS].table_keywords["profit_and_loss"]
    others = list(cfg.fields.types[AFS].table_keywords.values())
    first = kwtables.read(cfg, spec, STMT, pages, others)
    assert first is not None and first.page_start == 1           # the first header alone is the per-share sub-table
    readings = kwtables.candidates(cfg, spec, STMT, pages, others)
    assert {r.page_start for r in readings} == {1, 2}
    best, verdict, _ = C.choose(cfg.fields.types[AFS].table_contracts["profit_and_loss"], readings)
    assert best.page_start == 2 and verdict["met"]


def test_the_statement_extracted_is_the_one_that_meets_its_contract(cfg):
    out = extract_instance(cfg, AFS, _statement_pages(), None)
    pl = out["tables"]["profit_and_loss"]
    assert pl["status"] == "found" and pl["contract"]["met"]
    revenue = next(r for r in pl["rows"] if r["cells"]["particulars"] == "Revenue from operations")
    assert (revenue["cells"]["current_period"], revenue["cells"]["previous_period"]) == (70105.29, 70251.28)


def test_a_statement_that_does_not_add_up_is_kept_and_reported(cfg):
    pages = [grid(2, [[(40, "Particulars"), (320, "31.03.2026"), (440, "31.03.2025")],
                      [(40, "Revenue from operations"), (320, "70,105.29"), (440, "70,251.28")],
                      [(40, "Other income"), (320, "3,538.28"), (440, "2,437.61")],
                      [(40, "Total income"), (320, "99,999.99"), (440, "72,688.89")],
                      [(40, "Cost of materials consumed"), (320, "21,309.84"), (440, "19,809.83")],
                      [(40, "Employee benefit expense"), (320, "3,732.23"), (440, "3,569.46")],
                      [(40, "Finance costs"), (320, "45.73"), (440, "41.81")],
                      [(40, "Other expenses"), (320, "22,232.16"), (440, "24,621.18")],
                      [(40, "Total expenses"), (320, "47,320.23"), (440, "48,011.35")],
                      [(40, "Profit before tax"), (320, "26,315.77"), (440, "24,750.41")]])]
    out = extract_instance(cfg, AFS, pages, None)
    pl = out["tables"]["profit_and_loss"]
    assert pl["status"] == "found" and not pl["contract"]["met"]
    assert "total_income = revenue_from_operations + other_income" in pl["contract"]["summary"]


def test_the_table_under_its_title_is_kept_but_reported_when_it_holds_none_of_its_rows(cfg):
    out = extract_instance(cfg, AFS, _statement_pages()[:1], None)
    pl = out["tables"]["profit_and_loss"]
    assert pl["status"] == "found" and not pl["contract"]["met"]
    assert pl["contract"]["summary"].startswith("no revenue from operations, total expenses, profit before tax")


def test_a_header_with_no_title_above_it_and_none_of_the_rows_is_some_other_table(cfg):
    bs = grid(1, [[(40, "Particulars"), (320, "31.03.2026"), (440, "31.03.2025")],
                  [(40, "Share capital"), (320, "500"), (440, "400")],
                  [(40, "Trade payables"), (320, "1,500"), (440, "1,390")],
                  [(40, "Total equity and liabilities"), (320, "2,000"), (440, "1,790")],
                  [(40, "Inventories"), (320, "800"), (440, "700")],
                  [(40, "Trade receivables"), (320, "1,200"), (440, "1,090")],
                  [(40, "Total assets"), (320, "2,000"), (440, "1,790")]], title="Balance Sheet")
    note = grid(2, [[(40, "Particulars"), (320, "31.03.2026"), (440, "31.03.2025")],
                    [(40, "Raw materials"), (320, "500"), (440, "450")],
                    [(40, "Finished goods"), (320, "300"), (440, "250")]])
    out = extract_instance(cfg, AFS, [bs, note], None)
    assert out["tables"]["balance_sheet"]["status"] == "found" and out["tables"]["balance_sheet"]["contract"]["met"]
    assert out["tables"]["profit_and_loss"]["status"] == "missing"       # neither table is a profit and loss


def test_the_configured_contracts_name_only_columns_and_tables_the_types_have(cfg):
    assert cfg.check_consistency() == []
    assert set(cfg.fields.types[AFS].table_contracts) == {"profit_and_loss", "balance_sheet", "cash_flow"}
    assert cfg.fields.types["gstr_3b"].table_contracts["outward_supplies"].must_have == ["outward_taxable"]


def test_a_section_heading_that_shares_its_words_with_the_total_under_it_is_not_taken_for_the_total(cfg):
    cf = cfg.fields.types[AFS].table_contracts["cash_flow"]
    v = C.evaluate(cf, rows(("A. Cash flow from operating activities", None, None), ("Profit before tax", 154, 120),
                            ("Net cash from operating activities (A)", 210, 180)))
    assert v["met"] and not v["missing"]


def test_a_complete_reading_whose_printed_total_does_not_add_up_is_kept_and_the_model_is_not_asked(cfg):
    """The document's own total is wrong (17,186.76 printed for 17,176.76): that is reported, not "fixed" by a mapping
    of other columns that happen to add up."""
    from tests.test_llm_tables import Reader

    page = grid(1, [[(40, "Particulars"), (320, "31.03.2026"), (440, "31.03.2025")],
                    [(40, "Revenue from operations"), (320, "17,434.19"), (440, "20,741.76")],
                    [(40, "Other income"), (320, "714.52"), (440, "1,131.22")],
                    [(40, "Total income"), (320, "18,148.71"), (440, "21,872.98")],
                    [(40, "Cost of materials consumed"), (320, "12,114.46"), (440, "14,308.90")],
                    [(40, "Employee benefit expenses"), (320, "2,342.41"), (440, "2,323.47")],
                    [(40, "Finance cost"), (320, "539.97"), (440, "944.43")],
                    [(40, "Other expenses"), (320, "2,179.92"), (440, "1,840.09")],
                    [(40, "Total expenses"), (320, "17,186.76"), (440, "19,416.89")],
                    [(40, "Profit before exceptional and extraordinary items and tax"), (320, "971.95"), (440, "2,456.09")],
                    [(40, "Profit before tax"), (320, "971.95"), (440, "2,456.09")]], title="Statement of Profit and Loss")
    reader = Reader(lambda req: [])
    out = extract_instance(cfg, AFS, [page], reader)
    pl = out["tables"]["profit_and_loss"]
    assert pl["method"] == "keywords" and not pl["contract"]["met"]
    assert [f["column"] for f in pl["contract"]["failed"]] == ["current_period"]
    assert not [r for r in reader.requests if r.task == "table" and "profit" in r.user.lower()]
