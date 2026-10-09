"""F-10: label mismatch (TC-07) and party attribution (TC-08)."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ANALYST, RM, case_files, fixture_file, make_case, run_jobs, sign_in, upload

PARTIAL = [n for n, _ in case_files("partial")]


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
    rm, case_id = _case(client, published_data_root, PARTIAL + ["bank statement apr-mar.pdf"])
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
    assert _doc_of(client, rm, case_id, "heronbay audited fy2026.pdf")["label_mismatch"] is False


def test_tc08_swapped_kyc_is_reattributed_and_flagged(client: TestClient, published_data_root: Path):
    rm, case_id = _case(client, published_data_root, PARTIAL + ["Tarun Velankar PAN.pdf"])
    parties = {p["name"]: p for p in client.get(f"/api/cases/{case_id}/parties", headers=rm).json()}
    assert parties["Tarun Velankar"]["role"] == "director"
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
    rm, case_id = _case(client, published_data_root, PARTIAL + ["Sunil Karve PAN.pdf"])
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


def test_f10_a_directors_din_from_the_memorandum_joins_the_party(client: TestClient, published_data_root: Path):
    rm, case_id = _case(client, published_data_root, PARTIAL + ["kestrel memorandum and articles.pdf"])
    parties = {p["name"]: p for p in client.get(f"/api/cases/{case_id}/parties", headers=rm).json()}
    # The resolution names the directors; the memorandum's list adds each one's DIN, and the two are one party.
    assert len([p for p in parties.values() if p["role"] != "borrower"]) == 2
    assert parties["Tarun Velankar"]["din"] == "01234567" and parties["Ishita Barve"]["din"] == "07654321"


def _flip_identity(root: Path, doc_id: str, **changes) -> None:
    """Rewrite what a document's identity block says, then rebuild attribution."""
    import json

    from engine import db, parties

    conn = db.connect(root)
    try:
        identity = json.loads(conn.execute("SELECT identity FROM documents WHERE id = ?", (doc_id,)).fetchone()["identity"])
        identity.update(changes)
        conn.execute("UPDATE documents SET identity = ? WHERE id = ?", (json.dumps(identity), doc_id))
        case_id = conn.execute("SELECT case_id FROM documents WHERE id = ?", (doc_id,)).fetchone()["case_id"]
        parties.refresh(conn, root, case_id)
    finally:
        conn.close()


def test_identifier_and_printed_name_naming_different_people_is_a_conflict(client, published_data_root):
    rm, case_id = _case(client, published_data_root, [n for n, _ in case_files("complete")])
    parties_by_name = {p["name"]: p for p in client.get(f"/api/cases/{case_id}/parties", headers=rm).json()}
    ishita_doc = parties_by_name["Ishita Barve"]["kyc_document_ids"][0]
    # Ishita's PAN and DIN, Tarun's name.
    _flip_identity(published_data_root, ishita_doc, name="Tarun Velankar")
    doc = next(d for d in client.get(f"/api/cases/{case_id}/documents", headers=rm).json() if d["id"] == ishita_doc)
    assert doc["party_id"] == parties_by_name["Ishita Barve"]["id"]  # the identifier's party is proposed
    analyst = sign_in(client, ANALYST)
    flags = [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json() if i["kind"] == "party"]
    assert len(flags) == 1
    assert "PAN matches Ishita Barve but the name printed is Tarun Velankar" in flags[0]["summary"]
    queries = [q["text"] for q in client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
               if q["source_kind"] == "party" and not q["resolved"]]
    assert len(queries) == 1 and "identity number of Ishita Barve but the name of Tarun Velankar" in queries[0]


def test_identifier_match_with_an_unrelated_name_is_not_a_conflict(client, published_data_root):
    rm, case_id = _case(client, published_data_root, [n for n, _ in case_files("complete")])
    parties_by_name = {p["name"]: p for p in client.get(f"/api/cases/{case_id}/parties", headers=rm).json()}
    ishita_doc = parties_by_name["Ishita Barve"]["kyc_document_ids"][0]
    _flip_identity(published_data_root, ishita_doc, name="Tarun Velankar")
    # An unrelated name with a matching PAN is not a conflict: no second person is named.
    _flip_identity(published_data_root, ishita_doc, name="Zzyzx Qwerty")
    analyst = sign_in(client, ANALYST)
    flags = [i for i in client.get(f"/api/review?case_id={case_id}", headers=analyst).json() if i["kind"] == "party"]
    assert flags == []


def test_a_parallel_din_list_gives_each_named_person_a_din_only_when_counts_agree():
    from engine.configstore.schema import PartyList
    from engine.parties import party_entries

    spec = PartyList(field="authorized_persons", din_field="authorized_person_dins", role="director")
    fields = {"authorized_persons[0]": ("A Rao", 1), "authorized_persons[1]": ("B Nair", 1),
              "authorized_person_dins[0]": ("01234567", 1), "authorized_person_dins[1]": ("07654321", 1)}
    assert [e["din"] for e in party_entries(fields, spec)] == ["01234567", "07654321"]
    # One person without a printed DIN: the lists cannot be paired, so none is trusted.
    del fields["authorized_person_dins[1]"]
    assert [e["din"] for e in party_entries(fields, spec)] == [None, None]
