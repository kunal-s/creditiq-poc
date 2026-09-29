"""F-12 to F-14: checklist status per item with the specific deficiency,
readiness against the gate, and the consolidated query list.

TC-11 complete file; TC-12 missing items; TC-13 incomplete documents;
TC-14 outdated documents; TC-15 checklist per constitution and facility;
TC-16 one consolidated query list. All dates relative to the case's fixed
as_of (2026-09-29), never the wall clock.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import RM, fixture_file, make_case, run_jobs, set_as_of, sign_in, upload

PARTIAL = ["partial_bundle.pdf"]


def _checklist(client: TestClient, headers: dict, case_id: str) -> tuple[dict, dict[str, dict]]:
    readiness = client.get(f"/api/cases/{case_id}/checklist", headers=headers).json()
    return readiness, {i["item_id"]: i for i in readiness["items"]}


def _heronbay(client: TestClient, root: Path, names: list[str]) -> tuple[dict, str]:
    rm = sign_in(client, RM)
    case_id = make_case(
        client, rm, root, borrower="Heronbay Polymers Pvt Ltd", facilities=["cash_credit"], amount_inr=30000000,
        collateral_present=False,
    )
    assert upload(client, rm, case_id, [(n, fixture_file(n)) for n in names]).status_code == 202
    run_jobs(root)
    return rm, case_id


def test_tc11_complete_file_meets_the_gate_and_is_ready_for_credit(client: TestClient, published_data_root: Path):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Kestrel Fabricators Pvt Ltd")
    upload(client, rm, case_id, [("complete_bundle.pdf", fixture_file("complete_bundle.pdf"))])
    run_jobs(published_data_root)
    readiness, items = _checklist(client, rm, case_id)
    assert {i["status"] for i in items.values()} == {"satisfied"}, {k: v["deficiency"] for k, v in items.items()}
    assert readiness["score_pct"] == 100.0 and readiness["gate_met"] is True
    assert readiness["blocking_open"] == 0 and readiness["ready_for_credit"] is True
    # Every satisfied item links its documents.
    assert all(i["document_ids"] for i in items.values())
    # The nil declaration means no sanction letters are required (F-12.1).
    assert "sanction_letters" not in items
    # No open query remains.
    queries = client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
    assert queries and all(q["resolved"] for q in queries)


def test_tc11_same_file_a_year_later_is_outdated_not_satisfied(client: TestClient, published_data_root: Path):
    """No wall clock: moving as_of moves every age and window rule."""
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Kestrel Fabricators Pvt Ltd")
    upload(client, rm, case_id, [("complete_bundle.pdf", fixture_file("complete_bundle.pdf"))])
    run_jobs(published_data_root)
    set_as_of(published_data_root, case_id, "2027-09-29")
    readiness, items = _checklist(client, rm, case_id)
    assert readiness["gate_met"] is False
    assert items["fs_fy_minus1"]["status"] == "missing"
    assert "FY 2026-27" in items["fs_fy_minus1"]["deficiency"]
    assert items["stock_statement"]["status"] == "insufficient"


def test_tc12_missing_items_each_with_a_specific_request(client: TestClient, published_data_root: Path):
    rm, case_id = _heronbay(client, published_data_root, PARTIAL)
    readiness, items = _checklist(client, rm, case_id)
    missing = {k for k, v in items.items() if v["status"] == "missing"}
    assert missing == {"moa_aoa", "pan_entity", "gst_registration", "udyam", "fs_fy_minus2", "itr", "ageing",
                       "bureau_report", "sanction_letters"}
    assert items["fs_fy_minus2"]["deficiency"] == (
        "Not received: Audited financial statements for FY 2024-25 (year ended 31 Mar 2025)"
        " (received: FY 2025-26 (year ended 31 Mar 2026))"
    )
    assert "AY 2026-27 and AY 2025-26" in items["itr"]["deficiency"]
    assert items["moa_aoa"]["deficiency"].startswith("Not received: Memorandum and Articles")
    # Declared existing facilities bring in their sanction letters (F-12.1).
    assert items["sanction_letters"]["blocking"] is False
    assert readiness["gate_met"] is False and readiness["ready_for_credit"] is False
    needed = [q["text"] for q in client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
              if q["group"] == "documents_needed" and not q["resolved"]]
    assert "Memorandum and Articles of Association of the company." in needed
    assert "Audited financial statements for FY 2024-25 (year ended 31 Mar 2025)." in needed


def test_tc13_incomplete_documents_are_insufficient_with_their_deficiency(client, published_data_root):
    rm, case_id = _heronbay(client, published_data_root, PARTIAL)
    _, items = _checklist(client, rm, case_id)
    gst = items["gst_returns"]
    assert gst["status"] == "insufficient"
    assert gst["deficiency"] == "Sep 2025 to Dec 2025 absent (8 of 12 months)"
    assert len(gst["document_ids"]) == 8
    resolution = items["board_resolution"]
    assert resolution["status"] == "insufficient" and resolution["deficiency"].startswith("not signed")
    provisional = items["fs_provisional"]
    assert provisional["status"] == "insufficient" and "balance sheet pages absent" in provisional["deficiency"]
    bank = items["bank_statements"]
    assert bank["status"] == "insufficient"
    assert "Tidewater Bank ·5678" in bank["deficiency"] and "1 of 2" in bank["deficiency"]
    # KYC against the party set: the resolution names two directors, one KYC received.
    assert items["kyc_promoters"]["status"] == "insufficient"
    assert items["kyc_promoters"]["deficiency"] == "KYC missing for 1 of 2: Ishita Barve"


def test_tc14_outdated_document_states_its_date_and_permitted_age(client, published_data_root):
    rm, case_id = _heronbay(client, published_data_root, PARTIAL)
    _, items = _checklist(client, rm, case_id)
    stock = items["stock_statement"]
    assert stock["status"] == "insufficient"
    assert stock["deficiency"] == "Outdated: dated 30 Jun 2026, permitted age 60 days from 29 Sep 2026"
    queries = client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
    redo = [q["text"] for q in queries if q["group"] == "documents_to_redo"]
    assert (
        "Stock and book-debt statement dated within the last 60 days (the copy received is dated 30 Jun 2026)."
        in redo
    )


def test_tc16_one_consolidated_query_list(client: TestClient, published_data_root: Path):
    names = PARTIAL + ["bank statement apr-mar.pdf", "Sunil Karve PAN.pdf", "gst_sep_photo.pdf", "itr_blurred.pdf"]
    rm, case_id = _heronbay(client, published_data_root, names)
    queries = [q for q in client.get(f"/api/cases/{case_id}/queries", headers=rm).json() if not q["resolved"]]
    groups = [q["group"] for q in queries]
    # Grouped, in order: documents needed, documents to redo, clarifications.
    assert groups == sorted(groups, key=["documents_needed", "documents_to_redo", "clarifications"].index)
    by_group = {g: [q for q in queries if q["group"] == g] for g in set(groups)}
    assert {q["source_kind"] for q in by_group["documents_needed"]} == {"checklist"}
    redo = by_group["documents_to_redo"]
    assert any("not signed" in q["text"] for q in redo)
    assert any(q["source_kind"] == "quality" and "blurred" in q["text"] for q in redo)
    clar = by_group["clarifications"]
    assert any(q["source_kind"] == "label" and "bank statement apr-mar.pdf" in q["text"] for q in clar)
    assert any(q["source_kind"] == "party" and "Sunil Karve PAN.pdf" in q["text"] for q in clar)
    # GST gap asks for exactly the absent months (the photo covers Sep 2025).
    assert "GST returns (GSTR-3B) for Oct 2025 to Dec 2025." in [q["text"] for q in by_group["documents_needed"]]
    # Items link their evidence where there is a document.
    assert all(q["evidence"] for q in redo)


def test_tc16_resolved_items_stay_on_the_list_as_resolved(client: TestClient, published_data_root: Path):
    rm, case_id = _heronbay(client, published_data_root, PARTIAL)
    before = {q["id"]: q for q in client.get(f"/api/cases/{case_id}/queries", headers=rm).json()}
    fy2 = next(q for q in before.values() if q["source_ref"] == "fs_fy_minus2")
    assert fy2["resolved"] is False
    # The audited statements for FY 2024-25 arrive (named as a bank statement).
    upload(client, rm, case_id, [("bank statement apr-mar.pdf", fixture_file("bank statement apr-mar.pdf"))])
    run_jobs(published_data_root)
    after = {q["id"]: q for q in client.get(f"/api/cases/{case_id}/queries", headers=rm).json()}
    assert after[fy2["id"]]["resolved"] is True
    assert set(before) <= set(after)
    _, items = _checklist(client, rm, case_id)
    assert items["fs_fy_minus2"]["status"] == "satisfied"


@pytest.mark.parametrize(
    "constitution,facilities,amount,collateral,expected,absent",
    [
        ("private_limited", ["cash_credit", "term_loan"], 65000000, True,
         {"coi", "moa_aoa", "board_resolution", "fs_projected", "cma_data", "stock_statement", "title_document"},
         {"partnership_deed", "proprietor_declaration"}),
        ("partnership", ["overdraft"], 20000000, False,
         {"partnership_deed", "partner_authority_letter", "stock_statement", "ageing"},
         {"coi", "board_resolution", "fs_projected", "cma_data", "title_document"}),
        ("proprietorship", ["term_loan"], 8000000, True,
         {"proprietor_declaration", "fs_projected", "title_document", "valuation_report"},
         {"coi", "partnership_deed", "stock_statement", "cma_data"}),
        ("private_limited", ["bank_guarantee"], 10000000, False,
         {"coi", "bank_statements", "gst_returns"},
         {"stock_statement", "fs_projected", "cma_data", "title_document"}),
        ("partnership", ["cash_credit"], 90000000, False,
         {"cma_data", "stock_statement", "partnership_deed"},
         {"fs_projected", "coi"}),
    ],
)
def test_tc15_checklist_per_constitution_and_facility(
    client, published_data_root, constitution, facilities, amount, collateral, expected, absent
):
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower=f"Case {constitution} {facilities[0]} {amount}",
                        constitution=constitution, facilities=facilities, amount_inr=amount,
                        collateral_present=collateral)
    readiness, items = _checklist(client, rm, case_id)
    assert expected <= set(items)
    assert not absent & set(items)
    assert readiness["provisional"] is False
    for item in items.values():
        assert item["why"] and item["basis"]
