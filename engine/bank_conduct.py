"""Conduct of a case's bank accounts, read from the classified statement transactions: cash, returns, concentration,
round trips, balance behaviour, salary and statutory payments, promoter flows, unusual entries, and the integrity of
the statements themselves. Thresholds are configuration (config/bank_conduct.yaml). Every flag names its evidence,
and a flag is a question for a person, never a decision.

`build` is pure: it takes labelled rows and returns the figures. `compute` reads the case."""

from __future__ import annotations

import calendar
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import facts
from .configstore import reader
from .configstore.schema import BankConductSection
from .contracts import CaseDetail, Evidence
from .contracts.transactions import (AccountBalances, BalanceMonth, BankConduct, ConductFlag, MonthConduct, PartyShare,
                                     RoundTrip)
from .util import month_label

RETURN_DEBIT, RETURN_CREDIT = "cheque_return", "failed_debit_reversal"
# Credits and debits that a round trip can be made of: money that comes and goes with a named party.
TRIP_CREDIT = {"customer_receipt", "other_credit", "promoter_funding"}
TRIP_DEBIT = {"supplier_payment", "other_debit", "promoter_drawings"}


@dataclass
class Row:
    """One labelled statement row, as the metrics read it."""

    account: str
    date: date | None
    narration: str
    debit: float
    credit: float
    category: str
    settled: bool
    counterparty: str | None = None
    party_key: str | None = None
    balance: float | None = None
    reference: str = ""
    flags: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def amount(self) -> float:
        return self.credit or self.debit


def _ym(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _flag(out: list[ConductFlag], kind, severity, message, rows: list[Row] | None = None, *, month=None, account=None, amount=None):
    out.append(ConductFlag(kind=kind, severity=severity, message=message, month=month, account=account, amount=amount,
                           evidence=[e for r in (rows or [])[:3] for e in r.evidence[:1]]))


def _shares(rows: list[Row], total: float) -> list[PartyShare]:
    by: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        if r.party_key:
            by[r.party_key].append(r)
    out = [PartyShare(party=max(g, key=lambda r: r.amount).counterparty or k, amount=sum(r.amount for r in g), count=len(g),
                      share_pct=round(sum(r.amount for r in g) / total * 100, 1) if total else 0.0)
           for k, g in by.items()]
    return sorted(out, key=lambda p: -p.amount)


def _daily_balances(rows: list[Row]) -> dict[date, float]:
    """The balance at the close of each day the statement shows, carried forward over days with no entry."""
    last: dict[date, float] = {}
    for r in rows:
        if r.date and r.balance is not None:
            last[r.date] = r.balance
    if not last:
        return {}
    days, out, cur = sorted(last), {}, None
    d, end = days[0], days[-1]
    while d <= end:
        cur = last.get(d, cur)
        out[d] = cur
        d += timedelta(days=1)
    return out


def _balance_months(account: str, rows: list[Row], cfg: BankConductSection, flags: list[ConductFlag]) -> AccountBalances | None:
    daily = _daily_balances(rows)
    if not daily:
        return None
    months: dict[str, list[date]] = defaultdict(list)
    for d in daily:
        months[_ym(d)].append(d)
    out = []
    for ym, days in sorted(months.items()):
        y, m = int(ym[:4]), int(ym[5:])
        values = [daily[d] for d in days]
        end_day = date(y, m, calendar.monthrange(y, m)[1])
        month_end = daily.get(end_day)
        average = sum(values) / len(values)
        spike = False
        if month_end is not None and average > 0 and month_end / average >= cfg.balance.spike_ratio:
            after = [daily[d] for d in (end_day + timedelta(days=i) for i in range(1, cfg.balance.drop_days + 1)) if d in daily]
            if len(after) == cfg.balance.drop_days and sum(after) / len(after) <= month_end * (1 - cfg.balance.drop_pct / 100):
                spike = True
                _flag(flags, "balance_spike", "concern",
                      f"{account}: the balance on {end_day.isoformat()} was {month_end / average:.1f} times the month's average "
                      f"and fell by {cfg.balance.drop_pct:.0f}% or more within {cfg.balance.drop_days} days", None,
                      month=ym, account=account, amount=month_end)
        out.append(BalanceMonth(month=ym, average=round(average, 2), minimum=min(values), month_end=month_end, spike=spike))
    return AccountBalances(account=account, months=out)


def build(case_id: str, rows: list[Row], coverage: dict[str, set[tuple[int, int]]], cfg: BankConductSection,
          removed: set[str]) -> BankConduct:
    """The conduct figures of labelled `rows`. `removed` are the categories taken out of business inflow."""
    flags: list[ConductFlag] = []
    dated = [r for r in rows if r.date]
    by_month: dict[str, list[Row]] = defaultdict(list)
    for r in dated:
        by_month[_ym(r.date)].append(r)

    months: list[MonthConduct] = []
    for ym, mrows in sorted(by_month.items()):
        credits = sum(r.credit for r in mrows)
        cash = sum(r.credit for r in mrows if r.category == "cash_deposit")
        receipts = sum(r.credit for r in mrows if r.category == "customer_receipt")
        ret = [r for r in mrows if r.category == RETURN_DEBIT]
        sal = [r for r in mrows if r.category == "salary"]
        statutory: dict[str, int] = {}
        for r in mrows:
            if r.category in cfg.statutory_due_day:
                statutory[r.category] = max(statutory.get(r.category, 0), r.date.day)
        mc = MonthConduct(
            month=ym, credits=credits, business_credits=sum(r.credit for r in mrows if r.credit and r.category not in removed),
            customer_receipts=receipts, cash_deposits=cash, cash_share_pct=round(cash / credits * 100, 1) if credits else 0.0,
            returns_count=len(ret), returns_amount=sum(r.debit for r in ret),
            failed_debits_reversed=sum(r.credit for r in mrows if r.category == RETURN_CREDIT),
            salary=sum(r.debit for r in sal), salary_day=min((r.date.day for r in sal), default=None), statutory=statutory,
            promoter_in=sum(r.credit for r in mrows if r.category == "promoter_funding"),
            promoter_out=sum(r.debit for r in mrows if r.category == "promoter_drawings"))
        months.append(mc)
        label = month_label((int(ym[:4]), int(ym[5:])))
        if credits and mc.cash_share_pct >= cfg.cash.share_flag_pct:
            _flag(flags, "cash", "watch", f"{label}: cash deposits form {mc.cash_share_pct:.0f}% of gross credits", 
                  [r for r in mrows if r.category == "cash_deposit"], month=ym, amount=cash)
        if len(ret) >= cfg.returns.flag_per_month:
            _flag(flags, "returns", "concern", f"{label}: {len(ret)} cheque return{'s' if len(ret) != 1 else ''} (dishonoured)", ret,
                  month=ym, amount=mc.returns_amount)
        if receipts and mc.promoter_out / receipts * 100 >= cfg.promoter.drawings_flag_pct:
            _flag(flags, "promoter", "watch", f"{label}: promoter drawings are {mc.promoter_out / receipts * 100:.0f}% of customer receipts",
                  [r for r in mrows if r.category == "promoter_drawings"], month=ym, amount=mc.promoter_out)
    for r in dated:
        if r.category == "cash_deposit" and r.credit >= cfg.cash.large_deposit:
            _flag(flags, "cash", "info", f"Large cash deposit of {r.credit:,.0f} on {r.date.isoformat()}", [r], month=_ym(r.date), account=r.account, amount=r.credit)

    # Statutory payments: late, and months with none among months that otherwise have them. One line per payment.
    for cat, due in cfg.statutory_due_day.items():
        name = cat.replace("statutory_", "").replace("_", " ").upper()
        paid = {m.month: m.statutory[cat] for m in months if cat in m.statutory}
        late = {ym: day for ym, day in paid.items() if day > due}
        if late:
            usual = sorted(late.values())[len(late) // 2]
            _flag(flags, "statutory_late", "watch",
                  f"{name} paid after the due date (the {due}th) in {len(late)} of {len(paid)} months with a payment"
                  f" (typically the {usual}th): {', '.join(month_label((int(m[:4]), int(m[5:]))) for m in sorted(late)[:6])}"
                  f"{' and others' if len(late) > 6 else ''}",
                  [r for ym in sorted(late) for r in by_month[ym] if r.category == cat])
        if len(paid) >= 2:
            span = [m.month for m in months]
            gaps = [m for m in span[span.index(min(paid)): span.index(max(paid)) + 1] if m not in paid]
            if gaps:
                _flag(flags, "statutory_gap", "watch",
                      f"No {name} payment recorded for {', '.join(month_label((int(m[:4]), int(m[5:]))) for m in gaps[:6])}"
                      f"{' and others' if len(gaps) > 6 else ''}; payments are otherwise regular")

    # Concentration.
    receipts = [r for r in rows if r.category == "customer_receipt" and r.credit]
    total_receipts = sum(r.credit for r in receipts)
    customers = _shares(receipts, total_receipts)
    top1 = top5 = None
    if len(customers) >= cfg.concentration.min_parties:
        top1, top5 = customers[0].share_pct, round(sum(c.share_pct for c in customers[:5]), 1)
        if top1 >= cfg.concentration.top1_flag_pct:
            _flag(flags, "concentration", "watch", f"Customer concentration: {customers[0].party} accounts for {top1:.0f}% of customer receipts",
                  [r for r in receipts if r.party_key and r.counterparty == customers[0].party], amount=customers[0].amount)
        if top5 >= cfg.concentration.top5_flag_pct:
            _flag(flags, "concentration", "info", f"Top 5 customers account for {top5:.0f}% of customer receipts")
    payments = [r for r in rows if r.category == "supplier_payment" and r.debit and r.party_key]
    suppliers = _shares(payments, sum(r.debit for r in payments))

    # Round trips: money out to and in from the same named party, close in time and amount.
    trips: list[RoundTrip] = []
    used: set[int] = set()
    outs = sorted((r for r in dated if r.debit and r.category in TRIP_DEBIT and r.party_key and r.debit >= cfg.round_trip.min_amount),
                  key=lambda r: r.date)
    ins = [r for r in dated if r.credit and r.category in TRIP_CREDIT and r.party_key and r.credit >= cfg.round_trip.min_amount]
    for o in outs:
        for i in ins:
            if id(i) in used or i.party_key != o.party_key or abs((i.date - o.date).days) > cfg.round_trip.window_days:
                continue
            if abs(i.credit - o.debit) > o.debit * cfg.round_trip.amount_match_pct / 100:
                continue
            used.add(id(i))
            trips.append(RoundTrip(party=o.counterparty or o.party_key, out_date=o.date.isoformat(), out_amount=o.debit,
                                   in_date=i.date.isoformat(), in_amount=i.credit, evidence=[*o.evidence[:1], *i.evidence[:1]]))
            _flag(flags, "round_trip", "concern",
                  f"Possible round-tripping with {o.counterparty or o.party_key}: {o.debit:,.0f} paid on {o.date.isoformat()} and {i.credit:,.0f} received on {i.date.isoformat()}",
                  [o, i], month=_ym(o.date), account=o.account, amount=o.debit)
            break

    # Balances.
    balances = []
    for account in sorted({r.account for r in rows}):
        got = _balance_months(account, [r for r in rows if r.account == account], cfg, flags)
        if got:
            balances.append(got)

    # Unusual entries. A few are listed one by one; many are one line with the count and the largest as evidence.
    by_cat: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in dated:
        by_cat[(r.account, r.category)].append(r.amount)
    far: list[Row] = []
    weekend: list[Row] = []
    for r in dated:
        pool = sorted(by_cat[(r.account, r.category)])
        median = pool[len(pool) // 2]
        if len(pool) >= 3 and r.amount >= cfg.unusual.min_amount and r.amount >= median * cfg.unusual.multiple_of_median:
            far.append(r)
        elif r.date.weekday() >= 5 and r.amount >= cfg.unusual.weekend_min_amount:
            weekend.append(r)
    if 0 < len(far) <= 3:
        for r in far:
            _flag(flags, "unusual", "watch", f"{r.amount:,.0f} on {r.date.isoformat()} is {r.amount / (sorted(by_cat[(r.account, r.category)])[len(by_cat[(r.account, r.category)]) // 2]):.0f} "
                  f"times the median for this type of transaction in {r.account}", [r], month=_ym(r.date), account=r.account, amount=r.amount)
    elif far:
        big = sorted(far, key=lambda r: -r.amount)
        _flag(flags, "unusual", "watch", f"{len(far)} transactions significantly exceed the median for their type; the largest is {big[0].amount:,.0f} on {big[0].date.isoformat()}",
              big, amount=sum(r.amount for r in far))
    if weekend:
        big = sorted(weekend, key=lambda r: -r.amount)
        _flag(flags, "weekend", "info", f"{len(weekend)} high-value transaction{'s' if len(weekend) != 1 else ''} posted on non-working days"
              f" ({sum(r.amount for r in weekend):,.0f} in aggregate); the largest is {big[0].amount:,.0f} on {big[0].date.isoformat()}", big,
              amount=sum(r.amount for r in weekend))

    # Integrity of the statements.
    for account in sorted({r.account for r in rows}):
        mine = [r for r in rows if r.account == account]
        covered = sorted(coverage.get(account, set()))
        if len(covered) >= 2:
            y, m = covered[0]
            while (y, m) <= covered[-1]:
                if (y, m) not in coverage[account]:
                    _flag(flags, "period_gap", "concern", f"{account}: statement not available for {month_label((y, m))} (gap in the period covered)", None,
                          month=f"{y}-{m:02d}", account=account)
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        breaks = []
        prev = None
        for r in mine:
            if r.balance is not None and prev is not None and abs(prev + r.credit - r.debit - r.balance) > cfg.integrity.balance_tolerance:
                breaks.append(r)
            if r.balance is not None:
                prev = r.balance
        if breaks:
            _flag(flags, "balance_break", "concern", f"{account}: running balance does not reconcile with the transactions at {len(breaks)} point{'s' if len(breaks) != 1 else ''}",
                  breaks, account=account)
        seen: dict[tuple, Row] = {}
        twice: list[Row] = []
        for r in mine:
            key = (r.date, r.narration, r.debit, r.credit)
            if key in seen and r.date:
                twice += [seen[key], r]
            seen.setdefault(key, r)
        if twice:
            _flag(flags, "duplicate", "watch", f"{account}: {len(twice) // 2} possible duplicate transaction{'s' if len(twice) > 2 else ''} (same date, narration and amount)"
                  f", for example {twice[0].narration[:40]} on {twice[0].date.isoformat()}", twice, account=account, amount=sum(r.amount for r in twice[1::2]))
    refs: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        if r.reference:
            refs[r.reference].append(r)
    for ref, group in refs.items():
        if len({r.account for r in group}) > 1:
            _flag(flags, "duplicate_reference", "concern",
                  f"Same bank reference {ref} appears on {len({r.account for r in group})} accounts' statements", group)

    unsettled = [r for r in rows if not r.settled]
    if unsettled:
        _flag(flags, "unsettled", "info", f"{len(unsettled)} transaction{'s' if len(unsettled) != 1 else ''} pending classification; included in the figures as they stand", unsettled)

    order = {"concern": 0, "watch": 1, "info": 2}
    flags.sort(key=lambda f: (order[f.severity], f.month or "", f.kind))
    return BankConduct(
        case_id=case_id, accounts=sorted({r.account for r in rows}), months=months, customers=customers[:10],
        customer_top1_pct=top1, customer_top5_pct=top5, suppliers=suppliers[:10], round_trips=trips, balances=balances,
        promoter_in=sum(r.credit for r in rows if r.category == "promoter_funding"),
        promoter_out=sum(r.debit for r in rows if r.category == "promoter_drawings"), flags=flags, unsettled_count=len(unsettled))


def compute(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> BankConduct:
    inputs, finals, coverage, removed = facts.labelled_statement(conn, root, case)
    rows = [Row(account=t.account, date=t.date, narration=t.narration, debit=t.debit, credit=t.credit, category=f.category,
                settled=f.settled, counterparty=f.counterparty, party_key=f.counterparty_key, balance=t.balance,
                reference=t.reference, flags=f.flags, evidence=t.evidence)
            for t, f in zip(inputs.txns, finals)]
    return build(case.id, rows, coverage, reader.load_bank_conduct(root), removed)
