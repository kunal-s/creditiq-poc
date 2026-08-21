"""
Single source of truth for the financial backbone. Every document that touches
these numbers imports them from here so the whole set is internally consistent.

The anchor figures (revenue, EBITDA, PAT, net worth) are fixed by the brief and
must appear EXACTLY. Surrounding line items are derived so that:
    EBITDA - depreciation - finance costs = profit before tax
    profit before tax - tax = profit after tax   (== the anchor PAT)
    balance sheet: total assets == total equity and liabilities
"""

# ---- Anchor figures (fixed by the brief) --------------------------------- #
FY2024 = dict(
    label="FY2024", year_end="31 March 2024", ay="2024-25",
    revenue=184267400, ebitda=22112088, pat=8734210, net_worth=46218750,
)
FY2025 = dict(
    label="FY2025", year_end="31 March 2025", ay="2025-26",
    revenue=231784900, ebitda=28973113, pat=11462880, net_worth=57681630,
)
FY2026_9M = dict(
    label="9M FY2026", period="Nine months ended 31 December 2025",
    revenue=198642300, pat=9618470,
)

SHARE_CAPITAL = 10000000  # 10,00,000 equity shares of Rs.10 each

STOCK_30JUN2026 = 43892150
BOOKDEBT_30JUN2026 = 31247880
BOOKDEBT_OVER90 = 4183200


def _derive_pl(anchor, other_income, depreciation, finance_costs):
    """Fill in the P&L so PBT and tax reconcile the anchor PAT exactly."""
    pbt = anchor["ebitda"] - depreciation - finance_costs
    tax = pbt - anchor["pat"]
    total_income = anchor["revenue"] + other_income
    total_opex = total_income - anchor["ebitda"]  # materials + employee + other
    return dict(other_income=other_income, depreciation=depreciation,
                finance_costs=finance_costs, pbt=pbt, tax=tax,
                total_income=total_income, total_opex=total_opex)


def pl_fy2024():
    d = _derive_pl(FY2024, other_income=980000, depreciation=6800000,
                   finance_costs=3509102)
    # split total_opex into components (materials, change in inventory, employee, other)
    materials = 119000000
    change_inv = -1800000  # increase in stock -> negative expense
    employee = 22800000
    d.update(materials=materials, change_inv=change_inv, employee=employee,
             other_exp=d["total_opex"] - (materials + change_inv + employee))
    return d


def pl_fy2025():
    d = _derive_pl(FY2025, other_income=1250000, depreciation=9500000,
                   finance_costs=3982735)
    materials = 148000000
    change_inv = -2500000
    employee = 26400000
    d.update(materials=materials, change_inv=change_inv, employee=employee,
             other_exp=d["total_opex"] - (materials + change_inv + employee))
    return d


def pl_fy2026_9m():
    # part-year: derive a plausible EBITDA, then reconcile PAT exactly
    pat = FY2026_9M["pat"]
    depreciation = 7200000
    finance_costs = 3000000
    tax = 3379462
    pbt = pat + tax
    ebitda = pbt + depreciation + finance_costs
    other_income = 800000
    total_income = FY2026_9M["revenue"] + other_income
    total_opex = total_income - ebitda
    materials = 128000000
    change_inv = -2100000
    employee = 19800000
    return dict(revenue=FY2026_9M["revenue"], other_income=other_income,
                ebitda=ebitda, depreciation=depreciation, finance_costs=finance_costs,
                pbt=pbt, tax=tax, pat=pat, total_income=total_income,
                total_opex=total_opex, materials=materials, change_inv=change_inv,
                employee=employee,
                other_exp=total_opex - (materials + change_inv + employee))


def balance_sheet(net_worth, ppe, intangibles, lt_loans, borrowings_lt, dtl,
                  borrowings_st, trade_payables, other_cl, provisions,
                  inventories, receivables, cash):
    """Return a balanced balance sheet dict; short-term loans & advances plugs it."""
    reserves = net_worth - SHARE_CAPITAL
    total_eq_liab = (SHARE_CAPITAL + reserves + borrowings_lt + dtl +
                     borrowings_st + trade_payables + other_cl + provisions)
    known_assets = (ppe + intangibles + lt_loans + inventories + receivables + cash)
    st_loans = total_eq_liab - known_assets
    return dict(
        share_capital=SHARE_CAPITAL, reserves=reserves, net_worth=net_worth,
        borrowings_lt=borrowings_lt, dtl=dtl, borrowings_st=borrowings_st,
        trade_payables=trade_payables, other_cl=other_cl, provisions=provisions,
        ppe=ppe, intangibles=intangibles, lt_loans=lt_loans,
        inventories=inventories, receivables=receivables, cash=cash,
        st_loans=st_loans, total=total_eq_liab,
    )


def bs_fy2024():
    return balance_sheet(
        net_worth=FY2024["net_worth"], ppe=34800000, intangibles=320000,
        lt_loans=2200000, borrowings_lt=14500000, dtl=1980000,
        borrowings_st=8000000, trade_payables=21800000, other_cl=3150000,
        provisions=3400000, inventories=33000000, receivables=25500000, cash=2600000)


def bs_fy2025():
    return balance_sheet(
        net_worth=FY2025["net_worth"], ppe=38500000, intangibles=450000,
        lt_loans=2800000, borrowings_lt=12000000, dtl=2240000,
        borrowings_st=9500000, trade_payables=26450000, other_cl=3820000,
        provisions=4160000, inventories=39500000, receivables=29000000, cash=4200000)


# ---- FY2023, used only as the prior-year comparative in the FY2024 audit ---- #
# Net worth ties: FY2024 net worth = FY2023 net worth + FY2024 PAT.
FY2023 = dict(label="FY2023", year_end="31 March 2023", ay="2023-24",
              revenue=159200000, ebitda=18650000, pat=6820000,
              net_worth=FY2024["net_worth"] - FY2024["pat"])  # 3,74,84,540


def pl_fy2023():
    d = _derive_pl(FY2023, other_income=850000, depreciation=6200000,
                   finance_costs=3233784)
    materials = 103000000
    change_inv = -1500000
    employee = 19800000
    d.update(materials=materials, change_inv=change_inv, employee=employee,
             other_exp=d["total_opex"] - (materials + change_inv + employee))
    return d


def bs_fy2023():
    return balance_sheet(
        net_worth=FY2023["net_worth"], ppe=33000000, intangibles=280000,
        lt_loans=2000000, borrowings_lt=15500000, dtl=1750000,
        borrowings_st=7000000, trade_payables=19500000, other_cl=2800000,
        provisions=3000000, inventories=30500000, receivables=22000000, cash=2400000)


def cash_flow(cur_bs, prev_bs, pl):
    """
    Indirect-method cash flow that reconciles exactly to the movement in the
    balance-sheet cash figure. Financing activities carry the balancing figure.
    """
    d_inv = cur_bs["inventories"] - prev_bs["inventories"]
    d_rec = cur_bs["receivables"] - prev_bs["receivables"]
    d_pay = cur_bs["trade_payables"] - prev_bs["trade_payables"]
    d_ocl = (cur_bs["other_cl"] + cur_bs["provisions"]) - \
            (prev_bs["other_cl"] + prev_bs["provisions"])
    wc_change = -d_inv - d_rec + d_pay + d_ocl
    op_before_wc = pl["pbt"] + pl["depreciation"] + pl["finance_costs"]
    taxes_paid = pl["tax"]
    op_cash = op_before_wc + wc_change - taxes_paid

    capex = -((cur_bs["ppe"] - prev_bs["ppe"]) + pl["depreciation"])  # gross additions
    d_intang = -(cur_bs["intangibles"] - prev_bs["intangibles"])
    d_ltloan = -(cur_bs["lt_loans"] - prev_bs["lt_loans"])
    inv_cash = capex + d_intang + d_ltloan

    net_change = cur_bs["cash"] - prev_bs["cash"]
    fin_cash = net_change - op_cash - inv_cash  # balancing figure
    return dict(op_before_wc=op_before_wc, wc_change=wc_change, taxes_paid=taxes_paid,
                op_cash=op_cash, capex=capex, d_intang=d_intang, d_ltloan=d_ltloan,
                inv_cash=inv_cash, fin_cash=fin_cash, net_change=net_change,
                open_cash=prev_bs["cash"], close_cash=cur_bs["cash"])


if __name__ == "__main__":
    for name, d in [("FY2024 BS", bs_fy2024()), ("FY2025 BS", bs_fy2025())]:
        assets = (d["ppe"] + d["intangibles"] + d["lt_loans"] + d["inventories"] +
                  d["receivables"] + d["cash"] + d["st_loans"])
        print(name, "total", d["total"], "assets", assets, "balanced", assets == d["total"],
              "st_loans", d["st_loans"])
    for name, d in [("PL24", pl_fy2024()), ("PL25", pl_fy2025()), ("PL26", pl_fy2026_9m())]:
        print(name, "pbt", d["pbt"], "tax", d["tax"],
              "eff%", round(100 * d["tax"] / d["pbt"], 1),
              "other_exp", d["other_exp"])
