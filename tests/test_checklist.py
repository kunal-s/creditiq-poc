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

UNIVERSAL_ITEMS = {"pan_entity", "kyc_promoters", "fs_fy_minus2", "fs_fy_minus1", "itr", "bank_statements", "gst_returns"}

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
