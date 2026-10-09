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

from tests.conftest import RM, case_files, fixture_file, make_case, run_jobs, set_as_of, sign_in, upload

PARTIAL = [n for n, _ in case_files("partial")]
UNIVERSAL = {"pan_entity", "kyc_promoters", "fs_fy_minus2", "fs_fy_minus1", "itr", "bank_statements", "gst_returns"}
COMPANY = {"coi", "moa_aoa", "board_resolution"}


def _checklist(client: TestClient, headers: dict, case_id: str) -> tuple[dict, dict[str, dict]]:
    readiness = client.get(f"/api/cases/{case_id}/checklist", headers=headers).json()
    return readiness, {i["item_id"]: i for i in readiness["items"]}


def _case(client: TestClient, root: Path, names: list[str], borrower: str = "Heronbay Polymers Pvt Ltd") -> tuple[dict, str]:
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, root, borrower=borrower, facilities=["cash_credit"], amount_inr=30000000, collateral_present=False)
    assert upload(client, rm, case_id, [(n, fixture_file(n)) for n in names]).status_code == 202
    run_jobs(root)
    return rm, case_id


def test_tc11_complete_file_meets_the_gate_and_is_ready_for_credit(client: TestClient, published_data_root: Path):
    rm, case_id = _case(client, published_data_root, [n for n, _ in case_files("complete")], "Kestrel Fabricators Pvt Ltd")
    readiness, items = _checklist(client, rm, case_id)
    assert set(items) == UNIVERSAL | COMPANY
    assert {i["status"] for i in items.values()} == {"satisfied"}, {k: v["deficiency"] for k, v in items.items()}
    assert readiness["score_pct"] == 100.0 and readiness["gate_met"] is True
    assert readiness["blocking_open"] == 0 and readiness["ready_for_credit"] is True
    # Every satisfied item links its documents.
    assert all(i["document_ids"] for i in items.values())
    assert len(items["gst_returns"]["document_ids"]) == 12 and len(items["kyc_promoters"]["document_ids"]) == 2
    queries = client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
    assert queries and all(q["resolved"] for q in queries)


def test_tc11_same_file_a_year_later_is_outdated_not_satisfied(client: TestClient, published_data_root: Path):
    """No wall clock: moving as_of moves every age and window rule."""
    rm, case_id = _case(client, published_data_root, [n for n, _ in case_files("complete")], "Kestrel Fabricators Pvt Ltd")
    set_as_of(published_data_root, case_id, "2027-09-29")
    readiness, items = _checklist(client, rm, case_id)
    assert readiness["gate_met"] is False
    assert items["fs_fy_minus1"]["status"] == "missing"
    assert "FY 2026-27" in items["fs_fy_minus1"]["deficiency"]
    assert items["bank_statements"]["status"] == "insufficient" and "Outdated" in items["bank_statements"]["deficiency"]
    assert items["gst_returns"]["status"] == "insufficient"


def test_tc12_missing_items_each_with_a_specific_request(client: TestClient, published_data_root: Path):
    rm, case_id = _case(client, published_data_root, PARTIAL)
    readiness, items = _checklist(client, rm, case_id)
    missing = {k for k, v in items.items() if v["status"] == "missing"}
    assert missing == {"moa_aoa", "pan_entity", "fs_fy_minus2", "itr"}
    assert items["fs_fy_minus2"]["deficiency"] == (
        "Not received: Audited financial statements for FY 2024-25 (year ended 31 Mar 2025)"
        " (received: FY 2025-26 (year ended 31 Mar 2026))"
    )
    assert "AY 2026-27 and AY 2025-26" in items["itr"]["deficiency"]
    assert items["moa_aoa"]["deficiency"].startswith("Not received: Memorandum and Articles")
    assert readiness["gate_met"] is False and readiness["ready_for_credit"] is False
    needed = [q["text"] for q in client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
              if q["group"] == "documents_needed" and not q["resolved"]]
    assert "Memorandum and Articles of Association of the company." in needed
    assert "Audited financial statements for FY 2024-25 (year ended 31 Mar 2025)." in needed


def test_tc13_incomplete_documents_are_insufficient_with_their_deficiency(client, published_data_root):
    rm, case_id = _case(client, published_data_root, PARTIAL)
    _, items = _checklist(client, rm, case_id)
    gst = items["gst_returns"]
    assert gst["status"] == "insufficient"
    assert gst["deficiency"] == "Sep 2025 to Dec 2025 absent (8 of 12 months)"
    assert len(gst["document_ids"]) == 8
    resolution = items["board_resolution"]
    assert resolution["status"] == "insufficient" and resolution["deficiency"].startswith("not signed")
    bank = items["bank_statements"]
    assert bank["status"] == "insufficient"
    assert "Lotuscrest Bank ·1234" in bank["deficiency"] and "Sep 2025 to Dec 2025 absent" in bank["deficiency"]
    # KYC against the party set: the resolution names two directors, one KYC received.
    assert items["kyc_promoters"]["status"] == "insufficient"
    assert items["kyc_promoters"]["deficiency"] == "KYC missing for 1 of 2: Ishita Barve"


def test_tc14_outdated_document_states_its_date_and_permitted_age(client, published_data_root):
    rm, case_id = _case(client, published_data_root, PARTIAL)
    set_as_of(published_data_root, case_id, "2026-11-30")
    _, items = _checklist(client, rm, case_id)
    bank = items["bank_statements"]
    assert bank["status"] == "insufficient"
    assert "Outdated" in bank["deficiency"] and "dated 31 Aug 2026, permitted age 45 days from 30 Nov 2026" in bank["deficiency"]
    queries = client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
    redo = [q["text"] for q in queries if q["group"] == "documents_to_redo"]
    assert any("dated within the last 45 days" in t and "31 Aug 2026" in t for t in redo), redo


def test_tc16_one_consolidated_query_list(client: TestClient, published_data_root: Path):
    names = PARTIAL + ["bank statement apr-mar.pdf", "Sunil Karve PAN.pdf", "gst_sep_photo.pdf", "itr_blurred.pdf"]
    rm, case_id = _case(client, published_data_root, names)
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
    rm, case_id = _case(client, published_data_root, PARTIAL)
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
    "constitution,facilities,amount,collateral",
    [
        ("private_limited", ["cash_credit", "term_loan"], 65000000, True),
        ("partnership", ["overdraft"], 20000000, False),
        ("proprietorship", ["term_loan"], 8000000, True),
        ("private_limited", ["bank_guarantee"], 10000000, False),
        ("partnership", ["cash_credit"], 90000000, False),
    ],
)
def test_tc15_checklist_per_constitution_and_facility(client, published_data_root, constitution, facilities, amount, collateral):
    """The checklist asks for what the configured document types can satisfy: the company documents for a
    company, and the rest for every constitution, whatever the facilities or collateral."""
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower=f"Case {constitution} {facilities[0]} {amount}",
                        constitution=constitution, facilities=facilities, amount_inr=amount, collateral_present=collateral)
    readiness, items = _checklist(client, rm, case_id)
    assert set(items) == UNIVERSAL | (COMPANY if constitution == "private_limited" else set())
    assert readiness["provisional"] is False
    for item in items.values():
        assert item["why"] and item["basis"]


# --- Date validity (expiry, validity end, future-dated), all measured from as_of ---


def test_future_dated_documents_are_flagged_against_as_of(client, published_data_root):
    """Moving as_of before the documents were made leaves them dated after it."""
    rm, case_id = _case(client, published_data_root, [n for n, _ in case_files("complete")], "Kestrel Fabricators Pvt Ltd")
    set_as_of(published_data_root, case_id, "2025-06-01")
    _, items = _checklist(client, rm, case_id)
    resolution = items["board_resolution"]
    assert resolution["status"] == "insufficient" and "after 1 Jun 2025" in resolution["deficiency"]
    redo = [q["text"] for q in client.get(f"/api/cases/{case_id}/queries", headers=rm).json()
            if q["group"] == "documents_to_redo" and not q["resolved"]]
    assert any("which is after 1 Jun 2025" in t for t in redo), redo


def test_expired_id_document_is_insufficient_with_its_expiry_date(client, published_data_root):
    from engine import db

    rm, case_id = _case(client, published_data_root, [n for n, _ in case_files("complete")], "Kestrel Fabricators Pvt Ltd")
    conn = db.connect(published_data_root)
    try:
        doc = conn.execute(
            "SELECT id FROM documents WHERE case_id = ? AND classification LIKE '%director_kyc%' ORDER BY id LIMIT 1", (case_id,)
        ).fetchone()
        conn.execute(
            """INSERT INTO field_values (id, case_id, document_id, field, value, method, status)
               VALUES ('fv-expiry', ?, ?, 'expiry_date', '"2026-03-31"', 'manual', 'corrected')""",
            (case_id, doc["id"]),
        )
    finally:
        conn.close()
    _, items = _checklist(client, rm, case_id)
    kyc = items["kyc_promoters"]
    assert kyc["status"] == "insufficient" and "Expired: valid until 31 Mar 2026" in kyc["deficiency"]


def test_absent_validity_date_is_no_finding(client, published_data_root):
    rm, case_id = _case(client, published_data_root, [n for n, _ in case_files("complete")], "Kestrel Fabricators Pvt Ltd")
    _, items = _checklist(client, rm, case_id)
    assert items["kyc_promoters"]["status"] == "satisfied"
