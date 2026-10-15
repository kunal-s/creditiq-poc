"""Names of people in full (ID-09): beside the semantic match the other identity checks make, each
person's first, middle and last name across the documents. Every name is fictional."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import db, pipeline
from engine.names import compare_name_parts, name_parts, same_by_parts
from tests.conftest import ANALYST, make_case, sign_in
from tests.triangulation import add_doc


@pytest.mark.parametrize("a,b,expected", [
    ("Tarun S. Velankar", "Tarun Velankar", {"first": "same", "middle": "missing", "last": "same"}),
    ("Tarun Sunil Velankar", "T. S. Velankar", {"first": "initial", "middle": "initial", "last": "same"}),
    ("Tarun Sunil Velankar", "Tarun Suresh Velankar", {"first": "same", "middle": "different", "last": "same"}),
    ("Ishita Barvey", "Ishita Barve", {"first": "same", "middle": None, "last": "different"}),
    ("Tarun Velankar", "Velankar Tarun", {"first": "same", "middle": None, "last": "same"}),
    ("Tarun S Velankar", "Velankar Tarun S", {"first": "same", "middle": "same", "last": "same"}),
    ("Shri Tarun Velankar", "Mr. Tarun Velankar", {"first": "same", "middle": None, "last": "same"}),
    ("Tarun Velankar", "Tarun", {"first": "same", "middle": None, "last": "missing"}),
])
def test_a_name_is_compared_part_by_part(a, b, expected):
    assert compare_name_parts(a, b) == expected


def test_a_name_splits_into_its_parts():
    assert name_parts("Dr. Tarun S. Velankar") == name_parts("Tarun S. Velankar")
    parts = name_parts("Tarun S. Velankar")
    assert (parts.first, parts.middle, parts.last) == ("Tarun", ("S.",), "Velankar")
    assert (name_parts("Tarun").first, name_parts("Tarun").last) == ("Tarun", None)


def test_two_names_can_be_one_person_by_their_parts():
    assert same_by_parts("T. Velankar", "Tarun Velankar")
    assert same_by_parts("Tarun S. Velankar", "T Velankar")
    assert not same_by_parts("Tarun Kale", "Tarun Velankar")
    assert not same_by_parts("Sunil Velankar", "Tarun Velankar")


@pytest.fixture()
def analyst(client: TestClient) -> dict:
    return sign_in(client, ANALYST)


def _case(client: TestClient, analyst: dict, root: Path) -> str:
    return make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd")


def _refresh(root: Path, case_id: str) -> None:
    conn = db.connect(root)
    try:
        pipeline.refresh_case(conn, root, case_id)
    finally:
        conn.close()


def _id09(client: TestClient, analyst: dict, root: Path, case_id: str) -> dict:
    _refresh(root, case_id)
    board = client.get(f"/api/cases/{case_id}/cross-verification", headers=analyst).json()
    return next(i for i in board["items"] if i["finding"]["rule_id"] == "ID-09")["finding"]


def _kyc(root: Path, case_id: str, name: str, din: str = "01234567") -> None:
    add_doc(root, case_id, "director_kyc", {"person_name": name, "din": din, "pan": "ABCPV1234K"})


def _memorandum(root: Path, case_id: str, *names: str) -> None:
    add_doc(root, case_id, "memorandum_articles_of_association", {
        "company_name": "Kestrel Tools Private Limited", "cin": "U28999MH2015PTC123456",
        "directors": [{"name": n, "din": "01234567"} for n in names]})


def test_names_that_agree_in_full_pass(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _kyc(root, case_id, "Tarun Velankar")
    _memorandum(root, case_id, "Tarun Velankar")
    f = _id09(client, analyst, root, case_id)
    assert (f["outcome"], f["severity"], f["blocking"], f["area"]) == ("pass", "mild", False, "identity")
    assert f["explanation"] == "The names of 1 person(s) agree in full across the documents."
    # Neither name has a middle name: an empty cell, not a part missing.
    assert [r["cells"][2:] for r in f["detail"]["rows"]] == [["✓", "", "✓"], ["✓", "", "✓"]]
    assert not any(r["flagged_cells"] for r in f["detail"]["rows"])


def test_a_middle_name_missing_in_one_document_is_a_partial_match(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _kyc(root, case_id, "Tarun S. Velankar")
    _memorandum(root, case_id, "Tarun Velankar")
    f = _id09(client, analyst, root, case_id)
    assert f["outcome"] == "fail"
    assert f["explanation"].startswith("Names differ in part: Tarun S. Velankar: middle name missing in ")
    rows = f["detail"]["rows"]
    assert f["detail"]["columns"] == ["Document", "As written", "First name", "Middle name", "Last name"]
    kyc = next(r for r in rows if r["cells"][0] == "KYC received")
    other = next(r for r in rows if r["cells"][0] != "KYC received")
    assert kyc["cells"][1:] == ["Tarun S. Velankar", "✓", "✓", "✓"] and not kyc["flagged"]
    assert other["cells"][1:] == ["Tarun Velankar", "✓", "Missing", "✓"] and other["flagged"]
    # The middle-name cell is the reason; the KYC row has none.
    assert (other["flagged_cells"], kyc["flagged_cells"]) == ([3], [])
    assert [s["differs"] for s in f["sides"] if s["label"] == "KYC received"] == [False]
    assert f["query"].startswith("Please confirm each person's full name as on their PAN")
    # The card: each document's people split into first, middle and last name.
    columns = {c["label"]: c for c in f["columns"]}
    assert columns["KYC received"]["row_columns"] == ["Person", "First name", "Middle name", "Last name"]
    assert columns["KYC received"]["rows"][0]["cells"] == ["Tarun S. Velankar", "Tarun", "S.", "Velankar"]
    assert columns["KYC received"]["rows"][0]["evidence"], "the KYC's page"
    [line] = f["highlights"]
    assert line["label"] == "Tarun S. Velankar"
    assert [(x["value"], x["differs"]) for x in line["facts"]] == [("Tarun S. Velankar", False), ("Tarun Velankar", True)]
    assert line["note"].startswith("middle name missing in ")


def test_a_first_name_given_only_as_an_initial_is_found_where_similarity_misses_it(client, analyst,
                                                                                    published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _kyc(root, case_id, "T. Velankar")
    _memorandum(root, case_id, "Tarun Velankar")
    f = _id09(client, analyst, root, case_id)
    assert f["outcome"] == "fail"
    assert "first name only an initial in the KYC received" in f["explanation"]
    kyc = next(r for r in f["detail"]["rows"] if r["cells"][0] == "KYC received")
    assert (kyc["cells"][2], kyc["flagged_cells"]) == ("Initial only", [2])


def test_a_surname_written_differently_is_named_with_its_spelling(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _kyc(root, case_id, "Ishita Barve")
    add_doc(root, case_id, "commercial_bureau_report", {
        "company_name": "Kestrel Tools Private Limited", "pan": "AAACK1234F",
        "related_parties": [{"name": "Ishita Barvey", "relationship": "Director", "pan": "ABCPB5678M"}]})
    f = _id09(client, analyst, root, case_id)
    assert f["outcome"] == "fail"
    assert "Ishita Barvey: last name different (Barve) in the KYC received" in f["explanation"]


def test_the_sourcing_message_is_not_held_to_full_names(client, analyst, published_data_root):
    root = published_data_root
    case_id = make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd",
                        header={"promoters": {"value": "Tarun Velankar", "source": "person"}})
    _kyc(root, case_id, "Tarun S. Velankar")
    _memorandum(root, case_id, "Tarun S. Velankar")
    f = _id09(client, analyst, root, case_id)
    assert f["outcome"] == "pass"
    assert "Sourcing message" not in [s["label"] for s in f["sides"]]


def test_a_person_in_one_document_only_leaves_nothing_to_compare(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _memorandum(root, case_id, "Tarun Velankar")
    f = _id09(client, analyst, root, case_id)
    assert f["outcome"] in ("incomplete", "not_applicable")
    if f["outcome"] == "incomplete":
        assert "Director KYC" in f["missing"]


def test_the_board_counts_nine_identity_rules(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _refresh(root, case_id)
    board = client.get(f"/api/cases/{case_id}/cross-verification", headers=analyst).json()
    assert next(a for a in board["areas"] if a["area"] == "identity")["rules"] == 9


# --- One person or two: similar names listed in one document (ID-04, ID-06, ID-08, ID-09) ---


def _board_findings(client: TestClient, analyst: dict, root: Path, case_id: str) -> dict:
    _refresh(root, case_id)
    board = client.get(f"/api/cases/{case_id}/cross-verification", headers=analyst).json()
    return {i["finding"]["rule_id"]: i["finding"] for i in board["items"]}


def test_two_directors_with_similar_names_in_one_memorandum_are_two_people(client, analyst, published_data_root):
    root = published_data_root
    case_id = make_case(client, analyst, root, borrower="Kestrel Tools Pvt Ltd",
                        header={"promoters": {"value": "Varun Velankar; Tarun Velankar", "source": "person"}})
    _kyc(root, case_id, "Tarun Velankar")
    _memorandum(root, case_id, "Tarun Velankar", "Varun Velankar")
    found = _board_findings(client, analyst, root, case_id)
    # The names are alike (0.93 against name_match 0.90), but the memorandum and the message each list
    # both: the one KYC on file is Tarun's, and Varun's is missing.
    promoters = found["ID-04"]
    assert promoters["outcome"] == "fail"
    assert promoters["explanation"] == "The promoters named differ between sources: Varun Velankar has no KYC on file."
    assert [(r["label"], r["cells"], r["flagged"]) for r in promoters["detail"]["rows"]] == [
        ("Tarun Velankar", ["✓", "✓"], False), ("Varun Velankar", ["—", "✓"], True)]
    # The KYC accounts for Tarun alone; the message names both directors.
    assert [(r["label"], r["cells"]) for r in found["ID-08"]["detail"]["rows"]] == [
        ("Tarun Velankar", ["✓", "✓"]), ("Varun Velankar", ["—", "✓"])]
    # Neither name is held part by part against the other.
    assert found["ID-09"]["outcome"] == "pass"


def test_each_kyc_is_held_against_its_own_director_in_the_memorandum(client, analyst, published_data_root):
    root = published_data_root
    case_id = _case(client, analyst, root)
    _kyc(root, case_id, "Varun Velankar", din="07000002")
    _kyc(root, case_id, "Tarun Velankar", din="01234567")
    add_doc(root, case_id, "memorandum_articles_of_association", {
        "company_name": "Kestrel Tools Private Limited", "cin": "U28999MH2015PTC123456",
        "directors": [{"name": "Tarun Velankar", "din": "01234567"}, {"name": "Varun Velankar", "din": "07000002"}]})
    f = _board_findings(client, analyst, root, case_id)["ID-06"]
    # Varun's KYC is compared with Varun's line of the memorandum, not with Tarun's, which comes first.
    assert (f["outcome"], f["explanation"]) == ("pass", "Identifiers agree for 2 director(s).")
    assert sorted((r["label"], r["cells"][:2]) for r in f["detail"]["rows"]) == [
        ("Tarun Velankar", ["01234567", "01234567"]), ("Varun Velankar", ["07000002", "07000002"])]
