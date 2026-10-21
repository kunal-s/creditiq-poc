"""Conduct of the bank accounts, read from the classified transactions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from engine.bank_conduct import Row, build
from engine.configstore.schema import BankConductSection, TxnClassificationSection
from engine.txn_intel import Context, Txn
from engine.txn_labels import label_case
from tests.conftest import ANALYST, make_case, sign_in
from tests.test_txn_intel import KESTREL, SOUTHGATE, _kestrel_rows, _southgate, needs_kestrel
from tests.triangulation import bank

ROOT = Path(__file__).resolve().parent.parent
CFG = BankConductSection.model_validate(yaml.safe_load((ROOT / "config" / "bank_conduct.yaml").read_text()))
REMOVED = {"own_transfer_in", "loan_disbursal", "reversal_refund", "failed_debit_reversal"}
A = "Lotuscrest Bank ·1234"


def r(day: str, category: str, *, cr=0.0, dr=0.0, party=None, bal=None, ref="", account=A, settled=True, narration=None) -> Row:
    return Row(account=account, date=date.fromisoformat(day), narration=narration or f"{category} {party or ''}".strip(),
               debit=dr, credit=cr, category=category, settled=settled, counterparty=party.upper() if party else None,
               party_key=party.lower() if party else None, balance=bal, reference=ref)


def conduct(rows, coverage=None):
    return build("C", rows, coverage or {}, CFG, REMOVED)


def kinds(c):
    return [(f.kind, f.severity) for f in c.flags]


def test_the_defaults_are_a_valid_section_with_known_categories(published_data_root):
    from engine.configstore import reader
    assert reader.load_bank_conduct(published_data_root).statutory_due_day["statutory_gst"] == 20


def test_a_month_reports_cash_returns_salary_and_what_counts_as_business_inflow():
    c = conduct([
        r("2025-04-03", "customer_receipt", cr=700_000, party="Orchid Traders"),
        r("2025-04-05", "cash_deposit", cr=300_000),
        r("2025-04-06", "loan_disbursal", cr=2_000_000),
        r("2025-04-07", "cheque_return", dr=40_000), r("2025-04-08", "cheque_return", dr=10_000),
        r("2025-04-28", "salary", dr=120_000),
    ])
    m = c.months[0]
    assert (m.credits, m.business_credits, m.customer_receipts, m.cash_deposits) == (3_000_000, 1_000_000, 700_000, 300_000)
    assert (m.returns_count, m.returns_amount, m.salary, m.salary_day) == (2, 50_000, 120_000, 28)
    assert ("returns", "concern") in kinds(c) and not any(f.kind == "cash" for f in c.flags)   # 10% of credits: under the threshold


def test_cash_over_the_share_is_flagged_and_a_large_deposit_listed():
    c = conduct([r("2025-04-03", "customer_receipt", cr=600_000, party="X Co"), r("2025-04-05", "cash_deposit", cr=1_200_000)])
    assert [(f.kind, f.severity) for f in c.flags if f.kind == "cash"] == [("cash", "watch"), ("cash", "info")]


def test_concentration_needs_enough_customers_before_it_means_anything():
    few = conduct([r("2025-04-03", "customer_receipt", cr=900_000, party="Orchid"), r("2025-04-04", "customer_receipt", cr=100_000, party="Amber")])
    assert few.customer_top1_pct is None and not any(f.kind == "concentration" for f in few.flags)
    many = conduct([r("2025-04-03", "customer_receipt", cr=600_000, party="Orchid"), r("2025-04-04", "customer_receipt", cr=200_000, party="Amber"),
                    r("2025-04-05", "customer_receipt", cr=100_000, party="Birch"), r("2025-04-06", "customer_receipt", cr=100_000, party="Cedar")])
    assert many.customer_top1_pct == 60.0 and many.customer_top5_pct == 100.0
    assert [p.party for p in many.customers] == ["ORCHID", "AMBER", "BIRCH", "CEDAR"]
    assert ("concentration", "watch") in kinds(many)


def test_money_out_to_and_back_from_the_same_party_is_a_round_trip_inside_the_window_only():
    close = conduct([r("2025-04-03", "supplier_payment", dr=500_000, party="Acme Traders"),
                     r("2025-04-09", "customer_receipt", cr=490_000, party="Acme Traders")])
    assert [(t.party, t.out_amount, t.in_amount) for t in close.round_trips] == [("ACME TRADERS", 500_000, 490_000)]
    assert ("round_trip", "concern") in kinds(close)
    for rows in ([r("2025-04-03", "supplier_payment", dr=500_000, party="Acme Traders"), r("2025-05-20", "customer_receipt", cr=490_000, party="Acme Traders")],
                 [r("2025-04-03", "supplier_payment", dr=500_000, party="Acme Traders"), r("2025-04-05", "customer_receipt", cr=300_000, party="Acme Traders")],
                 [r("2025-04-03", "supplier_payment", dr=500_000, party="Acme Traders"), r("2025-04-05", "customer_receipt", cr=500_000, party="Other Co")]):
        assert conduct(rows).round_trips == []


def _balances(values, start="2025-04-01"):
    d = date.fromisoformat(start)
    from datetime import timedelta
    return [r((d + timedelta(days=i)).isoformat(), "other_credit", cr=1.0, bal=v) for i, v in enumerate(values)]


def test_a_balance_that_peaks_at_month_end_and_falls_back_is_a_spike():
    # April: 29 days at about 1,000,000, then 30 April at 5,000,000, then May's first week back at 1,000,000.
    values = [1_000_000] * 29 + [5_000_000] + [1_000_000] * 10
    c = conduct(_balances(values))
    april = next(m for m in c.balances[0].months if m.month == "2025-04")
    assert april.month_end == 5_000_000 and april.spike and ("balance_spike", "concern") in kinds(c)


def test_a_high_balance_that_stays_is_not_a_spike():
    c = conduct(_balances([1_000_000] * 29 + [5_000_000] + [5_000_000] * 10))
    assert not any(m.spike for m in c.balances[0].months) and not any(f.kind == "balance_spike" for f in c.flags)


def test_statutory_payments_late_or_missing_are_flagged():
    c = conduct([r("2025-04-18", "statutory_gst", dr=50_000), r("2025-05-24", "statutory_gst", dr=50_000),
                 r("2025-06-19", "customer_receipt", cr=1.0, party="X"), r("2025-07-19", "statutory_gst", dr=50_000)])
    assert [(f.kind, f.month) for f in c.flags if f.kind.startswith("statutory")] == [("statutory_late", "2025-05"), ("statutory_gap", "2025-06")]


def test_payments_to_promoters_are_flagged_by_their_share_of_customer_receipts():
    c = conduct([r("2025-04-03", "customer_receipt", cr=1_000_000, party="Orchid"), r("2025-04-10", "promoter_drawings", dr=150_000, party="Dir One"),
                 r("2025-04-12", "promoter_funding", cr=400_000, party="Dir One")])
    assert (c.promoter_out, c.promoter_in) == (150_000, 400_000) and ("promoter", "watch") in kinds(c)


def test_an_entry_far_above_its_kind_and_a_large_weekend_posting_are_unusual():
    rows = [r(f"2025-04-{d:02d}", "supplier_payment", dr=100_000, party="Acme") for d in (2, 3, 4)] + [r("2025-04-15", "supplier_payment", dr=900_000, party="Acme")]
    c = conduct(rows)
    assert [(f.kind, f.amount) for f in c.flags if f.kind == "unusual"] == [("unusual", 900_000)]
    weekend = conduct([r("2025-04-05", "supplier_payment", dr=1_500_000, party="Acme")])         # a Saturday
    assert ("weekend", "info") in kinds(weekend)


def test_the_statements_own_integrity_is_checked():
    rows = [r("2025-04-01", "customer_receipt", cr=100.0, party="A", bal=1_100.0), r("2025-04-02", "supplier_payment", dr=50.0, party="B", bal=1_050.0),
            r("2025-04-03", "supplier_payment", dr=50.0, party="B", bal=900.0),          # 1,050 - 50 is 1,000, not 900
            r("2025-04-03", "supplier_payment", dr=50.0, party="B", bal=850.0)]          # the same entry twice
    c = conduct(rows, coverage={A: {(2025, 4), (2025, 6)}})
    assert {f.kind for f in c.flags} >= {"balance_break", "duplicate", "period_gap"}
    gap = next(f for f in c.flags if f.kind == "period_gap")
    assert gap.month == "2025-05" and gap.severity == "concern"


def test_one_bank_reference_on_two_accounts_is_flagged():
    c = conduct([r("2025-04-01", "customer_receipt", cr=100.0, party="A", ref="NEFT/40007919"),
                 r("2025-04-01", "customer_receipt", cr=9.5, party="A", ref="NEFT/40007919", account="Meridian Trust ·9256")])
    assert ("duplicate_reference", "concern") in kinds(c)
    assert not any(f.kind == "duplicate_reference" for f in conduct([r("2025-04-01", "customer_receipt", cr=1.0, ref="NEFT/1"), r("2025-04-02", "customer_receipt", cr=1.0, ref="NEFT/2")]).flags)


def test_rows_nothing_has_filed_are_counted_and_said_so():
    c = conduct([r("2025-04-01", "other_debit", dr=10.0, settled=False), r("2025-04-02", "other_debit", dr=10.0, settled=False, narration="x"), r("2025-04-03", "salary", dr=1.0)])
    assert c.unsettled_count == 2 and ("unsettled", "info") in kinds(c)


# ---- the sample statements ---------------------------------------------------------------------------------------

def _cfg():
    return TxnClassificationSection.model_validate(yaml.safe_load((ROOT / "config" / "txn_classification.yaml").read_text()))


def _rows(txns):
    finals = label_case(_cfg(), txns, Context(emi_min_months=3, emi_tolerance_pct=5))
    return [Row(account=t.account, date=t.date, narration=t.narration, debit=t.debit, credit=t.credit, category=f.category, settled=f.settled,
                counterparty=f.counterparty, party_key=f.counterparty_key, flags=f.flags) for t, f in zip(txns, finals)]


def test_southgate_twelve_months_reads_as_a_steady_account():
    c = build("S", _rows(_southgate()), {}, CFG, REMOVED)
    assert len(c.months) == 12 and c.unsettled_count == 0
    assert all(m.returns_count == 0 and m.cash_deposits == 0 for m in c.months)
    assert all(m.salary > 0 for m in c.months) and c.customer_top1_pct is not None
    assert not any(f.kind in ("returns", "duplicate", "balance_break", "round_trip") for f in c.flags)


@needs_kestrel
def test_kestrel_clean_statement_has_no_integrity_concern():
    c = build("K", _rows(_kestrel_rows(KESTREL / "K00_clean" / "09_Bank_Statement_Harbour_CA.pdf")), {}, CFG, REMOVED)
    assert not [f for f in c.flags if f.severity == "concern" and f.kind in ("duplicate_reference", "balance_break")]


# ---- the endpoint ------------------------------------------------------------------------------------------------

def test_the_conduct_endpoint_is_behind_the_gate_and_reads_the_case(client: TestClient, published_data_root: Path):
    headers = sign_in(client, ANALYST)
    shut = make_case(client, headers, published_data_root, assessment_open=False)
    assert client.get(f"/api/cases/{shut}/transactions/conduct", headers=headers).json()["detail"] == "assessment_not_open"
    case_id = make_case(client, headers, published_data_root, borrower="Kestrel Tools Pvt Ltd")
    bank(published_data_root, case_id, [
        {"date": "2025-04-03", "description": "NEFT CR ORCHID TRADERS", "credit": 700_000},
        {"date": "2025-04-05", "description": "CASH DEPOSIT CDM TALOJA", "credit": 400_000},
        {"date": "2025-04-07", "description": "CHQ RET 004412 INSUFFICIENT FUNDS", "debit": 25_000},
        {"date": "2025-04-28", "description": "NEFT DR SALARY", "debit": 120_000},
    ])
    r = client.get(f"/api/cases/{case_id}/transactions/conduct", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["months"][0]["cash_deposits"] == 400_000 and body["months"][0]["returns_count"] == 1
    assert {f["kind"] for f in body["flags"]} >= {"cash", "returns"} and body["flags"][0]["severity"] == "concern"


def _kestrel_with_references(pdf: Path, account: str) -> list[Row]:
    import re
    import subprocess
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    refs = [m[1] for line in text.splitlines() if re.match(r"\d{2} \w{3} \d{4}", line) and (m := re.search(r"((?:NEFT|UTR|ACH|GST)/\S+)", line))]
    rows = _rows(_kestrel_rows(pdf))
    assert len(refs) == len(rows)
    for row, ref in zip(rows, refs):
        row.reference, row.account = ref, account
    return rows


@needs_kestrel
@pytest.mark.parametrize("name,second", [("K13_bank_mismatches", "12b_Bank_Statement_Meridian_Trust.pdf"),
                                         ("K10_accounts", "12_Bank_Statement_Undeclared_Account.pdf")])
def test_kestrel_second_statement_repeats_the_first_ones_bank_references(name, second):
    rows = (_kestrel_with_references(KESTREL / name / "09_Bank_Statement_Harbour_CA.pdf", "Harbour ·4417")
            + _kestrel_with_references(KESTREL / name / second, "Meridian ·9256"))
    flags = [f for f in build("K", rows, {}, CFG, REMOVED).flags if f.kind == "duplicate_reference"]
    assert flags and all(f.severity == "concern" for f in flags)


@needs_kestrel
def test_kestrel_clean_set_repeats_no_reference():
    rows = _kestrel_with_references(KESTREL / "K00_clean" / "09_Bank_Statement_Harbour_CA.pdf", "Harbour ·4417")
    assert not [f for f in build("K", rows, {}, CFG, REMOVED).flags if f.kind == "duplicate_reference"]
