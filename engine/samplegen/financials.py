"""Parametric financial model: derives a consistent P&L and balance sheet
for each fiscal year from a case's `financial_model` descriptor.

Reuses the reconciliation approach of the generic repo's `financials.py`
(`_derive_pl`'s EBITDA-down-to-PAT waterfall, `balance_sheet`'s plug), but
computed forward from descriptor inputs rather than backward from fixed
anchor figures — this repo's cases are generated, not pre-scripted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schema import FinancialModel

DAYS_IN_YEAR = 365
DEP_RATE = 0.15  # WDV rate on gross block, applied to the opening balance
CAPEX_RATIO = 0.045  # capex as a share of revenue, each year
CC_INTEREST_RATE = 0.1075
TL_INTEREST_RATE = 0.115
CASH_FLOAT_RATIO = 0.01  # cash held, as a share of revenue


@dataclass
class ProfitAndLoss:
    fy: int
    revenue: int
    ebitda: int
    depreciation: int
    finance_costs: int
    pbt: int
    tax: int
    pat: int


@dataclass
class BalanceSheet:
    fy: int
    share_capital: int
    reserves: int
    net_worth: int
    borrowings_lt: int
    borrowings_st: int
    trade_payables: int
    other_cl: int
    ppe: int
    inventories: int
    receivables: int
    cash: int
    total: int

    @property
    def current_assets(self) -> int:
        return self.inventories + self.receivables + self.cash

    @property
    def current_liabilities(self) -> int:
        return self.borrowings_st + self.trade_payables + self.other_cl

    @property
    def total_debt(self) -> int:
        return self.borrowings_lt + self.borrowings_st

    @property
    def total_outside_liabilities(self) -> int:
        return self.total_debt + self.trade_payables + self.other_cl


@dataclass
class YearModel:
    fy: int
    pl: ProfitAndLoss
    bs: BalanceSheet


@dataclass
class CaseFinancials:
    years: dict[int, YearModel] = field(default_factory=dict)

    def ratios(self, fy: int) -> dict[str, float]:
        y = self.years[fy]
        pl, bs = y.pl, y.bs
        term_debt_repayment = max(1, round(bs.borrowings_lt * 0.12))  # illustrative amortisation slice
        dscr_num = pl.pat + pl.depreciation + pl.finance_costs
        dscr_den = pl.finance_costs + term_debt_repayment
        return {
            "current-ratio": round(bs.current_assets / bs.current_liabilities, 2),
            "tol-tnw": round(bs.total_outside_liabilities / bs.net_worth, 2),
            "dscr": round(dscr_num / dscr_den, 2),
            "interest-coverage": round((pl.pbt + pl.finance_costs) / pl.finance_costs, 2),
            "debt-equity": round(bs.total_debt / bs.net_worth, 2),
        }


def build(model: FinancialModel, existing_term_debt_opening: int = 0) -> CaseFinancials:
    """Compute a consistent multi-year model. `existing_term_debt_opening` is
    the term-loan balance at the start of the earliest modelled year; it
    amortises by a flat 12%/year for the years modelled here."""

    years = sorted(model.revenue)
    result = CaseFinancials()

    opening_gross_block = model.revenue[years[0]] * CAPEX_RATIO * 4  # plausible pre-existing base
    net_worth = model.net_worth_opening
    term_debt = existing_term_debt_opening
    prev_bs: BalanceSheet | None = None

    materials = model.cost_ratios.get("materials", 0.0)
    employee = model.cost_ratios.get("employee", 0.0)
    power = model.cost_ratios.get("power", 0.0)
    other = model.cost_ratios.get("other", 0.0)
    opex_ratio = materials + employee + power + other

    inv_days = model.working_capital_days.get("inventory_days", 45)
    debtor_days = model.working_capital_days.get("debtor_days", 45)
    creditor_days = model.working_capital_days.get("creditor_days", 40)

    for fy in years:
        revenue = model.revenue[fy]
        ebitda = round(revenue * (1 - opex_ratio))

        capex = round(revenue * CAPEX_RATIO)
        gross_block = opening_gross_block + capex
        depreciation = round(gross_block * DEP_RATE)
        net_block = gross_block - depreciation

        term_debt_repayment = round(term_debt * 0.12)
        avg_term_debt = term_debt - term_debt_repayment / 2
        term_debt -= term_debt_repayment

        cogs_proxy = revenue * (materials + power)
        inventories = round(cogs_proxy * inv_days / DAYS_IN_YEAR)
        receivables = round(revenue * debtor_days / DAYS_IN_YEAR)
        trade_payables = round(cogs_proxy * creditor_days / DAYS_IN_YEAR)
        cash = round(revenue * CASH_FLOAT_RATIO)
        other_cl = round(revenue * 0.015)

        # CC utilisation is estimated first (to size finance costs), then
        # re-derived as the balance-sheet plug so the two agree by
        # construction rather than by luck.
        estimated_cc = max(0, inventories + receivables - trade_payables - cash)
        finance_costs = round(avg_term_debt * TL_INTEREST_RATE + estimated_cc * CC_INTEREST_RATE)

        pbt = ebitda - depreciation - finance_costs
        tax = round(pbt * model.tax_rate)
        pat = pbt - tax
        net_worth += pat

        pl = ProfitAndLoss(
            fy=fy, revenue=revenue, ebitda=ebitda, depreciation=depreciation,
            finance_costs=finance_costs, pbt=pbt, tax=tax, pat=pat,
        )

        share_capital = prev_bs.share_capital if prev_bs else max(1000000, round(model.net_worth_opening * 0.2))
        reserves = net_worth - share_capital

        # The plug: short-term borrowings (CC) make the balance sheet foot.
        # non_cash_assets + cash + 0 == liab_side_before_cc + cc, solved for cc.
        # If that would go negative (financing exceeds what the assets need),
        # the surplus is extra cash instead of a negative liability — the
        # exact bug the generic repo's fixed-anchor model had unguarded.
        non_cash_assets = net_block + inventories + receivables
        liab_side_before_cc = share_capital + reserves + term_debt + trade_payables + other_cl
        cc_utilisation = non_cash_assets + cash - liab_side_before_cc
        if cc_utilisation < 0:
            cash = liab_side_before_cc - non_cash_assets
            cc_utilisation = 0

        total_eq_liab = share_capital + reserves + term_debt + cc_utilisation + trade_payables + other_cl

        bs = BalanceSheet(
            fy=fy, share_capital=share_capital, reserves=reserves, net_worth=net_worth,
            borrowings_lt=term_debt, borrowings_st=cc_utilisation, trade_payables=trade_payables,
            other_cl=other_cl, ppe=net_block, inventories=inventories, receivables=receivables,
            cash=cash, total=total_eq_liab,
        )

        assets_total = net_block + inventories + receivables + cash
        assert assets_total == total_eq_liab, (
            f"FY{fy} balance sheet does not foot: assets {assets_total} vs eq+liab {total_eq_liab}"
        )
        assert cc_utilisation >= 0, f"FY{fy} CC utilisation is negative: {cc_utilisation}"
        assert cash >= 0, f"FY{fy} cash is negative: {cash}"

        result.years[fy] = YearModel(fy=fy, pl=pl, bs=bs)
        opening_gross_block = gross_block
        prev_bs = bs

    return result
