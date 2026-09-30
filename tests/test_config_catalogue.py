"""The configuration catalogue (docs/functional-requirements.md F-00)."""

from pathlib import Path

from engine.configstore import reader, writer
from engine.configstore.schema import cross_check


def test_every_checklist_item_is_satisfied_by_some_document_type(published_data_root: Path):
    types = reader.load_document_types(published_data_root)
    taxonomy = reader.load_checklist_taxonomy(published_data_root)
    covered = {item for t in types.types for item in t.satisfies}
    assert {i.id for i in taxonomy.items} <= covered


def test_every_referenced_dictionary_is_published(published_data_root: Path):
    types = reader.load_document_types(published_data_root)
    for t in types.types:
        if t.dictionary:
            assert reader.load_dictionary(published_data_root, t.dictionary).id == t.dictionary


def test_cross_check_reports_a_dangling_reference():
    sections = writer.load_authored_sections()
    broken = sections["document_types"].model_copy(deep=True)
    broken.types[1].satisfies = ["no_such_item"]
    problems = cross_check({**sections, "document_types": broken})
    assert any("no_such_item" in p for p in problems)


def test_cross_check_reports_a_bad_regex():
    sections = writer.load_authored_sections()
    broken = sections["document_types"].model_copy(deep=True)
    broken.types[1].signals.required = ["(unclosed"]
    assert any("does not compile" in p for p in cross_check({**sections, "document_types": broken}))


def test_key_fields_cover_the_test_plan_list(published_data_root: Path):
    """Test plan §5.3: the key fields exist in some dictionary, flagged key."""
    key = set()
    for t in reader.load_document_types(published_data_root).types:
        if t.dictionary:
            d = reader.load_dictionary(published_data_root, t.dictionary)
            key |= {f.name for f in d.fields if f.key_field}
    expected = {
        "pan", "gstin", "cin", "udyam_number", "revenue_from_operations", "ebitda", "profit_after_tax",
        "net_worth", "total_borrowings", "current_assets", "current_liabilities", "outward_taxable_supplies",
        "transactions", "score", "facilities", "amount_requested",
    }
    assert expected <= key, expected - key


def test_alignment_and_crosschecks_are_published(published_data_root: Path):
    alignment = reader.load_alignment(published_data_root)
    assert alignment.financial_year_start_month == 4
    assert {e.id for e in alignment.bank_credit_exclusions} >= {
        "own_account_transfer",
        "loan_disbursal",
        "reversal",
        "returned_cheque",
    }
    rules = reader.load_crosschecks(published_data_root).rules
    # The F-19.2 minimum rule set.
    assert {r.id for r in rules} >= {
        "ID-01", "ID-02", "ID-03", "ID-04", "TO-01", "TO-02", "TO-03", "TO-04",
        "BA-01", "BA-02", "OB-01", "OB-02",
    }


def test_cross_check_reports_an_unknown_tolerance_and_source():
    sections = writer.load_authored_sections()
    broken = sections["crosschecks"].model_copy(deep=True)
    broken.rules[0].tolerance = "no_such_tolerance"
    broken.rules[1].sources = ["no_such_type"]
    problems = cross_check({**sections, "crosschecks": broken})
    assert any("no_such_tolerance" in p for p in problems)
    assert any("no_such_type" in p for p in problems)


def test_policy_norms_are_published_with_their_categories(published_data_root: Path):
    policy = reader.load_policy(published_data_root)
    families = {n.family for n in policy.norms}
    assert families == {"eligibility", "ratios", "security_cover", "documentation"}
    categories = {c.key for c in policy.deviation_categories}
    assert all(n.category in categories for n in policy.norms)


def test_cross_check_reports_a_bad_norm():
    sections = writer.load_authored_sections()
    broken = sections["policy"].model_copy(deep=True)
    broken.norms[0].expression = "no_such_input / net_worth"
    broken.norms[1].category = "no_such_category"
    broken.norms[2].expression = "net_worth /"
    problems = cross_check({**sections, "policy": broken})
    assert any("no_such_input" in p for p in problems)
    assert any("no_such_category" in p for p in problems)
    assert any("does not parse" in p for p in problems)
