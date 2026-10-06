"""AD-2a, AD-4: the contract with the document-processing service (version 2).

The canned results the stub client serves, and the real service's output for the reference
documents, validate against the engine's models; the engine stores the real output correctly."""

import hashlib
import json
from pathlib import Path

import pytest

from engine import pipeline
from engine.contracts import IngestFileResult, IngestResult
from tests.conftest import RM, make_case, run_jobs, sign_in, upload

HERE = Path(__file__).resolve().parent / "fixtures"
REAL = sorted((HERE / "service_output").glob("*.json"))
REFERENCE_DOCS = Path(__file__).resolve().parents[1] / "workflow" / "docs" / "reference" / "fixtures" / "southgate"


def test_every_stub_fixture_validates_against_the_contract():
    fixtures = sorted((HERE / "ingest").glob("*.json"))
    assert fixtures
    for path in fixtures:
        IngestFileResult.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_every_fixture_file_has_a_canned_result():
    for path in sorted((HERE / "files").iterdir()):
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert (HERE / "ingest" / f"{sha}.json").is_file(), path.name


def test_the_published_schema_matches_the_model():
    schema = json.loads((Path(__file__).resolve().parents[1] / "contracts" / "ingest-result.schema.json").read_text())
    assert schema == IngestResult.model_json_schema()


def test_the_services_own_schema_has_the_same_properties():
    """The service's models and the engine's mirror cannot drift apart unnoticed."""
    path = Path(__file__).resolve().parents[1] / "services" / "ingestion" / "contracts" / "ingest-result.v2.schema.json"
    if not path.exists():
        pytest.skip("the ingestion service is not present")
    theirs = json.loads(path.read_text())

    def props(schema: dict) -> dict[str, set[str]]:
        return {name.removeprefix("Ingest"): set(d.get("properties", {})) for name, d in {**schema.get("$defs", {})}.items()}

    mine = props(IngestResult.model_json_schema())
    their = {k.removeprefix("Ingest"): set(d.get("properties", {})) for k, d in theirs.get("$defs", {}).items()}
    pairs = {"Field": "FieldResult", "Table": "TableResult", "Check": "Check", "Document": "Document", "Page": "PageInfo",
             "Classification": "Classification", "Confidence": "Confidence", "FileResult": "FileResult", "Source": "Source"}
    for mine_name, their_name in pairs.items():
        if mine_name in mine and their_name in their:
            assert mine[mine_name] == their[their_name], f"{mine_name} differs from the service's {their_name}"
    assert set(IngestResult.model_json_schema()["properties"]) == set(theirs["properties"])


@pytest.mark.skipif(not REAL, reason="no recorded service output")
@pytest.mark.parametrize("path", REAL, ids=lambda p: p.stem)
def test_the_real_service_output_validates(path: Path):
    IngestFileResult.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _unit_of(name: str):
    fr = IngestFileResult.model_validate(json.loads((HERE / "service_output" / f"{name}.json").read_text()))
    return fr, pipeline.units_of(fr)


@pytest.mark.skipif(not REAL, reason="no recorded service output")
def test_instances_become_separate_documents():
    fr, units = _unit_of("Southgate_GSTR3B_Dec2025_Jul2026")
    assert len(units) == 8 and [u.page_from for u in units] == list(range(2, 10))
    assert units[0].instance_key == "December 2025" and units[0].classification.types == ["gstr_3b"]
    assert units[0].identity["gstin"].startswith("33AAHCS6612M")
    _, kyc = _unit_of("Southgate_Director_KYC_Iyer_x2")
    assert [u.identity["name"] for u in kyc] == ["Lakshmi Iyer", "Venkat Iyer"] and kyc[0].identity["din"] == "07421683"


@pytest.mark.skipif(not REAL, reason="no recorded service output")
def test_fields_lists_and_table_cells_are_flattened_with_normalised_boxes():
    _, units = _unit_of("Southgate_MOA_AOA")
    fields = {f.field: f for f in units[0].fields}
    assert fields["directors[0].name"].value == "Lakshmi Iyer" and fields["directors[1].name"].value == "Venkat Iyer"
    assert fields["shareholding[0].number_of_shares"].value == 510000
    assert fields["cin"].status == "missing" and fields["cin"].missing_reason == "not_found"
    for u in (units[0], *_unit_of("Southgate_CCB_CA_Statements_12m")[1]):
        for f in u.fields:
            if f.bbox:
                assert all(0.0 <= v <= 1.0 for v in f.bbox) and f.bbox[0] < f.bbox[2] and f.bbox[1] < f.bbox[3], f.field
    fr, bank = _unit_of("Southgate_CCB_CA_Statements_12m")
    rows = {f.field for f in bank[0].fields if f.field.startswith("transactions[")}
    printed = fr.documents[0].tables["transactions"].rows
    assert len(printed) == 362 and "transactions[361].balance" in rows
    # Only printed cells are stored: a blank debit or credit is not a value.
    assert len([f for f in bank[0].fields if f.field.endswith(".credit")]) == sum(r.cells["credit"] is not None for r in printed)


@pytest.mark.skipif(not REAL, reason="no recorded service output")
def test_a_file_the_service_could_not_place_is_one_unclassified_document_with_candidates():
    fr, units = _unit_of("Southgate_Provisional_FY2026")
    assert len(units) == 1 and units[0].classification.types == [] and (units[0].page_from, units[0].page_to) == (1, 4)
    assert units[0].fields == []


@pytest.mark.skipif(not (REAL and REFERENCE_DOCS.exists()), reason="reference documents not present")
def test_the_reference_case_runs_end_to_end_through_the_engine(client, published_data_root, tmp_path, monkeypatch):
    """Upload the 14 reference documents; the stub serves the real service's recorded answers."""
    canned = tmp_path / "ingest"
    canned.mkdir()
    files = []
    for pdf in sorted(REFERENCE_DOCS.glob("*.pdf")):
        data = pdf.read_bytes()
        out = HERE / "service_output" / f"{pdf.stem}.json"
        (canned / f"{hashlib.sha256(data).hexdigest()}.json").write_text(out.read_text())
        files.append((pdf.name, data))
    monkeypatch.setenv("CREDITIQ_INGEST_FIXTURES", str(canned))
    rm = sign_in(client, RM)
    case_id = make_case(client, rm, published_data_root, borrower="Southgate Textiles Private Limited")
    assert upload(client, rm, case_id, files).status_code == 202
    assert run_jobs(published_data_root) == 1
    docs = client.get(f"/api/cases/{case_id}/documents", headers=rm).json()
    by_type: dict[str, int] = {}
    for d in docs:
        for t in (d["classification"] or {}).get("types", []) or ["unclassified"]:
            by_type[t] = by_type.get(t, 0) + 1
    assert by_type == {
        "gstr_3b": 8, "director_kyc": 2, "income_tax_return": 2, "audited_financial_statements": 2, "bank_statement": 1,
        "certificate_of_incorporation": 1, "memorandum_articles_of_association": 1, "company_pan": 1,
        "board_resolution_borrowing": 1, "unclassified": 4,
    }
    review = client.get(f"/api/review?case_id={case_id}", headers=sign_in(client, "ananya.krishnan@rblbank.com")).json()
    kinds = [i["kind"] for i in review]
    assert kinds.count("type") == 4  # the four documents outside the closed list
    fields = client.get(f"/api/cases/{case_id}/fields", headers=sign_in(client, "ananya.krishnan@rblbank.com")).json()
    assert any(f["field"] == "gstin" and f["status"] == "in_review" for f in fields)  # the check digit is wrong
    assert all(f["evidence"]["page"] >= 1 for f in fields if f["value"] is not None and f["status"] != "missing")
