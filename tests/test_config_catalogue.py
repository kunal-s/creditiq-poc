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
