import itertools
from pathlib import Path

from engine.checklist import CaseAttributes, derive_checklist

CONSTITUTIONS = ["private_limited", "proprietorship", "partnership"]
FACILITY_COMBOS = [["cash_credit"], ["term_loan"], ["cash_credit", "term_loan"]]
BOOL_COMBOS = list(itertools.product([True, False], repeat=2))  # (collateral, mpbf)


def _ids(items) -> set[str]:
    return {i.id for i in items}


CONSTITUTION_ONLY_ITEMS = {
    "private_limited": {"coi", "moa_aoa", "board_resolution"},
    "proprietorship": set(),
    "partnership": set(),
}

UNIVERSAL_ITEMS = {"pan_entity", "kyc_promoters", "fs_fy_minus3", "fs_fy_minus2", "fs_fy_minus1", "itr", "bank_statements", "gst_returns"}

# Items for documents the configured types cannot read are not on the list (AD-2a).
NOT_ON_THE_LIST = {"gst_registration", "udyam", "fs_provisional", "fs_projected", "cma_data", "stock_statement", "title_document",
                   "valuation_report", "bureau_report", "facilities_declaration", "sanction_letters"}


def test_every_constitution_and_attribute_combination(published_data_root: Path):
    for constitution, facility_types, (collateral, mpbf) in itertools.product(CONSTITUTIONS, FACILITY_COMBOS, BOOL_COMBOS):
        attrs = CaseAttributes.from_request(facility_types=facility_types, collateral_present=collateral, mpbf_applicable=mpbf)
        ids = _ids(derive_checklist(published_data_root, constitution, attrs))
        case = f"{constitution} / facilities={facility_types} / collateral={collateral} / mpbf={mpbf}"

        # Universal items are always required, whatever the constitution or attributes.
        assert UNIVERSAL_ITEMS <= ids, f"missing universal items for {case}: {UNIVERSAL_ITEMS - ids}"
        # The constitution documents the nine types can read, for a company only.
        for other_constitution, other_items in CONSTITUTION_ONLY_ITEMS.items():
            if other_constitution == constitution:
                assert other_items <= ids, f"missing {other_constitution} documents for {case}"
            else:
                assert not (other_items & ids), f"leaked {other_constitution} documents into {case}"
        assert not (NOT_ON_THE_LIST & ids), f"{NOT_ON_THE_LIST & ids} should not be asked for in {case}"
        assert ids == UNIVERSAL_ITEMS | CONSTITUTION_ONLY_ITEMS[constitution]


def test_derive_checklist_is_deterministic(published_data_root: Path):
    attrs = CaseAttributes.from_request(
        facility_types=["cash_credit", "term_loan"], collateral_present=True, mpbf_applicable=True
    )
    first = _ids(derive_checklist(published_data_root, "private_limited", attrs))
    second = _ids(derive_checklist(published_data_root, "private_limited", attrs))
    assert first == second


def test_section_weights_partition_by_category(published_data_root: Path):
    from engine.checklist import section_weights

    attrs = CaseAttributes.from_request(
        facility_types=["cash_credit", "term_loan"], collateral_present=True, mpbf_applicable=True
    )
    items = derive_checklist(published_data_root, "private_limited", attrs)
    weights = section_weights(items)
    assert set(weights) <= {"Constitution and KYC", "Financials", "Banking and operations"}
    assert sum(weights.values()) == sum(i.weight for i in items)


def _from_case(**extra) -> CaseAttributes:
    return CaseAttributes.from_case(
        facilities=["cash_credit"], amount_inr=10_000_000, collateral_present=False,
        facility_sets={"cash_credit": "cash_credit_requested"}, mpbf_above_limit_inr=50_000_000, **extra,
    )


def test_product_and_confirmed_case_type_set_attributes():
    """T2.1: product and case type reach the checklist as attributes an item can require."""
    attrs = _from_case(product="bbg", case_type="renewal")
    assert attrs.has("product_bbg") and attrs.has("case_type_renewal")
    assert attrs.has("cash_credit_requested") and not attrs.has("case_type_new")


def test_unknown_or_unrecorded_case_type_sets_nothing():
    for case_type in ("unknown", None):
        attrs = _from_case(product=None, case_type=case_type)
        assert not any(name.startswith(("case_type_", "product_")) for name in attrs.flags)


def test_no_published_item_requires_a_case_field_attribute_yet(published_data_root: Path):
    """Until T3.10, the case fields change no checklist: no item names them."""
    from engine.configstore.reader import load_checklist_taxonomy

    for item in load_checklist_taxonomy(published_data_root).items:
        assert not any(a.startswith(("product_", "case_type_")) for a in item.requires_attributes), item.id


# The loan against property items every case asks for, whatever its customer or case type
# (tests/test_lap_checklist.py has the full matrix).
LAP_COMMON = {
    "lap_application_form", "lap_pan_or_form_60", "lap_identity_proof", "lap_signature_proof", "lap_address_proof",
    "lap_bureau_report", "lap_property_title", "lap_property_completion", "lap_property_owner_kyc",
    "lap_supporting_documents",
}
LAP_SALARIED = {"lap_salary_slips", "lap_salary_certificate", "lap_form_16", "lap_salary_bank_statements"}


def _lap_ids(root: Path) -> set[str]:
    from engine.configstore.reader import load_checklist_taxonomy

    return {i.id for i in load_checklist_taxonomy(root).items if "lap" in i.products}


def test_each_product_gets_only_its_own_items(published_data_root: Path):
    """Products are a filter on the checklist, not an attribute: a business never gets a loan against
    property item, and a loan against property, keyed by its customer type, gets its items whatever the
    constitution (here, with no customer type, the items every customer needs)."""
    attrs = CaseAttributes.from_request(facility_types=["cash_credit"], collateral_present=True, mpbf_applicable=True)
    lap_items = _lap_ids(published_data_root)
    for constitution in [*CONSTITUTIONS, "unknown"]:
        lap = _ids(derive_checklist(published_data_root, constitution, attrs, product="lap"))
        assert lap == LAP_COMMON, constitution
        for product in ("bbg", None):
            bbg = _ids(derive_checklist(published_data_root, constitution, attrs, product=product))
            assert not bbg & lap_items, (constitution, product)


def test_the_lap_items_are_drafts_awaiting_rbl(published_data_root: Path):
    from engine.configstore.reader import load_checklist_taxonomy

    items = {i.id: i for i in load_checklist_taxonomy(published_data_root).items}
    lap_items = _lap_ids(published_data_root)
    assert all(items[i].source == "provisional" and items[i].products == ["lap"] for i in lap_items)
    assert items["lap_supporting_documents"].blocking is False
    assert all(i.products == ["bbg"] for i in items.values() if i.id not in lap_items)


def test_items_for_a_lap_case_are_provisional_until_its_customer_type(published_data_root: Path):
    from engine.completeness import items_for

    common = dict(constitution="unknown", facilities=[], amount_inr=4500000, collateral_present=True, product="lap")
    unknown, provisional = items_for(published_data_root, **common)
    chosen, settled = items_for(published_data_root, **common, customer_type="salaried")
    assert provisional is True and settled is False
    assert _ids(unknown) == LAP_COMMON
    assert _ids(chosen) == LAP_COMMON | LAP_SALARIED
