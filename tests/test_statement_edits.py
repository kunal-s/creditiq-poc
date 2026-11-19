"""A statement figure is changed on the Extractions tab only: the Credit Analyst changes the extracted value, the
Credit Manager approves it, and every reader of the statement lines (the spread, the norms, the cross-checks, the
memo) follows, with a record of what the change moved. An edit made directly on a statement line before stands in
place of the printed figure, in the statement's unit, and can still be put back; a new one is refused."""

import pytest
from fastapi.testclient import TestClient

from engine import statements
from engine.facts import Doc, StatementEdit, Value

from tests.test_statement_units import _cfg, _statement


def _with_edit(doc, line, value, column="current_period"):
    doc.edits = {(line, column): StatementEdit("SE-1", line, column, None, value, "typo on the sheet", "usr-1", "2026-10-22T10:00:00Z")}
    return doc


def test_an_edit_replaces_a_printed_figure_and_is_scaled_like_it():
    doc = _with_edit(_statement([("(b) Trade receivables", 100)]), "trade_receivables", 250)
    doc.get = lambda name: type("V", (), {"value": "Thousands"})() if name == "amount_unit" else None
    line = statements.lines(doc, _cfg([]))["trade_receivables"]
    assert (line.value, line.printed, line.state, line.manual) == (250_000, 250, "edited", True)
    assert line.edit.reason == "typo on the sheet"


def test_an_edit_supplies_a_line_the_statement_never_printed_so_the_derived_line_completes():
    doc = _with_edit(_statement([("(b) Trade receivables", 100)]), "inventories", 40)
    lines = statements.lines(doc, _cfg([]))
    assert lines["inventories"].state == "edited" and lines["current_assets"].value == 140


def test_an_edit_only_applies_to_its_own_column():
    doc = _with_edit(_statement([("(b) Trade receivables", 100)]), "trade_receivables", 9, column="previous_period")
    assert statements.lines(doc, _cfg([]))["trade_receivables"].state == "printed"


# --- Through the API ---

from pathlib import Path  # noqa: E402

from tests.conftest import ANALYST, MANAGER, RM, make_case, sign_in  # noqa: E402
from tests.triangulation import audited  # noqa: E402


def _row(spread, key):
    return next(r for r in spread["rows"] if r["key"] == key)


def _setup(client, root):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, root)
    audited(root, case_id)
    return analyst, case_id


def _payables(client, headers, case_id):
    return _row(client.get(f"/api/cases/{case_id}/spread", headers=headers).json(), "trade_payables")["cells"][0]


def _change(client, analyst, manager, case_id, field_id, value, reason="Auditor's letter revises this line"):
    """The Credit Analyst changes the extracted value; the Credit Manager approves it."""
    r = client.post(f"/api/cases/{case_id}/fields/{field_id}/edit", headers=analyst,
                    files=[("value", (None, str(value))), ("reason", (None, reason))])
    assert r.status_code == 200, r.text
    ok = client.post(f"/api/review/{r.json()['id']}/decision", json={"decision": "confirm"}, headers=manager)
    assert ok.status_code == 200, ok.text


def test_every_statement_line_says_where_it_was_read_and_is_changed_on_extractions(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    spread = client.get(f"/api/cases/{case_id}/spread", headers=analyst).json()
    cell = _row(spread, "trade_payables")["cells"][0]
    source = cell["working"]["source"]
    assert cell["working"]["state"] == "printed" and source["row_label"] and source["page"]
    assert source["field_id"] and source["line"], "the figure names the extracted value and the line it was read from"
    assert source["file_name"], "and the file it was read from"
    assert cell["working"]["target"] is None, "a statement figure is not edited on the financials"
    ratio = _row(spread, "current-ratio")["cells"][0]["working"]
    assert ratio["state"] == "ratio" and [i["key"] for i in ratio["inputs"]] == ["current_assets", "current_liabilities"]
    assert ratio["inputs"][1]["parts"], "a sum is followed down to the lines it adds"
    assert all(p["source"]["field_id"] for p in ratio["inputs"][1]["parts"] if p["state"] == "printed")
    assert _row(spread, "net_working_capital")["cells"][0]["working"]["target"] is None
    # A figure the spread works out itself (a margin, a total) traces each statement line it rests on.
    tol = _row(spread, "tol")["cells"][0]["working"]
    borrowings = next(i for i in tol["inputs"] if i["key"] == "long_term_borrowings")
    assert borrowings["source"]["field_id"] and borrowings["source"]["page"]
    assert next(i for i in tol["inputs"] if i["key"] == "current_liabilities")["parts"]
    assert tol["state"] == "derived"   # a sum is added up
    assert _row(spread, "ebitda_margin")["cells"][0]["working"]["state"] == "ratio"   # a margin is divided out


def test_a_statement_line_is_not_edited_directly(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    body = {"document_id": "any", "line": "trade_payables", "value": 1, "reason": "a typo on the sheet"}
    r = client.post(f"/api/cases/{case_id}/statement-edits", json=body, headers=analyst)
    assert r.status_code == 409 and "Extractions tab" in r.json()["detail"]


def test_an_approved_change_flows_through_the_figures_and_is_recorded(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    manager = sign_in(client, MANAGER)

    def current_ratio():
        norms = client.get(f"/api/cases/{case_id}/policy", headers=analyst).json()["norms"]
        return next(n for n in norms if n["family"] == "ratios" and "Current assets" in n["formula"])

    before, ratio_before = _payables(client, analyst, case_id), current_ratio()
    source = before["working"]["source"]
    _change(client, analyst, manager, case_id, source["field_id"], source["printed_value"] + 2_000)
    after = _payables(client, analyst, case_id)
    assert after["value"] == before["value"] + 2_000 * source["scale"] and after["relies_on_manual"] is True
    assert after["working"]["source"]["changed"] is True
    assert after["working"]["source"]["document_value"] == source["printed_value"], "the statement's own figure stays beside it"
    ratio_after = current_ratio()
    assert ratio_after["actual"] < ratio_before["actual"], "the norms follow the change"
    liabilities = next(i for i in ratio_after["inputs"] if i["name"] == "current_liabilities")
    assert liabilities["relies_on_manual"] and liabilities["working"]["state"] == "derived"

    history = client.get(f"/api/cases/{case_id}/recalculations", headers=analyst).json()
    assert len(history) == 1
    rec = history[0]
    assert rec["trigger"]["field_value_id"] == source["field_id"] and rec["trigger"]["label"].endswith("current year")
    assert rec["trigger"]["changed_by"] and rec["approved_by"] and rec["trigger"]["file_name"]
    moved = {(c["area"], c["key"]) for c in rec["changes"]}
    assert ("figure", "trade_payables") in moved and ("figure", "current_liabilities") in moved
    payables = next(c for c in rec["changes"] if c["key"] == "trade_payables")
    assert (payables["before"], payables["after"]) == (before["value"], after["value"])


def test_a_change_sent_back_recalculates_nothing(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    manager = sign_in(client, MANAGER)
    source = _payables(client, analyst, case_id)["working"]["source"]
    r = client.post(f"/api/cases/{case_id}/fields/{source['field_id']}/edit", headers=analyst,
                    files=[("value", (None, "12345")), ("reason", (None, "Auditor's letter revises this line"))])
    client.post(f"/api/review/{r.json()['id']}/decision", json={"decision": "waive", "reason": "letter is for another year"},
                headers=manager)
    assert client.get(f"/api/cases/{case_id}/recalculations", headers=analyst).json() == []


def test_the_memo_says_which_figures_rest_on_a_change(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    manager = sign_in(client, MANAGER)
    source = _payables(client, analyst, case_id)["working"]["source"]
    _change(client, analyst, manager, case_id, source["field_id"], source["printed_value"] + 100)
    cam = client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()
    text = " ".join(b["paragraph"]["text"] for s in cam["sections"] for b in s["blocks"] if b.get("paragraph"))
    assert "Trade payables for" in text and "changed and approved on the Extractions tab" in text
    assert "the statements give" in text


def test_a_failed_recalculation_record_leaves_the_approval_in_force(client: TestClient, published_data_root: Path,
                                                                   monkeypatch: pytest.MonkeyPatch):
    from engine import recalculation

    analyst, case_id = _setup(client, published_data_root)
    manager = sign_in(client, MANAGER)
    source = _payables(client, analyst, case_id)["working"]["source"]

    def broken(*_args, **_kwargs):
        raise RuntimeError("the record could not be written")

    monkeypatch.setattr(recalculation, "record", broken)
    _change(client, analyst, manager, case_id, source["field_id"], source["printed_value"] + 500)
    assert _payables(client, analyst, case_id)["working"]["source"]["changed"] is True
    assert client.get(f"/api/cases/{case_id}/recalculations", headers=analyst).json() == []
