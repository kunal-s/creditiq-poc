"""Product-first intake (plan 2026-11-27, section 14): a loan against property (LAP) and a business
banking (BBG) case, each with its own form, minimum, identifiers and case-number prefix, created
together with its files in one request (POST /api/cases/intake) or not at all."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db
from engine.store import MESSAGE_FILE_NAME, cases_dir
from tests.conftest import ANALYST, MANAGER, RM, fixture_file, new_case, sign_in

PDF = "kestrel pan.pdf"
OTHER_PDF = "kyc ishita barve.pdf"


def _cell(value: str, source: str = "person") -> dict:
    return {"value": value, "proposed": None, "source": source}


def _lap(**overrides) -> dict:
    """A loan against property: a salaried applicant and a co-applicant, one residential property."""
    body = {
        "product": "lap",
        "channel": "email",
        "customer_type": "salaried",
        "case_type": "new",
        "program": "income",
        "amount_inr": 4500000,
        "tenure_months": 180,
        "pan": "ABCPK1234F",
        "groups": {
            "applicants": [
                {"name": _cell("Rohan Kulkarni"), "role": _cell("applicant"),
                 "pan": _cell("ABCPK1234F", "identifier"), "income_considered": _cell("yes"),
                 "property_owner": _cell("yes"), "aadhaar_last4": _cell("4821")},
                {"name": _cell("Meera Kulkarni"), "role": _cell("co_applicant"), "relationship": _cell("spouse"),
                 "pan": _cell("BCDPK5678G"), "property_owner": _cell("yes")},
            ],
            "properties": [
                {"property_type": _cell("residential"), "occupancy": _cell("self_occupied"),
                 "pincode": _cell("411038"), "owners": _cell("Rohan Kulkarni; Meera Kulkarni"),
                 "declared_value_inr": _cell("9500000"), "construction": _cell("complete")},
            ],
        },
    }
    body.update(overrides)
    return body


def _bbg(**overrides) -> dict:
    body = new_case(product="bbg", collateral_present=False)
    body.update(overrides)
    return body


def _parts(case: dict | str, files: list[tuple[str, bytes]] | None = None) -> list:
    """The multipart body: the case as a JSON field (no file name) and the files."""
    part = case if isinstance(case, str) else json.dumps(case)
    files = [(PDF, fixture_file(PDF))] if files is None else files
    return [("case", (None, part, "application/json")),
            *[("files", (name, data, "application/octet-stream")) for name, data in files]]


def _intake(client: TestClient, headers: dict, case: dict | str, files: list[tuple[str, bytes]] | None = None):
    return client.post("/api/cases/intake", files=_parts(case, files), headers=headers)


def _no_case_left(root: Path) -> None:
    conn = db.connect(root)
    try:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
    finally:
        conn.close()
    folder = cases_dir(root)
    assert not folder.exists() or not any(folder.iterdir())
    spool = root / "intake-spool"
    assert not spool.exists() or not any(spool.iterdir())


@pytest.fixture()
def rm(client: TestClient) -> dict:
    return sign_in(client, RM)


# --- Creating a case with its files ---


def test_a_lap_case_is_created_with_its_applicants_property_and_files(client, rm, published_data_root):
    r = _intake(client, rm, _lap())
    assert r.status_code == 201, r.text
    case, upload = r.json()["case"], r.json()["upload"]
    assert re.fullmatch(r"LAP-\d{4}-000001", case["id"])
    assert (case["product"], case["customer_type"], case["program"], case["tenure_months"]) == (
        "lap", "salaried", "income", 180)
    # The borrower is the primary applicant, recorded with where the name came from.
    assert case["borrower"] == "Rohan Kulkarni" and case["header"]["borrower"]["source"] == "person"
    # Each row keeps every field's provenance (F-01.2).
    applicants = case["groups"]["applicants"]
    assert [a["name"]["value"] for a in applicants] == ["Rohan Kulkarni", "Meera Kulkarni"]
    assert applicants[0]["pan"] == {"value": "ABCPK1234F", "proposed": None, "source": "identifier"}
    assert case["groups"]["properties"][0]["property_type"]["value"] == "residential"
    # The file was stored with the case and queued for processing.
    assert [f["status"] for f in upload["files"]] == ["registered"] and upload["job_id"]
    files = client.get(f"/api/cases/{case['id']}/files", headers=rm).json()
    assert [f["original_name"] for f in files] == [PDF]
    assert (cases_dir(published_data_root) / case["id"] / "files" / files[0]["sha256"]).is_file()


def test_lap_applicants_become_the_case_parties(client, rm):
    case = _intake(client, rm, _lap()).json()["case"]
    parties = {p["name"]: p for p in client.get(f"/api/cases/{case['id']}/parties", headers=rm).json()}
    # The primary applicant is the borrower: one party, whose own KYC is asked for.
    assert set(parties) == {"Rohan Kulkarni", "Meera Kulkarni"}
    assert parties["Rohan Kulkarni"]["role"] == "applicant" and parties["Rohan Kulkarni"]["pan"] == "ABCPK1234F"
    assert parties["Meera Kulkarni"]["role"] == "co_applicant" and parties["Meera Kulkarni"]["source"] == "intake"
    assert parties["Meera Kulkarni"]["pan"] == "BCDPK5678G"


def test_a_bbg_case_without_a_message_has_no_message_document(client, rm, published_data_root):
    r = _intake(client, rm, _bbg(header={"borrower": _cell("Example Tools Pvt Ltd")}))
    assert r.status_code == 201, r.text
    case = r.json()["case"]
    assert re.fullmatch(r"BBG-\d{4}-\d{6}", case["id"])
    names = [f["original_name"] for f in client.get(f"/api/cases/{case['id']}/files", headers=rm).json()]
    assert MESSAGE_FILE_NAME not in names
    assert {h["source"].split(":")[0] for h in case["header"].values()} <= {"person", "default"}


def test_bbg_people_become_parties_from_the_form(client, rm):
    body = _bbg(groups={"people": [{"name": _cell("Tarun Velankar"), "role": _cell("director"),
                                    "din": _cell("01234567")}]})
    case = _intake(client, rm, body).json()["case"]
    parties = client.get(f"/api/cases/{case['id']}/parties", headers=rm).json()
    person = next(p for p in parties if p["name"] == "Tarun Velankar")
    assert (person["role"], person["din"], person["source"]) == ("director", "01234567", "intake")
    assert any(p["role"] == "borrower" for p in parties)


def test_bbg_facility_lines_give_the_facilities_and_amount(client, rm):
    lines = [{"facility": _cell("cash_credit"), "amount_inr": _cell("5000000")},
             {"facility": _cell("term_loan"), "amount_inr": _cell("2,500,000"), "tenure_months": _cell("60")}]
    case = _intake(client, rm, _bbg(facilities=[], amount_inr=0, groups={"facilities": lines})).json()["case"]
    assert case["facilities"] == ["cash_credit", "term_loan"] and case["amount_inr"] == 7500000


def test_each_prefix_counts_its_own_sequence(client, rm):
    ids = [
        _intake(client, rm, _bbg()).json()["case"]["id"],
        _intake(client, rm, _lap()).json()["case"]["id"],
        _intake(client, rm, _bbg(borrower="Another Borrower Works", duplicate_override_reason="test"),
                files=[(OTHER_PDF, fixture_file(OTHER_PDF))]).json()["case"]["id"],
    ]
    assert [i.split("-")[0] for i in ids] == ["BBG", "LAP", "BBG"]
    assert [int(i[-6:]) for i in ids] == [1, 1, 2]


def test_the_creation_log_counts_fields_by_source(client, rm, published_data_root):
    case = _intake(client, rm, _lap()).json()["case"]
    conn = db.connect(published_data_root)
    try:
        rows = {r["action"]: json.loads(r["detail"]) for r in conn.execute(
            "SELECT action, detail FROM decision_log WHERE case_id = ?", (case["id"],))}
    finally:
        conn.close()
    created = rows["case.created"]
    assert created["product"] == "lap" and created["message_sha256"] is None
    assert created["fields_by_source"]["identifier"] == 1 and created["fields_by_source"]["person"] > 1
    assert created["rows"] == {"applicants": 2, "properties": 1}
    assert "ABCPK1234F" not in json.dumps(created)   # counts only, no values
    assert rows["files.uploaded"]["counts"] == {"registered": 1}


# --- What the request is refused for: nothing is left behind ---


def test_a_lap_case_without_a_property_is_refused(client, rm, published_data_root):
    body = _lap()
    body["groups"]["properties"] = []
    r = _intake(client, rm, body)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "minimum_missing" and r.json()["detail"]["missing"] == ["properties"]
    _no_case_left(published_data_root)


@pytest.mark.parametrize(("product", "drop", "missing"), [
    ("lap", "tenure_months", ["tenure_months"]),
    ("lap", "customer_type", ["customer_type"]),
    ("lap", "applicants", ["applicants"]),
    ("bbg", "facilities", ["facilities"]),
    ("bbg", "borrower", ["borrower"]),
    ("bbg", "amount_inr", ["amount_inr"]),
])
def test_each_product_enforces_its_own_minimum(client, rm, published_data_root, product, drop, missing):
    body = _lap() if product == "lap" else _bbg()
    if drop == "applicants":
        body["groups"].pop("applicants")
    else:
        body.pop(drop)
    r = _intake(client, rm, body)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["missing"] == missing
    # The direct create enforces the same minimum.
    assert client.post("/api/cases", json=body, headers=rm).status_code == 422
    _no_case_left(published_data_root)


def test_no_files_is_refused(client, rm, published_data_root):
    r = _intake(client, rm, _lap(), files=[])
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert (detail["code"], detail["min_files"], detail["registered"]) == ("too_few_files", 1, 0)
    _no_case_left(published_data_root)


def test_junk_files_only_are_refused(client, rm, published_data_root):
    r = _intake(client, rm, _lap(), files=[(".DS_Store", b"\x00\x00\x00\x01Bud1"), ("Thumbs.db", b"junk")])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "too_few_files"
    _no_case_left(published_data_root)


def test_a_repeated_file_counts_once(client, rm, published_data_root, monkeypatch):
    from engine import case_create

    monkeypatch.setattr(case_create, "min_files", lambda product: 2)
    r = _intake(client, rm, _lap(), files=[(PDF, fixture_file(PDF)), ("copy.pdf", fixture_file(PDF))])
    assert r.status_code == 422 and r.json()["detail"]["registered"] == 1
    _no_case_left(published_data_root)


def test_a_case_part_over_the_limit_is_refused_not_cut_short(client, rm, published_data_root):
    limit = client.get("/api/meta", headers=rm).json()["form_field_max_kb"]
    body = _lap(header={"nature_of_business": _cell("x" * 400)}, message_text="y" * (limit * 1024))
    r = _intake(client, rm, body)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "case_part" and f"{limit} KB" in r.json()["detail"]["message"]
    _no_case_left(published_data_root)


@pytest.mark.parametrize("part", ["", "not json", json.dumps({"channel": "email", "amount_inr": -1})])
def test_a_missing_or_malformed_case_part_is_refused(client, rm, published_data_root, part):
    r = _intake(client, rm, part)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "case_part"
    _no_case_left(published_data_root)


def test_a_storage_failure_part_way_leaves_no_case(client, rm, published_data_root, monkeypatch):
    from engine import uploads
    from engine.api import app

    def fail(self):
        raise OSError("disk full")

    with monkeypatch.context() as m:
        m.setattr(uploads.Registrar, "write", fail)
        r = TestClient(app, raise_server_exceptions=False).post("/api/cases/intake", files=_parts(_lap()), headers=rm)
    assert r.status_code == 500
    _no_case_left(published_data_root)
    # The sequence rolled back with the case: the next case takes the first number.
    assert _intake(client, rm, _lap()).json()["case"]["id"].endswith("-000001")


def test_a_duplicate_needs_a_reason(client, rm, published_data_root):
    assert _intake(client, rm, _lap(application_id="LOS-77")).status_code == 201
    again = _intake(client, rm, _lap(application_id="los-77", pan=None),
                    files=[(OTHER_PDF, fixture_file(OTHER_PDF))])
    assert again.status_code == 409
    assert _intake(client, rm, _lap(application_id="los-77", pan=None, duplicate_override_reason="separate loan"),
                   files=[(OTHER_PDF, fixture_file(OTHER_PDF))]).status_code == 201


def test_intake_needs_create_and_upload_permission(client, published_data_root):
    assert _intake(client, {}, _lap()).status_code == 401
    assert _intake(client, sign_in(client, MANAGER), _lap()).status_code == 403
    assert _intake(client, sign_in(client, ANALYST), _lap()).status_code == 201


# --- Identifiers ---


def test_an_individual_pan_is_refused_as_a_company_pan(client, rm, published_data_root):
    r = _intake(client, rm, _bbg(constitution="private_limited", pan="ABCPK1234F"))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "identifier_invalid"
    _no_case_left(published_data_root)


def test_an_individual_pan_is_a_proprietorship_pan(client, rm):
    r = _intake(client, rm, _bbg(constitution="proprietorship", pan="ABCPK1234F"))
    assert r.status_code == 201, r.text
    assert r.json()["case"]["customer_type"] == "proprietorship"


def test_a_lap_applicant_pan_is_an_individual_pan_unless_the_customer_is_not_one(client, rm, published_data_root):
    company_pan = "AABCK1234F"
    body = _lap(pan=company_pan)
    r = _intake(client, rm, body)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "identifier_invalid"
    body = _lap(pan=None)
    body["groups"]["applicants"][1]["pan"] = _cell(company_pan)
    assert _intake(client, rm, body).status_code == 422
    assert _intake(client, rm, _lap(pan=company_pan, customer_type="non_individual")).status_code == 201


def test_cin_box_takes_a_cin_or_an_llpin(client, rm):
    assert _intake(client, rm, _bbg(cin="AAB-1234")).status_code == 201
    r = _intake(client, rm, _bbg(borrower="Other Works LLP", cin="AB-12"), files=[(OTHER_PDF, fixture_file(OTHER_PDF))])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "identifier_invalid"


def test_aadhaar_is_the_last_four_digits_only(client, rm, published_data_root):
    body = _lap()
    body["groups"]["applicants"][0]["aadhaar_last4"] = _cell("123412341234")
    r = _intake(client, rm, body)
    assert r.status_code == 422 and "4 digits" in r.json()["detail"]["message"]
    _no_case_left(published_data_root)


def test_rows_are_checked_against_the_form(client, rm, published_data_root):
    for change in (
        lambda b: b["groups"]["properties"][0].update(property_type=_cell("castle")),
        lambda b: b["groups"]["properties"][0].update(pincode=_cell("12345")),
        lambda b: b["groups"]["applicants"][0].update(shoe_size=_cell("9")),
        lambda b: b["groups"].update(cars=[{"make": _cell("x")}]),
        lambda b: b["groups"]["applicants"].extend([{"name": _cell(f"P{i}"), "role": _cell("guarantor")}
                                                    for i in range(5)]),
    ):
        body = _lap()
        change(body)
        assert _intake(client, rm, body).status_code == 422
    _no_case_left(published_data_root)


def test_a_lap_case_type_is_not_a_business_case_type(client, rm, published_data_root):
    assert _intake(client, rm, _lap(case_type="renewal")).status_code == 422
    assert _intake(client, rm, _bbg(case_type="balance_transfer")).status_code == 422
    assert _intake(client, rm, _lap(customer_type="private_limited")).status_code == 422
    _no_case_left(published_data_root)


# --- The proposal without a message ---


def _propose(client: TestClient, headers: dict, **body) -> dict:
    r = client.post("/api/cases/proposals", json={"channel": "email", **body}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_proposal_without_a_message_checks_duplicates_and_the_minimum(client, rm):
    first = _intake(client, rm, _bbg(pan="AABCE1234F")).json()["case"]
    p = _propose(client, rm, product="bbg", fields={"pan": "aabce1234f"})
    assert p["text_sha256"] is None
    assert [d["id"] for d in p["duplicates"]] == [first["id"]]
    assert p["fields"]["pan"] == {**p["fields"]["pan"], "value": "AABCE1234F", "status": "found",
                                  "source": "identifier"}
    assert p["missing_minimum"] == ["borrower", "facilities", "amount_inr"]
    by_id = _propose(client, rm, product="lap", fields={"application_id": "NOPE"})
    assert by_id["duplicates"] == []
    assert by_id["missing_minimum"] == ["applicants", "customer_type", "amount_inr", "tenure_months", "properties"]


def test_a_proposal_matches_on_the_application_id(client, rm):
    first = _intake(client, rm, _lap(application_id="LOS-123")).json()["case"]
    p = _propose(client, rm, product="lap", fields={"application_id": "los-123"})
    assert [d["id"] for d in p["duplicates"]] == [first["id"]]


def test_a_proposal_counts_the_rows_toward_the_minimum(client, rm):
    lap = _lap()
    p = _propose(client, rm, product="lap", groups=lap["groups"],
                 fields={"customer_type": "salaried", "amount_inr": "4500000", "tenure_months": "180"})
    assert p["missing_minimum"] == []


def test_typed_identifiers_are_flagged_not_corrected(client, rm):
    p = _propose(client, rm, product="lap", fields={"pan": "AABCK1234F", "co_applicant_pan": "bad"})
    assert p["fields"]["pan"]["status"] == "invalid" and "fourth letter" in p["fields"]["pan"]["note"]
    assert p["fields"]["co_applicant_pan"]["status"] == "invalid"
    assert p["fields"]["co_applicant_pan"]["value"] == "BAD"


def test_typed_values_win_over_the_message(client, rm):
    text = "Kestrel Fabricators Pvt Ltd, CC 50L, PAN AAACK1234F"
    p = _propose(client, rm, text=text, fields={"pan": "AAACK9999F"})
    assert p["fields"]["pan"]["value"] == "AAACK9999F" and p["fields"]["pan"]["source"] == "identifier"
    assert p["fields"]["borrower"]["value"] == "Kestrel Fabricators Pvt Ltd" and p["text_sha256"]


def test_case_type_words_are_read_for_the_product(client, rm):
    text = "Rohan Kulkarni, balance transfer with top-up of his home loan, 45 lakh"
    assert _propose(client, rm, text="Kestrel Fabricators Pvt Ltd, balance transfer of CC 50L", product="bbg")[
        "fields"]["case_type"]["value"] == "takeover"
    assert _propose(client, rm, text="balance transfer of the loan, 45 lakh", product="lap")[
        "fields"]["case_type"]["value"] == "balance_transfer"
    assert _propose(client, rm, text=text, product="lap")["fields"]["case_type"]["value"] == "balance_transfer_top_up"


def test_a_proposal_refuses_an_unknown_product_and_an_empty_text(client, rm):
    assert client.post("/api/cases/proposals", json={"channel": "email", "product": "car"}, headers=rm).status_code == 422
    assert client.post("/api/cases/proposals", json={"channel": "email", "text": ""}, headers=rm).status_code == 422


# --- Checklist preview and meta ---


def _preview(client: TestClient, headers: dict, **body) -> dict:
    r = client.post("/api/cases/checklist-preview", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_lap_preview_lists_the_lap_items_and_is_provisional_until_the_customer_type(client, rm):
    unknown = _preview(client, rm, product="lap", amount_inr=4500000)
    chosen = _preview(client, rm, product="lap", amount_inr=4500000, customer_type="self_employed")
    assert unknown["provisional"] is True and chosen["provisional"] is False
    # Until the customer type is known, the documents every customer needs; then its own as well
    # (tests/test_lap_checklist.py has the full matrix).
    assert {i["id"] for i in unknown["items"]} < {i["id"] for i in chosen["items"]}
    assert {"lap_itr", "lap_business_bank_statements"} <= {i["id"] for i in chosen["items"]} - {
        i["id"] for i in unknown["items"]}
    lap_items = {i["id"] for i in chosen["items"]}
    assert all(i.startswith("lap_") for i in lap_items)
    assert all(i["document_types"] for i in chosen["items"])
    bbg = _preview(client, rm, product="bbg", constitution="private_limited", facilities=["cash_credit"], amount_inr=1)
    assert not lap_items & {i["id"] for i in bbg["items"]} and bbg["items"]


def test_the_preview_refuses_choices_of_another_product(client, rm):
    for body in ({"product": "lap", "customer_type": "private_limited"}, {"product": "bbg", "case_type": "top_up"},
                 {"product": "car"}):
        assert client.post("/api/cases/checklist-preview", json=body, headers=rm).status_code == 422


def test_a_created_lap_case_has_the_lap_checklist(client, rm):
    case = _intake(client, rm, _lap()).json()["case"]
    readiness = client.get(f"/api/cases/{case['id']}/checklist", headers=sign_in(client, ANALYST)).json()
    # A salaried applicant's new loan: the documents every customer needs and a salaried one's.
    assert {i["item_id"] for i in readiness["items"]} == {
        "lap_application_form", "lap_pan_or_form_60", "lap_identity_proof", "lap_signature_proof",
        "lap_address_proof", "lap_bureau_report", "lap_property_title", "lap_property_completion",
        "lap_property_owner_kyc", "lap_supporting_documents", "lap_salary_slips", "lap_salary_certificate",
        "lap_form_16", "lap_salary_bank_statements"}
    assert readiness["provisional"] is False


def test_meta_carries_the_products_and_their_forms(client, rm):
    meta = client.get("/api/meta", headers=rm).json()
    products = {p["id"]: p for p in meta["products"]}
    assert list(products) == ["bbg", "lap"] and meta["product_default"] == "bbg"
    lap = products["lap"]
    assert (lap["label"], lap["prefix"]) == ("Loan against property", "LAP")
    assert [o["id"] for o in lap["customer_types"]] == [
        "salaried", "self_employed_professional", "self_employed", "non_individual"]
    assert {o["id"] for o in lap["case_types"]} == {"new", "balance_transfer", "balance_transfer_top_up", "top_up",
                                                    "unknown"}
    assert lap["minimum"] == ["applicants", "customer_type", "amount_inr", "tenure_months", "properties"]
    assert products["bbg"]["minimum"] == ["borrower", "facilities", "amount_inr"]
    assert {o["id"] for o in products["bbg"]["case_types"]} == {"new", "renewal", "enhancement", "takeover", "unknown"}
    # The forms: start rules and sections, options resolved.
    lap_form, bbg_form = meta["intake"]["lap"], meta["intake"]["bbg"]
    assert lap_form["start"]["documents"]["min_files"] == 1 and lap_form["start"]["message_required"] is False
    assert [i["id"] for i in lap_form["start"]["identifiers"]] == [
        "pan", "co_applicant_pan", "gstin", "udyam", "application_id", "existing_loan_account"]
    assert [i["id"] for i in bbg_form["start"]["identifiers"]] == ["pan", "gstin", "cin", "udyam", "application_id"]
    sections = {s["id"]: s for s in lap_form["sections"]}
    assert sections["applicants"]["repeat"] == {"min": 1, "max": 6}
    roles = next(f for f in sections["applicants"]["fields"] if f["id"] == "role")
    assert [o["id"] for o in roles["options"]] == ["applicant", "co_applicant", "guarantor"]
    assert sections["business"]["show_when"] == {"customer_type": ["self_employed_professional", "self_employed",
                                                                   "non_individual"]}
    assert {s["id"] for s in bbg_form["sections"]} >= {"borrower", "people", "facilities", "security", "banking"}
    # Kept for callers that predate products.
    assert meta["case_create_minimum"] == ["borrower", "product", "facilities", "amount_inr"]


# --- What a value without a message is called ---


def test_header_values_without_a_message_are_declared_at_intake(client, rm, published_data_root):
    from tests.conftest import open_assessment

    body = _bbg(header={"declared_turnover_inr": _cell("60000000"), "promoters": _cell("Tarun Velankar")})
    case = _intake(client, rm, body).json()["case"]
    open_assessment(published_data_root, case["id"])
    facts = client.get(f"/api/cases/{case['id']}/facts", headers=sign_in(client, ANALYST)).json()
    declared = [t for y in facts["turnover"] for t in y["figures"] if t["source"] == "declared"]
    assert [t["label"] for t in declared] == ["Turnover declared at intake"]
    assert declared[0]["evidence"] == []    # typed, so no page to cite
    people = next(s for s in facts["persons"] if s["source"] == "application_message")
    assert people["label"] == "Declared at intake"


def test_header_values_with_a_message_cite_it(client, rm, published_data_root):
    from tests.conftest import open_assessment

    text = "Kestrel Fabricators Pvt Ltd needs CC 50L. Turnover Rs 6 crore."
    start = text.index("Rs 6 crore")
    body = _bbg(message_text=text, header={
        "declared_turnover_inr": _cell("60000000", f"message:{start}-{start + 10}"),
        "proposed_emi_inr": _cell("200000", "default:config"),
    })
    case = _intake(client, rm, body).json()["case"]
    open_assessment(published_data_root, case["id"])
    facts = client.get(f"/api/cases/{case['id']}/facts", headers=sign_in(client, ANALYST)).json()
    declared = [t for y in facts["turnover"] for t in y["figures"] if t["source"] == "declared"]
    assert declared[0]["label"] == "Turnover declared in the sourcing message" and declared[0]["evidence"]
    # Only a span of the message is cited to it.
    assert facts["proposed_emi"]["evidence"] == []


# --- The store ---


def _store_at(path: Path, version: int) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    for n, script in enumerate(db.MIGRATIONS[:version], start=1):
        conn.executescript(f"BEGIN IMMEDIATE; {script}; PRAGMA user_version = {n}; COMMIT;")
    return conn


def _old_case(conn: sqlite3.Connection, case_id: str) -> None:
    conn.execute(
        """INSERT INTO cases (id, borrower, constitution, facilities, amount_inr, channel, stage, as_of,
               created_by, created_at) VALUES (?, 'Old Borrower', 'unknown', '["cash_credit"]',
               100, 'email', 'Intake', '2026-10-01', 'u-rm-1', '2026-10-01T00:00:00')""", (case_id,))


def test_bbg_numbering_continues_after_the_migration(tmp_path):
    conn = _store_at(tmp_path / "creditiq.sqlite3", 27)
    conn.execute("INSERT INTO case_seq (year, last) VALUES (2026, 5)")
    _old_case(conn, "BBG-2026-000007")   # a sequence that fell behind its cases
    db.migrate(conn)
    seq = {(r["prefix"], r["year"]): r["last"] for r in conn.execute("SELECT * FROM case_seq_prefix")}
    row = conn.execute("SELECT customer_type, program, tenure_months, intake_groups FROM cases").fetchone()
    conn.close()
    assert seq == {("BBG", 2026): 7}
    assert tuple(row) == (None, None, None, "{}")


def test_the_migration_checks_the_tables_not_only_the_version(tmp_path):
    """A store another working copy numbered past this migration without it still gets its tables."""
    conn = _store_at(tmp_path / "creditiq.sqlite3", 27)
    _old_case(conn, "BBG-2026-000003")
    conn.execute(f"PRAGMA user_version = {len(db.MIGRATIONS)}")
    db.migrate(conn)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(cases)")}
    last = conn.execute("SELECT last FROM case_seq_prefix WHERE prefix = 'BBG'").fetchone()[0]
    conn.close()
    assert {"customer_type", "program", "tenure_months", "intake_groups"} <= columns and last == 3


def test_a_case_number_already_held_is_skipped(client, rm, published_data_root):
    first = _intake(client, rm, _lap()).json()["case"]["id"]
    conn = db.connect(published_data_root)
    try:
        conn.execute("UPDATE case_seq_prefix SET last = 0 WHERE prefix = 'LAP'")
    finally:
        conn.close()
    second = _intake(client, rm, _lap(pan=None, duplicate_override_reason="again"),
                     files=[(OTHER_PDF, fixture_file(OTHER_PDF))]).json()["case"]["id"]
    assert first.endswith("-000001") and second.endswith("-000002")
