"""The loan against property document checklist (RBL scope document section 2.2, "LAP - Input Documents"):
only the documents that apply to the case, chosen in configuration by its customer type, its case type and
what its intake form declares (plan 2026-11-27 section 7.3). Every item is provisional until RBL confirms it."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db
from engine.checklist import declared_names, row_sections
from engine.completeness import items_for
from engine.configstore import reader, writer
from engine.configstore.schema import ChecklistTaxonomySection
from tests.conftest import ANALYST, RM, fixture_file, sign_in
from tests.triangulation import add_doc

# --- What applies, by case ---

COMMON = {
    "lap_application_form", "lap_pan_or_form_60", "lap_identity_proof", "lap_signature_proof", "lap_address_proof",
    "lap_bureau_report", "lap_property_title", "lap_property_completion", "lap_property_owner_kyc",
    "lap_supporting_documents",
}
COMMON_BLOCKING = {
    "lap_application_form", "lap_pan_or_form_60", "lap_identity_proof", "lap_signature_proof", "lap_address_proof",
    "lap_property_title",
}
SALARIED = {"lap_salary_slips", "lap_salary_certificate", "lap_form_16", "lap_salary_bank_statements"}
BUSINESS_INCOME = {
    "lap_itr", "lap_financials_latest", "lap_financials_previous", "lap_provisional_financials",
    "lap_business_bank_statements", "lap_business_proof", "lap_tds_certificates", "lap_sales_purchase_records",
}
BUSINESS_BLOCKING = {"lap_itr", "lap_financials_latest", "lap_financials_previous", "lap_business_bank_statements"}
GST = {"lap_gst_returns"}
PROFESSIONAL = {"lap_professional_registration"}
NON_INDIVIDUAL = {"lap_constitution_documents", "lap_entity_people", "lap_authorised_person"}
EXISTING_LOANS = {
    "lap_loan_sanction_letter", "lap_loan_agreement", "lap_loan_statement", "lap_loan_repayment_schedule",
    "lap_loan_emi_evidence",
}
TAKEOVER = {"lap_loan_closure"}
RENTAL = {"lap_rent_agreement", "lap_rent_credits"}
OTHER_INCOME = {"lap_agricultural_income", "lap_commission_income"}
ALL_LAP = (COMMON | SALARIED | BUSINESS_INCOME | GST | PROFESSIONAL | NON_INDIVIDUAL | EXISTING_LOANS | TAKEOVER
           | RENTAL | OTHER_INCOME)

GSTIN = "27AAPFU0939F1ZV"

# The matrix: (customer type, case type, declared values, rows) -> (items, blocking items).
SALARIED_NEW = dict(customer_type="salaried", case_type="new", declared=set(), rows={"applicants", "properties"})
PROFESSIONAL_BT_TOP_UP = dict(customer_type="self_employed_professional", case_type="balance_transfer_top_up",
                              declared={"gstin", "declared_rental_income_inr"}, rows={"applicants", "properties"})
NON_INDIVIDUAL_NEW = dict(customer_type="non_individual", case_type="new", declared=set(), rows={"applicants", "properties"})

MATRIX = [
    (SALARIED_NEW, COMMON | SALARIED, COMMON_BLOCKING | SALARIED),
    (PROFESSIONAL_BT_TOP_UP,
     COMMON | BUSINESS_INCOME | GST | PROFESSIONAL | EXISTING_LOANS | TAKEOVER | RENTAL,
     COMMON_BLOCKING | BUSINESS_BLOCKING | GST),
    (NON_INDIVIDUAL_NEW, COMMON | BUSINESS_INCOME | NON_INDIVIDUAL,
     COMMON_BLOCKING | BUSINESS_BLOCKING | {"lap_constitution_documents"}),
]


def _ids(items) -> set[str]:
    return {i.id for i in items}


def _lap_items(root: Path, **case) -> tuple[list, bool]:
    return items_for(root, constitution="unknown", facilities=[], amount_inr=4_500_000, collateral_present=True,
                     product="lap", **case)


@pytest.mark.parametrize("case,expected,blocking", MATRIX, ids=["salaried-new", "professional-bt-top-up",
                                                                "non-individual-new"])
def test_the_lap_matrix_applies_exactly_the_documents_of_the_case(published_data_root: Path, case, expected, blocking):
    items, provisional = _lap_items(published_data_root, **case)
    assert provisional is False
    assert _ids(items) == expected
    assert {i.id for i in items if i.blocking} == blocking


def test_every_lap_item_is_provisional_and_of_the_lap_product_only(published_data_root: Path):
    items = {i.id: i for i in reader.load_checklist_taxonomy(published_data_root).items}
    lap = {i for i, item in items.items() if "lap" in item.products}
    assert lap == ALL_LAP
    assert all(items[i].products == ["lap"] and items[i].source == "provisional" for i in lap)


def test_while_the_customer_type_is_unknown_only_the_common_documents_are_listed(published_data_root: Path):
    items, provisional = _lap_items(published_data_root, case_type="unknown", declared=set(), rows=set())
    assert provisional is True and _ids(items) == COMMON


def test_gst_returns_are_asked_only_when_a_gstin_is_given(published_data_root: Path):
    without, _ = _lap_items(published_data_root, customer_type="self_employed", case_type="new")
    with_gstin, _ = _lap_items(published_data_root, customer_type="self_employed", case_type="new", declared={"gstin"})
    assert "lap_gst_returns" not in _ids(without) and "lap_gst_returns" in _ids(with_gstin)
    # A salaried customer's GSTIN asks for no business return.
    salaried, _ = _lap_items(published_data_root, customer_type="salaried", case_type="new", declared={"gstin"})
    assert not (GST | BUSINESS_INCOME) & _ids(salaried)


@pytest.mark.parametrize("case_type,rows,expected", [
    ("new", set(), set()),
    ("new", {"existing_loans"}, EXISTING_LOANS),
    ("top_up", set(), EXISTING_LOANS),
    ("balance_transfer", set(), EXISTING_LOANS | TAKEOVER),
    ("balance_transfer_top_up", {"existing_loans"}, EXISTING_LOANS | TAKEOVER),
    ("unknown", set(), set()),
])
def test_existing_loan_documents_follow_the_case_type_or_the_loans_declared(published_data_root: Path, case_type, rows,
                                                                            expected):
    items, _ = _lap_items(published_data_root, customer_type="salaried", case_type=case_type, rows=rows)
    assert _ids(items) & (EXISTING_LOANS | TAKEOVER) == expected


@pytest.mark.parametrize("declared,expected", [
    (set(), set()),
    ({"declared_rental_income_inr"}, RENTAL),
    ({"declared_other_income_inr"}, OTHER_INCOME),
    ({"declared_rental_income_inr", "declared_other_income_inr"}, RENTAL | OTHER_INCOME),
    ({"declared_monthly_salary_inr"}, set()),
])
def test_other_income_documents_follow_what_is_declared(published_data_root: Path, declared, expected):
    items, _ = _lap_items(published_data_root, customer_type="salaried", case_type="new", declared=declared)
    assert _ids(items) & (RENTAL | OTHER_INCOME) == expected


def test_the_professional_documents_are_a_professionals_only(published_data_root: Path):
    for customer_type in ("salaried", "self_employed", "non_individual"):
        items, _ = _lap_items(published_data_root, customer_type=customer_type, case_type="new")
        assert not PROFESSIONAL & _ids(items), customer_type
        assert bool(NON_INDIVIDUAL & _ids(items)) == (customer_type == "non_individual"), customer_type


def test_the_periods_are_those_of_the_checklist(published_data_root: Path):
    items = {i.id: i for i in reader.load_checklist_taxonomy(published_data_root).items}
    cov = {i: (items[i].coverage.kind, items[i].coverage.months, items[i].coverage.count, items[i].coverage.offset)
           for i in ALL_LAP if items[i].coverage}
    assert cov["lap_salary_slips"] == ("monthly_periods", 3, 0, 0)
    assert cov["lap_form_16"] == ("assessment_years", 0, 2, 0)
    assert cov["lap_salary_bank_statements"] == ("account_months", 6, 0, 0)
    assert cov["lap_itr"] == ("assessment_years", 0, 2, 0)
    assert cov["lap_financials_latest"][::3] == ("financial_year", 1)
    assert cov["lap_financials_previous"][::3] == ("financial_year", 2)
    assert cov["lap_business_bank_statements"] == ("account_months", 12, 0, 0)
    assert cov["lap_gst_returns"] == ("monthly_periods", 12, 0, 0)
    per_person = {i for i in ALL_LAP if items[i].coverage and items[i].coverage.kind == "parties"}
    assert per_person == {"lap_pan_or_form_60", "lap_identity_proof", "lap_signature_proof", "lap_address_proof",
                          "lap_property_owner_kyc"}
    assert items["lap_property_owner_kyc"].coverage.named_in == ["properties.owners"]


def test_every_lap_item_is_satisfied_by_a_document_type_a_person_can_assign(published_data_root: Path):
    types = reader.load_document_types(published_data_root).types
    for item_id in ALL_LAP:
        assert any(item_id in t.satisfies for t in types), item_id
    new = {"application_form", "pan_card", "form_60", "identity_proof", "signature_proof", "address_proof",
           "salary_slip", "salary_certificate", "form_16", "tds_certificate", "sales_purchase_register",
           "gst_registration", "business_registration", "professional_registration", "llp_agreement",
           "directors_shareholders_list", "authority_letter", "consumer_bureau_report", "loan_agreement",
           "loan_statement", "repayment_schedule", "loan_closure", "property_title", "property_completion",
           "rent_agreement", "agricultural_income_proof", "commission_certificate", "supporting_declaration"}
    assert new <= {t.id for t in types}
    # The service knows each one, so a person may assign it, but its classifier never offers it (no keywords yet).
    ingestion = {d["document_type"]: d for d in reader.load_ingestion_section(published_data_root, "document_types")["documents"]}
    keywords = reader.load_ingestion_section(published_data_root, "keywords")["types"]
    for type_id in new:
        assert ingestion[type_id]["enabled"] is False, type_id
        assert type_id not in keywords, type_id


# --- The business checklist is unchanged ---

BBG_ITEMS = {"coi", "moa_aoa", "board_resolution", "pan_entity", "kyc_promoters", "fs_fy_minus3", "fs_fy_minus2",
             "fs_fy_minus1", "itr", "bank_statements", "gst_returns"}


def test_the_business_checklist_names_no_lap_condition(published_data_root: Path):
    items = {i.id: i for i in reader.load_checklist_taxonomy(published_data_root).items}
    assert {i for i, item in items.items() if "bbg" in item.products} == BBG_ITEMS
    for item_id in BBG_ITEMS:
        item = items[item_id]
        assert (item.customer_types, item.case_types, item.when_any) == ([], [], None), item_id
    bbg, provisional = items_for(published_data_root, constitution="private_limited", facilities=["cash_credit"],
                                 amount_inr=1, collateral_present=False, product="bbg", case_type="renewal",
                                 declared={"gstin"}, rows={"existing_loans"})
    assert _ids(bbg) == BBG_ITEMS and provisional is False


# --- What counts as declared ---


def test_a_value_is_declared_when_it_says_something():
    values = {"gstin": GSTIN, "declared_rental_income_inr": "2,40,000", "declared_other_income_inr": "0",
              "declared_monthly_salary_inr": "", "pan": None, "co_owner": "no", "property_owner": "yes"}
    assert declared_names(values) == {"gstin", "declared_rental_income_inr", "property_owner"}


def test_a_section_has_rows_when_a_row_holds_a_value():
    groups = {
        "existing_loans": [{"lender": {"value": "Example Bank", "proposed": None, "source": "person"}}],
        "properties": [{"property_type": {"value": " ", "proposed": None, "source": "person"}}],
        "applicants": [],
    }
    assert row_sections(groups) == {"existing_loans"}


# --- Validation at publish ---


def _publish_with(tmp_path: Path, monkeypatch, old: str, new: str) -> None:
    config = tmp_path / "config"
    shutil.copytree(writer.CONFIG_DIR, config)
    path = config / "checklist_taxonomy.yaml"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    monkeypatch.setattr(writer, "CONFIG_DIR", config)
    writer.publish(data_root=tmp_path / "a", author="t")


@pytest.mark.parametrize("old,new,message", [
    ("customer_types: [salaried]", "customer_types: [pensioner]", "unknown customer type 'pensioner'"),
    ("customer_types: [salaried]", "customer_types: [private_limited]", "unknown customer type 'private_limited'"),
    ("case_types: [balance_transfer, balance_transfer_top_up]", "case_types: [balance_transfer, renewal]",
     "unknown case type 'renewal'"),
    ("declared: [gstin]", "declared: [gstn]", "declares unknown value 'gstn'"),
    ("rows: [existing_loans]", "rows: [existing_loan]", "unknown repeating section 'existing_loan'"),
    ("named_in: [properties.owners]", "named_in: [properties.owner]", "unknown parties field 'properties.owner'"),
    ("customer_types: [salaried]", "customer_type: [salaried]", r"unknown keys \['customer_type'\]"),
    ("rows: [existing_loans]", "row: [existing_loans]", r"(?s)when_any\.row\b.*Extra inputs are not permitted"),
    ("coverage: {kind: parties, named_in", "coverage: {kind: parties, name_in", r"unknown keys \['name_in'\]"),
    ("category: Application", "category: Applications", "category 'Applications' is not one of the sections"),
])
def test_publishing_refuses_an_unknown_applicability_rule(tmp_path: Path, monkeypatch, old, new, message):
    with pytest.raises(ValueError, match=message):
        _publish_with(tmp_path, monkeypatch, old, new)


def test_the_check_refuses_an_empty_condition_and_a_named_list_outside_a_parties_coverage():
    from engine.configstore.schema import ChecklistCondition, CoverageRule, checklist_problems
    from engine.intake import checklist_terms

    taxonomy = writer.load_authored_sections()["checklist_taxonomy"].model_copy(deep=True)
    assert checklist_problems(taxonomy, checklist_terms()) == []
    items = {i.id: i for i in taxonomy.items}
    items["lap_rent_agreement"].when_any = ChecklistCondition()
    items["lap_salary_slips"].coverage = CoverageRule(kind="monthly_periods", months=3, named_in=["properties.owners"])
    assert checklist_problems(taxonomy, checklist_terms()) == [
        "checklist_taxonomy.lap_salary_slips: named_in is for a parties coverage",
        "checklist_taxonomy.lap_rent_agreement: when_any names no condition",
    ]
    # Without the products' terms (a caller that has none), only the sections are checked.
    assert checklist_problems(taxonomy, None) == []


def test_a_checklist_published_before_the_applicability_rules_still_reads(published_data_root: Path):
    """A version published before customer types, case types, declared values and named parties were
    checklist keys still loads: none of its items has a condition, so each applies as before."""
    version = reader.published_version(published_data_root)["version"]
    folder = published_data_root / "config_store" / "versions" / version
    taxonomy = json.loads((folder / "checklist_taxonomy.json").read_text(encoding="utf-8"))
    for item in taxonomy["items"]:
        for key in ("customer_types", "case_types", "when_any"):
            item.pop(key, None)
        if item.get("coverage"):
            item["coverage"].pop("named_in", None)
            item["coverage"].pop("what", None)
    older = ChecklistTaxonomySection.model_validate(taxonomy)
    assert all((i.customer_types, i.case_types, i.when_any) == ([], [], None) for i in older.items)
    assert all(i.coverage is None or i.coverage.named_in == [] for i in older.items)


# --- Through the screens: the preview and a created case ---


def _cell(value: str, source: str = "person") -> dict:
    return {"value": value, "proposed": None, "source": source}


APPLICANTS = [
    {"name": _cell("Rohan Kulkarni"), "role": _cell("applicant"), "pan": _cell("ABCPK1234F", "identifier"),
     "income_considered": _cell("yes"), "property_owner": _cell("yes")},
    {"name": _cell("Meera Kulkarni"), "role": _cell("co_applicant"), "relationship": _cell("spouse"),
     "pan": _cell("BCDPK5678G")},
]
PROPERTY = {"property_type": _cell("residential"), "occupancy": _cell("self_occupied"), "pincode": _cell("411038"),
            "owners": _cell("Rohan Kulkarni"), "declared_value_inr": _cell("9500000"), "construction": _cell("complete")}


def _lap_case(**overrides) -> dict:
    body = {"product": "lap", "channel": "email", "customer_type": "salaried", "case_type": "new",
            "amount_inr": 4_500_000, "tenure_months": 180, "pan": "ABCPK1234F",
            "groups": {"applicants": APPLICANTS, "properties": [PROPERTY]}}
    body.update(overrides)
    return body


PROFESSIONAL_CASE = dict(customer_type="self_employed_professional", case_type="balance_transfer_top_up",
                         gstin=GSTIN, header={"declared_rental_income_inr": _cell("240000")})


@pytest.fixture()
def rm(client: TestClient) -> dict:
    return sign_in(client, RM)


def _preview(client: TestClient, headers: dict, **body) -> dict:
    r = client.post("/api/cases/checklist-preview", json={"product": "lap", "amount_inr": 4_500_000, **body},
                    headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_preview_reads_the_case_type_and_what_the_form_declares(client, rm):
    salaried = _preview(client, rm, customer_type="salaried", case_type="new")
    assert {i["id"] for i in salaried["items"]} == COMMON | SALARIED and salaried["provisional"] is False
    professional = _preview(client, rm, customer_type="self_employed_professional", case_type="balance_transfer_top_up",
                            fields={"gstin": GSTIN, "declared_rental_income_inr": "240000"})
    assert {i["id"] for i in professional["items"]} == MATRIX[1][1]
    assert {i["id"] for i in professional["items"] if i["blocking"]} == MATRIX[1][2]
    loans = _preview(client, rm, customer_type="salaried", case_type="new",
                     groups={"existing_loans": [{"lender": _cell("Example Bank"), "emi_inr": _cell("25000")}]})
    assert EXISTING_LOANS <= {i["id"] for i in loans["items"]} and not TAKEOVER & {i["id"] for i in loans["items"]}
    # Each item names the documents a person can file for it.
    assert all(i["document_types"] for i in professional["items"])
    # The sections are the checklist's, in order: each item's is one of them.
    assert {i["category"] for i in professional["items"]} <= set(professional["sections"])


def test_a_preview_without_the_new_fields_reads_as_before(client, rm):
    body = _preview(client, rm, customer_type="salaried")
    assert {i["id"] for i in body["items"]} == COMMON | SALARIED


def _intake(client: TestClient, headers: dict, case: dict):
    parts = [("case", (None, json.dumps(case), "application/json")),
             ("files", ("kestrel pan.pdf", fixture_file("kestrel pan.pdf"), "application/octet-stream"))]
    r = client.post("/api/cases/intake", files=parts, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["case"]


@pytest.mark.parametrize("overrides,index", [({}, 0), (PROFESSIONAL_CASE, 1)], ids=["salaried-new",
                                                                                     "professional-bt-top-up"])
def test_a_created_lap_case_has_exactly_its_checklist(client, rm, overrides, index):
    case = _intake(client, rm, _lap_case(**overrides))
    readiness = client.get(f"/api/cases/{case['id']}/checklist", headers=sign_in(client, ANALYST)).json()
    _, expected, blocking = MATRIX[index]
    assert {i["item_id"] for i in readiness["items"]} == expected
    assert {i["item_id"] for i in readiness["items"] if i["blocking"]} == blocking
    assert readiness["provisional"] is False


def test_the_property_owners_kyc_asks_only_for_the_owners_named(client, rm, published_data_root):
    case = _intake(client, rm, _lap_case())
    root = published_data_root
    add_doc(root, case["id"], "pan_card", {"person_name": "Rohan Kulkarni", "pan": "ABCPK1234F"})
    conn = db.connect(root)
    try:
        from engine import pipeline

        pipeline.refresh_case(conn, root, case["id"])
    finally:
        conn.close()
    items = {i["item_id"]: i for i in client.get(f"/api/cases/{case['id']}/checklist",
                                                 headers=sign_in(client, ANALYST)).json()["items"]}
    # Rohan, the only owner named on the property, has filed his PAN: the owners' KYC is complete.
    assert items["lap_property_owner_kyc"]["status"] == "satisfied"
    # Every applicant's PAN or Form 60 is asked for: Meera's is not yet on file, and the gap says so.
    pan = items["lap_pan_or_form_60"]
    assert pan["status"] == "insufficient"
    assert pan["deficiency"] == "PAN or Form 60 missing for 1 of 2: Meera Kulkarni"
    assert items["lap_signature_proof"]["status"] == "missing"
