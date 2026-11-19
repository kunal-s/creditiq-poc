"""The statement lines of an Ind AS statement filed in XBRL, read by the published configuration's row names
(config/statements.yaml): its own names ("Equity share capital", "Borrowings, non-current", "Total profit before
tax") are the same lines as the older layout's, and the lines it prints on their own (bank balances other than
cash, other current financial assets and liabilities, current tax) count in current assets and liabilities, so
those add up to the totals the statement prints."""

import pytest
import yaml

from engine import statements
from engine.configstore.schema import StatementsSection
from tests.test_statement_units import _statement


@pytest.fixture(scope="module")
def cfg() -> StatementsSection:
    with open("config/statements.yaml") as fh:
        return StatementsSection.model_validate(yaml.safe_load(fh))


BALANCE_SHEET = [   # an Ind AS balance sheet as the registrar's rendering prints it (crore)
    ("Property, plant and equipment", 22737.19), ("Capital work-in-progress", 1077.97),
    ("Other intangible assets", 2055.74), ("Non-current investments", 22821.94), ("Loans, non-current", 2.63),
    ("Other non-current assets", 1229.22), ("Inventories", 12631.51), ("Current investments", 11916.88),
    ("Trade receivables, current", 3311.45), ("Cash and cash equivalents", 197.63),
    ("Bank balance other than cash and cash equivalents", 6020.06), ("Loans, current", 9.1),
    ("Other current financial assets", 849.86), ("Total current financial assets", 22304.98),
    ("Other current assets", 1134.18), ("Total current assets", 36070.67), ("Total assets", 87327.6),
    ("Equity share capital", 1248.47), ("Other equity", 70984.83), ("Total equity", 72233.3),
    ("Borrowings, non-current", 1.76), ("Provisions, non-current", 221.45), ("Deferred tax liabilities (net)", 2083.66),
    ("Borrowings, current", 1.52), ("Trade payables, current", 4489.55), ("Other current financial liabilities", 1706.07),
    ("Other current liabilities", 5389.75), ("Provisions, current", 68.72), ("Current tax liabilities", 760),
    ("Total current liabilities", 12415.61), ("Total equity and liabilities", 87327.6),
]


def test_the_xbrl_names_are_the_same_lines(cfg):
    lines = statements.lines(_statement(BALANCE_SHEET), cfg)
    got = {k: lines[k].value for k in ("share_capital", "reserves_and_surplus", "long_term_borrowings",
                                       "short_term_borrowings", "trade_payables", "trade_receivables", "inventories",
                                       "cash_and_bank_balances", "net_fixed_assets", "long_term_provisions",
                                       "short_term_provisions", "deferred_tax_liability", "total_equity_and_liabilities")}
    assert got == {"share_capital": 1248.47, "reserves_and_surplus": 70984.83, "long_term_borrowings": 1.76,
                   "short_term_borrowings": 1.52, "trade_payables": 4489.55, "trade_receivables": 3311.45,
                   "inventories": 12631.51, "cash_and_bank_balances": 197.63, "net_fixed_assets": 22737.19,
                   "long_term_provisions": 221.45, "short_term_provisions": 68.72, "deferred_tax_liability": 2083.66,
                   "total_equity_and_liabilities": 87327.6}
    assert lines["net_worth"].value == pytest.approx(72233.3)


def test_current_assets_and_liabilities_add_up_to_the_printed_totals(cfg):
    lines = statements.lines(_statement(BALANCE_SHEET), cfg)
    assert lines["current_assets"].value == pytest.approx(36070.67)
    assert lines["current_liabilities"].value == pytest.approx(12415.61)


def test_an_older_layout_reads_the_ind_as_lines_as_nil(cfg):
    older = [("(a) Inventories", 400), ("(b) Trade receivables", 300), ("(c) Cash and bank balances", 50),
             ("(d) Short-term loans and advances", 20), ("(e) Other current assets", 30), ("(a) Short-term borrowings", 100),
             ("(b) Trade payables", 200), ("(c) Other current liabilities", 40), ("(d) Short-term provisions", 10)]
    lines = statements.lines(_statement(older), cfg)
    assert lines["current_assets"].value == 800 and lines["current_liabilities"].value == 350
    nil = {p.name for p in lines["current_assets"].parts + lines["current_liabilities"].parts if p.not_printed}
    assert nil == {"current_investments", "bank_balances_other_than_cash", "other_current_financial_assets",
                   "current_tax_assets", "other_current_financial_liabilities", "current_tax_liabilities"}


def _pl(rows):
    """A statement of profit and loss: the same rows, as the profit_and_loss table."""
    doc = _statement(rows)
    table = doc.rows
    doc.rows = lambda name: table("balance_sheet") if name == "profit_and_loss" else []
    return doc


def test_the_xbrl_profit_and_loss_lines(cfg):
    lines = statements.lines(_pl([
        ("Revenue from operations", 70105.29), ("Other income", 3538.28), ("Finance costs", 45.73),
        ("Depreciation, depletion and amortisation expense", 1647.82), ("Total profit before tax", 26315.77),
        ("Current tax", 5661.21), ("Total tax expense", 5893.8),
        ("Total profit (loss) for period from continuing operations", 20421.97),
        ("Tax expense of discontinued operations", 0), ("Total profit (loss) for period", 20421.97),
    ]), cfg)
    assert lines["profit_before_tax"].value == 26315.77 and lines["profit_after_tax"].value == 20421.97
    assert lines["tax_expense"].value == 5893.8, "not the tax on discontinued operations"
    assert lines["ebitda"].value == pytest.approx(26315.77 + 45.73 + 1647.82)
