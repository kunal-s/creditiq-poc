"""A simplified bank-account ledger for the provisional-year bank statement.

Not the full double-entry engine reference/05 section B describes (that
models purchases, payroll, EPF/ESI, depreciation and more as posted
journal entries); this generates the one thing the bank statement actually
prints: a dated, running-balance transaction list for the cash-credit
account, deterministic per named RNG stream, that reconciles exactly to the
opening and closing CC utilisation the financial model already computed —
"the plug is also the bank statement's opening balance" (reference/05
section B), and the closing balance ties the same way at year end.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date

from .financials import CaseFinancials
from .rng import named_rng
from .schema import CaseDescriptor

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_CUSTOMER_POOL = [
    "GLOBAL AUTO ENGG PVT LTD", "PRECISION DRIVETRAIN CO", "ORIENT FASTENERS LTD",
    "APEX FORGE INDUSTRIES", "SUNRAY METAL WORKS", "VECTRA COMPONENTS PVT",
    "NORTHFIELD TOOLING CO", "CENTURY GEARS LTD", "BLUEROCK ENGG PVT LTD",
    "ASHOKA TRADERS", "HARBOUR LINE EXPORTS", "TRIVENI HARDWARE CO",
]
_SUPPLIER_POOL = [
    "SRI VENKATESA STEELS", "MODERN ALLOY TRADERS", "KRISHNA CASTINGS PVT",
    "UNITY BEARINGS CO", "STARLITE FASTENERS", "GOLDEN TOOLS SUPPLY",
    "RAJDHANI HARDWARE", "PIONEER LUBRICANTS CO",
]


@dataclass
class Transaction:
    txn_date: date
    narration: str
    reference: str
    debit: int
    credit: int
    balance: int
    tags: list[str] = field(default_factory=list)


def _month_dates(year: int) -> list[date]:
    """The 12 (year, month) starts of an FY window beginning 1 April `year`-1."""
    months = []
    y, m = year - 1, 4
    for _ in range(12):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _truncate_name(rng, name: str) -> str:
    if rng.random() < 0.15:
        words = name.split()
        if len(words) > 1:
            return " ".join(words[:-1])
    return name


def generate_bank_ledger(
    descriptor: CaseDescriptor, financials: CaseFinancials, fy: int
) -> list[Transaction]:
    rng = named_rng(descriptor.seed, descriptor.case_id, f"bank_ledger/{fy}")

    opening_balance = financials.years[fy - 1].bs.borrowings_st if (fy - 1) in financials.years else 0
    closing_target = financials.years[fy].bs.borrowings_st
    net_reduction_target = opening_balance - closing_target  # positive => balance falls over the year

    revenue = financials.years[fy].pl.revenue
    materials_cost = revenue * sum(
        v for k, v in descriptor.financial_model.cost_ratios.items() if k in ("materials", "power")
    )
    employee_cost = revenue * descriptor.financial_model.cost_ratios.get("employee", 0.0)
    gst_rate = descriptor.financial_model.gst_rate

    months = _month_dates(fy)
    events: list[Transaction] = []

    # --- debit side: supplier payments, salary, GST, interest -------------
    total_debits = 0
    for i, month_start in enumerate(months):
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        month_supplier_total = 0
        n_payments = rng.randint(3, 5)
        shares = [rng.uniform(0.6, 1.4) for _ in range(n_payments)]
        share_sum = sum(shares)
        for share in shares:
            amt = round(materials_cost / 12 * (share / share_sum) / 1000) * 1000
            amt = max(amt, 1000)
            day = rng.randint(3, last_day - 5)
            supplier = rng.choice(_SUPPLIER_POOL)
            events.append(
                Transaction(
                    date(month_start.year, month_start.month, day),
                    f"NEFT/{supplier}/PURCHASE",
                    f"NEFT{rng.randint(100000,999999)}",
                    amt,
                    0,
                    0,
                    ["supplier_payment"],
                )
            )
            month_supplier_total += amt
        total_debits += month_supplier_total

        salary_day = min(last_day, rng.randint(28, 30) if last_day >= 28 else last_day)
        salary_amt = round(employee_cost / 12 / 1000) * 1000
        events.append(
            Transaction(
                date(month_start.year, month_start.month, salary_day),
                "NEFT/SALARY/BULK",
                f"SAL{rng.randint(100000,999999)}",
                salary_amt,
                0,
                0,
                ["payroll"],
            )
        )
        total_debits += salary_amt

        gst_day = min(20, last_day)
        gst_amt = round(revenue / 12 * gst_rate * 0.14 / 1000) * 1000
        events.append(
            Transaction(
                date(month_start.year, month_start.month, gst_day),
                "GST PAYMENT",
                f"GSTCH{rng.randint(100000,999999)}",
                gst_amt,
                0,
                0,
                ["gst_payment"],
            )
        )
        total_debits += gst_amt

        interest_day = last_day
        interest_amt = round(opening_balance * 0.1075 / 12 / 1000) * 1000
        events.append(
            Transaction(
                date(month_start.year, month_start.month, interest_day),
                "CC INTEREST DEBIT",
                f"INT{rng.randint(100000,999999)}",
                interest_amt,
                0,
                0,
                ["cc_interest"],
            )
        )
        total_debits += interest_amt

    # --- outward cheque return (precision trap: one, this year) -----------
    trap_month = months[rng.randint(2, 9)]
    cheque_amt = round(materials_cost / 12 * 0.4 / 1000) * 1000
    cheque_day = rng.randint(5, 20)
    events.append(
        Transaction(
            date(trap_month.year, trap_month.month, cheque_day),
            f"CHQ PAID/{rng.choice(_SUPPLIER_POOL)}",
            f"CHQ{rng.randint(100000,999999)}",
            cheque_amt,
            0,
            0,
            ["supplier_payment"],
        )
    )
    total_debits += cheque_amt
    events.append(
        Transaction(
            date(trap_month.year, trap_month.month, min(cheque_day + 2, 28)),
            "CHEQUE RETURN OUTWARD",
            f"CHQRET{rng.randint(100000,999999)}",
            0,
            cheque_amt,
            0,
            ["cheque_return_outward"],
        )
    )
    bounce_charge = 500
    events.append(
        Transaction(
            date(trap_month.year, trap_month.month, min(cheque_day + 2, 28)),
            "CHEQUE RETURN CHARGES",
            f"CHG{rng.randint(100000,999999)}",
            bounce_charge,
            0,
            0,
            ["bank_charge"],
        )
    )
    total_debits += bounce_charge

    # --- credit side: customer receipts, sized so the year ties exactly ---
    # (total_credits_target is finalised below, once every debit — including
    # the reversal's — is known.)
    gross_factor = 1 + gst_rate  # bank credits are GST-inclusive (plan.md C6)

    receipt_events: list[Transaction] = []
    for month_start in months:
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        n_receipts = rng.randint(3, 5)
        shares = [rng.uniform(0.6, 1.4) for _ in range(n_receipts)]
        share_sum = sum(shares)
        month_target = revenue / 12 * gross_factor
        for share in shares:
            amt = round(month_target * (share / share_sum) / 1000) * 1000
            amt = max(amt, 1000)
            day = rng.randint(2, last_day - 2)
            customer = _truncate_name(rng, rng.choice(_CUSTOMER_POOL))
            mode = rng.choice(["NEFT", "RTGS", "IMPS"])
            receipt_events.append(
                Transaction(
                    date(month_start.year, month_start.month, day),
                    f"{mode}/{customer}/RECEIPT",
                    f"{mode}{rng.randint(100000,999999)}",
                    0,
                    amt,
                    0,
                    ["customer_receipt"],
                )
            )

    # One own-account sweep, tagged for exclusion from business credits.
    sweep_month = months[rng.randint(2, 9)]
    sweep_amt = round(revenue / 12 * 0.9 / 1000) * 1000
    receipt_events.append(
        Transaction(
            date(sweep_month.year, sweep_month.month, rng.randint(5, 25)),
            "OWN ACCOUNT TRANSFER IN",
            f"SELF{rng.randint(100000,999999)}",
            0,
            sweep_amt,
            0,
            ["own_transfer"],
        )
    )

    # One reversed NEFT: a receipt immediately undone.
    reversal_month = months[rng.randint(2, 9)]
    reversal_amt = round(revenue / 12 * 0.35 / 1000) * 1000
    reversal_day = rng.randint(5, 20)
    reversed_customer = rng.choice(_CUSTOMER_POOL)
    reversed_receipt = Transaction(
        date(reversal_month.year, reversal_month.month, reversal_day),
        f"NEFT/{reversed_customer}/RECEIPT",
        f"NEFT{rng.randint(100000,999999)}",
        0,
        reversal_amt,
        0,
        ["customer_receipt"],
    )
    receipt_events.append(reversed_receipt)
    events.append(
        Transaction(
            date(reversal_month.year, reversal_month.month, min(reversal_day + 1, 28)),
            "NEFT RETURN",
            f"NEFTRET{rng.randint(100000,999999)}",
            reversal_amt,
            0,
            0,
            ["reversal"],
        )
    )
    total_debits += reversal_amt

    # total_credits - total_debits must equal net_reduction_target, and every
    # debit is now accounted for.
    total_credits_target = total_debits + net_reduction_target

    # Scale the ordinary receipts (everything except the fixed-size traps:
    # the sweep and the reversed receipt) so the year ties to the target
    # exactly, absorbing rounding in the last one.
    fixed = {id(receipt_events[-2]), id(reversed_receipt)}  # sweep, reversed receipt
    scalable = [e for e in receipt_events if id(e) not in fixed]
    scalable_total = sum(e.credit for e in scalable)
    # The cheque-return credit (which offsets the cheque debit already inside
    # total_debits) is fixed too, like the sweep and the reversed receipt.
    target_scalable_total = total_credits_target - sweep_amt - reversal_amt - cheque_amt
    if scalable_total > 0:
        factor = target_scalable_total / scalable_total
        running_total = 0
        for i, e in enumerate(scalable):
            if i < len(scalable) - 1:
                new_amt = round(e.credit * factor / 100) * 100
                running_total += new_amt
                e.credit = new_amt
            else:
                e.credit = target_scalable_total - running_total

    events.extend(receipt_events)
    events.sort(key=lambda e: e.txn_date)

    balance = opening_balance
    for e in events:
        balance = balance - e.credit + e.debit
        e.balance = balance

    return events
