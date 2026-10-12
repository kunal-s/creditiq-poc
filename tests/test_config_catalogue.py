"""The configuration catalogue (docs/functional-requirements.md F-00, AD-2a)."""

import subprocess
from pathlib import Path

import pytest

import yaml

from engine import policy
from engine.config import load_roles_config, option_ids
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
# The cross-checks switched off: the board-resolution and statement rules.
SWITCHED_OFF = {"BR-01", "BR-02", "BR-03", "BR-04", "FS-01", "FS-02"}


def _cross(sections, **changes):
    return cross_check({**sections, **changes}, writer.load_ingestion_sections(), facilities=option_ids("facilities"))


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
    assert "9 document types" in out.stdout


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
        "ID-01", "ID-02", "ID-03", "ID-04", "ID-05", "ID-06", "ID-07", "ID-08", "ID-09",
        "BR-01", "BR-02", "BR-03", "BR-04",
        "TO-01", "TO-02", "TO-03", "TO-04", "TO-05",
        "TX-01", "TX-02", "TX-03", "TX-04", "TX-05", "FS-01", "FS-02",
        "BA-01", "BA-02", "OB-01", "OB-02", "OB-03",
    }
    # The income-tax rules are shown with turnover (the tax return's turnover among the sources).
    assert {r.area for r in rules} == {"identity", "authority", "turnover", "financials", "accounts", "obligations"}


def test_six_rules_are_switched_off_and_stay_configured(published_data_root: Path):
    """The cross-verification board covers the test plan's four areas: the board-resolution and
    statement rules stay configured, switched off (`enabled: false`), and the others run in their
    configured order, the income-tax rules with turnover."""
    checks = reader.load_crosschecks(published_data_root)
    assert (len(checks.rules), len(checks.enabled_rules)) == (30, 24)
    assert {r.id for r in checks.rules if not r.enabled} == SWITCHED_OFF
    assert [r.id for r in checks.enabled_rules] == [r.id for r in checks.rules if r.id not in SWITCHED_OFF]
    assert list(dict.fromkeys(r.area for r in checks.enabled_rules)) == ["identity", "turnover", "accounts", "obligations"]


def test_cross_check_validates_a_switched_off_rule():
    """So that it can be switched back on, a switched-off rule's problems are reported as an enabled rule's are."""
    sections = writer.load_authored_sections()
    broken = sections["crosschecks"].model_copy(deep=True)
    rule = next(r for r in broken.rules if r.id == "FS-02")
    assert not rule.enabled
    rule.tolerance = "no_such_tolerance"
    assert _cross(sections, crosschecks=broken) == ["crosschecks.FS-02: unknown tolerance 'no_such_tolerance'"]


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


def _norm_problems(sections, **changes) -> list[str]:
    broken = sections["policy"].model_copy(deep=True)
    norm_id = changes.pop("norm", "EL-03")
    norm = next(n for n in broken.norms if n.id == norm_id)
    for key, value in changes.items():
        setattr(norm, key, value)
    return _cross(sections, policy=broken)


@pytest.mark.parametrize("norm,changes,expected", [
    ("EL-03", {"expression": "net_worth ** 2"}, "unsupported expression"),
    ("EL-03", {"expression": "net_worth > 0"}, "unsupported expression"),
    ("EL-03", {"expression": "net_worth * True"}, "unsupported expression"),
    ("EL-03", {"threshold": None}, "needs label, kind and threshold"),
    ("FR-01", {"ratio": "no_such_ratio"}, "unknown ratio"),
    ("EL-03", {"source": None}, "needs a source and status"),
    ("EL-03", {"non_positive_denominator": "deviation"}, "non_positive_denominator needs a division"),
    ("EL-05", {"threshold": 25}, "threshold differs from the turnover method"),
])
def test_cross_check_reports_each_bad_norm(norm, changes, expected):
    problems = _norm_problems(writer.load_authored_sections(), norm=norm, **changes)
    assert any(expected in p for p in problems), problems


def test_cross_check_reports_a_duplicate_norm_id():
    sections = writer.load_authored_sections()
    broken = sections["policy"].model_copy(deep=True)
    broken.norms.append(broken.norms[0].model_copy())
    assert any("duplicate norm ids" in p for p in _cross(sections, policy=broken))


def test_security_cover_waits_for_a_collateral_document_type(published_data_root: Path):
    families = {n.family for n in reader.load_policy(published_data_root).norms}
    groups = {t.group for t in reader.load_document_types(published_data_root).types}
    assert "security_cover" not in families
    # When a collateral document type arrives, security-cover norms are owed (F-20.1).
    assert "collateral" not in groups


def test_approval_matrix_is_published_and_provisional(published_data_root: Path):
    assert "approval_matrix" in reader.published_version(published_data_root)["section_hashes"]
    matrix = reader.load_approval_matrix(published_data_root)
    assert matrix.source == "provisional" and matrix.status == "provisional"
    rows = [*matrix.authorities, *[b for bands in matrix.bands.values() for b in bands], *matrix.deviations]
    assert rows and all(r.status == "provisional" for r in rows)


def test_matrix_authorities_are_roles_or_committees(published_data_root: Path):
    roles = load_roles_config()
    names = {u["name"].lower() for u in roles["users"]} | {part.lower() for u in roles["users"] for part in u["name"].split()}
    role_labels = {r["label"].lower() for r in roles["roles"]}
    for authority in reader.load_approval_matrix(published_data_root).authorities:
        label = authority.label
        assert label.endswith(("Officer", "Head", "Committee")), label
        assert not any(name in label.lower().split() for name in names), label
        assert label.lower() not in role_labels, label


def test_matrix_products_cover_every_facility(published_data_root: Path):
    products = reader.load_approval_matrix(published_data_root).products
    union = [f for p in products for f in p.facilities]
    assert set(union) == option_ids("facilities") and len(union) == len(set(union))


def _matrix(**changes):
    sections = writer.load_authored_sections()
    raw = sections["approval_matrix"].model_dump()
    for path, value in changes.items():
        target = raw
        keys = path.split(".")
        for key in keys[:-1]:
            target = target[int(key)] if key.isdigit() else target[key]
        last = keys[-1]
        if value is _DELETE:
            del target[int(last) if last.isdigit() else last]
        elif last.isdigit():
            target[int(last)] = value
        else:
            target[last] = value
    model = type(sections["approval_matrix"]).model_validate(raw)
    return _cross(sections, approval_matrix=model)


_DELETE = object()


@pytest.mark.parametrize("changes,expected", [
    ({"bands.term.1.authority": "branch_head"}, "bands.term: unknown authority 'branch_head'"),
    ({"bands.term.1.up_to_inr": 10_000_000}, "bands.term: up_to_inr must strictly ascend"),
    ({"bands.term.4.up_to_inr": 900_000_000}, "bands.term: exactly one open band, and it last"),
    ({"bands.term.0.up_to_inr": None}, "bands.term: exactly one open band, and it last"),
    ({"bands.term": _DELETE}, "bands must be given for exactly the products"),
    ({"deviations.3": _DELETE}, "deviation category 'documentation' has no rule"),
    ({"deviations.3.category": "pricing"}, "deviation rule for unknown category 'pricing'"),
    ({"deviations.3.category": "financial"}, "duplicate deviation rule category"),
    ({"authorities.1.level": 1}, "duplicate authority levels"),
    ({"authorities.4.level": 7}, "authority levels must be consecutive from 1"),
    ({"authorities.1.key": "credit_officer"}, "duplicate authority keys"),
    ({"deviations.0.at_least": "branch_head"}, "names unknown authority 'branch_head'"),
    ({"bands.term.1.authority": "credit_officer", "bands.term.0.authority": "regional_credit_head"},
     "bands.term: the authority must not fall as the amount rises"),
    ({"products.1.facilities": ["term_loan", "cash_credit"]}, "facility 'cash_credit' must belong to exactly one product"),
    ({"products.1.facilities": ["overdraft"]}, "facility 'term_loan' must belong to exactly one product"),
    ({"products.1.facilities": ["term_loan", "gold_loan"]}, "unknown facility 'gold_loan'"),
    ({"status": "active"}, "an active matrix may not keep provisional rows"),
])
def test_cross_check_rejects_a_broken_matrix(changes, expected):
    problems = _matrix(**changes)
    assert any(expected in p for p in problems), problems


def test_the_committed_matrix_passes_the_cross_check():
    assert _matrix() == []


def test_private_config_overrides_the_committed_section(tmp_path: Path):
    private = tmp_path / "private"
    private.mkdir()
    raw = yaml.safe_load((writer.CONFIG_DIR / "policy.yaml").read_text(encoding="utf-8"))
    norm = next(n for n in raw["norms"] if n["id"] == "FR-01")
    norm["threshold"] = 1.3
    (private / "policy.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    default = writer.publish(data_root=tmp_path / "a", author="t")
    overridden = writer.publish(data_root=tmp_path / "b", author="t", private_dir=private)
    assert overridden["private_sections"] == ["policy"] and default["private_sections"] == []
    assert overridden["version"] != default["version"]
    published = reader.load_policy(tmp_path / "b")
    assert next(n for n in published.norms if n.id == "FR-01").threshold == 1.3
