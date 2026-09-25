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
    "proprietorship": {"proprietor_declaration"},
    "partnership": {"partnership_deed", "partner_authority_letter"},
}

UNIVERSAL_ITEMS = {
    "pan_entity",
    "gst_registration",
    "udyam",
    "kyc_promoters",
    "fs_fy_minus2",
    "fs_fy_minus1",
    "fs_provisional",
    "itr",
    "bank_statements",
    "gst_returns",
}


def test_every_constitution_and_attribute_combination(published_data_root: Path):
    for constitution, facility_types, (collateral, mpbf) in itertools.product(
        CONSTITUTIONS, FACILITY_COMBOS, BOOL_COMBOS
    ):
        attrs = CaseAttributes.from_request(
            facility_types=facility_types,
            collateral_present=collateral,
            mpbf_applicable=mpbf,
        )
        items = derive_checklist(published_data_root, constitution, attrs)
        ids = _ids(items)
        case = f"{constitution} / facilities={facility_types} / collateral={collateral} / mpbf={mpbf}"

        # Universal items are always required, whatever the constitution or attributes.
        assert UNIVERSAL_ITEMS <= ids, f"missing universal items for {case}: {UNIVERSAL_ITEMS - ids}"

        # Constitution-specific documents: exactly the right family, and no other.
        for other_constitution, other_items in CONSTITUTION_ONLY_ITEMS.items():
            if other_constitution == constitution:
                assert other_items <= ids, f"missing {other_constitution} documents for {case}"
            else:
                assert not (other_items & ids), f"leaked {other_constitution} documents into {case}"

        # Collateral-gated items.
        collateral_items = {"title_document", "valuation_report"}
        if collateral:
            assert collateral_items <= ids, f"missing collateral documents for {case}"
        else:
            assert not (collateral_items & ids), f"collateral documents present without collateral for {case}"

        # MPBF-gated item.
        if mpbf:
            assert "cma_data" in ids, f"missing CMA data for {case}"
        else:
            assert "cma_data" not in ids, f"CMA data present without MPBF for {case}"

        # Facility-gated items.
        if "term_loan" in facility_types:
            assert "fs_projected" in ids, f"missing projected financials for {case}"
        else:
            assert "fs_projected" not in ids, f"projected financials present without a term loan for {case}"

        if "cash_credit" in facility_types:
            assert "stock_statement" in ids, f"missing stock statement for {case}"
        else:
            assert "stock_statement" not in ids, f"stock statement present without cash credit for {case}"


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
    assert set(weights) <= {"Constitution and KYC", "Financials", "Banking and operations", "Collateral and security"}
    assert sum(weights.values()) == sum(i.weight for i in items)
