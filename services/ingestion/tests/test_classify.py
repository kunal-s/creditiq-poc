import pytest

from .conftest import IN_SCOPE, OUT_OF_SCOPE


@pytest.mark.parametrize("name,expected", list(IN_SCOPE.items()))
def test_in_scope_documents_are_identified_by_content(results, name, expected):
    c = results[name].classification
    assert c.type == expected and c.tier == "signals" and not c.needs_review
    assert len(c.candidates) == 3 and c.candidates[0].type == expected
    assert c.signals["required"]


@pytest.mark.parametrize("name", OUT_OF_SCOPE)
def test_documents_outside_the_list_are_never_forced_into_a_type(results, name):
    r = results[name]
    assert r.classification.type is None and r.classification.needs_review
    assert r.documents == [] and r.decision == "human_review"
    assert r.review_reasons[0]["kind"] == "type_unassigned"


def test_no_sample_is_flagged_as_mixed_content(results):
    for n, r in results.items():
        assert r.classification.mixed_content == [], n


def test_file_name_is_never_an_input(cfg, ingestor):
    from .conftest import fixture_doc, spec
    b = fixture_doc("Southgate_Entity_PAN.pdf")
    r = ingestor.process_file("C", spec("Certificate_of_Incorporation_FINAL.pdf", b), b)
    assert r.classification.type == "company_pan"


def test_a_bank_narration_mentioning_gst_is_not_a_gst_return(results):
    r = results["Southgate_CCB_CA_Statements_12m.pdf"]
    assert r.classification.type == "bank_statement"
    gstr = next(c for c in r.classification.candidates if c.type == "gstr_3b") if any(c.type == "gstr_3b" for c in r.classification.candidates) else None
    assert gstr is None or gstr.score < r.classification.confidence


def test_provisional_statements_are_not_audited_statements(results):
    r = results["Southgate_Provisional_FY2026.pdf"]
    assert r.classification.type is None
