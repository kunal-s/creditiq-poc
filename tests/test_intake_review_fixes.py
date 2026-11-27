"""The intake's limits and rules after the security and Python reviews (2026-11-27): a bounded multipart
body, the duplicate check inside the write and across applicants, what a duplicate discloses, the sources a
create may record, typed case columns, case numbers past leftover folders, the intake spool, a create that
survives a failing refresh, the form's show_when, repeat.min, required and parties rules, and parties of
another name kept apart."""

from __future__ import annotations

import copy
import io
import json
import logging
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, uploads
from engine.store import cases_dir
from tests.conftest import ANALYST, RM, fixture_file, new_case, open_assessment, sign_in
from tests.test_intake_products import PDF, OTHER_PDF, _bbg, _cell, _intake, _lap, _no_case_left, _parts


@pytest.fixture()
def rm(client: TestClient) -> dict:
    return sign_in(client, RM)


def _detail(r) -> dict:
    return r.json()["detail"]


# --- 1. The multipart body is bounded ---


def _body(boundary: str, fields: list[tuple[str, str]]) -> bytes:
    parts = "".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n" for n, v in fields)
    return (parts + f"--{boundary}--\r\n").encode()


def test_only_the_allowed_text_fields_are_kept(tmp_path: Path):
    lim = uploads.limits()
    receiver = uploads.MultipartReceiver("multipart/form-data; boundary=B", tmp_path / "in", lim)
    receiver.write(_body("B", [("junk", "x" * (lim.max_case_part * 2)), ("channel", "email")]))
    receiver.finish()
    assert receiver.fields == {"channel": "email"} and receiver.oversize_fields == set()


def test_the_case_part_limit_is_the_intake_case_part_only(client, rm, published_data_root):
    lim = uploads.limits()
    assert lim.max_form_field == 4 * 1024 and lim.max_case_part == 256 * 1024
    case_id = client.post("/api/cases", json=new_case(), headers=rm).json()["id"]
    r = client.post(f"/api/cases/{case_id}/files", headers=rm,
                    files=[("channel", (None, "e" * (lim.max_form_field + 1))), ("files", (PDF, fixture_file(PDF)))])
    assert r.status_code == 422 and "channel" in r.json()["detail"]
    r = _intake(client, rm, _lap())
    assert r.status_code == 201   # a case part well above 4 KB is fine


def test_too_many_parts_are_refused(client, rm, published_data_root, monkeypatch):
    real = uploads.limits

    def few():
        lim = real()
        lim.max_parts = 3
        return lim

    monkeypatch.setattr(uploads, "limits", few)
    files = [(f"f{i}.pdf", fixture_file(PDF)) for i in range(4)]
    r = _intake(client, rm, _lap(), files=files)
    assert r.status_code == 422 and _detail(r)["code"] == "bad_body" and "parts" in _detail(r)["message"]
    _no_case_left(published_data_root)


def test_a_request_over_the_size_limit_is_refused_up_front_and_while_streaming(client, rm, published_data_root,
                                                                              monkeypatch, tmp_path):
    real = uploads.limits

    def small():
        lim = real()
        lim.max_request = 500
        return lim

    monkeypatch.setattr(uploads, "limits", small)
    r = _intake(client, rm, _lap())   # the case part alone is larger than 500 bytes
    assert r.status_code == 422 and "MB limit" in _detail(r)["message"]
    _no_case_left(published_data_root)
    with pytest.raises(uploads.UploadError):
        uploads.check_content_length("501", small())
    receiver = uploads.MultipartReceiver("multipart/form-data; boundary=B", tmp_path / "in", small())
    with pytest.raises(uploads.UploadError):
        receiver.write(b"x" * 501)


def test_a_part_that_looks_like_a_zip_and_is_not_is_refused_unread(client, rm, published_data_root):
    case_id = client.post("/api/cases", json=new_case(), headers=rm).json()["id"]
    fake = b"PK\x03\x04" + b"\x00" * 2000
    r = client.post(f"/api/cases/{case_id}/files", headers=rm, files=[("files", ("broken.zip", fake))])
    assert r.status_code == 202, r.text
    record = r.json()["files"][0]
    assert record["status"] == "rejected" and "damaged" in record["reason"]


def test_a_workbook_over_the_file_limit_is_refused_unread(client, rm, published_data_root, monkeypatch):
    real = uploads.limits

    def tiny():
        lim = real()
        lim.max_file = 100
        return lim

    monkeypatch.setattr(uploads, "limits", tiny)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as zf:
        zf.writestr("xl/workbook.xml", "<workbook/>" * 50)
    case_id = client.post("/api/cases", json=new_case(), headers=rm).json()["id"]
    r = client.post(f"/api/cases/{case_id}/files", headers=rm, files=[("files", ("book.xlsx", data.getvalue()))])
    record = r.json()["files"][0]
    assert record["status"] == "rejected" and "limit per file" in record["reason"]


@pytest.mark.parametrize("where", ["intake", "upload"])
def test_an_unknown_files_channel_is_refused(client, rm, published_data_root, where):
    if where == "intake":
        r = client.post("/api/cases/intake", headers=rm, files=[*_parts(_lap()), ("channel", (None, "fax"))])
        assert r.status_code == 422 and _detail(r)["code"] == "bad_body"
        _no_case_left(published_data_root)
    else:
        case_id = client.post("/api/cases", json=new_case(), headers=rm).json()["id"]
        r = client.post(f"/api/cases/{case_id}/files", headers=rm,
                        files=[("channel", (None, "fax")), ("files", (PDF, fixture_file(PDF)))])
        assert r.status_code == 422
    ok = client.post("/api/cases/intake", headers=rm, files=[*_parts(_lap()), ("channel", (None, "whatsapp"))])
    assert ok.status_code == 201 and ok.json()["upload"]["files"][0]["channel"] == "whatsapp"


# --- 2, 3. The duplicate check runs inside the write, and over every applicant's PAN ---


def test_a_duplicate_written_since_the_first_check_stops_the_create(client, rm, published_data_root, monkeypatch):
    from engine import case_create

    first = _intake(client, rm, _bbg()).json()["case"]
    real = case_create.find_duplicates
    calls = {"n": 0}

    def first_check_misses(*args, **kwargs):
        calls["n"] += 1
        return [] if calls["n"] == 1 else real(*args, **kwargs)

    monkeypatch.setattr(case_create, "find_duplicates", first_check_misses)
    r = _intake(client, rm, _bbg(), files=[(OTHER_PDF, fixture_file(OTHER_PDF))])
    assert r.status_code == 409 and [d["id"] for d in _detail(r)["duplicates"]] == [first["id"]]
    conn = db.connect(published_data_root)
    try:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 1
    finally:
        conn.close()


def test_the_primary_applicants_pan_is_the_cases_and_every_applicants_pan_is_checked(client, rm):
    body = _lap(pan=None)
    case = _intake(client, rm, body).json()["case"]
    assert case["pan"] == "ABCPK1234F" and case["header"]["pan"]["source"] == "identifier"
    # Another applicant whose PAN is the first case's co-applicant's.
    other = _lap(pan=None, application_id="LOS-2")
    other["groups"]["applicants"] = [{"name": _cell("Sunita Rao"), "role": _cell("applicant"),
                                      "pan": _cell("BCDPK5678G")}]
    other["groups"]["properties"][0]["owners"] = _cell("Sunita Rao")
    r = _intake(client, rm, other, files=[(OTHER_PDF, fixture_file(OTHER_PDF))])
    assert r.status_code == 409 and [d["id"] for d in _detail(r)["duplicates"]] == [case["id"]]
    p = client.post("/api/cases/proposals", headers=rm,
                    json={"channel": "email", "product": "lap", "groups": other["groups"]}).json()
    assert [d["id"] for d in p["duplicates"]] == [case["id"]]


# --- 4. A duplicate discloses only what the user may read ---


def test_another_rms_case_is_named_by_number_and_rm_only(client, rm, published_data_root):
    analyst = sign_in(client, ANALYST)
    theirs = _intake(client, analyst, _bbg(pan="AABCE1234F")).json()["case"]
    p = client.post("/api/cases/proposals", headers=rm,
                    json={"channel": "email", "fields": {"pan": "AABCE1234F"}}).json()
    assert p["duplicates"] == []
    assert p["duplicates_elsewhere"] == [{"id": theirs["id"], "rm": theirs["rm"]}]
    r = _intake(client, rm, _bbg(pan="AABCE1234F", borrower="Different Name Works"),
                files=[(OTHER_PDF, fixture_file(OTHER_PDF))])
    assert r.status_code == 409
    assert _detail(r)["duplicates"] == [] and _detail(r)["duplicates_elsewhere"] == [{"id": theirs["id"], "rm": theirs["rm"]}]
    assert theirs["id"] in _detail(r)["message"]
    # A user who may read every case sees it in full.
    mine = client.post("/api/cases", json=new_case(pan="AAACK1234F", borrower="Unrelated Fabrics Works"),
                       headers=rm).json()
    full = client.post("/api/cases/proposals", headers=analyst,
                       json={"channel": "email", "fields": {"pan": "AAACK1234F"}}).json()
    assert [d["id"] for d in full["duplicates"]] == [mine["id"]] and full["duplicates_elsewhere"] == []


# --- 5. A create records only the sources a client may claim ---


@pytest.mark.parametrize("source", ["document:D-1:p1", "copilot", "default:other", "message:0-5"])
def test_a_forged_source_is_refused(client, rm, published_data_root, source):
    body = _bbg(header={"borrower": _cell("Example Tools Pvt Ltd", source)})
    assert client.post("/api/cases", json=body, headers=rm).status_code == 422
    row = _lap()
    row["groups"]["properties"][0]["pincode"] = _cell("411038", source)
    assert _intake(client, rm, row).status_code == 422
    _no_case_left(published_data_root)


def test_the_sources_a_create_may_record_are_accepted(client, rm):
    header = {name: _cell("x", source) for name, source in (("contact", None), ("promoters", "identifier"),
                                                             ("existing_banking", "intake"))}
    body = _bbg(header={**header, "borrower": _cell("Example Tools Pvt Ltd", "default:config")},
                message_text="hello world")
    body["header"]["contact"] = {"value": "x", "proposed": None, "source": "message:0-5"}
    assert client.post("/api/cases", json=body, headers=rm).status_code == 201


# --- 6. The case's own columns are typed ---


@pytest.mark.parametrize(("change", "status"), [
    ({"amount_inr": 10 ** 16}, 422),
    ({"tenure_months": 601}, 422),
    ({"borrower": "Example\x07Tools"}, 422),
    ({"application_id": "A" * 101}, 422),
    ({"customer_id": "C\x00"}, 422),
])
def test_case_columns_are_checked_not_stored_blindly(client, rm, published_data_root, change, status):
    assert client.post("/api/cases", json=_bbg(**change), headers=rm).status_code == status
    assert _intake(client, rm, _lap(**change)).status_code == status
    _no_case_left(published_data_root)


def test_a_tenure_is_checked_against_the_configured_limit(client, rm, published_data_root, monkeypatch):
    from engine import intake

    cfg = copy.deepcopy(intake.load_intake_config())
    cfg["limits"]["months_max"] = 120
    monkeypatch.setattr(intake, "load_intake_config", lambda: cfg)
    r = _intake(client, rm, _lap(tenure_months=180))
    assert r.status_code == 422 and "1 to 120" in _detail(r)["message"]
    assert _intake(client, rm, _lap(tenure_months=120)).status_code == 201


def test_unicode_digits_are_refused_not_a_server_error(client, rm, published_data_root):
    lines = [{"facility": _cell("term_loan"), "amount_inr": _cell("5000000"), "tenure_months": _cell("²")}]
    r = _intake(client, rm, _bbg(facilities=[], amount_inr=0, groups={"facilities": lines}))
    assert r.status_code == 422
    p = client.post("/api/cases/proposals", headers=rm,
                    json={"channel": "email", "product": "lap", "fields": {"tenure_months": "²", "amount_inr": "٣"}})
    assert p.status_code == 200
    assert {"tenure_months", "amount_inr"} <= set(p.json()["missing_minimum"])
    assert p.json()["fields"]["tenure_months"]["status"] == "invalid"


# --- 7. A leftover folder does not block the next case ---


def test_a_case_number_whose_folder_is_left_over_is_skipped(client, rm, published_data_root, caplog):
    from datetime import datetime, timezone

    year = datetime.now(timezone.utc).year
    leftover = cases_dir(published_data_root) / f"LAP-{year}-000001"
    leftover.mkdir(parents=True)
    with caplog.at_level(logging.WARNING, logger="creditiq.cases"):
        case = _intake(client, rm, _lap()).json()["case"]
    assert case["id"] == f"LAP-{year}-000002"
    assert any("skipped" in m for m in caplog.messages)


def test_the_default_products_numbers_keep_the_old_sequence_in_step(client, rm, published_data_root):
    case = client.post("/api/cases", json=new_case(), headers=rm).json()
    year, seq = int(case["id"].split("-")[1]), int(case["id"].split("-")[2])
    conn = db.connect(published_data_root)
    try:
        assert conn.execute("SELECT last FROM case_seq WHERE year = ?", (year,)).fetchone()[0] == seq
    finally:
        conn.close()
    _intake(client, rm, _lap())
    conn = db.connect(published_data_root)
    try:
        assert conn.execute("SELECT last FROM case_seq WHERE year = ?", (year,)).fetchone()[0] == seq
    finally:
        conn.close()


# --- 8. The intake spool ---


def test_the_engine_clears_the_intake_spool_at_start(published_data_root, monkeypatch):
    monkeypatch.setenv("CREDITIQ_DATA_ROOT", str(published_data_root))
    monkeypatch.setenv("CREDITIQ_WORKER", "0")
    left = uploads.intake_staging(published_data_root)
    (left / "incoming").mkdir()
    (left / "incoming" / "part").write_bytes(b"x")
    from engine.api import app

    with TestClient(app):
        pass
    assert not any((published_data_root / uploads.INTAKE_SPOOL).iterdir())


# --- 9. A failing refresh after the commit ---


def test_a_case_created_before_its_refresh_failed_is_still_created(client, rm, published_data_root, monkeypatch, caplog):
    from engine import pipeline

    def broken(*args, **kwargs):
        raise RuntimeError("refresh broke")

    monkeypatch.setattr(pipeline, "refresh_case", broken)
    with caplog.at_level(logging.ERROR, logger="creditiq.api"):
        r = _intake(client, rm, _lap())
        direct = client.post("/api/cases", json=new_case(), headers=rm)
    assert r.status_code == 201 and direct.status_code == 201
    assert sum("was not rebuilt" in m for m in caplog.messages) == 2


# --- Python review 4: the form's own rules ---


def test_values_show_when_hides_are_refused(client, rm, published_data_root):
    # A business section for a salaried applicant; a balance transfer's lender on a new loan.
    assert _intake(client, rm, _lap(header={"business_name": _cell("Kulkarni Traders")})).status_code == 422
    assert _intake(client, rm, _lap(header={"existing_lender": _cell("Other Bank")})).status_code == 422
    # The GSTIN box is shown only for a self-employed or non-individual customer.
    assert _intake(client, rm, _lap(gstin="27AAACK1234F1Z0")).status_code == 422
    _no_case_left(published_data_root)
    ok = _lap(customer_type="self_employed", case_type="balance_transfer", gstin="27AAACK1234F1Z0",
              header={"business_name": _cell("Kulkarni Traders"), "existing_lender": _cell("Other Bank")})
    assert _intake(client, rm, ok).status_code == 201


def _with_config(monkeypatch, change) -> None:
    from engine import intake

    cfg = copy.deepcopy(intake.load_intake_config())
    change(cfg)
    monkeypatch.setattr(intake, "load_intake_config", lambda: cfg)


def test_a_section_needs_its_least_rows(client, rm, published_data_root, monkeypatch):
    def two_properties(cfg):
        next(s for s in cfg["lap"]["sections"] if s["id"] == "properties")["repeat"]["min"] = 2

    _with_config(monkeypatch, two_properties)
    r = _intake(client, rm, _lap())
    assert r.status_code == 422 and "at least 2 rows" in _detail(r)["message"]
    _no_case_left(published_data_root)


def test_a_required_single_value_is_asked_only_where_it_is_shown(client, rm, monkeypatch):
    def business_name_required(cfg):
        section = next(s for s in cfg["lap"]["sections"] if s["id"] == "business")
        next(f for f in section["fields"] if f["id"] == "business_name")["required"] = True

    _with_config(monkeypatch, business_name_required)
    r = _intake(client, rm, _lap(customer_type="self_employed"))
    assert r.status_code == 422 and "business_name: required" in _detail(r)["message"]
    assert _intake(client, rm, _lap()).status_code == 201   # salaried: the business section is not shown


def test_property_owners_are_the_applicants(client, rm, published_data_root):
    body = _lap()
    body["groups"]["properties"][0]["owners"] = _cell("Rohan Kulkarni; Somebody Else")
    r = _intake(client, rm, body)
    assert r.status_code == 422 and "Somebody Else not named in applicants" in _detail(r)["message"]
    body["groups"]["properties"][0]["owners"] = _cell("rohan kulkarni")
    assert _intake(client, rm, body).status_code == 201


def test_a_direct_business_create_needs_no_facility_lines(client, rm):
    assert client.post("/api/cases", json=new_case(), headers=rm).status_code == 201


# --- Python review 6, 7, 9 ---


def test_a_typed_pan_is_judged_with_the_constitution_the_message_or_form_gives(client, rm):
    typed = client.post("/api/cases/proposals", headers=rm, json={
        "channel": "email", "fields": {"pan": "ABCPK1234F", "constitution": "private_limited"}}).json()
    assert typed["fields"]["pan"]["status"] == "invalid"
    read = client.post("/api/cases/proposals", headers=rm, json={
        "channel": "email", "text": "Kestrel Fabricators Pvt Ltd needs CC 50L", "fields": {"pan": "ABCPK1234F"}}).json()
    assert read["fields"]["constitution"]["value"] == "private_limited"
    assert read["fields"]["pan"]["status"] == "invalid"
    sole = client.post("/api/cases/proposals", headers=rm, json={
        "channel": "email", "fields": {"pan": "ABCPK1234F", "constitution": "proprietorship"}}).json()
    assert sole["fields"]["pan"]["status"] == "found"


def test_a_borrower_of_another_name_keeps_its_party_and_the_applicant_theirs(client, rm):
    body = _lap(pan=None, customer_type="non_individual", borrower="Kulkarni Traders LLP")
    case = _intake(client, rm, body).json()["case"]
    assert case["borrower"] == "Kulkarni Traders LLP" and case["pan"] is None
    parties = {p["name"]: p for p in client.get(f"/api/cases/{case['id']}/parties", headers=rm).json()}
    assert parties["Kulkarni Traders LLP"]["role"] == "borrower"
    assert parties["Rohan Kulkarni"]["role"] == "applicant" and parties["Rohan Kulkarni"]["pan"] == "ABCPK1234F"


def test_an_identifier_typed_in_a_box_relies_on_a_person(client, rm, published_data_root):
    body = _bbg(pan="AAACK1234F", header={"pan": _cell("AAACK1234F", "identifier")})
    case = _intake(client, rm, body).json()["case"]
    open_assessment(published_data_root, case["id"])
    facts = client.get(f"/api/cases/{case['id']}/facts", headers=sign_in(client, ANALYST)).json()
    declared = [v for v in facts["identities"]["entity_pan"] if v["source"] == "application_message"]
    assert declared and declared[0]["relies_on_manual"] is True


# --- Python review 2, 10: the checklist and the configuration ---


def test_an_item_naming_no_product_is_the_default_products_only():
    from engine.checklist import for_product
    from engine.configstore.schema import ChecklistItemDef

    item = ChecklistItemDef(id="x", name="X", category="C", constitutions=["private_limited"], why="w", basis="b",
                            source="provisional", blocking=True, weight=1)
    assert for_product(item, "bbg") and for_product(item, None) and not for_product(item, "lap")


def test_a_people_section_role_must_be_a_party_role(monkeypatch):
    from engine import intake
    from engine.config import ConfigError, product

    def odd_role(cfg):
        section = next(s for s in cfg["lap"]["sections"] if s["id"] == "applicants")
        role = next(f for f in section["fields"] if f["id"] == "role")
        role["options"] = "loan_types"
        section["people"] = {"default_role": "other"}

    _with_config(monkeypatch, odd_role)
    with pytest.raises(ConfigError, match="party roles"):
        intake.product_schema(product("lap"))


def test_text_limits_come_from_the_configuration(client, rm, published_data_root, monkeypatch):
    _with_config(monkeypatch, lambda cfg: cfg["limits"].update(text_max=10))
    body = _lap()
    body["groups"]["properties"][0]["address"] = _cell("12 Long Street Name")
    r = _intake(client, rm, body)
    assert r.status_code == 422 and "longer than 10 characters" in _detail(r)["message"]
