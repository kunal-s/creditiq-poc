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
    assert r.classification.type == "provisional_financial_statements"
    assert all(d.document_type != "audited_financial_statements" for d in r.documents)


def test_a_switched_off_type_is_never_offered(cfg):
    """`enabled: false` keeps a type out of the scores, the second pass and the model's list (decision 14)."""
    from ingestion.stages import siblings
    from ingestion.stages.classify import classify
    from ingestion.stages.read import read_document

    from .conftest import fixture_doc

    off = cfg.model_copy(deep=True)
    for d in off.document_types.documents:
        if d.document_type == "audited_financial_statements":
            d.enabled = False
    name = "Southgate_Audited_FS_FY2025.pdf"
    pages = read_document(fixture_doc(name), "pdf", off.quality, off.routing, None)
    result = classify(off, pages, None)
    assert result["type"] != "audited_financial_statements"
    assert all(c["type"] != "audited_financial_statements" for c in result["candidates"])
    assert "audited_financial_statements" not in siblings.group_of(off, "income_tax_return")
    assert "audited_financial_statements" in siblings.group_of(cfg, "income_tax_return")
