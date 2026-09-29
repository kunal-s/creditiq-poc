"""F-10: label mismatch (TC-07) and party attribution (TC-08)."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, RM, fixture_file, make_case, run_jobs, sign_in, upload


def _case(client: TestClient, root: Path, names: list[str]) -> tuple[dict, str]:
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, root, borrower="Heronbay Polymers Pvt Ltd", facilities=["cash_credit"],
                        amount_inr=30000000, collateral_present=False)
    upload(client, rm, case_id, [(n, fixture_file(n)) for n in names])
    run_jobs(root)
    return rm, case_id


def _doc_of(client, headers, case_id, file_name):
    files = {f["id"]: f for f in client.get(f"/api/cases/{case_id}/files", headers=headers).json()}
    docs = client.get(f"/api/cases/{case_id}/documents", headers=headers).json()
    return next(d for d in docs if files[d["file_id"]]["original_name"] == file_name)


def test_tc07_balance_sheet_named_as_bank_statement_is_classified_and_reported(client, published_data_root):
    rm, case_id = _case(client, published_data_root, ["partial_bundle.pdf", "bank statement apr-mar.pdf"])
    doc = _doc_of(client, rm, case_id, "bank statement apr-mar.pdf")
    # Classified by content, never by the name (F-09.1)...
    assert doc["classification"]["types"] == ["audited_financial_statements"]
    # ...and the disagreement with the label is reported (F-10.1).
    assert doc["label_mismatch"] is True
    files = client.get(f"/api/cases/{case_id}/files", headers=rm).json()
    hint = next(f for f in files if f["original_name"] == "bank statement apr-mar.pdf")["label_hint"]
    assert hint == "bank statement apr mar"
    # It satisfies what it is, not what it is called.
    items = {i["item_id"]: i for i in client.get(f"/api/cases/{case_id}/checklist", headers=rm).json()["items"]}
    assert doc["id"] in items["fs_fy_minus2"]["document_ids"]
    assert doc["id"] not in items["bank_statements"]["document_ids"]
    # A file whose name agrees with its content is not flagged.
    bundle = _doc_of(client, rm, case_id, "partial_bundle.pdf")
    assert bundle["label_mismatch"] is False


def test_tc08_swapped_kyc_is_reattributed_and_flagged(client: TestClient, published_data_root: Path):
    rm, case_id = _case(client, published_data_root, ["partial_bundle.pdf", "Tarun Velankar PAN.pdf"])
    parties = {p["name"]: p for p in client.get(f"/api/cases/{case_id}/parties", headers=rm).json()}
    assert parties["Tarun Velankar"]["role"] == "director" and parties["Tarun Velankar"]["din"] == "01234567"
    assert parties["Ishita Barve"]["source"].startswith("document:")
    swapped = _doc_of(client, rm, case_id, "Tarun Velankar PAN.pdf")
    # Filed under the person it belongs to, not the one the label names.
    assert swapped["party_id"] == parties["Ishita Barve"]["id"]
    assert swapped["id"] in parties["Ishita Barve"]["kyc_document_ids"]
    assert swapped["id"] not in parties["Tarun Velankar"]["kyc_document_ids"]
    analyst = sign_in(client, ANALYST)
    flags = [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json() if i["kind"] == "party"]
    assert len(flags) == 1
    assert "labelled Tarun Velankar" in flags[0]["summary"] and "filed under Ishita Barve" in flags[0]["summary"]
    # KYC is now complete for both directors (F-10.4).
    items = {i["item_id"]: i for i in client.get(f"/api/cases/{case_id}/checklist", headers=rm).json()["items"]}
    assert items["kyc_promoters"]["status"] == "satisfied"


def test_tc08_kyc_matching_no_party_may_not_belong(client: TestClient, published_data_root: Path):
    rm, case_id = _case(client, published_data_root, ["partial_bundle.pdf", "Sunil Karve PAN.pdf"])
    stranger = _doc_of(client, rm, case_id, "Sunil Karve PAN.pdf")
    assert stranger["party_id"] is None
    analyst = sign_in(client, ANALYST)
    flags = [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json() if i["kind"] == "party"]
    assert len(flags) == 1 and "may not belong to this case" in flags[0]["summary"]
    # A person confirms or overrides the attribution, with a reason (F-10.5).
    parties = {p["name"]: p for p in client.get(f"/api/cases/{case_id}/parties", headers=rm).json()}
    decided = client.post(
        f"/api/review/{flags[0]['id']}/decision",
        json={"decision": "correct", "value": parties["Tarun Velankar"]["id"], "reason": "Guarantor's KYC, filed in error"},
        headers=analyst,
    )
    assert decided.status_code == 200 and decided.json()["status"] == "decided"
    assert _doc_of(client, rm, case_id, "Sunil Karve PAN.pdf")["party_id"] == parties["Tarun Velankar"]["id"]
    # The party clarification is now resolved on the query list.
    queries = client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
    party_q = [q for q in queries if q["source_kind"] == "party"]
    assert party_q and all(q["resolved"] for q in party_q)


def test_f10_parties_endpoint_permissions(client: TestClient, published_data_root: Path):
    analyst = sign_in(client, ANALYST)
    case_id = make_case(client, analyst, published_data_root)
    assert client.get(f"/api/cases/{case_id}/parties").status_code == 401
    # An RM does not see another RM's case, not even its existence.
    assert client.get(f"/api/cases/{case_id}/parties", headers=sign_in(client, RM)).status_code == 404
    parties = client.get(f"/api/cases/{case_id}/parties", headers=analyst).json()
    assert [p["role"] for p in parties] == ["borrower"]
