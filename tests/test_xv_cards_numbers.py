"""The number cards of the cross-verification board (F-19.3; engine/xv_cards/numbers.py): TO-01 to
TO-05, TX-01, TX-02, FS-01 and FS-02. Each figure the rule compared is a column with the rows
behind it (the returns month by month, each account's credits by month with the credits excluded,
the printed lines), and the rows add up to the figure; the gap is the rule's own variance against
the rule's own tolerance; a check that could not run says what would complete it, and a year not
yet ended asks for nothing; each turnover check gives its key-figure line for the area's overview
card. The cards never change an outcome. TX-01, TX-02, FS-01 and FS-02 are switched off in
configuration: their tests switch every rule on (all_rules_enabled). Every name is fictional."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cases, crosschecks, db, facts, pipeline, xv_cards
from engine.configstore import reader
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, months, row_index

FY26 = months((2025, 4), 12)  # FY 2025-26
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]
TURNOVER = ("TO-01", "TO-02", "TO-03", "TO-04", "TO-05")
RULES = (*TURNOVER, "TX-01", "TX-02", "FS-01", "FS-02")
LOTUSCREST, HARBOURLINE = "Lotuscrest Bank ·1234", "Harbourline Bank ·5678"
GST_HEADINGS = ["Period", "Filed", "3.1(a)+(b)+(c) outward supplies"]
TABLE_3_1 = {
    "a": "(a) Outward taxable supplies (other than zero rated, nil rated and exempted)",
    "b": "(b) Outward taxable supplies (zero rated)",
    "c": "(c) Other outward supplies (nil rated, exempted)",
    "d": "(d) Inward supplies (liable to reverse charge)",
    "e": "(e) Non-GST outward supplies",
}
"""The rows of table 3.1 of a GSTR-3B, as the return prints them."""
BANK_HEADINGS = ["Month", "Account", "Credits", "Excluded credits"]
DISBURSAL = "TL DISB LOAN A/C 88991"
GST_AGAINST_BANK = {"label": "Gap against bank credits", "base": "GST outward supplies",
                    "legs": "GST outward supplies against bank credits"}


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _case(client: TestClient, headers: dict, root: Path, **overrides) -> str:
    return make_case(client, headers, root, **{"borrower": "Kestrel Tools Pvt Ltd", **overrides})


# --- Documents ---


def _gstr(root: Path, case_id: str, ym: str, taxable: int, *, page: int = 2, pending: bool = False,
          rows: dict[str, int] | None = None) -> str:
    """One GSTR-3B for the month `ym` ("2025-04"), filed on the 20th of the next month. Table 3.1
    prints row (a) with `taxable`, or the rows of `rows` (by letter) instead."""
    filed = months((int(ym[:4]), int(ym[5:])), 2)[1]
    printed = rows or {"a": taxable}
    return add_doc(root, case_id, "gstr_3b", {
        "gstin": "27AAACK1234F1Z0", "legal_name": "Kestrel Tools Private Limited", "filing_date": f"{filed}-20",
        "tax_period": f"{MONTH_NAMES[int(ym[5:]) - 1]} {ym[:4]}",
        "outward_supplies": [{"description": TABLE_3_1[k], "taxable_value": v} for k, v in printed.items()],
    }, page=page, pending={"outward_supplies[0].taxable_value"} if pending else None)


def _bank(root: Path, case_id: str, transactions: list[dict], *, last4: str = "1234",
          bank_name: str = "Lotuscrest Bank", start: str = "2025-04-01", end: str = "2026-03-31", page: int = 4) -> str:
    return add_doc(root, case_id, "bank_statement", {
        "account_holder_name": "Kestrel Tools Pvt Ltd", "account_number": f"90100000{last4}", "bank_name": bank_name,
        "statement_period_start": start, "statement_period_end": end, "transactions": transactions,
    }, page=page)


def _receipts(month_list: list[str], amount: int, *, day: str = "15",
              description: str = "NEFT CR CUSTOMER RECEIPT") -> list[dict]:
    return [{"date": f"{ym}-{day}", "description": description, "credit": amount} for ym in month_list]


def _harbourline(root: Path, case_id: str, month_list: list[str], amount: int, **period) -> str:
    """A second account, with its own statement on its own page."""
    return _bank(root, case_id, _receipts(month_list, amount, day="20", description="RTGS CR CUSTOMER RECEIPT"),
                 last4="5678", bank_name="Harbourline Bank", page=6, **period)


# --- The board ---


def _board(client: TestClient, headers: dict, root: Path, case_id: str) -> dict[str, list[dict]]:
    """Run the checks and read the board: each rule's findings, with their cards."""
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()
    response = client.get(f"/api/cases/{case_id}/cross-verification", headers=headers)
    assert response.status_code == 200, response.text
    found: dict[str, list[dict]] = {}
    for item in response.json()["items"]:
        found.setdefault(item["finding"]["rule_id"], []).append(item["finding"])
    _gaps_agree(found)
    _lines_agree(found)
    return found


def _lines_agree(found: dict[str, list[dict]]) -> None:
    """On every turnover check the rule compared: one key-figure line, its figures the card's own
    values, the smaller one marked exactly when the rule failed, and the gap as the card's leg gives it."""
    for rule in TURNOVER:
        for f in found.get(rule, []):
            if f["outcome"] not in ("pass", "fail"):
                continue
            [line] = f["highlights"]
            assert [x["value"] for x in line["facts"]] == [c["value"] for c in f["columns"]], rule
            marked = [x["value"] for x in line["facts"] if x["differs"]]
            assert marked == ([min(c["value"] for c in f["columns"])] if f["outcome"] == "fail" else []), rule
            assert line["note"].startswith(f"{f['gaps'][0]['pct']:.1f}% apart · "), rule


def _lines(f: dict) -> list[tuple]:
    """The finding's key-figure lines for the overview card: label, facts (label, value, differs), note.
    Each names its finding, rule and outcome, and every figure is in rupees."""
    for h in f["highlights"]:
        assert (h["finding_id"], h["rule_id"], h["outcome"]) == (f["id"], f["rule_id"], f["outcome"])
        assert all(x["unit"] == "inr" for x in h["facts"])
    return [(h["label"], [(x["label"], x["value"], x["differs"]) for x in h["facts"]], h["note"]) for h in f["highlights"]]


def _gaps_agree(found: dict[str, list[dict]]) -> None:
    """On every number card: gaps only where the rule compared the figures, a breached leg exactly when
    it failed, measured against the rule's own tolerance, and an amount wherever there is a gap."""
    for rule in RULES:
        for f in found.get(rule, []):
            compared = f["outcome"] in ("pass", "fail") and rule != "TX-01"  # TX-01 compares years, not amounts
            assert bool(f["gaps"]) == compared, (rule, f["outcome"], f["gaps"])
            if not compared:
                assert f["amount"] is None and f["gap_tolerance"] is None, rule
                continue
            assert any(g["breached"] for g in f["gaps"]) == (f["outcome"] == "fail"), (rule, f["gaps"])
            assert f["gap_tolerance"] == f["tolerance"], rule
            # FS-02 ranks by the excess over the audited balance, and a balance below it has none.
            assert f["amount"] is not None or f["gaps"][0]["label"].startswith("Below"), rule


def _card(found: dict[str, list[dict]], rule: str, scope: str | None = None) -> dict:
    [f] = [f for f in found[rule] if scope is None or f["scope"] == scope]
    return f


def _page(document_id: str, page: int) -> dict:
    return {"document_id": document_id, "page": page, "bbox": None}


def _rows(column: dict, kind: str = "row") -> list[dict]:
    return [r for r in column["rows"] if r["kind"] == kind]


def _reconciles(column: dict) -> None:
    """A bank column adds up: the total row is the credits and excluded credits of the rows above it,
    the exclusions listed are the excluded credits, and the headline is the credits less them."""
    rows, removed = _rows(column), _rows(column, "excluded")
    gross, excluded = sum(r["cells"][2] for r in rows), sum(r["cells"][3] for r in rows)
    [total] = _rows(column, "total")
    assert total["cells"][2:] == pytest.approx([gross, excluded])
    assert sum(r["cells"][3] for r in removed) == pytest.approx(excluded)
    assert column["value"] == pytest.approx(gross - excluded)
    assert all(r["evidence"] for r in rows + removed)


# --- Turnover ---


def test_gst_against_bank_shows_each_return_and_each_credit_with_its_exclusions(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    returns = {ym: _gstr(root, case_id, ym, 4_000_000) for ym in FY26}
    lotus = _bank(root, case_id, _receipts(FY26, 2_000_000) + [
        {"date": "2025-06-10", "description": DISBURSAL, "credit": 5_000_000},
        {"date": "2025-07-09", "description": "IMPS TRF FROM A/C XXXX5678 KESTREL TOOLS", "credit": 300_000},
        {"date": "2025-08-07", "description": "REVERSAL OF CHG", "credit": 1_500},
    ])
    harbour = _harbourline(root, case_id, FY26, 1_200_000)
    found = _board(client, analyst, root, case_id)

    f = _card(found, "TO-02", "FY 2025-26")
    assert f["outcome"] == "fail"
    gst, credits = f["columns"]
    # GST: every return of the year, with its filing date and page, adding up to the figure compared.
    assert (gst["label"], gst["provenance"], gst["unit"], gst["differs"]) == (
        "GST outward supplies (GSTR-3B)", ["borrower_supplied"], "inr", True)
    assert gst["value"] == f["sides"][0]["value"] == 48_000_000
    assert gst["coverage"] == "Apr 2025 to Mar 2026 · 12 of 12 returns filed"
    assert gst["row_columns"] == GST_HEADINGS
    assert [r["cells"] for r in _rows(gst)][:2] == [["Apr 2025", "2025-05-20", 4_000_000],
                                                    ["May 2025", "2025-06-20", 4_000_000]]
    assert [r["evidence"] for r in _rows(gst)] == [[_page(returns[ym], 2)] for ym in FY26]
    assert _rows(gst, "total") == [{"cells": ["Aggregate FY 2025-26", "", 48_000_000], "evidence": [], "kind": "total"}]
    assert gst["evidence"] == [_page(returns[ym], 2) for ym in FY26]
    # Bank: each account's credits month by month, their total, then every credit excluded.
    assert (credits["label"], credits["provenance"], credits["unit"], credits["differs"]) == (
        "Business credits in bank statements", ["borrower_supplied"], "inr", True)
    assert credits["value"] == f["sides"][1]["value"] == 38_400_000
    assert credits["coverage"] == f"Apr 2025 to Mar 2026 · 2 accounts: {LOTUSCREST}, {HARBOURLINE}"
    assert credits["row_columns"] == BANK_HEADINGS
    rows = _rows(credits)
    assert len(rows) == 24
    assert [r["cells"] for r in rows[:2]] == [["Apr 2025", LOTUSCREST, 2_000_000, 0],
                                              ["Apr 2025", HARBOURLINE, 1_200_000, 0]]
    assert [r["cells"] for r in rows if r["cells"][3]] == [["Jun 2025", LOTUSCREST, 7_000_000, 5_000_000],
                                                           ["Jul 2025", LOTUSCREST, 2_300_000, 300_000],
                                                           ["Aug 2025", LOTUSCREST, 2_001_500, 1_500]]
    statement_page = {LOTUSCREST: _page(lotus, 4), HARBOURLINE: _page(harbour, 6)}
    assert all(r["evidence"] == [statement_page[r["cells"][1]]] for r in rows)
    assert _rows(credits, "total")[0]["cells"] == ["Total FY 2025-26", "", 43_701_500, 5_301_500]
    excluded = _rows(credits, "excluded")
    assert [r["cells"] for r in excluded] == [
        ["10 Jun 2025", LOTUSCREST, f"Loan disbursal: {DISBURSAL}", 5_000_000],
        ["9 Jul 2025", LOTUSCREST,
         "Transfer between the borrower's own accounts: IMPS TRF FROM A/C XXXX5678 KESTREL TOOLS", 300_000],
        ["7 Aug 2025", LOTUSCREST, "Reversal or refund: REVERSAL OF CHG", 1_500],
    ]
    assert all(r["evidence"] == [_page(lotus, 4)] for r in excluded)
    assert credits["evidence"] == [_page(lotus, 4), _page(harbour, 6)]
    _reconciles(credits)
    # The gap: the rule's own variance, against its tolerance.
    assert f["gaps"] == [{**GST_AGAINST_BANK, "amount": 9_600_000, "pct": 20.0, "breached": True}]
    assert (f["gap_tolerance"], f["amount"], f["request"], f["mismatch"]) == ("1%", 9_600_000, None, None)
    # The overview line: the two figures, the smaller marked, and how far apart against the tolerance.
    assert _lines(f) == [("GST against bank credits · FY 2025-26", [("GST outward supplies", 48_000_000, False),
                                                                    ("Bank credits", 38_400_000, True)],
                          "20.0% apart · tolerance 1%")]

    # No audited statements: TO-01 and TO-03 show the one figure on file and ask for the other.
    for rule, label, name in (("TO-01", "GST outward supplies (GSTR-3B)", "Audited against GST"),
                              ("TO-03", "Business credits in bank statements", "Audited against bank credits")):
        f = _card(found, rule, "FY 2025-26")
        assert f["outcome"] == "incomplete" and [c["label"] for c in f["columns"]] == [label]
        assert f["request"] == "audited financial statements for FY 2025-26"
        # A year's figure alone is not set beside anything: the line says what would complete it.
        assert _lines(f) == [(f"{name} · FY 2025-26", [], "audited financial statements for FY 2025-26 needed")]
    # Nothing declared, and the months both cover are the year TO-02 compared: no line.
    for rule in ("TO-04", "TO-05"):
        f = _card(found, rule)
        assert (f["outcome"], f["columns"], f["request"], f["highlights"]) == ("not_applicable", [], None, [])


@pytest.mark.usefixtures("all_rules_enabled")
def test_missing_months_are_asked_for_and_months_a_figure_does_not_count_are_left_out(client, analyst,
                                                                                      published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    books = audited(root, case_id, "2026-03-31", scale=48_000_000 / 118_000_000, page=8)
    for ym in FY26[:6]:  # Apr to Sep 2025
        _gstr(root, case_id, ym, 4_000_000)
    lotus = _bank(root, case_id, _receipts(FY26, 2_500_000) + [
        {"date": "2025-05-07", "description": "REVERSAL OF CHG", "credit": 2_000},
        {"date": "2025-10-10", "description": DISBURSAL, "credit": 5_000_000},
    ])
    _harbourline(root, case_id, FY26[:5], 1_480_000, end="2025-08-31")  # its statement stops in August
    found = _board(client, analyst, root, case_id)

    to1 = _card(found, "TO-01", "FY 2025-26")
    assert to1["outcome"] == "incomplete" and to1["request"] == "GSTR-3B returns for Oct 2025 to Mar 2026"
    # Half a year of returns is not set beside a year's revenue: the line says what would complete it.
    assert _lines(to1) == [("Audited against GST · FY 2025-26", [], "GSTR-3B returns for Oct 2025 to Mar 2026 needed")]
    revenue, gst = to1["columns"]
    assert (revenue["label"], revenue["provenance"], revenue["value"], revenue["coverage"]) == (
        "Audited financial statements", ["borrower_supplied"], 48_000_000, "Year ended 31 Mar 2026 · audited")
    assert revenue["row_columns"] == ["Line", "Year", "Amount"]
    assert revenue["rows"] == [{"cells": ["Revenue from operations", "FY 2025-26", 48_000_000],
                                "evidence": [_page(books, 8)], "kind": "row"}]
    assert gst["coverage"] == "Apr 2025 to Sep 2025 · 6 of 12 returns filed; Oct 2025 to Mar 2026 missing"
    assert len(_rows(gst)) == 6 and _rows(gst, "total")[0]["cells"] == ["Aggregate FY 2025-26", "", 24_000_000]

    to2 = _card(found, "TO-02", "FY 2025-26")
    assert to2["outcome"] == "incomplete"
    assert to2["request"] == ("GSTR-3B returns for Oct 2025 to Mar 2026 and bank statements for every account "
                              "covering Sep 2025 to Mar 2026")
    credits = to2["columns"][1]
    # The bank figure counts only the months every account's statements cover: April to August.
    assert credits["value"] == to2["sides"][1]["value"] == 19_900_000
    assert credits["coverage"] == f"Apr 2025 to Aug 2025 · 2 accounts: {LOTUSCREST}, {HARBOURLINE}"
    assert [r["cells"][:2] for r in _rows(credits)] == [[m, account] for m in ("Apr 2025", "May 2025", "Jun 2025",
                                                                               "Jul 2025", "Aug 2025")
                                                        for account in (LOTUSCREST, HARBOURLINE)]
    # The October disbursal falls in a month the figure does not count, so it is not listed.
    assert _rows(credits, "excluded") == [
        {"cells": ["7 May 2025", LOTUSCREST, "Reversal or refund: REVERSAL OF CHG", 2_000], "evidence": [_page(lotus, 4)],
         "kind": "excluded"}]
    _reconciles(credits)
    to3 = _card(found, "TO-03", "FY 2025-26")
    assert to3["request"] == "bank statements for every account covering Sep 2025 to Mar 2026"

    # TO-05 compares the five months both cover.
    to5 = _card(found, "TO-05")
    assert to5["outcome"] == "pass" and to5["scope"] == "Apr 2025 to Aug 2025"
    gst, credits = to5["columns"]
    assert (gst["coverage"], gst["value"], gst["differs"]) == ("Apr 2025 to Aug 2025 · 5 returns", 20_000_000, False)
    assert len(_rows(gst)) == 5
    assert _rows(gst, "total")[0]["cells"] == ["Aggregate Apr 2025 to Aug 2025", "", 20_000_000]
    assert (credits["value"], credits["differs"]) == (19_900_000, False)
    assert _rows(credits, "total")[0]["cells"][0] == "Total Apr 2025 to Aug 2025"
    _reconciles(credits)
    assert to5["gaps"] == [{**GST_AGAINST_BANK, "amount": 100_000, "pct": 0.5, "breached": False}]
    assert (to5["amount"], to5["gap_tolerance"], to5["request"]) == (100_000, "1%", None)
    # Over the months both cover: the window names the line; within the tolerance, nothing is marked.
    assert _lines(to5) == [("GST against bank credits · Apr 2025 to Aug 2025",
                            [("GST outward supplies", 20_000_000, False), ("Bank credits", 19_900_000, False)],
                            "0.5% apart · within 1%")]

    # One audited year, and no balance on its year end: the statement checks keep their default card.
    for rule in ("FS-01", "FS-02"):
        assert (_card(found, rule)["outcome"], _card(found, rule)["columns"]) == ("not_applicable", []), rule
    # No income tax return: TX-01 shows the audited year and asks for the returns.
    tx1 = _card(found, "TX-01")
    assert tx1["outcome"] == "incomplete" and tx1["request"] == "the income tax return"
    assert [c["label"] for c in tx1["columns"]] == ["Audited statements"]
    assert tx1["columns"][0]["rows"] == [{"cells": ["FY 2025-26", "Audited"], "evidence": [_page(books, 8)],
                                          "kind": "row"}]


def test_audited_turnover_against_bank_credits_and_over_the_months_both_cover(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    books = audited(root, case_id, "2026-03-31", scale=48_000_000 / 118_000_000, page=8)
    for ym in FY26[4:]:  # Aug 2025 to Mar 2026
        _gstr(root, case_id, ym, 4_000_000)
    disbursal = {"date": "2025-09-10", "description": DISBURSAL, "credit": 5_000_000}
    _bank(root, case_id, _receipts(FY26, 3_000_000) + [disbursal])
    found = _board(client, analyst, root, case_id)

    to3 = _card(found, "TO-03", "FY 2025-26")
    assert to3["outcome"] == "fail"
    revenue, credits = to3["columns"]
    assert revenue["differs"] and credits["differs"] and revenue["evidence"] == [_page(books, 8)]
    assert (credits["value"], credits["coverage"]) == (36_000_000, f"Apr 2025 to Mar 2026 · 1 account: {LOTUSCREST}")
    assert [r["cells"] for r in _rows(credits, "excluded")] == [
        ["10 Sep 2025", LOTUSCREST, f"Loan disbursal: {DISBURSAL}", 5_000_000]]
    _reconciles(credits)
    assert to3["gaps"] == [{"label": "Gap against bank credits", "amount": 12_000_000, "pct": 25.0, "base": "audited",
                            "legs": "audited against bank credits", "breached": True}]
    assert (to3["amount"], to3["gap_tolerance"]) == (12_000_000, "1%")
    assert _lines(to3) == [("Audited against bank credits · FY 2025-26",
                            [("Audited", 48_000_000, False), ("Bank credits", 36_000_000, True)],
                            "25.0% apart · tolerance 1%")]
    for rule in ("TO-01", "TO-02"):
        assert _card(found, rule, "FY 2025-26")["request"] == "GSTR-3B returns for Apr 2025 to Jul 2025"

    to5 = _card(found, "TO-05")
    assert to5["outcome"] == "fail" and to5["scope"] == "Aug 2025 to Mar 2026"
    gst, credits = to5["columns"]
    assert (gst["value"], gst["coverage"], gst["differs"]) == (32_000_000, "Aug 2025 to Mar 2026 · 8 returns", True)
    assert (credits["value"], credits["differs"]) == (24_000_000, True)
    assert [r["cells"][0] for r in _rows(credits)] == ["Aug 2025", "Sep 2025", "Oct 2025", "Nov 2025", "Dec 2025",
                                                       "Jan 2026", "Feb 2026", "Mar 2026"]
    assert [r["cells"][2:] for r in _rows(credits) if r["cells"][0] == "Sep 2025"] == [[8_000_000, 5_000_000]]
    _reconciles(credits)
    assert to5["gaps"] == [{**GST_AGAINST_BANK, "amount": 8_000_000, "pct": 25.0, "breached": True}]
    assert to5["amount"] == 8_000_000
    assert _lines(to5) == [("GST against bank credits · Aug 2025 to Mar 2026",
                            [("GST outward supplies", 32_000_000, False), ("Bank credits", 24_000_000, True)],
                            "25.0% apart · tolerance 1%")]


def test_declared_turnover_is_held_against_the_audited_figure_or_a_full_year_of_returns(client, analyst,
                                                                                         published_data_root):
    root = published_data_root
    message = "Kestrel Tools Pvt Ltd: turnover INR 7 crore in FY 2025-26."
    start = message.index("INR 7 crore")
    case_id = _case(client, analyst, root, message_text=message, header={
        "declared_turnover_inr": {"value": "70000000", "source": f"message:{start}-{start + 11}"}})
    books = audited(root, case_id, "2026-03-31", scale=48_000_000 / 118_000_000, page=3)
    f = _card(_board(client, analyst, root, case_id), "TO-04", "FY 2025-26")
    assert f["outcome"] == "fail"
    declared, revenue = f["columns"]
    assert (declared["label"], declared["provenance"], declared["unit"], declared["value"], declared["differs"]) == (
        "Turnover declared in the sourcing message", ["declared"], "inr", 70_000_000, True)
    assert declared["coverage"] == "Declared for FY 2025-26"
    # The sourcing message is the declaration's page.
    assert declared["evidence"] == f["sides"][0]["evidence"] and declared["evidence"][0]["page"] == 1
    assert declared["rows"] == [{"cells": ["Declared turnover", "FY 2025-26", 70_000_000],
                                 "evidence": declared["evidence"], "kind": "row"}]
    assert revenue["rows"][0]["cells"] == ["Revenue from operations", "FY 2025-26", 48_000_000]
    assert revenue["evidence"] == [_page(books, 3)]
    assert f["gaps"] == [{"label": "Gap against audited", "amount": 22_000_000, "pct": 31.4, "base": "declared",
                          "legs": "declared against audited", "breached": True}]
    assert (f["gap_tolerance"], f["amount"]) == ("2%", 22_000_000)
    assert _lines(f) == [("Declared against audited · FY 2025-26", [("Declared", 70_000_000, False),
                                                                     ("Audited", 48_000_000, True)],
                          "31.4% apart · tolerance 2%")]

    # Without audited statements, a full year of returns stands in, as the rule takes it.
    other = _case(client, analyst, root, borrower="Heronbay Polymers Pvt Ltd", header={
        "declared_turnover_inr": {"value": "48500000", "source": "person"}})
    for ym in FY26:
        _gstr(root, other, ym, 4_000_000)
    f = _card(_board(client, analyst, root, other), "TO-04", "FY 2025-26")
    assert f["outcome"] == "pass"
    declared, gst = f["columns"]
    assert (gst["label"], gst["value"]) == ("GST outward supplies (GSTR-3B)", 48_000_000)
    # Confirmed by a person: no page to trace to.
    assert declared["evidence"] == [] and declared["rows"][0]["evidence"] == []
    assert f["gaps"] == [{"label": "Gap against GST outward supplies", "amount": 500_000, "pct": 1.0,
                          "base": "declared", "legs": "declared against GST outward supplies", "breached": False}]
    assert f["amount"] == 500_000
    # The line names the figure that stood in.
    assert _lines(f) == [("Declared against GST · FY 2025-26", [("Declared", 48_500_000, False),
                                                                ("GST outward supplies", 48_000_000, False)],
                          "1.0% apart · within 2%")]


def test_a_figure_waiting_for_review_asks_the_customer_for_nothing(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    for ym in FY26:
        _gstr(root, case_id, ym, 4_000_000, pending=ym == "2025-04")
    _bank(root, case_id, _receipts(FY26, 3_800_000))
    f = _card(_board(client, analyst, root, case_id), "TO-02", "FY 2025-26")
    assert f["outcome"] == "incomplete" and f["explanation"].startswith("Waiting for review of GST outward supplies")
    gst, credits = f["columns"]
    assert gst["awaiting_review"] and not credits["awaiting_review"]
    assert (gst["value"], credits["value"]) == (48_000_000, 45_600_000)
    # The review completes the check: there is nothing to put on the query list.
    assert (f["request"], f["gaps"], f["amount"]) == (None, [], None)
    response = client.post(f"/api/cases/{case_id}/cross-verification/findings/{f['id']}/query", headers=analyst)
    assert response.status_code == 409, response.text
    assert _lines(f) == [("GST against bank credits · FY 2025-26", [], "waiting for review")]

    # Over the months both cover, likewise.
    other = _case(client, analyst, root, borrower="Heronbay Polymers Pvt Ltd")
    for ym in FY26[4:]:  # Aug 2025 to Mar 2026
        _gstr(root, other, ym, 4_000_000, pending=ym == "2025-09")
    _bank(root, other, _receipts(FY26, 3_000_000))
    found = _board(client, analyst, root, other)
    f = _card(found, "TO-05")
    assert (f["outcome"], f["scope"]) == ("incomplete", "Aug 2025 to Mar 2026")
    assert [c["awaiting_review"] for c in f["columns"]] == [True, False]
    assert (f["request"], f["gaps"], f["amount"]) == (None, [], None)
    assert _lines(f) == [("GST against bank credits · Aug 2025 to Mar 2026", [], "waiting for review")]
    # Short of months as well as waiting: the review comes first, so nothing is asked for yet.
    to2 = _card(found, "TO-02", "FY 2025-26")
    assert to2["outcome"] == "incomplete" and "covers 8 of 12 months" in to2["explanation"]
    assert to2["columns"][0]["awaiting_review"] and to2["request"] is None


@pytest.mark.usefixtures("all_rules_enabled")
def test_statement_checks_waiting_for_review_ask_the_customer_for_nothing(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    cash = f"balance_sheet[{row_index('balance_sheet', '(c) Cash and bank balances')}].current_period"
    audited(root, case_id, "2026-03-31", pending={cash})
    audited(root, case_id, "2025-03-31", page=3)
    add_doc(root, case_id, "income_tax_return", {
        "pan": "AAACK1234F", "assessment_year": "2025-26",
        "income_computation": [{"particulars": "Profit as per profit and loss account", "amount": 6_000_000}],
    }, page=7, pending={"income_computation[0].amount"})
    _bank(root, case_id, [{"date": "2026-03-20", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 1_000_000,
                           "balance": 9_500_000}], start="2025-09-01", end="2026-08-31")
    found = _board(client, analyst, root, case_id)
    for rule, scope in (("TX-02", "FY 2024-25"), ("FS-02", "FY 2025-26")):
        f = _card(found, rule, scope)
        assert f["outcome"] == "incomplete" and f["explanation"].startswith("Waiting for review of"), rule
        # The return's profit, the audited cash balance: the second column waits.
        assert [c["awaiting_review"] for c in f["columns"]] == [False, True], rule
        assert (f["request"], f["gaps"], f["amount"], f["gap_tolerance"]) == (None, [], None, None), rule


def test_too_few_months_in_common_ask_for_returns_and_statements_for_the_same_months(client, analyst,
                                                                                     published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root, header={"declared_turnover_inr": {"value": "50000000", "source": "person"}})
    for ym in FY26[:6]:
        _gstr(root, case_id, ym, 4_000_000)
    _bank(root, case_id, _receipts(["2025-09"], 4_000_000), start="2025-09-01", end="2026-08-31")
    found = _board(client, analyst, root, case_id)
    f = _card(found, "TO-05")
    assert f["outcome"] == "incomplete" and "share 1 month(s)" in f["explanation"]
    assert f["request"] == "GSTR-3B returns and bank statements covering the same months (at least 3)"
    assert _lines(f) == [("GST against bank credits · months both cover", [],
                          "GSTR-3B returns and bank statements covering the same months (at least 3) needed")]
    # What each source covers on its own.
    gst, credits = f["columns"]
    assert (gst["coverage"], gst["value"], gst["differs"]) == ("Apr 2025 to Sep 2025 · 6 returns", 24_000_000, False)
    assert (credits["coverage"], credits["differs"]) == (f"Sep 2025 to Aug 2026 · 1 account: {LOTUSCREST}", False)
    assert _rows(credits, "total")[0]["cells"] == ["Total Sep 2025 to Aug 2026", "", 4_000_000, 0]
    _reconciles(credits)

    # The declared turnover has neither audited statements nor a full year of returns to be held against.
    to4 = _card(found, "TO-04", "FY 2025-26")
    assert to4["outcome"] == "incomplete" and [c["label"] for c in to4["columns"]] == [
        "Turnover declared in the sourcing message"]
    assert to4["request"] == "audited financial statements for FY 2025-26"
    assert _lines(to4) == [("Declared against audited · FY 2025-26", [], "audited financial statements for FY 2025-26 needed")]


def test_a_year_not_yet_ended_asks_for_nothing_and_its_months_to_come_are_not_missing(client, analyst,
                                                                                      published_data_root):
    """The appraisal date is 29 Sep 2026, in FY 2026-27: no return, statement or audit the customer
    could send now completes a check of that year (as on BBG-2026-000006, TO-02 FY 2026-27, and
    BBG-2026-000001, TO-03 FY 2026-27), so nothing is asked for and nothing goes on the query list.
    A year that has ended still asks for what it lacks."""
    root = published_data_root
    case_id = _case(client, analyst, root)
    for ym in months((2025, 6), 14):  # Jun 2025 to Jul 2026
        _gstr(root, case_id, ym, 4_000_000)
    _bank(root, case_id, _receipts(months((2025, 4), 17), 3_900_000), end="2026-08-31")  # Apr 2025 to Aug 2026
    found = _board(client, analyst, root, case_id)

    # FY 2025-26 ended on 31 Mar 2026: its missing returns are asked for, as before.
    ended = _card(found, "TO-02", "FY 2025-26")
    assert ended["outcome"] == "incomplete" and ended["request"] == "GSTR-3B returns for Apr 2025 to May 2025"
    assert ended["columns"][0]["coverage"] == ("Jun 2025 to Mar 2026 · 10 of 12 returns filed; "
                                               "Apr 2025 to May 2025 missing")
    assert _lines(ended) == [("GST against bank credits · FY 2025-26", [], "GSTR-3B returns for Apr 2025 to May 2025 needed")]

    # FY 2026-27 runs to 31 Mar 2027: nothing is asked for, though the explanation names what it lacks.
    running = _card(found, "TO-02", "FY 2026-27")
    assert running["outcome"] == "incomplete" and running["request"] is None
    assert "GST outward supplies covers 4 of 12 months" in running["explanation"]
    # Missing are the months that ended before the appraisal date: August, not September onwards.
    assert running["columns"][0]["coverage"] == "Apr 2026 to Jul 2026 · 4 of 12 returns filed; Aug 2026 missing"
    assert _lines(running) == [("GST against bank credits · FY 2026-27", [], "the year ends on 31 Mar 2027")]
    response = client.post(f"/api/cases/{case_id}/cross-verification/findings/{running['id']}/query", headers=analyst)
    assert response.status_code == 409, response.text

    # No audited statements: TO-01 and TO-03 hold the latest year, whose statements cannot exist yet.
    for rule in ("TO-01", "TO-03"):
        f = _card(found, rule, "FY 2026-27")
        assert f["outcome"] == "incomplete" and f["explanation"] == "Audited turnover for FY 2026-27 is not on file."
        assert f["request"] is None, rule
        assert _lines(f)[0][2] == "the year ends on 31 Mar 2027", rule


def test_a_statement_without_credits_still_names_its_account_and_page(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    for ym in FY26:
        _gstr(root, case_id, ym, 4_000_000)
    statement = _bank(root, case_id, [{"date": "2025-05-02", "description": "NEFT DR SUPPLIER PAYMENT",
                                       "debit": 500_000}])
    f = _card(_board(client, analyst, root, case_id), "TO-02", "FY 2025-26")
    assert f["outcome"] == "fail"
    credits = f["columns"][1]
    assert (credits["value"], credits["coverage"]) == (0, f"Apr 2025 to Mar 2026 · 1 account: {LOTUSCREST}")
    assert credits["rows"] == [{"cells": ["Total FY 2025-26", "", 0, 0], "evidence": [], "kind": "total"}]
    assert credits["evidence"] == [_page(statement, 4)]
    assert f["gaps"] == [{**GST_AGAINST_BANK, "amount": 48_000_000, "pct": 100.0, "breached": True}]


def test_the_gst_rows_name_the_rows_of_table_3_1_the_figure_sums(client, analyst, published_data_root):
    root = published_data_root
    # The rows of table 3.1 the configuration sums into a month's figure, found as the facts find them
    # (engine/statements.py): the heading names exactly those.
    pattern = re.compile(reader.load_statements(root).gst_outward.row, re.IGNORECASE)
    summed = [k for k, label in TABLE_3_1.items() if pattern.search(label)]
    assert summed == ["a", "b", "c"]
    assert GST_HEADINGS[2] == "3.1" + "+".join(f"({k})" for k in summed) + " outward supplies"

    # A return with zero-rated, exempt, reverse-charge and non-GST rows: its month shows (a) + (b) + (c).
    case_id = _case(client, analyst, root)
    april = _gstr(root, case_id, FY26[0], 0, rows={"a": 3_000_000, "b": 500_000, "c": 200_000, "d": 100_000,
                                                   "e": 50_000})
    for ym in FY26[1:]:
        _gstr(root, case_id, ym, 4_000_000)
    _bank(root, case_id, _receipts(FY26, 3_900_000))
    f = _card(_board(client, analyst, root, case_id), "TO-02", "FY 2025-26")
    gst = f["columns"][0]
    assert gst["row_columns"] == GST_HEADINGS
    assert _rows(gst)[0] == {"cells": ["Apr 2025", "2025-05-20", 3_700_000], "evidence": [_page(april, 2)], "kind": "row"}
    assert _rows(gst, "total")[0]["cells"] == ["Aggregate FY 2025-26", "", 47_700_000]
    assert gst["value"] == f["sides"][0]["value"] == 47_700_000


@pytest.mark.usefixtures("all_rules_enabled")
def test_checks_without_their_documents_ask_for_them(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "company_pan", {"pan": "AAACK1234F"})
    found = _board(client, analyst, root, case_id)
    # Each document named as every card names it; FS-01 needs two years of the statements.
    for rule, request in {
        "TO-01": "the audited financial statements and the GSTR-3B",
        "TO-02": "the GSTR-3B and the bank statement",
        "TO-03": "the audited financial statements and the bank statement",
        "TO-05": "the GSTR-3B and the bank statement",
        "TX-01": "the audited financial statements and the income tax return",
        "TX-02": "the audited financial statements and the income tax return",
        "FS-01": "the audited financial statements for two consecutive years",
        "FS-02": "the audited financial statements and the bank statement",
    }.items():
        f = _card(found, rule)
        assert (f["outcome"], f["request"], f["columns"]) == ("incomplete", request, []), rule
    assert (_card(found, "TO-04")["outcome"], _card(found, "TO-04")["request"]) == ("not_applicable", None)
    # Each turnover check's line says what would complete it.
    for rule, label in {"TO-01": "Audited against GST", "TO-02": "GST against bank credits",
                        "TO-03": "Audited against bank credits",
                        "TO-05": "GST against bank credits · months both cover"}.items():
        f = _card(found, rule)
        assert _lines(f) == [(label, [], f"{f['request']} needed")], rule


# --- Tax (switched off in configuration) ---


@pytest.mark.usefixtures("all_rules_enabled")
def test_an_audited_year_without_its_return_is_named(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    years = [("FY 2025-26", "2026-03-31", 5), ("FY 2024-25", "2025-03-31", 3), ("FY 2023-24", "2024-03-31", 1)]
    docs = {fy: audited(root, case_id, end, page=page) for fy, end, page in years}
    itr = add_doc(root, case_id, "income_tax_return", {"pan": "AAACK1234F", "assessment_year": "2025-26"}, page=7)
    f = _card(_board(client, analyst, root, case_id), "TX-01")
    assert f["outcome"] == "fail"
    assert f["mismatch"] == "No income tax return for FY 2023-24, though due."
    books, returns = f["columns"]
    assert (books["label"], books["value"], books["coverage"], books["differs"]) == (
        "Audited statements", "FY 2025-26, FY 2024-25, FY 2023-24", "3 years audited", False)
    assert books["row_columns"] == ["Year", "Statements"]
    assert books["rows"] == [{"cells": [fy, "Audited"], "evidence": [_page(docs[fy], page)], "kind": "row"}
                             for fy, _, page in years]
    assert (returns["label"], returns["provenance"], returns["value"], returns["coverage"], returns["differs"]) == (
        "Income tax returns", ["borrower_supplied"], "AY 2025-26", "1 return on file", True)
    assert returns["rows"] == [{"cells": ["AY 2025-26", "FY 2024-25"], "evidence": [_page(itr, 7)], "kind": "row"}]
    assert returns["evidence"] == [_page(itr, 7)]
    assert (f["gaps"], f["amount"], f["request"]) == ([], None, None)


@pytest.mark.usefixtures("all_rules_enabled")
@pytest.mark.parametrize("filed,outcome,gap,pct", [(6_000_000, "fail", 1_500_000, 20.0),
                                                   (7_200_000, "pass", 300_000, 4.0)])
def test_book_profit_against_the_return(client, analyst, published_data_root, filed, outcome, gap, pct):
    root = published_data_root
    case_id = _case(client, analyst, root)
    books = audited(root, case_id, "2025-03-31", page=3)  # profit before tax 75 lakh
    itr = add_doc(root, case_id, "income_tax_return", {
        "pan": "AAACK1234F", "assessment_year": "2025-26",
        "income_computation": [{"particulars": "Profit as per profit and loss account", "amount": filed},
                               {"particulars": "Total income", "amount": 8_600_000}],
    }, page=7)
    f = _card(_board(client, analyst, root, case_id), "TX-02", "FY 2024-25")
    assert f["outcome"] == outcome
    book, ret = f["columns"]
    assert (book["label"], book["coverage"], book["value"]) == (
        "Audited financial statements", "Year ended 31 Mar 2025 · audited", 7_500_000)
    assert book["rows"] == [{"cells": ["Profit before tax", "FY 2024-25", 7_500_000], "evidence": [_page(books, 3)],
                             "kind": "row"}]
    assert (ret["label"], ret["coverage"], ret["value"]) == (
        "Income tax return", "AY 2025-26 · computation of income", filed)
    assert ret["rows"] == [{"cells": ["Profit as per the computation", "AY 2025-26", filed],
                            "evidence": [_page(itr, 7)], "kind": "row"}]
    assert book["differs"] == ret["differs"] == (outcome == "fail")
    assert f["gaps"] == [{"label": "Gap against tax return", "amount": gap, "pct": pct, "base": "audited",
                          "legs": "audited against tax return", "breached": outcome == "fail"}]
    assert (f["amount"], f["gap_tolerance"]) == (gap, "10%")


# --- Statements (switched off in configuration) ---


@pytest.mark.usefixtures("all_rules_enabled")
@pytest.mark.parametrize("scale,outcome", [(0.70, "fail"), (0.85, "pass")])
def test_previous_year_figures_against_that_years_statements(client, analyst, published_data_root, scale, outcome):
    root = published_data_root
    case_id = _case(client, analyst, root)
    later = audited(root, case_id, "2026-03-31")  # its previous-year column is 0.85 of the printed figures
    earlier = audited(root, case_id, "2025-03-31", scale=scale, page=3)
    f = _card(_board(client, analyst, root, case_id), "FS-01", "FY 2025-26")
    assert f["outcome"] == outcome
    restated, filed = f["columns"]
    assert (restated["label"], filed["label"]) == ("FY 2024-25 column of the FY 2025-26 statements",
                                                   "FY 2024-25 audited statements")
    lines = {"Revenue from operations": 118_000_000, "Profit after tax": 6_400_000, "Net worth": 42_000_000,
             "Total borrowings": 27_000_000}
    assert [r["cells"] for r in restated["rows"]] == [[line, round(v * 0.85)] for line, v in lines.items()]
    assert [r["cells"] for r in filed["rows"]] == [[line, round(v * scale)] for line, v in lines.items()]
    assert all(r["evidence"] == [_page(later, 1)] for r in restated["rows"])
    assert all(r["evidence"] == [_page(earlier, 3)] for r in filed["rows"])
    # The headline is the line the rule's sides show.
    assert (restated["value"], filed["value"]) == (f["sides"][0]["value"], f["sides"][1]["value"])
    assert restated["coverage"] == "Revenue from operations · 4 lines compared"
    assert restated["differs"] == filed["differs"] == (outcome == "fail")
    legs = f["gaps"]
    assert [g["label"] for g in legs] == [g["legs"] for g in legs] == list(lines)
    assert all(g["breached"] == (outcome == "fail") for g in legs)
    if outcome == "fail":
        assert {g["base"] for g in legs} == {"as restated"} and {g["pct"] for g in legs} == {17.6}
        assert f["amount"] == max(g["amount"] for g in legs) == 17_700_000
    else:
        assert {g["pct"] for g in legs} == {0.0} and f["amount"] == 0
    assert f["gap_tolerance"] == "1%"


@pytest.mark.usefixtures("all_rules_enabled")
def test_year_end_bank_balances_against_the_audited_balance(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    books = audited(root, case_id, "2026-03-31", page=3)  # cash and bank balances 60 lakh
    statement = _bank(root, case_id, [
        {"date": "2026-03-20", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 1_000_000, "balance": 9_500_000},
        {"date": "2026-04-10", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 1_000_000, "balance": 10_500_000},
    ], start="2025-09-01", end="2026-08-31")
    f = _card(_board(client, analyst, root, case_id), "FS-02", "FY 2025-26")
    assert f["outcome"] == "fail"
    balances, cash = f["columns"]
    assert (balances["label"], balances["value"], balances["coverage"], balances["differs"]) == (
        "Year-end bank balances", 9_500_000, "On 31 Mar 2026 · 1 account", True)
    assert balances["row_columns"] == ["Account", "Date", "Balance"]
    assert balances["rows"] == [{"cells": [LOTUSCREST, "31 Mar 2026", 9_500_000], "evidence": [_page(statement, 4)],
                                 "kind": "row"}]
    assert (cash["label"], cash["value"], cash["coverage"], cash["differs"]) == (
        "Audited cash and bank balance", 6_000_000, "Balance sheet as at 31 Mar 2026", False)
    assert cash["rows"] == [{"cells": ["Cash and bank balances", "FY 2025-26", 6_000_000],
                             "evidence": [_page(books, 3)], "kind": "row"}]
    assert f["gaps"] == [{"label": "Above the audited cash and bank balance", "amount": 3_500_000, "pct": 58.3,
                          "base": "audited", "legs": "bank balances against audited", "breached": True}]
    assert (f["amount"], f["gap_tolerance"]) == (3_500_000, "1%")

    # Below the audited balance: the check passes, with no excess to rank by.
    other = _case(client, analyst, root, borrower="Heronbay Polymers Pvt Ltd")
    audited(root, other, "2026-03-31")
    _bank(root, other, [{"date": "2026-03-20", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 1_000_000,
                         "balance": 5_000_000}], start="2025-09-01", end="2026-08-31")
    f = _card(_board(client, analyst, root, other), "FS-02", "FY 2025-26")
    assert f["outcome"] == "pass" and not f["columns"][0]["differs"]
    assert f["gaps"] == [{"label": "Below the audited cash and bank balance", "amount": 1_000_000, "pct": 16.7,
                          "base": "audited", "legs": "bank balances against audited", "breached": False}]
    assert f["amount"] is None


# --- The cards never decide ---


@pytest.mark.usefixtures("all_rules_enabled")
def test_the_cards_never_change_an_outcome(client, analyst, published_data_root, monkeypatch):
    """The checks decide the same with the cards built as without any card builder: every finding's
    outcome, explanation, sides, detail and missing documents (and its tolerance, query, severity)."""
    root = published_data_root
    case_id = _case(client, analyst, root, header={"declared_turnover_inr": {"value": "50000000", "source": "person"}})
    audited(root, case_id, "2026-03-31")
    audited(root, case_id, "2025-03-31", scale=0.70, page=3)
    add_doc(root, case_id, "income_tax_return", {
        "pan": "AAACK1234F", "assessment_year": "2025-26",
        "income_computation": [{"particulars": "Profit as per profit and loss account", "amount": 4_900_000}]}, page=7)
    span = months((2025, 4), 17)  # Apr 2025 to Aug 2026
    for ym in span:
        _gstr(root, case_id, ym, 10_000_000)
    _bank(root, case_id, _receipts(span, 9_000_000) + [
        {"date": "2025-06-10", "description": DISBURSAL, "credit": 5_000_000},
        {"date": "2026-03-25", "description": "REVERSAL OF CHG", "credit": 2_000, "balance": 5_500_000},
    ], end="2026-08-31")
    _harbourline(root, case_id, span, 800_000, end="2026-08-31")
    conn = db.connect(root)
    try:
        case = cases.get_case(conn, case_id)
        built = crosschecks.evaluate(root, case, facts.compute(conn, root, case))
        monkeypatch.setattr(xv_cards, "BUILDERS", {})
        bare = crosschecks.evaluate(root, case, facts.compute(conn, root, case))
    finally:
        conn.close()
    decided = {"rule_id", "scope", "outcome", "explanation", "sides", "detail", "missing", "tolerance", "query",
               "severity", "blocking"}
    assert [f.model_dump(include=decided) for f in built] == [f.model_dump(include=decided) for f in bare]
    # The case exercised the number cards on every kind of outcome they compare.
    mine = [f for f in built if f.rule_id in RULES]
    assert {f.outcome for f in mine} >= {"pass", "fail", "incomplete"}
    assert all(f.gaps for f in mine if f.outcome in ("pass", "fail") and f.rule_id != "TX-01")
    assert not any(f.gaps for f in bare)
