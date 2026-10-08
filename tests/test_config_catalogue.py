"""The configuration catalogue (docs/functional-requirements.md F-00, AD-2a)."""

import subprocess
from pathlib import Path

import pytest

from engine import policy
from engine.configstore import reader, writer
from engine.configstore.schema import cross_check

ROOT = Path(__file__).resolve().parents[1]
INGESTION_VENV = ROOT / "services" / "ingestion" / ".venv" / "bin" / "python"
NINE = {
    "certificate_of_incorporation", "memorandum_articles_of_association", "board_resolution_borrowing", "company_pan",
    "director_kyc", "audited_financial_statements", "income_tax_return", "gstr_3b", "bank_statement",
}
# Existing facilities and the bureau (test plan TC-20, TC-23).
FACILITIES = {"existing_facilities_declaration", "sanction_letter", "commercial_bureau_report"}
TYPES = NINE | FACILITIES


def _cross(sections, **changes):
    return cross_check({**sections, **changes}, writer.load_ingestion_sections())


def test_the_closed_list_is_the_document_types_and_the_sourcing_message(published_data_root: Path):
    types = reader.load_document_types(published_data_root).types
    assert {t.id for t in types} == TYPES | {"application_message"}
    # The facility and bureau types are reconciled by the cross-checks, not asked for on the checklist.
    assert all(not t.satisfies for t in types if t.id in FACILITIES)


def test_every_checklist_item_is_satisfied_by_some_document_type(published_data_root: Path):
    types = reader.load_document_types(published_data_root)
    taxonomy = reader.load_checklist_taxonomy(published_data_root)
    covered = {item for t in types.types for item in t.satisfies}
    assert {i.id for i in taxonomy.items} <= covered


def test_one_version_carries_the_engine_and_the_service_configuration(published_data_root: Path):
    ing = {n: reader.load_ingestion_section(published_data_root, n) for n in writer.INGESTION_SECTIONS}
    assert {d["document_type"] for d in ing["document_types"]["documents"]} == TYPES
    assert set(ing["signals"]["types"]) == TYPES and "reason_codes" in ing["quality"]
    version = reader.published_version(published_data_root)
    assert {f"ingestion.{n}" for n in writer.INGESTION_SECTIONS} <= set(version["section_hashes"])


def test_changing_the_service_configuration_changes_the_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a = writer.publish(data_root=tmp_path / "a", author="t")["version"]
    original = writer.load_ingestion_sections

    def edited():
        sections = original()
        sections["decision"] = {**sections["decision"], "accept_min_document_confidence": 0.99}
        return sections

    monkeypatch.setattr(writer, "load_ingestion_sections", edited)
    b = writer.publish(data_root=tmp_path / "b", author="t")["version"]
    assert a != b


@pytest.mark.skipif(not INGESTION_VENV.exists(), reason="the ingestion service is not installed")
def test_the_service_accepts_the_published_configuration():
    out = subprocess.run([str(INGESTION_VENV), "-m", "ingestion.cli", "config-validate", str(ROOT / "config" / "ingestion")],
                         cwd=ROOT / "services" / "ingestion", env={"PYTHONPATH": "."}, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "12 document types" in out.stdout


def test_cross_check_reports_a_dangling_reference():
    sections = writer.load_authored_sections()
    broken = sections["document_types"].model_copy(deep=True)
    broken.types[1].satisfies = ["no_such_item"]
    assert any("no_such_item" in p for p in _cross(sections, document_types=broken))


def test_cross_check_reports_a_type_the_service_does_not_know():
    sections = writer.load_authored_sections()
    broken = sections["document_types"].model_copy(deep=True)
    broken.types[1].id = "memorandum_of_association"
    assert any("ids differ" in p for p in _cross(sections, document_types=broken))


def test_required_fields_include_the_identifiers_the_checks_rely_on():
    docs = {d["document_type"]: d for d in writer.load_ingestion_sections()["document_types"]["documents"]}
    required = {t: {f["name"] for f in d["schema"]["fields"] if f["required"]} for t, d in docs.items()}
    assert {"cin", "date_of_incorporation"} <= required["certificate_of_incorporation"]
    assert {"pan"} <= required["company_pan"] and {"gstin", "tax_period"} <= required["gstr_3b"]
    assert {"account_number", "statement_period_start", "statement_period_end"} <= required["bank_statement"]
    assert {"assessment_year"} <= required["income_tax_return"] and {"financial_year"} <= required["audited_financial_statements"]
    assert {"borrowing_limit", "lender_name"} <= {f["name"] for f in docs["board_resolution_borrowing"]["schema"]["fields"]}


def test_alignment_and_crosschecks_are_published(published_data_root: Path):
    alignment = reader.load_alignment(published_data_root)
    assert alignment.financial_year_start_month == 4
    assert {e.id for e in alignment.bank_credit_exclusions} >= {"own_account_transfer", "loan_disbursal", "reversal", "returned_cheque"}
    rules = reader.load_crosschecks(published_data_root).rules
    # The rules of docs/cross-verification-plan.md, with OB-01 now that the declaration of existing
    # facilities, the sanction letter and the bureau report are document types.
    assert {r.id for r in rules} == {
        "ID-01", "ID-02", "ID-03", "ID-04", "ID-05", "ID-06", "ID-07", "ID-08",
        "BR-01", "BR-02", "BR-03", "BR-04",
        "TO-01", "TO-02", "TO-03", "TO-04", "TO-05",
        "TX-01", "TX-02", "FS-01", "FS-02",
        "BA-01", "BA-02", "OB-01", "OB-02", "OB-03",
    }
    assert {r.area for r in rules} == {"identity", "authority", "turnover", "tax", "financials", "accounts", "obligations"}


def test_cross_check_reports_an_unknown_tolerance_and_source():
    sections = writer.load_authored_sections()
    broken = sections["crosschecks"].model_copy(deep=True)
    broken.rules[0].tolerance = "no_such_tolerance"
    broken.rules[1].sources = ["no_such_type"]
    problems = _cross(sections, crosschecks=broken)
    assert any("no_such_tolerance" in p for p in problems)
    assert any("no_such_type" in p for p in problems)


def test_policy_norms_are_published_with_their_categories(published_data_root: Path):
    pol = reader.load_policy(published_data_root)
    assert {n.family for n in pol.norms} == {"eligibility", "ratios", "documentation"}
    categories = {c.key for c in pol.deviation_categories}
    assert all(n.category in categories for n in pol.norms)


def test_every_financial_input_of_the_policy_has_a_configured_statement_line(published_data_root: Path):
    cfg = reader.load_statements(published_data_root)
    assert set(policy.FINANCIAL_INPUTS) <= set(cfg.lines) | set(cfg.derived)


def test_derived_statement_lines_name_configured_lines(published_data_root: Path):
    from engine.statements import _terms

    cfg = reader.load_statements(published_data_root)
    for key, expression in cfg.derived.items():
        assert {name for _, name in _terms(expression)} <= set(cfg.lines) | set(cfg.derived) - {key}, key


def test_cross_check_reports_a_bad_norm():
    sections = writer.load_authored_sections()
    broken = sections["policy"].model_copy(deep=True)
    broken.norms[0].expression = "no_such_input / net_worth"
    broken.norms[1].category = "no_such_category"
    broken.norms[2].expression = "net_worth /"
    problems = _cross(sections, policy=broken)
    assert any("no_such_input" in p for p in problems)
    assert any("no_such_category" in p for p in problems)
    assert any("does not parse" in p for p in problems)
