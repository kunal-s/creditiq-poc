"""Bank-statement transaction classification, the deterministic pass (config/txn_classification.yaml)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
import yaml

from engine.configstore import reader
from engine.configstore.schema import TxnClassificationSection
from engine.txn_intel import Context, Txn, classify

ROOT = Path(__file__).resolve().parent.parent
SOUTHGATE = ROOT / "tests" / "fixtures" / "service_output" / "Southgate_CCB_CA_Statements_12m.json"
KESTREL = ROOT / "workflow" / "docs" / "reference" / "fixtures" / "kestrel"


@pytest.fixture(scope="module")
def cfg() -> TxnClassificationSection:
    return TxnClassificationSection.model_validate(yaml.safe_load((ROOT / "config" / "txn_classification.yaml").read_text()))


def one(cfg, narration: str, *, dr: float = 0, cr: float = 0, ctx: Context | None = None, **kw):
    return classify(cfg, [Txn("t1", "A", date(2026, 4, 1), narration, debit=dr, credit=cr, **kw)], ctx)[0]


def test_the_published_config_carries_the_section(published_data_root: Path):
    section = reader.load_txn_classification(published_data_root)
    assert {c.id for c in section.categories} >= {"customer_receipt", "loan_emi", "other_debit", "other_credit"}
    assert section.problems() == []


def test_a_rule_that_names_a_category_of_the_other_direction_is_refused(cfg):
    bad = cfg.model_copy(deep=True)
    bad.rules[0].category = "customer_receipt"   # a debit rule giving a credit category
    assert any("cannot give" in p for p in bad.problems())


def test_a_pattern_that_does_not_compile_is_refused(cfg):
    bad = cfg.model_copy(deep=True)
    bad.rules[0].any = ["(unclosed"]
    assert any("bad pattern" in p for p in bad.problems())


# narration, direction, expected category, expected counterparty (None: do not care)
CASES = [
    ("NEFT CR PRAGATI TOOLING", "cr", "customer_receipt", "PRAGATI TOOLING"),
    ("RTGS DR SUPPLIER PAYMENT", "dr", "supplier_payment", None),
    ("NACH DR LOTUSCREST FIN 000123 EMI", "dr", "loan_emi", "LOTUSCREST FIN"),
    ("MERIDIAN BANK EMI DR", "dr", "loan_emi", "MERIDIAN BANK"),
    ("NEFT DR GST CHALLAN PAYMENT", "dr", "statutory_gst", None),
    ("NEFT DR SALARY", "dr", "salary", None),
    ("SALARY BULK NEFT - STAFF", "dr", "salary", None),
    ("EPF ESI REMITTANCE", "dr", "statutory_pf_esi", None),
    ("TDS PAYMENT CHALLAN 281", "dr", "statutory_tds", None),
    ("ADVANCE TAX Q2", "dr", "statutory_income_tax", None),
    ("BANK CHARGES + GST", "dr", "bank_charges", None),
    ("TNEB ELECTRICITY CHG", "dr", "rent_utilities", None),
    ("CASH DEPOSIT CDM TALOJA", "cr", "cash_deposit", None),
    ("CASH WDL SELF CHQ 004412", "dr", "cash_withdrawal", None),
    ("CHQ RET 004412 INSUFFICIENT FUNDS", "dr", "cheque_return", None),
    ("NACH RETURN REVERSAL 778811", "cr", "failed_debit_reversal", None),   # both cues: see the ambiguity test
    ("REFUND OF EXCESS CHARGES", "cr", "reversal_refund", None),
    ("INT CR SB 0926", "cr", "interest_credit", None),
    ("INCOME TAX REFUND ITD", "cr", "tax_refund", None),
    ("LOAN DISBURSAL TL 99120", "cr", "loan_disbursal", None),
    ("UPI/DR/402211009988/ZOMATO", "dr", "supplier_payment", "ZOMATO"),
    ("IMPS CR RELIANCE RETAIL LTD", "cr", "customer_receipt", "RELIANCE RETAIL LTD"),
]


@pytest.mark.parametrize("narration,side,category,party", CASES)
def test_narrations(cfg, narration, side, category, party):
    label = one(cfg, narration, dr=500.5 if side == "dr" else 0, cr=500.5 if side == "cr" else 0)
    if label.status == "ambiguous":
        assert category in label.candidates
        return
    assert (label.category, label.status) == (category, "matched"), label
    if party:
        assert label.counterparty == party


def test_a_narration_with_two_competing_cues_is_ambiguous_and_goes_to_the_model(cfg):
    label = one(cfg, "NACH RETURN REVERSAL 778811", cr=1000)
    assert label.status == "ambiguous"
    assert set(label.candidates) == {"failed_debit_reversal", "reversal_refund"}
    assert label.category == "other_credit" and label.needs_model and label.rule_id is None


def test_a_narration_nothing_matches_is_unmatched_and_goes_to_the_model(cfg):
    label = one(cfg, "XQ77 MISC ADJ", dr=250)
    assert (label.status, label.category, label.needs_model) == ("unmatched", "other_debit", True)


def test_direction_decides_which_rules_apply(cfg):
    assert one(cfg, "REFUND", cr=100).category == "reversal_refund"
    assert one(cfg, "REFUND", dr=100).status == "unmatched"   # no debit rule reads a refund


def test_a_more_specific_tier_wins_over_the_channel_default(cfg):
    assert one(cfg, "NEFT DR SALARY", dr=1000).rule_id == "salary"        # tier 1 over the tier 3 default
    assert one(cfg, "NEFT DR ACME PARTS", dr=1000).rule_id == "supplier_payment_default"


def test_the_case_supplies_names_a_narration_may_mention(cfg):
    ctx = Context(borrower_name="Kestrel Fabricators Private Limited", own_account_last4=frozenset({"4417", "9256"}),
                  lender_names=("Vesta Capital Limited",), director_names=("Ishita Barve",))
    assert one(cfg, "NEFT DR TRF TO A/C 740030099256", dr=100000, ctx=ctx, account_last4="4417").category == "own_transfer_out"
    assert one(cfg, "NEFT CR 740030094417 SELF", cr=100000, ctx=ctx, account_last4="9256").category == "own_transfer_in"
    assert one(cfg, "TRANSFER KESTREL FABRICATORS PVT LTD", dr=10, ctx=ctx).category == "own_transfer_out"
    assert one(cfg, "NACH DR VESTA CAPITAL 778811", dr=96500, ctx=ctx).category == "loan_emi"
    assert one(cfg, "RTGS CR VESTA CAPITAL LTD", cr=5000000, ctx=ctx).category == "loan_disbursal"
    assert one(cfg, "NEFT CR ISHITA BARVE", cr=2500000, ctx=ctx).category == "promoter_funding"
    assert one(cfg, "NEFT DR ISHITA BARVE", dr=300000, ctx=ctx).category == "promoter_drawings"
    # the same narrations with no such context are read as trade
    assert one(cfg, "NEFT CR ISHITA BARVE", cr=2500000).category == "customer_receipt"


def test_a_lookup_never_matches_the_accounts_own_digits(cfg):
    ctx = Context(own_account_last4=frozenset({"4417"}))
    assert one(cfg, "NEFT DR REF 740030094417", dr=10, ctx=ctx, account_last4="4417").category == "supplier_payment"


def test_round_amounts_are_flagged(cfg):
    assert "round_amount" in one(cfg, "NEFT CR ACME", cr=2500000).flags
    assert "round_amount" not in one(cfg, "NEFT CR ACME", cr=2500001).flags
    assert "round_amount" not in one(cfg, "NEFT CR ACME", cr=50000).flags


def _monthly(narrations: list[str], months: int, amount: float) -> list[Txn]:
    return [Txn(f"r{i}-{m}", "A", date(2026, 1 + m, 5), n, debit=amount + i) for m in range(months) for i, n in enumerate(narrations)]


def test_a_recurring_debit_to_a_lender_with_no_instalment_cue_is_a_loan_instalment(cfg):
    rows = _monthly(["ONLINE PMT KARMA FINCORP 55"], months=4, amount=48000)
    labels = classify(cfg, rows, Context(emi_min_months=3, emi_tolerance_pct=5))
    assert {l.category for l in labels} == {"loan_emi"}
    assert {l.rule_id for l in labels} == {"recurring_lender_debit"} and all("recurring" in l.flags for l in labels)


def test_a_recurring_debit_to_a_non_lender_is_flagged_but_keeps_its_category(cfg):
    labels = classify(cfg, _monthly(["NEFT DR ACME PACKAGING"], months=4, amount=48000), Context())
    assert {l.category for l in labels} == {"supplier_payment"} and all("recurring" in l.flags for l in labels)


def test_amounts_that_drift_are_not_recurring(cfg):
    rows = [Txn(f"d{m}", "A", date(2026, 1 + m, 5), "NEFT DR ACME PACKAGING", debit=10000 * (m + 1) ** 2) for m in range(4)]
    assert not any("recurring" in l.flags for l in classify(cfg, rows, Context()))


def test_equal_amounts_between_two_accounts_are_a_transfer_when_nothing_else_is_said(cfg):
    out = Txn("o", "A", date(2026, 4, 1), "MISC DEBIT 8841", debit=750000.0)
    inn = Txn("i", "B", date(2026, 4, 2), "MISC CREDIT 1190", credit=750000.0)
    a, b = classify(cfg, [out, inn], Context())
    assert (a.category, b.category) == ("own_transfer_out", "own_transfer_in")
    assert (a.paired_with, b.paired_with) == ("i", "o") and a.rule_id == "paired_transfer"


def test_a_pair_further_apart_than_the_window_is_not_a_transfer(cfg):
    out = Txn("o", "A", date(2026, 4, 1), "MISC DEBIT 8841", debit=750000.0)
    inn = Txn("i", "B", date(2026, 4, 20), "MISC CREDIT 1190", credit=750000.0)
    assert [l.status for l in classify(cfg, [out, inn], Context())] == ["unmatched", "unmatched"]


def test_the_result_is_the_same_every_time(cfg):
    rows = _monthly(["NACH DR VESTA CAPITAL 778811 EMI", "NEFT DR SALARY", "XQ77 MISC"], months=4, amount=50000)
    assert classify(cfg, rows, Context()) == classify(cfg, rows, Context())


# ---- the sample statements -----------------------------------------------------------------------------------

def _southgate() -> list[Txn]:
    doc = json.loads(SOUTHGATE.read_text())["documents"][0]
    out = []
    for i, r in enumerate(doc["tables"]["transactions"]["rows"]):
        c = r["cells"]
        if (c["debit"] or 0) == 0 and (c["credit"] or 0) == 0:
            continue
        out.append(Txn(f"s{i}", "Southgate", date.fromisoformat(c["date"]), c["description"], debit=c["debit"] or 0, credit=c["credit"] or 0))
    return out


def test_southgate_twelve_months_are_all_labelled_by_rule(cfg):
    txns = _southgate()
    labels = classify(cfg, txns, Context(emi_min_months=3, emi_tolerance_pct=5))
    assert len(labels) == len(txns) > 300
    unsettled = [(t.narration, l.status) for t, l in zip(txns, labels) if l.status != "matched"]
    assert unsettled == []
    by = Counter(l.category for l in labels)
    assert by["loan_emi"] == 12 and by["salary"] == 12 and by["statutory_pf_esi"] == 12 and by["bank_charges"] == 11
    assert by["customer_receipt"] > 100 and by["supplier_payment"] > 100


def _kestrel_rows(pdf: Path) -> list[Txn]:
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    opening = int(re.search(r"Opening Balance[^\n]*?([\d,]{4,})\s*$", text, re.M)[1].replace(",", ""))
    prev, out = opening, []
    for line in text.splitlines():
        m = re.match(r"(\d{2} \w{3} \d{4})\s+(.+?)\s{2,}", line)
        nums = re.findall(r"(?<![\w/])\d[\d,]*(?:\.\d+)?(?=\s|$)", line)
        if not m or len(nums) < 2:
            continue
        balance, amount = (int(n.replace(",", "")) for n in nums[-2:][::-1])
        when = date(*(__import__("time").strptime(m[1], "%d %b %Y")[:3]))
        credit = balance > prev
        out.append(Txn(f"k{len(out)}", pdf.name, when, re.sub(r"\s+\S+/\S+$", "", m[2]).strip(),
                       credit=amount if credit else 0, debit=0 if credit else amount))
        prev = balance
    return out


needs_kestrel = pytest.mark.skipif(not KESTREL.is_dir() or not shutil.which("pdftotext"), reason="the Kestrel sets are not on this machine")


@needs_kestrel
def test_kestrel_clean_set_is_all_labelled_and_names_its_lender(cfg):
    txns = _kestrel_rows(KESTREL / "K00_clean" / "09_Bank_Statement_Harbour_CA.pdf")
    assert len(txns) > 100
    labels = classify(cfg, txns, Context(lender_names=("Lotuscrest Finance",), emi_min_months=3, emi_tolerance_pct=5))
    assert [l.status for l in labels if l.status != "matched"] == []
    emi = [l for l in labels if l.category == "loan_emi"]
    assert len(emi) == 18 and {l.counterparty for l in emi} == {"LOTUSCREST FIN"}
    assert {l.counterparty for l in labels if l.category == "customer_receipt"} == {
        "PRAGATI TOOLING", "BHARAT PUMPS LTD", "ORIENT GEARBOX CO", "SUNRISE HYDRAULICS", "VARDHAN AUTOMOTIVE"}


@needs_kestrel
def test_kestrel_undeclared_lender_is_found_among_the_instalments(cfg):
    txns = _kestrel_rows(KESTREL / "K11_obligations" / "09_Bank_Statement_Harbour_CA.pdf")
    labels = classify(cfg, txns, Context(lender_names=("Lotuscrest Finance",), emi_min_months=3, emi_tolerance_pct=5))
    emi = Counter(l.counterparty for l in labels if l.category == "loan_emi")
    assert emi == {"LOTUSCREST FIN": 18, "VESTA CAPITAL": 18}
