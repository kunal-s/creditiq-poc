"""Statement lines by their wordings and sections, and the tie-out to the printed totals (Epic 5c of the
classification restructure; FRD F-15.14): scenarios 18, 26, 28 and 29 of the plan, and TC-08."""

import re
from types import SimpleNamespace

import pytest
import yaml

from engine import statements
from engine.configstore.schema import StatementsSection


@pytest.fixture(scope="module")
def cfg() -> StatementsSection:
    with open("config/statements.yaml") as fh:
        return StatementsSection.model_validate(yaml.safe_load(fh))


def statement(table: str, rows: list[tuple[str, float | None]]):
    cells = {f"{table}[{i}].{k}": SimpleNamespace(value=v, manual=False, field_id=f"F{i}{k}", pending=False, raw=str(v))
             for i, (label, amount) in enumerate(rows) for k, v in (("particulars", label), ("current_period", amount))
             if v is not None}
    doc = SimpleNamespace(id="DOC-1", edits={}, get=lambda name: None, evidence=lambda *a: [])

    def rows_of(t):
        out = {}
        for name, v in cells.items():
            m = re.match(rf"{re.escape(t)}\[(\d+)\]\.(.+)", name)
            if m:
                out.setdefault(int(m[1]), {})[m[2]] = v
        return [out[i] for i in sorted(out)]
    doc.rows = rows_of
    return doc


@pytest.mark.parametrize("label", ["Share capital", "(a) Share capital", "1. Share capital", "II. Share capital",
                                   "i) Share capital", "Equity share capital", "SHARE CAPITAL"])
def test_scenario_18_a_line_is_found_whatever_its_numbering_and_wording(cfg, label):
    got = statements.lines(statement("balance_sheet", [(label, 500)]), cfg)
    assert got["share_capital"].value == 500


IND_AS = [
    ("EQUITY AND LIABILITIES", None), ("Equity", None), ("Equity share capital", 100), ("Other equity", 900),
    ("Total equity", 1000),
    ("Non-current liabilities", None), ("Borrowings", 400), ("Provisions", 50), ("Total non-current liabilities", 450),
    ("Current liabilities", None), ("Borrowings", 150), ("Trade payables", 300), ("Provisions", 20),
    ("Total current liabilities", 470), ("TOTAL", 1920),
    ("ASSETS", None), ("Non-current assets", None), ("Property, plant and equipment", 1000), ("Investments", 120),
    ("Total non-current assets", 1120),
    ("Current assets", None), ("Inventories", 300), ("Investments", 80), ("Trade receivables", 350),
    ("Cash and cash equivalents", 70), ("Total current assets", 800), ("TOTAL", 1920)]


def test_scenario_26_borrowings_under_both_sections_each_map_to_their_own_line(cfg):
    got = statements.lines(statement("balance_sheet", IND_AS), cfg)
    assert (got["long_term_borrowings"].value, got["short_term_borrowings"].value) == (400, 150)
    assert (got["long_term_provisions"].value, got["short_term_provisions"].value) == (50, 20)
    assert (got["non_current_investments"].value, got["current_investments"].value) == (120, 80)
    assert (got["total_assets"].value, got["total_equity_and_liabilities"].value) == (1920, 1920)
    ties = statements.tie_outs(statement("balance_sheet", IND_AS), cfg)
    assert ties and all(t.agrees for t in ties)
    assert {t.section for t in ties} >= {"current_liabilities", "current_assets", "equity"}


def test_scenario_28_a_row_mapped_to_no_line_breaks_the_tie_out_and_is_named(cfg):
    rows = [r if r != ("Trade payables", 300) else ("Statutory dues payable", 300) for r in IND_AS]
    ties = {t.section: t for t in statements.tie_outs(statement("balance_sheet", rows), cfg)}
    bad = ties["current_liabilities"]
    assert not bad.agrees and bad.difference == 300 and bad.unmapped == ["Statutory dues payable"]


def test_scenario_29_current_investments_count_in_current_assets(cfg):
    got = statements.lines(statement("balance_sheet", IND_AS), cfg)
    assert got["current_assets"].value == 800       # inventories, current investments, receivables, cash


def test_tc_08_a_proprietorships_accounts_read_by_their_own_wordings(cfg):
    bs = statements.lines(statement("balance_sheet", [("Capital account", 900), ("Sundry creditors", 300),
                                                       ("Sundry debtors", 350), ("Closing stock", 200)]), cfg)
    assert (bs["share_capital"].value, bs["trade_payables"].value, bs["trade_receivables"].value, bs["inventories"].value) == (
        900, 300, 350, 200)
    pl = statements.lines(statement("profit_and_loss", [("Sales", 5000), ("Net profit", 400)]), cfg)
    assert (pl["revenue_from_operations"].value, pl["profit_after_tax"].value) == (5000, 400)


def test_without_section_headings_a_line_is_read_wherever_it_is(cfg):
    got = statements.lines(statement("balance_sheet", [("(a) Long-term borrowings", 400), ("(a) Short-term borrowings", 150)]), cfg)
    assert (got["long_term_borrowings"].value, got["short_term_borrowings"].value) == (400, 150)


def test_a_label_that_is_the_wording_wins_over_one_that_begins_with_it(cfg):
    rows = [("Trade payables - total outstanding dues of micro enterprises", 40), ("Trade payables", 300)]
    assert statements.lines(statement("balance_sheet", rows), cfg)["trade_payables"].value == 300


PL = [("I. Revenue from operations", 5000), ("II. Other income", 100), ("III. Total income (I + II)", 5100),
      ("IV. Expenses", None), ("Cost of materials consumed", 3000), ("Employee benefits expense", 600),
      ("Depreciation and amortisation expense", 200), ("Other expenses", 500), ("Total expenses (IV)", 4300),
      ("V. Profit before tax (III - IV)", 800)]


def test_tc_09_a_debt_free_company_prints_no_finance_cost_and_ebitda_still_follows(cfg):
    got = statements.lines(statement("profit_and_loss", PL), cfg)
    assert got["finance_costs"].value == 0 and got["finance_costs"].state == "not_printed"
    assert got["ebitda"].value == 1000                 # profit before tax + finance costs (nil) + depreciation


def test_tc_09_an_absent_line_is_not_nil_when_the_expenses_do_not_tie_out(cfg):
    rows = [r if r[0] != "Total expenses (IV)" else ("Total expenses (IV)", 4450) for r in PL]   # 150 printed nowhere
    got = statements.lines(statement("profit_and_loss", rows), cfg)
    assert "finance_costs" not in got and "ebitda" not in got
