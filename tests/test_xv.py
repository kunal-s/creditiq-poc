"""The cross-verification board's server side (F-19; engine/xv.py): references that stay with a
finding across runs, the record of each run, the board's areas, order and counts, the reviewer's
decisions (accept, dismiss, escalate to the Credit Manager, each with a comment, on the board or in
the review queue), escalations kept with their discrepancies through runs that withdraw the review
item, requests put on the query list from checks that could not run (worded as the check asks now),
and the card kept with each finding.

What a card shows is the builders' (tests/test_xv_cards_*.py). Where the order depends on a card's
amount, these tests set the amount themselves, so they hold whatever the builders' cards say. The
board runs the rules switched on in configuration (tests/test_crosschecks_switch.py switches them
off and on). Every name is fictional."""

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import auth, cases, config, db, pipeline, review, xv, xv_cards
from engine.configstore import reader
from engine.contracts import Evidence, Finding, GapLeg, ReviewDecisionRequest, XvDecisionRequest
from engine.crosschecks import CARD_FIELDS
from tests.conftest import ANALYST, MANAGER, RM, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

FY26 = months((2025, 4), 12)
MONTH_NAMES = ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January",
               "February", "March"]
PERIODS = [f"{m} {2025 if i < 9 else 2026}" for i, m in enumerate(MONTH_NAMES)]  # FY 2025-26
CO = "Kestrel Tools Private Limited"
TIDEWATER = {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12_000_000,
             "outstanding": 7_500_000, "emi": 250_000}
LOTUSCREST = {"lender": "Lotuscrest Bank", "facility": "Cash credit", "sanctioned_amount": 20_000_000,
              "outstanding": 18_500_000}
DECLARED_TURNOVER = {"declared_turnover_inr": {"value": "60000000", "source": "person"}}
CIN = "U28990MH2015PTC123456"
# The discrepancies of `_discrepancies`, by credit impact (with the `amounts` fixture's cards): the
# order of their references.
RANKED = ["OB-01", "ID-01", "TO-02", "TO-01", "OB-03", "TO-04"]
# The same on the board: by area, in the areas' configured order, each area's by credit impact.
BY_AREA = {"identity": ["ID-01"], "turnover": ["TO-02", "TO-01", "TO-04"], "accounts": [],
           "obligations": ["OB-01", "OB-03"]}
TALLY = ("discrepancies", "open", "serious", "moderate", "mild", "blocking_open", "adjudicated", "incomplete", "passed",
         "not_applicable")
"""An area's counts, as its overview card shows them."""


# --- Helpers ---


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _rows(root: Path, sql: str, *args) -> list[sqlite3.Row]:
    conn = db.connect(root)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _set_value(root: Path, document_id: str, field: str, value: object) -> None:
    conn = db.connect(root)
    try:
        conn.execute("UPDATE field_values SET value = ? WHERE document_id = ? AND field = ?",
                     (json.dumps(value), document_id, field))
    finally:
        conn.close()


def _confirm_values(root: Path, document_id: str) -> None:
    """A person confirms the document's values that were waiting for review."""
    conn = db.connect(root)
    try:
        conn.execute("UPDATE field_values SET status = 'accepted' WHERE document_id = ?", (document_id,))
    finally:
        conn.close()


def _escalations(root: Path, case_id: str) -> list[tuple]:
    """The escalations kept with the case's discrepancies: rule, scope, by, at, comment, resolved by."""
    return [tuple(r) for r in _rows(root, """SELECT rule_id, scope, escalated_by, escalated_at, comment, resolved_by
                                             FROM finding_escalations WHERE case_id = ? ORDER BY rule_id""", case_id)]


def _as(email: str) -> dict:
    """The signed-in user, as the API hands it to the engine."""
    return auth.user_payload(config.find_user(email))


def _number(case_id: str) -> str:
    return case_id.rsplit("-", 1)[1]


def _board(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/cross-verification", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _item(board: dict, rule_id: str) -> dict:
    [item] = [i for i in board["items"] if i["finding"]["rule_id"] == rule_id]
    return item


def _tally(board: dict, area: str) -> dict:
    """An area's counts, as its findings on the board give them."""
    mine = [i for i in board["items"] if i["finding"]["area"] == area]
    failed = [i for i in mine if i["finding"]["outcome"] == "fail"]
    open_ = [i["finding"] for i in failed if not i["adjudicated"]]
    outcomes = [i["finding"]["outcome"] for i in mine]
    return {"discrepancies": len(failed), "open": len(open_),
            **{s: sum(1 for f in open_ if f["severity"] == s) for s in ("serious", "moderate", "mild")},
            "blocking_open": sum(1 for f in open_ if f["blocking"]), "adjudicated": len(failed) - len(open_),
            "incomplete": outcomes.count("incomplete"), "passed": outcomes.count("pass"),
            "not_applicable": outcomes.count("not_applicable")}


def _decide(client: TestClient, headers: dict, case_id: str, finding_id: str, decision: str,
            comment: str = "Checked against the documents on file"):
    return client.post(f"/api/cases/{case_id}/cross-verification/findings/{finding_id}/decision",
                       json={"decision": decision, "comment": comment}, headers=headers)


def _add_query(client: TestClient, headers: dict, case_id: str, finding_id: str):
    return client.post(f"/api/cases/{case_id}/cross-verification/findings/{finding_id}/query", headers=headers)


def _review_decide(client: TestClient, headers: dict, item_id: str, decision: str, reason: str | None = None):
    return client.post(f"/api/review/{item_id}/decision", json={"decision": decision, "reason": reason}, headers=headers)


def _audit(client: TestClient, headers: dict, case_id: str, action: str) -> list[dict]:
    response = client.get(f"/api/audit?case_id={case_id}&action={action}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["entries"]


def _meanwhile(monkeypatch: pytest.MonkeyPatch, act: Callable[[], None]) -> None:
    """The next decision on the board reads the board, then another reviewer's `act` lands before
    the decision is written."""
    read = xv._finding

    def finding(conn, root, case, finding_id):
        item = read(conn, root, case, finding_id)
        monkeypatch.setattr(xv, "_finding", read)
        act()
        return item

    monkeypatch.setattr(xv, "_finding", finding)


# --- Scenarios ---


def _case(client: TestClient, headers: dict, root: Path, **overrides) -> str:
    return make_case(client, headers, root, **{"borrower": "Kestrel Tools Pvt Ltd", **overrides})


def _pan_mismatch(root: Path, case_id: str, pan: str = "AAACK1234F", other: str = "AAACK9876Q",
                  company: str = "Kestrel Tools Pvt Ltd") -> str:
    """The company PAN and the income tax return give different PANs: ID-01 fails (serious,
    blocking), and the legal names agree (ID-03 passes). Returns the return's document id."""
    add_doc(root, case_id, "company_pan", {"pan": pan, "company_name": company})
    return add_doc(root, case_id, "income_tax_return", {"pan": other, "taxpayer_name": company})


def _incorporation(root: Path, case_id: str, memorandum_cin: str = CIN) -> str:
    """The certificate of incorporation and the memorandum, each with its CIN: ID-05 passes when they
    agree and fails (serious, blocking) when they differ. Returns the memorandum's document id."""
    add_doc(root, case_id, "certificate_of_incorporation", {"cin": CIN})
    return add_doc(root, case_id, "memorandum_articles_of_association", {"cin": memorandum_cin})


def _turnover(root: Path, case_id: str) -> None:
    """FY 2025-26: audited INR 3.86 cr, GST INR 4.80 cr, bank credits INR 3.84 cr (TO-01 and TO-02
    fail, TO-03 passes); the long-term borrowings in the books have no instalments in the bank (OB-03 fails)."""
    audited(root, case_id, "2026-03-31", scale=38_600_000 / 118_000_000)
    for period in PERIODS:
        gstr(root, case_id, period, 4_000_000)
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 3_200_000}
                         for ym in FY26])


def _facilities(root: Path, case_id: str) -> None:
    """The bureau reports a facility the declaration omits: OB-01 fails (serious, not blocking)."""
    add_doc(root, case_id, "existing_facilities_declaration", {
        "company_name": CO, "declaration_date": "2026-09-15", "facilities": [TIDEWATER], "bank_accounts": []})
    add_doc(root, case_id, "commercial_bureau_report", {
        "company_name": CO, "pan": "AAACK1234F", "report_date": "2026-09-20", "credit_rank": "4",
        "credit_facilities": [{**f, "overdue": 0, "status": "Standard"} for f in (TIDEWATER, LOTUSCREST)],
        "related_parties": []})


def _discrepancies(client: TestClient, headers: dict, root: Path) -> tuple[str, str]:
    """Six discrepancies at once: serious OB-01 (with an amount) and ID-01 (blocking); moderate
    TO-02 and TO-01 (with amounts) and OB-03; mild TO-04 (the declared turnover against the
    audited). Returns the case and the income tax return's document id."""
    case_id = _case(client, headers, root, header=DECLARED_TURNOVER)
    itr = _pan_mismatch(root, case_id)
    _turnover(root, case_id)
    _facilities(root, case_id)
    _refresh(root, case_id)
    return case_id, itr


@pytest.fixture()
def amounts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cards with only a known amount for TO-01, TO-02 and OB-01 (the other rules' columns come from
    their sides), so the order is the board's own: TO-02's gap is larger than TO-01's although
    TO-01 comes first in the configuration, and OB-01's amount puts it above ID-01."""
    from engine import xv_cards

    def amount(value: float):
        def build(ctx, rule, finding: Finding) -> None:
            if finding.outcome in ("pass", "fail"):
                finding.amount = value
        return build

    monkeypatch.setattr(xv_cards, "BUILDERS", {"turnover_audited_vs_gst": amount(1_000_000),
                                               "turnover_gst_vs_bank": amount(9_600_000),
                                               "facilities_reconcile": amount(500_000)})


# --- References and runs ---


def test_the_case_number_names_references_and_runs():
    assert xv.case_number("BBG-2026-000004") == "000004"
    assert xv.run_label("BBG-2026-000004", 7) == "XR-000004-007"


def test_rank_key_orders_by_severity_then_amount_then_configuration(published_data_root):
    rules = reader.load_crosschecks(published_data_root).rules

    def finding(rule_id: str, severity: str, amount: float | None = None, scope: str | None = None) -> Finding:
        return Finding(id=f"{rule_id} {scope}", case_id="C", rule_id=rule_id, title=rule_id, outcome="fail",
                       severity=severity, blocking=False, explanation="", sides=[], amount=amount, scope=scope)

    found = [finding("ID-07", "mild", 900_000_000), finding("TO-01", "moderate", None, "FY 2025-26"),
             finding("ID-03", "moderate"), finding("TO-01", "moderate", 1_000_000, "FY 2024-25"),
             finding("OB-01", "serious"), finding("TO-02", "moderate", 9_600_000, "FY 2025-26"),
             finding("TO-01", "moderate", None, "FY 2023-24"), finding("ID-01", "serious")]
    ranked = sorted(found, key=xv.rank_key(rules))
    # Severity first, however large a milder gap; then the larger amount; then those with no
    # amount in the configured order, a rule's years in order.
    assert [(f.rule_id, f.scope) for f in ranked] == [
        ("ID-01", None), ("OB-01", None), ("TO-02", "FY 2025-26"), ("TO-01", "FY 2024-25"), ("ID-03", None),
        ("TO-01", "FY 2023-24"), ("TO-01", "FY 2025-26"), ("ID-07", None)]


def test_references_are_given_in_ranked_order_at_the_first_failure_and_kept(client, published_data_root, amounts):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id, itr = _discrepancies(client, analyst, root)
    number = _number(case_id)
    board = _board(client, analyst, case_id)
    refs = {i["finding"]["rule_id"]: i["finding"]["ref"] for i in board["items"] if i["finding"]["outcome"] == "fail"}
    # Across the board, whatever the area.
    assert refs == {rule: f"XV-{number}-{n:02d}" for n, rule in enumerate(RANKED, start=1)}
    assert all(i["finding"]["ref"] is None for i in board["items"] if i["finding"]["outcome"] != "fail")

    # The PAN is corrected: ID-01 passes and keeps its reference, as every other finding keeps its own.
    _set_value(root, itr, "pan", "AAACK1234F")
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    assert _item(board, "ID-01")["finding"]["outcome"] == "pass" and _item(board, "ID-01")["rank"] is None
    assert {rule: _item(board, rule)["finding"]["ref"] for rule in RANKED} == refs

    # A new failure takes the next number, though it ranks above most of the others (first in its area).
    _incorporation(root, case_id, "U28990MH2015PTC123465")
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    cin = _item(board, "ID-05")
    assert cin["finding"]["outcome"] == "fail" and cin["rank"] == 1
    assert cin["finding"]["ref"] == f"XV-{number}-07"

    # Failing again, ID-01 has the reference it was first given.
    _set_value(root, itr, "pan", "AAACK9876Q")
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    assert _item(board, "ID-01")["finding"]["outcome"] == "fail"
    assert {i["finding"]["rule_id"]: i["finding"]["ref"] for i in board["items"] if i["rank"]} == {
        **refs, "ID-05": f"XV-{number}-07"}

    # Each case numbers its own.
    other = _case(client, analyst, root, borrower="Heronbay Polymers Pvt Ltd")
    _pan_mismatch(root, other, "AAACH5678Q", "AAACH9876R", "Heronbay Polymers Pvt Ltd")
    _refresh(root, other)
    assert _item(_board(client, analyst, other), "ID-01")["finding"]["ref"] == f"XV-{_number(other)}-01"
    assert _item(_board(client, analyst, case_id), "ID-05")["finding"]["ref"] == f"XV-{number}-07"


@pytest.mark.usefixtures("all_rules_enabled")
def test_each_run_of_the_checks_is_recorded(client, published_data_root):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    number = _number(case_id)
    # Every configured rule runs here, the board resolution's among them.
    configured = len(reader.load_crosschecks(root).enabled_rules)
    # Creating the case ran the checks once, with no document to compare.
    first = _board(client, analyst, case_id)["run"]
    assert first["id"] == f"XR-{number}-001" and first["rules"] == configured and first["sources"] == 0

    _pan_mismatch(root, case_id)
    add_doc(root, case_id, "board_resolution_borrowing", {"borrowing_limit": 100_000_000, "resolution_date": "2025-06-10"})
    _refresh(root, case_id)
    _refresh(root, case_id)
    run = _board(client, analyst, case_id)["run"]
    assert run["id"] == f"XR-{number}-003" and run["rules"] == configured and run["at"] >= first["at"]
    findings = client.get(f"/api/cases/{case_id}/findings", headers=analyst).json()
    assert {f["run_id"] for f in findings} == {run["id"]}
    # The sources are the document types compared: here the company PAN, the return, the resolution
    # and the sourcing message (the amount requested); not the appraisal date the resolution is held against.
    types = {t.id for t in reader.load_document_types(root).types}
    sides = {s for f in findings for side in f["sides"] for s in side["sources"]}
    assert sides & types == {"company_pan", "income_tax_return", "board_resolution_borrowing", "application_message"}
    assert "case.as_of" in sides
    compared = sides | {s for f in findings for c in f["columns"] for s in c["sources"]}
    assert run["sources"] == len(compared & types)


def test_a_run_counts_the_rules_switched_on(client, published_data_root):
    """Six of the 30 configured rules are switched off: a run counts the 24 that ran, and each of
    them gives its findings."""
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    checks = reader.load_crosschecks(root)
    assert (len(checks.rules), len(checks.enabled_rules)) == (30, 24)
    assert _board(client, analyst, case_id)["run"]["rules"] == 24
    findings = client.get(f"/api/cases/{case_id}/findings", headers=analyst).json()
    assert {f["rule_id"] for f in findings} == {r.id for r in checks.enabled_rules}


def test_a_run_counts_only_configured_document_types_as_its_sources(client, published_data_root, monkeypatch):
    """A source that is not a configured document type is not counted, even one a card names
    without a dot (the case's own record, as "case.as_of", always has one)."""
    def card(ctx, rule, finding: Finding) -> None:
        finding.columns = [xv_cards.column(ctx, "pan", "Company PAN", sources=["company_pan"], value="AAACK1234F"),
                           xv_cards.column(ctx, "register", "Register of companies", sources=["company_register"],
                                           value="AAACK1234F")]

    monkeypatch.setattr(xv_cards, "BUILDERS", {"entity_pan": card})
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    run = _board(client, analyst, case_id)["run"]
    findings = client.get(f"/api/cases/{case_id}/findings", headers=analyst).json()
    named = {s for f in findings for x in f["sides"] + f["columns"] for s in x["sources"]}
    types = {t.id for t in reader.load_document_types(root).types}
    assert "company_register" in named and "company_register" not in types
    assert run["sources"] == len(named & types) and {"company_pan", "income_tax_return"} <= named & types


# --- The board ---


def test_the_board_ranks_the_discrepancies_within_each_area_and_counts_them(client, published_data_root, amounts):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id, _ = _discrepancies(client, analyst, root)
    board = _board(client, analyst, case_id)
    items = board["items"]
    # By area, in the order the areas first appear in the configuration: identity, turnover, bank
    # accounts, existing obligations.
    assert [a["area"] for a in board["areas"]] == list(BY_AREA)
    shown = [i["finding"]["area"] for i in items]
    assert shown == sorted(shown, key=list(BY_AREA).index)
    order = {r.id: n for n, r in enumerate(reader.load_crosschecks(root).enabled_rules)}
    groups = ["incomplete", "pass", "not_applicable"]
    for area, ranked in BY_AREA.items():
        mine = [i for i in items if i["finding"]["area"] == area]
        # First the area's discrepancies by credit impact: severity, then the larger amount, then those
        # without one, in the configured order; each ranked within its area.
        failed, rest = mine[:len(ranked)], mine[len(ranked):]
        assert [i["finding"]["rule_id"] for i in failed] == ranked
        assert [i["rank"] for i in failed] == list(range(1, len(ranked) + 1))
        assert all(i["finding"]["outcome"] == "fail" and i["review_item_id"] and not i["adjudicated"] for i in failed)
        # Then the checks that could not run, those that passed and those that did not apply, each in
        # the configured order, with no rank.
        assert all(i["finding"]["outcome"] != "fail" and i["rank"] is None and i["review_item_id"] is None
                   for i in rest)
        keys = [(groups.index(i["finding"]["outcome"]), order[i["finding"]["rule_id"]], i["finding"]["scope"] or "")
                for i in rest]
        assert keys == sorted(keys), area
    assert {i["finding"]["outcome"] for i in items} == {"fail", *groups}
    # Every finding of the run is on the board, once.
    findings = client.get(f"/api/cases/{case_id}/findings", headers=analyst).json()
    assert sorted(i["finding"]["id"] for i in items) == sorted(f["id"] for f in findings)
    assert board["counts"] == {"serious": 2, "moderate": 3, "mild": 1, "adjudicated": 0, "total": 6, "blocking_open": 1}
    assert board["blocked"]

    # Deciding the blocking discrepancy unblocks submission; the order and the ranks stay.
    assert _decide(client, analyst, case_id, _item(board, "ID-01")["finding"]["id"], "accept").status_code == 200
    assert _decide(client, analyst, case_id, _item(board, "TO-04")["finding"]["id"], "dismiss").status_code == 200
    board = _board(client, analyst, case_id)
    assert [(i["finding"]["rule_id"], i["rank"]) for i in board["items"] if i["rank"]] == [
        (rule, rank) for ranked in BY_AREA.values() for rank, rule in enumerate(ranked, start=1)]
    assert board["counts"] == {"serious": 1, "moderate": 3, "mild": 0, "adjudicated": 2, "total": 6, "blocking_open": 0}
    assert not board["blocked"]


def test_each_area_sums_up_its_findings_and_where_it_stands(client, published_data_root, amounts):
    """An area's overview card: its counts, its status (open: a discrepancy is open; decided: every one
    is decided; incomplete: none, but a check could not run; clear: every check passed or did not
    apply) and its greatest discrepancy, open ones first. The board names the open blocking
    discrepancy the banner points to and the discrepancy it opens on."""
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id, _ = _discrepancies(client, analyst, root)
    board = _board(client, analyst, case_id)
    ids = {i["finding"]["rule_id"]: i["finding"]["id"] for i in board["items"] if i["rank"]}
    rules = reader.load_crosschecks(root).enabled_rules

    def holds(board: dict) -> None:
        """Each area counts its own findings, its enabled rules among them, and the areas add up to the board."""
        for a in board["areas"]:
            assert {k: a[k] for k in TALLY} == _tally(board, a["area"]), a["area"]
            assert a["rules"] == sum(1 for r in rules if r.area == a["area"]), a["area"]
        counts, areas = board["counts"], board["areas"]
        assert sum(a["discrepancies"] for a in areas) == counts["total"]
        assert sum(a["adjudicated"] for a in areas) == counts["adjudicated"]
        assert sum(a["blocking_open"] for a in areas) == counts["blocking_open"]
        assert all(sum(a[s] for a in areas) == counts[s] for s in ("serious", "moderate", "mild"))

    holds(board)
    assert [(a["area"], a["rules"]) for a in board["areas"]] == [
        ("identity", 9), ("turnover", 10), ("accounts", 2), ("obligations", 3)]
    assert [(a["discrepancies"], a["serious"], a["moderate"], a["mild"], a["blocking_open"]) for a in board["areas"]] == [
        (1, 1, 0, 0, 1), (3, 0, 2, 1, 0), (0, 0, 0, 0, 0), (2, 1, 1, 0, 0)]
    assert [(a["status"], a["top_finding_id"]) for a in board["areas"]] == [
        ("open", ids["ID-01"]), ("open", ids["TO-02"]), ("clear", None), ("open", ids["OB-01"])]
    # The banner points to the blocking discrepancy; the board opens on its first card, the greatest
    # discrepancy of the first area with an open one (the greatest on the board is OB-01, further down).
    assert (board["first_blocking"], board["top_finding_id"]) == (ids["ID-01"], ids["ID-01"])

    # Every turnover discrepancy decided: the area is decided, and still names its greatest.
    for rule, decision in (("TO-02", "accept"), ("TO-01", "dismiss"), ("TO-04", "accept")):
        assert _decide(client, analyst, case_id, ids[rule], decision).status_code == 200
    board = _board(client, analyst, case_id)
    holds(board)
    assert [(a["status"], a["top_finding_id"]) for a in board["areas"]] == [
        ("open", ids["ID-01"]), ("decided", ids["TO-02"]), ("clear", None), ("open", ids["OB-01"])]
    assert board["areas"][1]["adjudicated"] == 3 and board["areas"][1]["open"] == 0

    # The blocking discrepancy and the greatest one decided: nothing blocks, the banner has nothing to
    # point to, and the board opens on the first area with a discrepancy still open.
    assert _decide(client, analyst, case_id, ids["ID-01"], "accept").status_code == 200
    assert _decide(client, analyst, case_id, ids["OB-01"], "dismiss").status_code == 200
    board = _board(client, analyst, case_id)
    holds(board)
    assert [(a["status"], a["top_finding_id"]) for a in board["areas"]] == [
        ("decided", ids["ID-01"]), ("decided", ids["TO-02"]), ("clear", None), ("open", ids["OB-03"])]
    assert (board["first_blocking"], board["top_finding_id"], board["blocked"]) == (None, ids["OB-03"], False)

    # Every discrepancy decided: the board opens on the first area's greatest.
    assert _decide(client, analyst, case_id, ids["OB-03"], "accept").status_code == 200
    board = _board(client, analyst, case_id)
    holds(board)
    assert [a["status"] for a in board["areas"]] == ["decided", "decided", "clear", "decided"]
    assert board["areas"][3]["top_finding_id"] == ids["OB-01"]
    assert (board["first_blocking"], board["top_finding_id"]) == (None, ids["ID-01"])

    # No discrepancy, but a check that could not run: the area is incomplete. With two blocking
    # discrepancies, the banner points to the greater, then to the next once it is decided.
    other = _case(client, analyst, root, borrower="Heronbay Polymers Pvt Ltd")
    _pan_mismatch(root, other, "AAACH5678Q", "AAACH9876R", "Heronbay Polymers Pvt Ltd")
    _incorporation(root, other, "U28990MH2015PTC123465")
    _refresh(root, other)
    board = _board(client, analyst, other)
    holds(board)
    pan, cin = _item(board, "ID-01"), _item(board, "ID-05")
    assert (pan["rank"], cin["rank"]) == (1, 2)
    assert [(a["area"], a["status"], a["top_finding_id"]) for a in board["areas"]] == [
        ("identity", "open", pan["finding"]["id"]), ("turnover", "incomplete", None), ("accounts", "incomplete", None),
        ("obligations", "incomplete", None)]
    assert (board["first_blocking"], board["top_finding_id"]) == (pan["finding"]["id"], pan["finding"]["id"])
    assert _decide(client, analyst, other, pan["finding"]["id"], "dismiss").status_code == 200
    board = _board(client, analyst, other)
    assert (board["first_blocking"], board["top_finding_id"]) == (cin["finding"]["id"], cin["finding"]["id"])
    assert board["areas"][0]["top_finding_id"] == cin["finding"]["id"] and board["blocked"]


@pytest.mark.usefixtures("all_rules_enabled")
def test_the_banner_points_to_the_greatest_blocking_discrepancy_across_the_areas(
        client, published_data_root, monkeypatch):
    """Blocking discrepancies in two areas, the greater in the later area: the banner points to the
    greatest across the board, while the board opens on its first card, the greatest discrepancy of
    the first area. Here BR-01 (authority, a shortfall in rupees) outranks ID-01 (identity, no amount):
    both are serious and blocking, and a discrepancy with an amount ranks above one without. The card
    with BR-01's amount is set here, so the order holds whatever the builders' cards say."""
    def shortfall(ctx, rule, finding: Finding) -> None:
        if finding.outcome in ("pass", "fail"):
            finding.amount = 45_000_000

    monkeypatch.setattr(xv_cards, "BUILDERS", {"borrowing_limit": shortfall})
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)  # INR 6.50 cr requested
    _pan_mismatch(root, case_id)
    add_doc(root, case_id, "board_resolution_borrowing", {"borrowing_limit": 20_000_000})
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    pan, limit = _item(board, "ID-01"), _item(board, "BR-01")
    assert all(i["finding"]["outcome"] == "fail" and i["finding"]["blocking"] and i["finding"]["severity"] == "serious"
               for i in (pan, limit))
    areas = [a["area"] for a in board["areas"]]
    assert areas.index("identity") < areas.index("authority")
    # Each is the greatest of its area; the first card on the board is ID-01's.
    assert (pan["rank"], limit["rank"]) == (1, 1)
    assert next(i for i in board["items"] if i["finding"]["outcome"] == "fail")["finding"]["id"] == pan["finding"]["id"]
    assert (board["first_blocking"], board["top_finding_id"]) == (limit["finding"]["id"], pan["finding"]["id"])
    assert board["counts"]["blocking_open"] == 2 and board["blocked"]

    # BR-01 decided: the banner points to ID-01, the one still blocking.
    assert _decide(client, analyst, case_id, limit["finding"]["id"], "accept").status_code == 200
    board = _board(client, analyst, case_id)
    assert (board["first_blocking"], board["top_finding_id"], board["blocked"]) == (
        pan["finding"]["id"], pan["finding"]["id"], True)


def test_the_board_needs_the_findings_permission(client, published_data_root):
    rm = sign_in(client, RM)
    case_id = _case(client, rm, published_data_root)
    assert client.get(f"/api/cases/{case_id}/cross-verification", headers=rm).status_code == 403
    assert client.get(f"/api/cases/{case_id}/cross-verification").status_code == 401
    assert client.get(f"/api/cases/{case_id}/cross-verification", headers=sign_in(client, MANAGER)).status_code == 200


def test_the_board_needs_a_published_configuration(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, published_data_root)
    _pan_mismatch(published_data_root, case_id)
    _refresh(published_data_root, case_id)
    finding_id = _item(_board(client, analyst, case_id), "ID-01")["finding"]["id"]
    (published_data_root / "config_store" / "published.json").unlink()
    assert client.get(f"/api/cases/{case_id}/cross-verification", headers=analyst).status_code == 503
    assert _decide(client, analyst, case_id, finding_id, "accept").status_code == 503
    assert _add_query(client, analyst, case_id, finding_id).status_code == 503


# --- Decisions ---


def test_a_decision_needs_a_comment(client, published_data_root):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    finding_id = _item(_board(client, analyst, case_id), "ID-01")["finding"]["id"]
    for decision in ("accept", "dismiss", "escalate"):
        for comment in ("", "ok", "     ", "  a  "):
            response = _decide(client, analyst, case_id, finding_id, decision, comment)
            assert response.status_code == 422, (decision, comment, response.text)
    item = _item(_board(client, analyst, case_id), "ID-01")
    assert not item["adjudicated"] and item["decision"] is None and item["escalation"] is None
    assert not _audit(client, analyst, case_id, "finding.escalated")


def test_accepting_confirms_the_finding_and_keeps_it_on_the_query_list(client, published_data_root):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    item = _item(_board(client, analyst, case_id), "ID-01")
    finding_id = item["finding"]["id"]

    def asked() -> dict:
        [query] = [q for q in client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
                   if q["source_ref"] == f"ID-01:{finding_id}"]
        return query

    assert not asked()["resolved"] and asked()["group"] == "clarifications"
    comment = "The return quotes a different PAN; a revised return is to be obtained"
    response = _decide(client, analyst, case_id, finding_id, "accept", comment)
    assert response.status_code == 200, response.text
    decided = response.json()
    assert decided["adjudicated"] and decided["escalation"] is None and decided["finding"]["id"] == finding_id
    decision = decided["decision"]
    assert (decision["decision"], decision["comment"], decision["by"], decision["by_name"]) == (
        "accept", comment, "ananya-krishnan", "Ananya Krishnan") and decision["at"]
    # The review item is confirmed, with the comment as its reason.
    [review] = [i for i in client.get(f"/api/review?case_id={case_id}&include_decided=true", headers=analyst).json()
                if i["id"] == item["review_item_id"]]
    assert (review["status"], review["decision"], review["reason"], review["decided_by"]) == (
        "decided", "confirm", comment, "ananya-krishnan")
    [entry] = [e for e in _audit(client, analyst, case_id, "review.decided") if e["detail"]["item_id"] == review["id"]]
    assert entry["detail"]["decision"] == "confirm" and entry["detail"]["reason"] == comment
    # A valid finding stays on the query list.
    assert not asked()["resolved"]
    board = _board(client, analyst, case_id)
    assert _item(board, "ID-01")["decision"] == decision and _item(board, "ID-01")["adjudicated"]
    assert not board["blocked"] and board["counts"]["adjudicated"] == 1


def test_dismissing_waives_the_finding_and_takes_it_off_the_query_list(client, published_data_root):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    item = _item(_board(client, analyst, case_id), "ID-01")
    finding_id = item["finding"]["id"]
    comment = "The return on file belongs to a group company and was filed by mistake"
    response = _decide(client, analyst, case_id, finding_id, "dismiss", comment)
    assert response.status_code == 200, response.text
    assert response.json()["adjudicated"] and response.json()["decision"]["decision"] == "dismiss"
    [review] = [i for i in client.get(f"/api/review?case_id={case_id}&include_decided=true", headers=analyst).json()
                if i["id"] == item["review_item_id"]]
    assert (review["status"], review["decision"], review["reason"]) == ("decided", "waive", comment)
    [query] = [q for q in client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
               if q["source_ref"] == f"ID-01:{finding_id}"]
    assert query["resolved"]
    # The finding itself stays, with its decision.
    board = _board(client, analyst, case_id)
    assert _item(board, "ID-01")["finding"]["outcome"] == "fail" and _item(board, "ID-01")["decision"]["comment"] == comment
    assert not board["blocked"]


def test_an_escalated_discrepancy_stays_open_for_the_credit_manager(client, published_data_root):
    root = published_data_root
    analyst, manager = sign_in(client, ANALYST), sign_in(client, MANAGER)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _turnover(root, case_id)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    pan, gst = _item(board, "ID-01"), _item(board, "TO-02")
    comment = "Two PANs on file; for the Credit Manager to decide"
    response = _decide(client, analyst, case_id, pan["finding"]["id"], "escalate", comment)
    assert response.status_code == 200, response.text
    escalated = response.json()
    escalation = escalated["escalation"]
    assert (escalation["decision"], escalation["comment"], escalation["by"], escalation["by_name"]) == (
        "escalate", comment, "ananya-krishnan", "Ananya Krishnan") and escalation["at"]
    assert not escalated["adjudicated"] and escalated["decision"] is None

    # It stays open and blocking, through another run of the checks.
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    assert _item(board, "ID-01")["escalation"] == escalation and not _item(board, "ID-01")["adjudicated"]
    assert board["blocked"] and board["counts"]["blocking_open"] == 1 and board["counts"]["serious"] == 1
    [row] = _rows(root, "SELECT status, detail FROM review_items WHERE id = ?", pan["review_item_id"])
    assert row["status"] == "open"
    assert json.loads(row["detail"])["escalation"] == {"by": "ananya-krishnan", "at": escalation["at"], "comment": comment}
    queue = {i["id"]: i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json()}
    assert queue[pan["review_item_id"]]["escalated"] and not queue[gst["review_item_id"]]["escalated"]
    [entry] = _audit(client, analyst, case_id, "finding.escalated")
    assert entry["actor"] == "ananya-krishnan" and entry["detail"] == {
        "finding_id": pan["finding"]["id"], "rule_id": "ID-01", "ref": pan["finding"]["ref"], "comment": comment}
    # It is also kept with the discrepancy itself, unresolved (a run cannot withdraw it there).
    assert _escalations(root, case_id) == [("ID-01", "", "ananya-krishnan", escalation["at"], comment, None)]

    # The analyst can no longer decide it, on the board or in the review queue.
    for decision in ("accept", "dismiss", "escalate"):
        response = _decide(client, analyst, case_id, pan["finding"]["id"], decision)
        assert response.status_code == 403, (decision, response.text)
    for decision, reason in (("confirm", None), ("confirm", "A valid finding"), ("waive", "Not a valid finding")):
        response = _review_decide(client, analyst, pan["review_item_id"], decision, reason)
        assert response.status_code == 403, (decision, response.text)
    assert not _item(_board(client, analyst, case_id), "ID-01")["adjudicated"]

    # It is escalated once: the Credit Manager cannot escalate it again over the analyst's reason.
    response = _decide(client, manager, case_id, pan["finding"]["id"], "escalate", "Escalating again")
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "this discrepancy has already been escalated to the Credit Manager"
    assert _item(_board(client, analyst, case_id), "ID-01")["escalation"] == escalation
    assert json.loads(_rows(root, "SELECT detail FROM review_items WHERE id = ?", pan["review_item_id"])[0]["detail"])[
        "escalation"] == {"by": "ananya-krishnan", "at": escalation["at"], "comment": comment}
    assert len(_audit(client, analyst, case_id, "finding.escalated")) == 1
    assert _escalations(root, case_id) == [("ID-01", "", "ananya-krishnan", escalation["at"], comment, None)]

    # The Credit Manager decides it, on the board ...
    response = _decide(client, manager, case_id, pan["finding"]["id"], "accept", "The return's PAN is wrong; revised return to follow")
    assert response.status_code == 200, response.text
    decided = response.json()
    assert decided["adjudicated"] and decided["escalation"] == escalation
    assert (decided["decision"]["decision"], decided["decision"]["by"], decided["decision"]["by_name"]) == (
        "accept", "meenal-kulkarni", "Meenal Kulkarni")
    assert not _board(client, analyst, case_id)["blocked"]
    # The decision resolves the escalation.
    assert _escalations(root, case_id) == [
        ("ID-01", "", "ananya-krishnan", escalation["at"], comment, "meenal-kulkarni")]

    # ... or in the review queue.
    assert _decide(client, analyst, case_id, gst["finding"]["id"], "escalate", "Bank credits short of GST by a fifth").status_code == 200
    assert _review_decide(client, analyst, gst["review_item_id"], "confirm", "A valid finding").status_code == 403
    response = _review_decide(client, manager, gst["review_item_id"], "waive", "Receipts in an account at another bank; statement to follow")
    assert response.status_code == 200, response.text
    assert response.json()["escalated"] and response.json()["decision"] == "waive"
    item = _item(_board(client, analyst, case_id), "TO-02")
    assert item["adjudicated"] and (item["decision"]["decision"], item["decision"]["by"]) == ("dismiss", "meenal-kulkarni")
    assert [e["detail"]["rule_id"] for e in _audit(client, analyst, case_id, "finding.escalated")] == ["TO-02", "ID-01"]
    assert [(r[0], r[1], r[5]) for r in _escalations(root, case_id)] == [
        ("ID-01", "", "meenal-kulkarni"), ("TO-02", "FY 2025-26", "meenal-kulkarni")]


def test_an_escalated_discrepancy_decided_in_the_review_queue_needs_a_comment(client, published_data_root):
    root = published_data_root
    analyst, manager = sign_in(client, ANALYST), sign_in(client, MANAGER)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _turnover(root, case_id)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    pan, gst = _item(board, "ID-01"), _item(board, "TO-02")
    assert _decide(client, analyst, case_id, pan["finding"]["id"], "escalate", "Two PANs on file").status_code == 200

    # The Credit Manager's confirmation needs a comment as much as a waiver does.
    for decision in ("confirm", "waive"):
        for reason in (None, "", "ok", "  a  "):
            response = _review_decide(client, manager, pan["review_item_id"], decision, reason)
            assert response.status_code == 422, (decision, reason, response.text)
            assert response.json()["detail"] == "a comment is required for every decision on a discrepancy"
    assert not _item(_board(client, analyst, case_id), "ID-01")["adjudicated"]
    # Only the Credit Manager decides it, with or without a comment.
    assert _review_decide(client, analyst, pan["review_item_id"], "confirm").status_code == 403
    assert _review_decide(client, analyst, pan["review_item_id"], "confirm", "A valid finding").status_code == 403

    comment = "The return quotes a group company's PAN; a revised return is to follow"
    response = _review_decide(client, manager, pan["review_item_id"], "confirm", comment)
    assert response.status_code == 200, response.text
    assert (response.json()["decision"], response.json()["reason"], response.json()["escalated"]) == ("confirm", comment, True)
    [entry] = [e for e in _audit(client, analyst, case_id, "review.decided") if e["detail"]["item_id"] == pan["review_item_id"]]
    assert entry["detail"]["reason"] == comment
    # The board shows the comment as the decision's.
    decided = _item(_board(client, analyst, case_id), "ID-01")
    assert decided["adjudicated"] and decided["escalation"]["comment"] == "Two PANs on file"
    assert (decided["decision"]["decision"], decided["decision"]["comment"], decided["decision"]["by"]) == (
        "accept", comment, "meenal-kulkarni")

    # A discrepancy never escalated needs a comment in the queue too, as on the board.
    for reason in (None, "", "ok"):
        response = _review_decide(client, analyst, gst["review_item_id"], "confirm", reason)
        assert response.status_code == 422, (reason, response.text)
        assert response.json()["detail"] == "a comment is required for every decision on a discrepancy"
    response = _review_decide(client, analyst, gst["review_item_id"], "confirm",
                              "Bank credits short of GST; explanation sought")
    assert response.status_code == 200, response.text
    assert _item(_board(client, analyst, case_id), "TO-02")["decision"]["comment"] == (
        "Bank credits short of GST; explanation sought")


def test_every_decision_on_a_discrepancy_in_the_review_queue_needs_a_comment(client, published_data_root):
    """As on the board, a discrepancy confirmed or waived in the review queue needs a comment of at
    least three characters, so the board never shows a decision without one."""
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _turnover(root, case_id)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    pan, gst = _item(board, "ID-01"), _item(board, "TO-02")
    for item in (pan, gst):
        for decision in ("confirm", "waive"):
            for reason in (None, "", "   ", "ok", "  a  "):
                response = _review_decide(client, analyst, item["review_item_id"], decision, reason)
                assert response.status_code == 422, (item["finding"]["rule_id"], decision, reason, response.text)
                assert response.json()["detail"] == "a comment is required for every decision on a discrepancy"
    board = _board(client, analyst, case_id)
    assert not any(i["adjudicated"] for i in board["items"]) and board["blocked"]
    assert not _audit(client, analyst, case_id, "review.decided")

    # With a comment each is decided, and the board shows it as the decision's comment.
    response = _review_decide(client, analyst, pan["review_item_id"], "confirm", "  The return quotes another PAN  ")
    assert response.status_code == 200, response.text
    assert response.json()["reason"] == "The return quotes another PAN"
    response = _review_decide(client, analyst, gst["review_item_id"], "waive", "Receipts in an account at another bank")
    assert response.status_code == 200, response.text
    board = _board(client, analyst, case_id)
    decided = [_item(board, "ID-01")["decision"], _item(board, "TO-02")["decision"]]
    assert [(d["decision"], d["comment"]) for d in decided] == [
        ("accept", "The return quotes another PAN"), ("dismiss", "Receipts in an account at another bank")]
    assert not board["blocked"]


def test_an_escalation_stays_with_the_discrepancy_when_a_run_withdraws_its_review_item(client, published_data_root):
    """A run withdraws the open review item of a discrepancy that does not fail: a value it uses waits
    for review, or a correction makes it pass. The escalation stays with the discrepancy (case, rule,
    scope: the key of its reference), so when the discrepancy fails again it is still with the Credit
    Manager, and only the Credit Manager decides it. The decision resolves the escalation."""
    root = published_data_root
    analyst, manager = sign_in(client, ANALYST), sign_in(client, MANAGER)
    case_id = _case(client, analyst, root)
    itr = _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    pan = _item(_board(client, analyst, case_id), "ID-01")
    comment = "Two PANs on file; for the Credit Manager to decide"
    response = _decide(client, analyst, case_id, pan["finding"]["id"], "escalate", comment)
    assert response.status_code == 200, response.text
    escalation = response.json()["escalation"]
    kept = ("ID-01", "", "ananya-krishnan", escalation["at"], comment)

    def withdrawn(outcome: str) -> None:
        item = _item(_board(client, analyst, case_id), "ID-01")
        assert item["finding"]["outcome"] == outcome
        assert item["review_item_id"] is None and item["escalation"] is None
        assert not _rows(root, "SELECT 1 FROM review_items WHERE id = ?", pan["review_item_id"])
        assert _escalations(root, case_id) == [(*kept, None)]

    def still_escalated() -> None:
        board = _board(client, analyst, case_id)
        item = _item(board, "ID-01")
        assert item["finding"]["outcome"] == "fail" and item["finding"]["ref"] == pan["finding"]["ref"]
        assert (item["review_item_id"], item["escalation"], item["adjudicated"]) == (
            pan["review_item_id"], escalation, False)
        assert board["blocked"]
        queue = {i["id"]: i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json()}
        assert queue[pan["review_item_id"]]["escalated"]
        for decision in ("accept", "dismiss", "escalate"):
            response = _decide(client, analyst, case_id, pan["finding"]["id"], decision)
            assert response.status_code == 403, (decision, response.text)
        for decision in ("confirm", "waive"):
            response = _review_decide(client, analyst, pan["review_item_id"], decision, "Checked against the return")
            assert response.status_code == 403, (decision, response.text)

    # A commercial bureau report arrives whose PAN waits for review: the check cannot complete.
    bureau = add_doc(root, case_id, "commercial_bureau_report", {"pan": "AAACK1234F", "company_name": CO},
                     pending={"pan"})
    _refresh(root, case_id)
    withdrawn("incomplete")
    # The PAN is confirmed and the discrepancy fails again: it is still with the Credit Manager.
    _confirm_values(root, bureau)
    _refresh(root, case_id)
    still_escalated()

    # The return's PAN is corrected, so the check passes; then the correction is undone.
    _set_value(root, itr, "pan", "AAACK1234F")
    _refresh(root, case_id)
    withdrawn("pass")
    _set_value(root, itr, "pan", "AAACK9876Q")
    _refresh(root, case_id)
    still_escalated()

    # The Credit Manager decides it, which resolves the escalation; the decision then stays through runs
    # in which the discrepancy passes and fails again, as every decision does.
    response = _decide(client, manager, case_id, pan["finding"]["id"], "dismiss",
                       "The return was filed with a typing error")
    assert response.status_code == 200, response.text
    assert _escalations(root, case_id) == [(*kept, "meenal-kulkarni")]
    _set_value(root, itr, "pan", "AAACK1234F")
    _refresh(root, case_id)
    _set_value(root, itr, "pan", "AAACK9876Q")
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    item = _item(board, "ID-01")
    assert item["finding"]["outcome"] == "fail" and item["adjudicated"] and item["escalation"] == escalation
    assert (item["decision"]["decision"], item["decision"]["by"]) == ("dismiss", "meenal-kulkarni")
    assert not board["blocked"] and _escalations(root, case_id) == [(*kept, "meenal-kulkarni")]


def test_escalations_recorded_on_review_items_alone_are_kept_by_the_migration(tmp_path):
    """A store from before escalations were kept with their discrepancies: migration 8 keeps the
    escalation of every open finding review item. A decided item's escalation was resolved by its
    decision, and an item never escalated has none."""
    conn = sqlite3.connect(tmp_path / "creditiq.sqlite3", isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        for n, script in enumerate(db.MIGRATIONS[:7], start=1):
            conn.executescript(f"BEGIN IMMEDIATE; {script}; PRAGMA user_version = {n}; COMMIT;")
        escalation = {"by": "ananya-krishnan", "at": "2026-10-09T10:00:00+00:00", "comment": "Two PANs on file"}
        rows = [("ID-01", None, "open", escalation),
                ("TO-02", "FY 2025-26", "open", {**escalation, "comment": "Short by a fifth"}),
                ("ID-05", None, "decided", escalation), ("OB-01", None, "open", None)]
        for n, (rule, scope, status, raised) in enumerate(rows):
            finding_id = f"FND-{n}"
            conn.execute("""INSERT INTO findings (id, case_id, rule_id, title, outcome, severity, blocking, explanation,
                            sides, scope) VALUES (?, 'BBG-2026-000001', ?, ?, 'fail', 'serious', 1, '', '[]', ?)""",
                         (finding_id, rule, rule, scope))
            detail = {"finding_id": finding_id, "rule_id": rule, **({"escalation": raised} if raised else {})}
            conn.execute("""INSERT INTO review_items (id, case_id, kind, ref, summary, created_at, status, detail)
                            VALUES (?, 'BBG-2026-000001', 'finding', ?, '', '', ?, ?)""",
                         (f"RV-{n}", f"finding:{finding_id}", status, json.dumps(detail)))
        db.migrate(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
        kept = [tuple(r) for r in conn.execute(
            """SELECT case_id, rule_id, scope, escalated_by, escalated_at, comment, resolved_by, resolved_at
               FROM finding_escalations ORDER BY rule_id""")]
    finally:
        conn.close()
    assert kept == [
        ("BBG-2026-000001", "ID-01", "", "ananya-krishnan", escalation["at"], "Two PANs on file", None, None),
        ("BBG-2026-000001", "TO-02", "FY 2025-26", "ananya-krishnan", escalation["at"], "Short by a fifth", None, None)]


def test_an_escalation_is_checked_again_when_it_is_recorded(client, published_data_root, monkeypatch):
    """The board an escalation was made on can be out of date when the escalation is written: another
    reviewer has decided the discrepancy, or escalated it, meanwhile. Neither is overwritten: the
    escalation is refused (409), and an acceptance on the board meets the escalation (403)."""
    root = published_data_root
    analyst, manager = sign_in(client, ANALYST), sign_in(client, MANAGER)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _turnover(root, case_id)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    pan, gst = _item(board, "ID-01"), _item(board, "TO-02")

    def queue_decision(item: dict, email: str, decision: str, reason: str) -> Callable[[], None]:
        def act() -> None:
            conn = db.connect(root)
            try:
                review.decide(conn, root, item["review_item_id"],
                              ReviewDecisionRequest(decision=decision, reason=reason), _as(email))
            finally:
                conn.close()
        return act

    def escalation(case: str, item: dict, email: str, comment: str) -> Callable[[], None]:
        def act() -> None:
            conn = db.connect(root)
            try:
                xv.decide(conn, root, cases.get_case(conn, case), item["finding"]["id"],
                          XvDecisionRequest(decision="escalate", comment=comment), _as(email))
            finally:
                conn.close()
        return act

    def review_row(item: dict) -> tuple[str, dict]:
        [row] = _rows(root, "SELECT status, detail FROM review_items WHERE id = ?", item["review_item_id"])
        return row["status"], json.loads(row["detail"])

    # The Credit Manager accepts ID-01 in the review queue while the analyst escalates it from the board.
    _meanwhile(monkeypatch, queue_decision(pan, MANAGER, "confirm", "A valid finding; a revised return is to follow"))
    response = _decide(client, analyst, case_id, pan["finding"]["id"], "escalate", "For the Credit Manager")
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "this discrepancy has already been decided"
    status, detail = review_row(pan)
    assert status == "decided" and "escalation" not in detail
    item = _item(_board(client, analyst, case_id), "ID-01")
    assert item["adjudicated"] and item["escalation"] is None and item["decision"]["by"] == "meenal-kulkarni"
    assert not _audit(client, analyst, case_id, "finding.escalated") and not _escalations(root, case_id)

    # The analyst escalates TO-02 while the Credit Manager, on a board read before, escalates it too.
    _meanwhile(monkeypatch, escalation(case_id, gst, ANALYST, "Bank credits short of GST by a fifth"))
    response = _decide(client, manager, case_id, gst["finding"]["id"], "escalate", "Escalating it myself")
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "this discrepancy has already been escalated to the Credit Manager"
    status, detail = review_row(gst)
    assert status == "open" and (detail["escalation"]["by"], detail["escalation"]["comment"]) == (
        "ananya-krishnan", "Bank credits short of GST by a fifth")
    assert [e["actor"] for e in _audit(client, analyst, case_id, "finding.escalated")] == ["ananya-krishnan"]
    assert [(r[0], r[2], r[4]) for r in _escalations(root, case_id)] == [
        ("TO-02", "ananya-krishnan", "Bank credits short of GST by a fifth")]

    # An acceptance on a board read before the escalation meets it: only the Credit Manager decides it.
    other = _case(client, analyst, root, borrower="Heronbay Polymers Pvt Ltd")
    _pan_mismatch(root, other, "AAACH5678Q", "AAACH9876R", "Heronbay Polymers Pvt Ltd")
    _refresh(root, other)
    pan = _item(_board(client, analyst, other), "ID-01")
    _meanwhile(monkeypatch, escalation(other, pan, ANALYST, "Two PANs on file"))
    response = _decide(client, analyst, other, pan["finding"]["id"], "accept", "A valid finding")
    assert response.status_code == 403, response.text
    status, detail = review_row(pan)
    assert status == "open" and detail["escalation"]["comment"] == "Two PANs on file"
    item = _item(_board(client, analyst, other), "ID-01")
    assert not item["adjudicated"] and item["escalation"]["by"] == "ananya-krishnan"


def test_decisions_that_do_not_apply_are_refused(client, published_data_root):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    finding_id = _item(board, "ID-01")["finding"]["id"]
    # Only a discrepancy is adjudicated: not a check that passed or could not run.
    for rule, outcome in (("ID-03", "pass"), ("ID-05", "incomplete"), ("TO-04", "not_applicable")):
        assert _item(board, rule)["finding"]["outcome"] == outcome
        response = _decide(client, analyst, case_id, _item(board, rule)["finding"]["id"], "accept")
        assert response.status_code == 409, (rule, response.text)
    assert _decide(client, analyst, case_id, "FND-NOPE", "accept").status_code == 404
    assert _decide(client, analyst, "BBG-2026-999999", finding_id, "accept").status_code == 404
    # A decision needs the decision permission, and a session.
    assert _decide(client, sign_in(client, RM), case_id, finding_id, "accept").status_code == 403
    assert client.post(f"/api/cases/{case_id}/cross-verification/findings/{finding_id}/decision",
                       json={"decision": "accept", "comment": "Valid finding"}).status_code == 401
    assert client.post(f"/api/cases/{case_id}/cross-verification/findings/{finding_id}/decision",
                       json={"decision": "waive", "comment": "Not a valid finding"}, headers=analyst).status_code == 422
    # A discrepancy is decided once.
    assert _decide(client, analyst, case_id, finding_id, "dismiss").status_code == 200
    for decision in ("accept", "dismiss", "escalate"):
        response = _decide(client, analyst, case_id, finding_id, decision)
        assert response.status_code == 409, (decision, response.text)
    assert _decide(client, sign_in(client, MANAGER), case_id, finding_id, "accept").status_code == 409
    assert _item(_board(client, analyst, case_id), "ID-01")["decision"]["decision"] == "dismiss"


# --- Requests on the query list ---


def test_a_check_that_could_not_run_puts_its_request_on_the_query_list(client, published_data_root):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)  # no certificate of incorporation or memorandum on file
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    item = _item(board, "ID-05")
    finding = item["finding"]
    assert finding["outcome"] == "incomplete" and finding["request"] and not item["in_query_list"]
    text = f"Please provide {finding['request']}, so that the check “{finding['compares']}” can be completed."

    def asked() -> list[dict]:
        return [q for q in client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
                if q["source_ref"] == "ID-05::request"]

    assert not asked()
    response = _add_query(client, analyst, case_id, finding["id"])
    assert response.status_code == 200, response.text
    assert response.json()["in_query_list"] and response.json()["finding"]["id"] == finding["id"]
    [query] = asked()
    assert (query["text"], query["group"], query["source_kind"], query["resolved"]) == (
        text, "documents_needed", "finding", False)
    # Adding it again changes nothing, and the decision log records the addition once.
    assert _add_query(client, analyst, case_id, finding["id"]).status_code == 200
    assert asked() == [query] and _item(_board(client, analyst, case_id), "ID-05")["in_query_list"]
    [entry] = _audit(client, analyst, case_id, "finding.query_added")
    assert entry["actor"] == "ananya-krishnan" and entry["detail"] == {
        "finding_id": finding["id"], "rule_id": "ID-05", "request": finding["request"]}

    # Only a check that could not run, with something to ask for: not a discrepancy or a pass.
    for rule in ("ID-01", "ID-03", "TO-04"):
        response = _add_query(client, analyst, case_id, _item(board, rule)["finding"]["id"])
        assert response.status_code == 409, (rule, response.text)
    assert _add_query(client, analyst, case_id, "FND-NOPE").status_code == 404
    assert _add_query(client, sign_in(client, RM), case_id, finding["id"]).status_code == 403

    # The certificate and the memorandum arrive and the check runs: the request is resolved.
    _incorporation(root, case_id)
    _refresh(root, case_id)
    assert _item(_board(client, analyst, case_id), "ID-05")["finding"]["outcome"] == "pass"
    [query] = asked()
    assert query["resolved"] and query["text"] == text


def test_a_check_is_on_the_query_list_only_while_it_cannot_run(client, published_data_root):
    """The request stays recorded once its check completes, and comes back if the check cannot run
    again; the board shows the check on the query list only while it is incomplete."""
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    finding_id = _item(_board(client, analyst, case_id), "ID-05")["finding"]["id"]
    assert _add_query(client, analyst, case_id, finding_id).json()["in_query_list"]

    def asked() -> dict:
        [query] = [q for q in client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
                   if q["source_ref"] == "ID-05::request"]
        return query

    memorandum = _incorporation(root, case_id)
    _refresh(root, case_id)
    item = _item(_board(client, analyst, case_id), "ID-05")
    assert item["finding"]["outcome"] == "pass" and not item["in_query_list"] and asked()["resolved"]

    # The memorandum is withdrawn: the check cannot run again, and is back on the query list.
    conn = db.connect(root)
    try:
        conn.execute("UPDATE documents SET status = 'superseded' WHERE id = ?", (memorandum,))
    finally:
        conn.close()
    _refresh(root, case_id)
    item = _item(_board(client, analyst, case_id), "ID-05")
    assert item["finding"]["outcome"] == "incomplete" and item["in_query_list"] and not asked()["resolved"]


def test_the_query_list_asks_for_what_the_check_needs_now(client, published_data_root, monkeypatch):
    """A request on the query list is worded as the check asks now: it narrows as documents arrive (the
    same query, reworded). Once the check only waits for a person's review it asks the customer for
    nothing, so the query is resolved and the board no longer shows the check on the query list; so too
    once it completes. (The cards are the sides here: the request names the documents not on file.)"""
    monkeypatch.setattr(xv_cards, "BUILDERS", {})
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)  # neither the certificate of incorporation nor the memorandum

    def now() -> tuple[dict, dict]:
        item = _item(_board(client, analyst, case_id), "ID-05")
        [query] = [q for q in client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
                   if q["source_ref"] == "ID-05::request"]
        return item, query

    def asks(item: dict) -> str:
        f = item["finding"]
        return f"Please provide {f['request']}, so that the check “{f['compares']}” can be completed."

    finding_id = _item(_board(client, analyst, case_id), "ID-05")["finding"]["id"]
    first = _add_query(client, analyst, case_id, finding_id).json()
    assert first["finding"]["request"] == xv_cards.documents(
        ["Certificate of incorporation", "Memorandum and articles of association"])
    item, query = now()
    assert item["in_query_list"] and (query["text"], query["resolved"]) == (asks(first), False)

    # The certificate arrives: the check still cannot run, and now asks only for the memorandum.
    add_doc(root, case_id, "certificate_of_incorporation", {"cin": CIN})
    _refresh(root, case_id)
    item, narrowed = now()
    assert item["finding"]["outcome"] == "incomplete"
    assert item["finding"]["request"] == xv_cards.documents(["Memorandum and articles of association"])
    assert item["in_query_list"] and narrowed["id"] == query["id"] and not narrowed["resolved"]
    assert narrowed["text"] == asks(item) and narrowed["text"] != query["text"]

    # The memorandum arrives, its CIN waiting for review: nothing to ask the customer for.
    memorandum = add_doc(root, case_id, "memorandum_articles_of_association", {"cin": CIN}, pending={"cin"})
    _refresh(root, case_id)
    item, waiting = now()
    assert item["finding"]["outcome"] == "incomplete" and item["finding"]["request"] is None
    assert not item["in_query_list"] and waiting["resolved"]
    assert _add_query(client, analyst, case_id, item["finding"]["id"]).status_code == 409

    # Confirmed, the check runs and passes: the query stays resolved, and the check off the query list.
    _confirm_values(root, memorandum)
    _refresh(root, case_id)
    item, done = now()
    assert item["finding"]["outcome"] == "pass" and not item["in_query_list"] and done["resolved"]
    # The addition itself stays recorded, with what was first asked.
    [added] = _rows(root, "SELECT text FROM query_additions WHERE case_id = ? AND rule_id = 'ID-05'", case_id)
    assert added["text"] == asks(first)


def test_deleting_a_case_removes_its_references_runs_requests_and_escalations(client, published_data_root):
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    assert _add_query(client, analyst, case_id, _item(board, "ID-05")["finding"]["id"]).status_code == 200
    assert _decide(client, analyst, case_id, _item(board, "ID-01")["finding"]["id"], "escalate").status_code == 200
    tables = ("finding_refs", "crosscheck_runs", "query_additions", "finding_escalations")

    def counts() -> dict[str, int]:
        return {t: _rows(root, f"SELECT COUNT(*) FROM {t} WHERE case_id = ?", case_id)[0][0] for t in tables}

    assert counts() == {t: 1 for t in tables}
    response = client.request("DELETE", f"/api/cases/{case_id}", json={"reason": "testing restart"}, headers=analyst)
    assert response.status_code == 204, response.text
    assert counts() == {t: 0 for t in tables}
    [entry] = _rows(root, "SELECT detail FROM decision_log WHERE case_id = ? AND action = 'case.deleted'", case_id)
    deleted = json.loads(entry["detail"])["rows"]
    assert {t: deleted.get(t) for t in tables} == {t: 1 for t in tables}


# --- The card ---


def test_the_card_is_kept_with_the_finding(client, published_data_root, monkeypatch):
    """Whatever a builder sets is stored with the finding (findings.card) and read back unchanged
    by the findings and the board; the columns are capped at four."""
    from engine import xv_cards

    def card(ctx, rule, finding: Finding) -> None:
        if finding.outcome != "fail":
            return
        page = Evidence(document_id=finding.sides[0].evidence[0].document_id, page=1)
        finding.columns = [
            xv_cards.column(ctx, f"source-{n}", f"Source {n}", sources=["company_pan"], value=f"AAACK{n}234F",
                            coverage=f"Page {n}", differs=n == 2, evidence=[page], row_columns=["Field", "Value"],
                            rows=[xv_cards.row(["PAN", f"AAACK{n}234F"], [page]), xv_cards.row(["Total", n], kind="total")])
            for n in range(1, 7)]
        finding.gaps = [GapLeg(label="Gap against bank credits", amount=9_600_000, pct=20.0, base="GST outward supplies",
                               legs="GST outward supplies against bank credits", breached=True)]
        finding.gap_tolerance = "10%"
        finding.mismatch = "The income tax return gives AAACK9876Q; the other source gives AAACK1234F."
        finding.reference = "AAACK1234F"
        finding.amount = 9_600_000

    monkeypatch.setattr(xv_cards, "BUILDERS", {"entity_pan": card})
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _refresh(root, case_id)

    [row] = _rows(root, "SELECT card FROM findings WHERE case_id = ? AND rule_id = 'ID-01'", case_id)
    stored = json.loads(row["card"])
    rule = next(r for r in reader.load_crosschecks(root).rules if r.id == "ID-01")
    assert set(stored) == CARD_FIELDS
    assert (stored["ref"], stored["finding_title"], stored["compares"], stored["policy_ref"]) == (
        f"XV-{_number(case_id)}-01", rule.finding_title, rule.title, rule.policy_ref)
    assert [c["label"] for c in stored["columns"]] == ["Source 1", "Source 2", "Source 3", "Source 4"]
    first = stored["columns"][0]
    [page] = first["evidence"]
    assert page["page"] == 1 and first["provenance"] == ["borrower_supplied"] and first["coverage"] == "Page 1"
    assert first["rows"] == [{"cells": ["PAN", "AAACK1234F"], "evidence": [page], "kind": "row"},
                             {"cells": ["Total", 1], "evidence": [], "kind": "total"}]
    assert not first["differs"] and stored["columns"][1]["differs"]
    assert stored["gaps"] == [{"label": "Gap against bank credits", "amount": 9_600_000, "pct": 20.0,
                               "base": "GST outward supplies", "legs": "GST outward supplies against bank credits",
                               "breached": True}]
    assert (stored["gap_tolerance"], stored["reference"], stored["amount"], stored["request"]) == (
        "10%", "AAACK1234F", 9_600_000, None)
    assert stored["mismatch"].startswith("The income tax return gives AAACK9876Q")

    [listed] = [f for f in client.get(f"/api/cases/{case_id}/findings", headers=analyst).json() if f["rule_id"] == "ID-01"]
    shown = _item(_board(client, analyst, case_id), "ID-01")["finding"]
    assert {k: listed[k] for k in CARD_FIELDS} == stored
    assert {k: shown[k] for k in CARD_FIELDS} == stored
    assert listed == shown


def test_without_a_card_builder_the_columns_are_the_sides(client, published_data_root, monkeypatch):
    monkeypatch.setattr(xv_cards, "BUILDERS", {})
    root = published_data_root
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    _pan_mismatch(root, case_id)
    _turnover(root, case_id)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    provenance = {t.id: t.provenance for t in reader.load_document_types(root).types}
    rules = {r.id: r for r in reader.load_crosschecks(root).rules}
    for item in board["items"]:
        f = item["finding"]
        rule = rules[f["rule_id"]]
        assert (f["finding_title"], f["compares"], f["policy_ref"]) == (rule.finding_title, rule.title, rule.policy_ref)
        assert len(f["columns"]) == min(len(f["sides"]), 4), f["rule_id"]
        for column, side in zip(f["columns"], f["sides"]):
            assert (column["label"], column["value"], column["sources"], column["differs"], column["evidence"],
                    column["awaiting_review"], column["relies_on_manual"], column["field_ids"]) == (
                side["label"], side["value"], side["sources"], side["differs"], side["evidence"],
                side["awaiting_review"], side["relies_on_manual"], side["field_ids"])
            assert column["provenance"] == list(dict.fromkeys(provenance[s] for s in side["sources"] if provenance.get(s)))
            assert column["unit"] == ("inr" if isinstance(side["value"], (int, float)) else "text")
            assert column["rows"] == [{"cells": [side["label"]], "evidence": [e], "kind": "row"} for e in side["evidence"]]
        assert (f["gaps"], f["gap_tolerance"], f["mismatch"], f["reference"], f["amount"]) == ([], None, None, None, None)
        # A check that could not run asks for the documents it is missing, as every card words them.
        missing = f["missing"]
        if f["outcome"] == "incomplete" and missing:
            assert f["request"] == xv_cards.documents(missing), f["rule_id"]
        else:
            assert f["request"] is None, f["rule_id"]
    pan = _item(board, "ID-01")["finding"]
    assert [(c["value"], c["differs"]) for c in pan["columns"]] == [(s["value"], s["differs"]) for s in pan["sides"]]
    assert _item(board, "TO-02")["finding"]["columns"][0]["unit"] == "inr"
    assert _item(board, "ID-07")["finding"]["request"] == "the certificate of incorporation"
    assert _item(board, "ID-05")["finding"]["request"] == (
        "the certificate of incorporation and the memorandum and articles of association")

    # A check waiting for a person's review has nothing to ask the customer for.
    waiting = _case(client, analyst, root, borrower="Heronbay Polymers Pvt Ltd")
    add_doc(root, waiting, "company_pan", {"pan": "AAACH5678Q"}, pending={"pan"})
    add_doc(root, waiting, "income_tax_return", {"pan": "AAACH9876R"})
    _refresh(root, waiting)
    item = _item(_board(client, analyst, waiting), "ID-01")
    assert item["finding"]["outcome"] == "incomplete" and item["finding"]["request"] is None
    assert any(c["awaiting_review"] for c in item["finding"]["columns"])
    assert _add_query(client, analyst, waiting, item["finding"]["id"]).status_code == 409


@pytest.mark.usefixtures("all_rules_enabled")
def test_every_check_short_of_documents_names_each_document_in_one_wording(client, published_data_root):
    """Whichever rule asks, a document is named the same way after "Please provide": "the <name>",
    with an ordinary first word in lower case and an acronym or a code kept as written (the rules
    switched off in configuration too, switched on here)."""
    root = published_data_root
    names = [t.name for t in reader.load_document_types(root).types]
    assert {n: xv_cards.document(n) for n in names} == {
        "Sourcing message": "the sourcing message",
        "Certificate of incorporation": "the certificate of incorporation",
        "Memorandum and articles of association": "the memorandum and articles of association",
        "Board resolution for borrowing": "the board resolution for borrowing",
        "Company PAN": "the company PAN",
        "Director KYC": "the director KYC",
        "Audited financial statements": "the audited financial statements",
        "Income tax return": "the income tax return",
        "GSTR-3B": "the GSTR-3B",
        "GSTR-1": "the GSTR-1",
        "Bank statement": "the bank statement",
        "Declaration of existing facilities": "the declaration of existing facilities",
        "Sanction letter": "the sanction letter",
        "Commercial bureau report": "the commercial bureau report",
    }
    assert xv_cards.documents(["Director KYC", "GSTR-3B", "Income tax return"]) == (
        "the director KYC, the GSTR-3B and the income tax return")
    assert xv_cards.documents(["Sanction letter", "Commercial bureau report"], "or") == (
        "the sanction letter or the commercial bureau report")

    # Every family's checks, short of their documents: each request names them so (OB-01 would take
    # any one of them; FS-01 needs two years of the statements).
    analyst = sign_in(client, ANALYST)
    case_id = _case(client, analyst, root)
    add_doc(root, case_id, "existing_facilities_declaration", {"company_name": CO, "facilities": [TIDEWATER]})
    _refresh(root, case_id)
    asked = [i["finding"] for i in _board(client, analyst, case_id)["items"]
             if i["finding"]["outcome"] == "incomplete" and i["finding"]["missing"]]
    assert {f["area"] for f in asked} == {"identity", "turnover", "financials", "accounts", "obligations",
                                          "authority"}
    for f in asked:
        wanted = xv_cards.documents(f["missing"], "or" if f["rule_id"] == "OB-01" else "and")
        assert f["request"] == wanted or f["request"] == f"{wanted} for two consecutive years", (f["rule_id"], f["request"])
