"""Switching a cross-check off and on (config/crosschecks.yaml `enabled`; F-19). A switched-off rule
stays configured, and validated, but is not run: it gives no finding, so no review item, query, CAM
or PD-note entry, and it blocks nothing. Switched back on, all of it returns. Six rules are
switched off (the board-resolution and statement rules), so the board covers the test plan's four
areas, and the other 24 give what they give with every rule on. Publishing through the
command line re-runs every case at once. Every name is fictional."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import cases, cli, crosschecks, db, facts, pipeline, xv_cards
from engine.configstore import reader, writer
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc, audited, bank, gstr, months

ROOT = Path(__file__).resolve().parents[1]
SWITCHED_OFF = {"BR-01", "BR-02", "BR-03", "BR-04", "FS-01", "FS-02"}
SHORTFALL = "The board resolution authorises borrowing up to INR 2.00 cr; the amount requested is INR 6.50 cr."
"""BR-01's explanation on `_resolution_case`."""
NOTHING = {"findings": [], "review": [], "queries": [], "cam": [], "pd_note": [], "board": []}
"""What a switched-off rule leaves on a case (`_left`)."""
RULE_FIELDS = {"rule_id", "title", "area", "scope", "outcome", "severity", "blocking", "explanation", "sides", "detail",
               "missing", "tolerance", "query"}
"""What a rule decides about its finding (the card is presentation)."""
CO = "Kestrel Tools Private Limited"
FY26 = months((2025, 4), 12)
MONTH_NAMES = ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January",
               "February", "March"]
PERIODS = [f"{m} {2025 if i < 9 else 2026}" for i, m in enumerate(MONTH_NAMES)]  # FY 2025-26
TIDEWATER = {"lender": "Tidewater Finance Limited", "facility": "Term loan", "sanctioned_amount": 12_000_000,
             "outstanding": 7_500_000, "emi": 250_000}
LOTUSCREST = {"lender": "Lotuscrest Bank", "facility": "Cash credit", "sanctioned_amount": 20_000_000,
              "outstanding": 18_500_000}


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _publish(root: Path, monkeypatch: pytest.MonkeyPatch, *switched_on: str) -> None:
    """Publish the authored configuration with these rules switched back on, as deleting their
    `enabled: false` would; naming none publishes it as authored."""
    authored = writer.load_authored_sections()
    checks = authored["crosschecks"].model_copy(deep=True)
    for rule in checks.rules:
        rule.enabled = rule.enabled or rule.id in switched_on
    with monkeypatch.context() as m:
        m.setattr(writer, "load_authored_sections", lambda private_dir=None: {**authored, "crosschecks": checks})
        writer.publish(data_root=root, author="test", note="switched on: " + (", ".join(switched_on) or "none"))


def _resolution_case(client: TestClient, analyst: dict, root: Path, borrower: str = "Kestrel Tools Pvt Ltd") -> str:
    """INR 6.50 cr requested against a board resolution for INR 2.00 cr in favour of another bank:
    switched on, BR-01 fails (serious, blocking) and BR-03 fails (moderate). No other rule fails."""
    case_id = make_case(client, analyst, root, borrower=borrower, amount_inr=65_000_000)
    add_doc(root, case_id, "board_resolution_borrowing",
            {"borrowing_limit": 20_000_000, "lender_name": "Lotuscrest Bank Limited"})
    return case_id


def _board(client: TestClient, headers: dict, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/cross-verification", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _item(board: dict, rule_id: str) -> dict:
    [item] = [i for i in board["items"] if i["finding"]["rule_id"] == rule_id]
    return item


def _left(client: TestClient, headers: dict, root: Path, case_id: str, rule_id: str,
          explanation: str, *, refresh: bool = True) -> dict[str, list]:
    """What the rule leaves on the case after a run of the checks (or as it stands, without
    `refresh`): its findings, its review items (open or decided), its open queries, its CAM entries
    (the memo states a failure by its `explanation`), its PD-note questions and its items on the board."""
    if refresh:
        _refresh(root, case_id)

    def get(path: str):
        response = client.get(f"/api/cases/{case_id}/{path}", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    cam = get("cam")
    return {
        "findings": [f for f in get("findings") if f["rule_id"] == rule_id],
        "review": [i for i in client.get(f"/api/review?case_id={case_id}&include_decided=true", headers=headers).json()
                   if i["kind"] == "finding" and i["summary"].startswith(f"{rule_id} ")],
        "queries": [q for q in get("queries") if q["source_ref"].startswith(f"{rule_id}:") and not q["resolved"]],
        "cam": [i for i in cam["summary"] if i["kind"] == "finding" and i["text"] == explanation]
               + [t for t in _cam_texts(cam) if explanation in t],
        "pd_note": [q for q in get("pd-note")["questions"] if q["rule"] == rule_id],
        "board": [i for i in get("cross-verification")["items"] if i["finding"]["rule_id"] == rule_id],
    }


def _cam_texts(cam: dict) -> list[str]:
    """Every statement in the memo's sections: paragraphs, key facts and table cells."""
    out = []
    for s in cam["sections"]:
        for b in s["blocks"]:
            out += [b["paragraph"]["text"]] if b["paragraph"] else []
            out += [f["value"]["text"] for f in b["facts"]]
            out += [c["text"] for row in (b["table"]["rows"] if b["table"] else []) for c in row]
    return out


def _attention(client: TestClient, headers: dict, case_id: str) -> int:
    progress = client.get(f"/api/cases/{case_id}/progress", headers=headers).json()
    return next(s for s in progress["stages"] if s["key"] == "cross_verification")["attention"]


# --- Configuration (the switch itself: tests/test_config_catalogue.py) ---


def test_a_version_published_before_rules_could_be_switched_off_runs_every_rule(client, analyst, published_data_root):
    root = published_data_root
    version = reader.published_version(root)["version"]
    path = root / "config_store" / "versions" / version / "crosschecks.json"
    published = json.loads(path.read_text(encoding="utf-8"))
    assert {r["id"] for r in published["rules"] if r["enabled"] is False} == SWITCHED_OFF
    # As such a version was written: without the key.
    for rule in published["rules"]:
        del rule["enabled"]
    path.write_text(json.dumps(published, indent=2, sort_keys=True), encoding="utf-8")

    checks = reader.load_crosschecks(root)
    assert len(checks.enabled_rules) == len(checks.rules) == 30
    case_id = make_case(client, analyst, root)
    board = _board(client, analyst, case_id)
    assert board["run"]["rules"] == 30
    assert {i["finding"]["rule_id"] for i in board["items"]} == {r.id for r in checks.rules}
    assert [a["area"] for a in board["areas"]] == [
        "identity", "authority", "turnover", "financials", "accounts", "obligations"]


def test_every_caller_reads_the_rules_through_the_reader_module():
    """The tests of the switched-off rules switch them on by replacing reader.load_crosschecks
    (tests/conftest.py all_rules_enabled): a module that held the function itself would keep them off."""
    for path in sorted((ROOT / "engine").rglob("*.py")):
        if path.name == "reader.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bimport\b[^\n]*\bload_crosschecks\b", text), path
        assert not re.search(r"(?<!reader\.)\bload_crosschecks\b", text), path


# --- On a case ---


def test_a_switched_off_rule_leaves_nothing_on_the_case_and_switched_on_all_of_it_returns(
        client, analyst, published_data_root, monkeypatch):
    root = published_data_root
    case_id = _resolution_case(client, analyst, root)
    assert _left(client, analyst, root, case_id, "BR-01", SHORTFALL) == NOTHING
    board = _board(client, analyst, case_id)
    assert (board["blocked"], board["first_blocking"], board["counts"]["blocking_open"]) == (False, None, 0)
    assert board["run"]["rules"] == 24 and "authority" not in {a["area"] for a in board["areas"]}
    assert _attention(client, analyst, case_id) == 0

    _publish(root, monkeypatch, "BR-01")
    left = _left(client, analyst, root, case_id, "BR-01", SHORTFALL)
    [finding] = left["findings"]
    assert (finding["outcome"], finding["severity"], finding["blocking"], finding["explanation"]) == (
        "fail", "serious", True, SHORTFALL)
    assert [i["status"] for i in left["review"]] == ["open"]
    assert [q["text"] for q in left["queries"]] == ["Please provide a board resolution authorising borrowing of INR 6.50 cr."]
    assert left["cam"] and [q["source"] for q in left["pd_note"]] == ["finding"]
    assert [i["finding"]["id"] for i in left["board"]] == [finding["id"]]
    board = _board(client, analyst, case_id)
    assert (board["blocked"], board["first_blocking"], board["counts"]["blocking_open"]) == (True, finding["id"], 1)
    assert board["run"]["rules"] == 25
    assert [(a["area"], a["rules"], a["status"]) for a in board["areas"] if a["area"] == "authority"] == [
        ("authority", 1, "open")]
    assert _attention(client, analyst, case_id) == 1

    # Switched off again, it leaves nothing once more.
    _publish(root, monkeypatch)
    assert _left(client, analyst, root, case_id, "BR-01", SHORTFALL) == NOTHING
    assert not _board(client, analyst, case_id)["blocked"] and _attention(client, analyst, case_id) == 0


def test_switched_off_between_two_runs_an_open_item_is_withdrawn_and_a_decided_one_kept(
        client, analyst, published_data_root, monkeypatch):
    root = published_data_root
    _publish(root, monkeypatch, "BR-01", "BR-03")
    case_id = _resolution_case(client, analyst, root)
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    limit, lender = _item(board, "BR-01"), _item(board, "BR-03")
    assert limit["finding"]["outcome"] == lender["finding"]["outcome"] == "fail"
    comment = "The resolution names another lender; a fresh resolution is to follow"
    response = client.post(f"/api/cases/{case_id}/cross-verification/findings/{lender['finding']['id']}/decision",
                           json={"decision": "accept", "comment": comment}, headers=analyst)
    assert response.status_code == 200, response.text
    # BR-01 is escalated to the Credit Manager, and stays open.
    response = client.post(f"/api/cases/{case_id}/cross-verification/findings/{limit['finding']['id']}/decision",
                           json={"decision": "escalate", "comment": "A shortfall of INR 4.50 cr"}, headers=analyst)
    assert response.status_code == 200, response.text
    escalation = response.json()["escalation"]

    def asked() -> dict[str, bool]:
        """The two rules' queries on the query list, and whether each is resolved."""
        return {q["source_ref"].split(":")[0]: q["resolved"]
                for q in client.get(f"/api/cases/{case_id}/queries", headers=analyst).json()
                if q["source_ref"].split(":")[0] in SWITCHED_OFF}

    # An accepted finding stays on the query list, as an open one does.
    assert asked() == {"BR-01": False, "BR-03": False}

    # Switched off: until the case's checks run again, the board leaves out their last findings.
    _publish(root, monkeypatch)
    board = _board(client, analyst, case_id)
    assert not {i["finding"]["rule_id"] for i in board["items"]} & SWITCHED_OFF and not board["blocked"]

    # The next run withdraws the open item; the decided one stays, as the record of the decision.
    _refresh(root, case_id)
    review = {i["id"]: i for i in client.get(f"/api/review?case_id={case_id}&include_decided=true",
                                             headers=analyst).json()}
    assert limit["review_item_id"] not in review
    kept = review[lender["review_item_id"]]
    assert (kept["status"], kept["decision"], kept["reason"]) == ("decided", "confirm", comment)
    # Neither has a finding or a place on the board, their queries are resolved, and nothing blocks.
    findings = client.get(f"/api/cases/{case_id}/findings", headers=analyst).json()
    assert not {f["rule_id"] for f in findings} & SWITCHED_OFF
    assert asked() == {"BR-01": True, "BR-03": True}
    board = _board(client, analyst, case_id)
    assert not {i["finding"]["rule_id"] for i in board["items"]} & SWITCHED_OFF
    assert (board["blocked"], board["first_blocking"], board["counts"]["total"]) == (False, None, 0)

    # Switched back on: BR-01 is raised again, open and still escalated; BR-03 returns with its decision;
    # each keeps its reference.
    _publish(root, monkeypatch, "BR-01", "BR-03")
    _refresh(root, case_id)
    board = _board(client, analyst, case_id)
    again, decided = _item(board, "BR-01"), _item(board, "BR-03")
    assert (again["review_item_id"], again["adjudicated"], again["finding"]["ref"], again["escalation"]) == (
        limit["review_item_id"], False, limit["finding"]["ref"], escalation)
    assert decided["adjudicated"] and (decided["decision"]["decision"], decided["decision"]["comment"]) == ("accept", comment)
    assert decided["finding"]["ref"] == lender["finding"]["ref"]
    assert board["blocked"] and board["first_blocking"] == again["finding"]["id"]
    assert asked() == {"BR-01": False, "BR-03": False}
    # Only the Credit Manager decides it.
    response = client.post(f"/api/cases/{case_id}/cross-verification/findings/{again['finding']['id']}/decision",
                           json={"decision": "accept", "comment": "Valid; a fresh resolution is to follow"},
                           headers=analyst)
    assert response.status_code == 403, response.text


def test_publishing_through_the_command_line_reruns_every_case(
        client, analyst, published_data_root, monkeypatch, capsys):
    """`creditiq config publish` re-runs every case's checks once the version is published, so a rule
    switched off there leaves nothing on any case straight away: no finding, review item, query, CAM
    or PD-note entry, nothing on the board, nothing for the stage to attend to. With --no-rerun a case
    keeps its last run's findings until it runs again."""
    root = published_data_root
    _publish(root, monkeypatch, "BR-01")
    both = [_resolution_case(client, analyst, root, borrower)
            for borrower in ("Kestrel Tools Pvt Ltd", "Heronbay Polymers Pvt Ltd")]
    for case_id in both:
        left = _left(client, analyst, root, case_id, "BR-01", SHORTFALL)
        assert all(left.values()), left
        assert _attention(client, analyst, case_id) == 1

    # Switched off as authored, published through the command line: both cases are re-run at once.
    capsys.readouterr()
    assert cli.main(["config", "publish", "--author", "test", "--note", "BR-01 off", "--data-root", str(root)]) == 0
    out, err = capsys.readouterr()
    assert f'"version": "{reader.published_version(root)["version"]}"' in out and not err
    assert out.strip().splitlines()[-1] == "re-ran the checks of 2 case(s)"
    for case_id in both:
        assert _left(client, analyst, root, case_id, "BR-01", SHORTFALL, refresh=False) == NOTHING
        board = _board(client, analyst, case_id)
        assert (board["blocked"], board["first_blocking"], board["run"]["rules"]) == (False, None, 24)
        assert _attention(client, analyst, case_id) == 0

    # With --no-rerun, a case keeps its last run's findings until it runs again.
    _publish(root, monkeypatch, "BR-01")
    _refresh(root, both[0])
    assert cli.main(["config", "publish", "--author", "test", "--no-rerun", "--data-root", str(root)]) == 0
    assert "re-ran" not in capsys.readouterr().out
    assert _left(client, analyst, root, both[0], "BR-01", SHORTFALL, refresh=False)["findings"]
    assert _left(client, analyst, root, both[0], "BR-01", SHORTFALL) == NOTHING


def test_publishing_with_no_case_store_yet_reruns_nothing(tmp_path, capsys):
    assert cli.main(["config", "publish", "--author", "test", "--data-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "re-ran the checks of 0 case(s): no case store yet"
    assert not db.db_path(tmp_path).exists()


def _every_family(client: TestClient, analyst: dict, root: Path) -> str:
    """Documents for every family of checks, with discrepancies among them: two PANs and two CINs, a
    director without KYC; GST, bank credits and the books apart; a declared account without a
    statement; instalments and a bureau facility nobody declared; a tax return; and a board resolution
    and two years of statements for the six switched off."""
    case_id = make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd", amount_inr=65_000_000, header={
        "promoters": {"value": "Tarun Velankar; Ishita Barve", "source": "person"},
        "declared_turnover_inr": {"value": "60000000", "source": "person"},
        "existing_banking": {"value": "Current account with Lotuscrest Bank a/c 90100005678", "source": "person"}})
    add_doc(root, case_id, "company_pan", {"pan": "AAACK1234F", "company_name": "Kestrel Tools Pvt Ltd"})
    add_doc(root, case_id, "income_tax_return", {
        "pan": "AAACK9876Q", "taxpayer_name": "Kestrel Tools Pvt Ltd", "assessment_year": "2025-26",
        "income_computation": [{"particulars": "Profit as per profit and loss account", "amount": 6_000_000}]})
    add_doc(root, case_id, "certificate_of_incorporation",
            {"cin": "U28990MH2015PTC123456", "date_of_incorporation": "2015-06-01", "company_name": CO})
    add_doc(root, case_id, "memorandum_articles_of_association", {
        "cin": "U28990MH2015PTC123465",
        "directors": [{"name": "Tarun Velankar", "din": "01234567"}, {"name": "Sunil Karve"}]})
    add_doc(root, case_id, "director_kyc", {"person_name": "Tarun Velankar", "din": "01234567", "pan": "ABCPV1234K"})
    add_doc(root, case_id, "director_kyc", {"person_name": "Ishita Barve", "din": "07654321"})
    add_doc(root, case_id, "board_resolution_borrowing", {
        "borrowing_limit": 20_000_000, "authorized_persons": ["Tarun Velankar"],
        "lender_name": "Lotuscrest Bank Limited", "resolution_date": "2025-06-10"})
    audited(root, case_id, "2026-03-31", scale=40_000_000 / 118_000_000)
    audited(root, case_id, "2025-03-31", scale=0.25)
    for period in PERIODS:
        gstr(root, case_id, period, 4_000_000)
    bank(root, case_id, [{"date": f"{ym}-15", "description": "NEFT CR CUSTOMER RECEIPT", "credit": 3_200_000}
                         for ym in FY26]
         + [{"date": f"{ym}-05", "description": "NACH DR TIDEWATER FIN", "debit": 250_000} for ym in FY26])
    add_doc(root, case_id, "existing_facilities_declaration", {
        "company_name": CO, "declaration_date": "2026-09-15", "facilities": [LOTUSCREST], "bank_accounts": []})
    add_doc(root, case_id, "commercial_bureau_report", {
        "company_name": CO, "pan": "AAACK1234F", "report_date": "2026-09-20", "credit_rank": "4",
        "credit_facilities": [{**f, "overdue": 0, "status": "Standard"} for f in (TIDEWATER, LOTUSCREST)],
        "related_parties": []})
    return case_id


def _evaluated(root: Path, case_id: str) -> dict[str, dict]:
    """The case's findings under the published rules, by finding id: what each rule decided."""
    conn = db.connect(root)
    try:
        case = cases.get_case(conn, case_id)
        found = crosschecks.evaluate(root, case, facts.compute(conn, root, case))
    finally:
        conn.close()
    return {f.id: f.model_dump(include=RULE_FIELDS) for f in found}


def test_switching_the_six_off_leaves_the_other_twenty_four_as_they_are(
        client, analyst, published_data_root, monkeypatch):
    """With the six switched off, each of the other 24 rules gives exactly what it gives with every
    rule on: the same findings, each with the same outcome, explanation, sides, line-by-line detail and
    missing documents (and severity, blocking, tolerance and query), on a case with documents for every
    family of checks and on one with none. (The cards play no part in what a rule decides.)"""
    monkeypatch.setattr(xv_cards, "BUILDERS", {})
    root = published_data_root
    every_family = _every_family(client, analyst, root)
    nothing_on_file = make_case(client, analyst, root, borrower="Heronbay Polymers Pvt Ltd")
    enabled = {r.id for r in reader.load_crosschecks(root).enabled_rules}
    assert len(enabled) == 24 and not enabled & SWITCHED_OFF
    switched_off = {c: _evaluated(root, c) for c in (every_family, nothing_on_file)}
    _publish(root, monkeypatch, *SWITCHED_OFF)
    every_rule = {c: _evaluated(root, c) for c in (every_family, nothing_on_file)}
    for case_id in (every_family, nothing_on_file):
        assert {f["rule_id"] for f in switched_off[case_id].values()} == enabled
        assert {f["rule_id"] for f in every_rule[case_id].values()} == enabled | SWITCHED_OFF
        assert {i: f for i, f in every_rule[case_id].items() if f["rule_id"] in enabled} == switched_off[case_id]
    # The documents put the checks to work: discrepancies in each of the four areas, checks that pass,
    # and discrepancies among the six when they run.
    outcomes = {(f["area"], f["outcome"]) for f in switched_off[every_family].values()}
    assert {(area, "fail") for area in ("identity", "turnover", "accounts", "obligations")} <= outcomes
    assert any(outcome == "pass" for _, outcome in outcomes)
    assert "fail" in {f["outcome"] for f in every_rule[every_family].values() if f["rule_id"] in SWITCHED_OFF}
