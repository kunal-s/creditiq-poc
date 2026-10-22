"""An edit of a statement line stands in place of the printed figure for every reader of the statement lines,
is entered in the statement's unit, keeps the document's figure and a reason, and can be put back."""

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

from tests.conftest import ANALYST, RM, make_case, sign_in  # noqa: E402
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


def test_every_statement_line_says_how_it_was_read_and_can_be_edited(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    spread = client.get(f"/api/cases/{case_id}/spread", headers=analyst).json()
    cell = _row(spread, "trade_payables")["cells"][0]
    assert cell["working"]["state"] == "printed" and cell["working"]["source"]["row_label"]
    assert cell["working"]["target"]["line"] == "trade_payables"
    ratio = _row(spread, "current-ratio")["cells"][0]["working"]
    assert ratio["state"] == "ratio" and [i["key"] for i in ratio["inputs"]] == ["current_assets", "current_liabilities"]
    assert ratio["inputs"][1]["parts"], "a sum is followed down to the lines it adds"
    # A ratio and a derived line are worked out, never typed over.
    assert _row(spread, "net_working_capital")["cells"][0]["working"]["target"] is None


def test_an_edit_flows_through_the_ratios_and_keeps_the_documents_figure(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    before = _payables(client, analyst, case_id)
    target = before["working"]["target"]
    body = {**target, "value": before["value"] + 10_000_000, "reason": "Sheet shows a note adding to this line"}
    response = client.post(f"/api/cases/{case_id}/statement-edits", json=body, headers=analyst)
    assert response.status_code == 201, response.text
    after = _payables(client, analyst, case_id)
    assert after["value"] == before["value"] + 10_000_000 and after["relies_on_manual"] is True
    edit = after["working"]["edit"]
    assert (edit["original"], edit["reason"]) == (before["value"], body["reason"]) and edit["edited_by"]
    spread = client.get(f"/api/cases/{case_id}/spread", headers=analyst).json()
    assert _row(spread, "current_liabilities")["cells"][0]["value"] > 0
    assert _row(spread, "current-ratio")["cells"][0]["value"] < 1.59   # the norms and ratios follow the edit


def test_an_edit_needs_a_reason_a_real_line_and_the_permission(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    target = _payables(client, analyst, case_id)["working"]["target"]
    url = f"/api/cases/{case_id}/statement-edits"
    assert client.post(url, json={**target, "value": 1, "reason": " "}, headers=analyst).status_code == 422
    assert client.post(url, json={**target, "line": "current_ratio", "value": 1, "reason": "why"}, headers=analyst).status_code == 422
    assert client.post(url, json={**target, "line": "net_worth", "value": 1, "reason": "why"}, headers=analyst).status_code == 422
    assert client.post(url, json={**target, "value": 1, "reason": "because"}, headers=sign_in(client, RM)).status_code == 403


def test_putting_the_documents_figure_back_keeps_the_history(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    before = _payables(client, analyst, case_id)
    url = f"/api/cases/{case_id}/statement-edits"
    first = client.post(url, json={**before["working"]["target"], "value": 5, "reason": "first try"}, headers=analyst).json()
    second = client.post(url, json={**before["working"]["target"], "value": 7, "reason": "second try"}, headers=analyst).json()
    assert _payables(client, analyst, case_id)["working"]["edit"]["id"] == second["id"]
    assert client.post(f"{url}/{first['id']}/revert", json={"reason": "stale"}, headers=analyst).status_code == 409
    assert client.post(f"{url}/{second['id']}/revert", json={"reason": "document is right"}, headers=analyst).status_code == 204
    back = _payables(client, analyst, case_id)
    assert back["value"] == before["value"] and back["working"]["edit"] is None


def test_the_policy_norms_follow_an_edit_and_say_so(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)

    def current_ratio():
        norms = client.get(f"/api/cases/{case_id}/policy", headers=analyst).json()["norms"]
        return next(n for n in norms if n["family"] == "ratios" and "Current assets" in n["formula"])

    before = current_ratio()
    payables = _payables(client, analyst, case_id)
    client.post(f"/api/cases/{case_id}/statement-edits", headers=analyst,
                json={**payables["working"]["target"], "value": payables["value"] + 20_000_000, "reason": "a note adds to it"})
    after = current_ratio()
    assert after["actual"] < before["actual"]
    liabilities = next(i for i in after["inputs"] if i["name"] == "current_liabilities")
    assert liabilities["relies_on_manual"] and liabilities["working"]["state"] == "derived"
    assert any(p["state"] == "edited" for p in liabilities["working"]["inputs"])


def test_the_memo_says_which_figures_rest_on_an_edit(client: TestClient, published_data_root: Path):
    analyst, case_id = _setup(client, published_data_root)
    payables = _payables(client, analyst, case_id)
    client.post(f"/api/cases/{case_id}/statement-edits", headers=analyst,
                json={**payables["working"]["target"], "value": payables["value"] + 1_000_000, "reason": "a note adds to it"})
    cam = client.get(f"/api/cases/{case_id}/cam", headers=analyst).json()
    text = " ".join(b["paragraph"]["text"] for s in cam["sections"] for b in s["blocks"] if b.get("paragraph"))
    assert "Trade payables for" in text and "a note adds to it" in text and "the statements give" in text
