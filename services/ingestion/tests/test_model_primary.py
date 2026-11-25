"""Model-primary extraction (fields.yaml `extraction: model`): the model reads, code verifies on the page, validators check the figures."""

import re

from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.store import Store
from ingestion.stages.extract.run import cue_pages
from ingestion.stages.validate import validate_instance

from .conftest import fixture_doc, spec
from .test_validators import F, get

ITR = "Southgate_ITR_FY2024_FY2025.pdf"
CO = "Southgate Textiles Private Limited"
LABELS = {"taxpayer_name": CO, "assessment_year": r"Assessment Year\s*:?\s*(\d{4}-\d{2})", "gross_total_income": r"Gross Total Income\s+([\d,]+)"}
WRONG: dict[str, str] = {}


def answerer(req):
    if req.task == "classify":
        return {"type": "none_of_these", "reason": "n/a"}
    lines = dict(re.findall(r"^(p\d+\.l\d+): (.*)$", req.user, re.M))
    out = {}
    for f in re.findall(r"^- (\w+) \(", req.user, re.M):
        value, ids = None, []
        for i, t in lines.items():
            if f in WRONG:
                value, ids = WRONG[f], [i]
                break
            if f in LABELS and (m := re.search(LABELS[f], t)):
                value, ids = (m.group(1) if m.groups() else m.group(0)), [i]
                break
        out[f] = {"value": value, "line_ids": ids}
    return {"fields": out}


def run(cfg):
    client = ModelClient(FixtureProvider(cfg.llm, answerer), "record", Store())
    return Ingestor(cfg, Store(), client, None).process_file("C", spec(ITR, fixture_doc(ITR)), fixture_doc(ITR)), client


def test_the_model_reads_the_fields_and_identifiers_stay_rule_based(cfg):
    r, client = run(cfg)
    d = r.documents[0]
    assert d.fields["pan"].method != "model"                       # identifier rule
    assert d.fields["taxpayer_name"].method == "model" and d.fields["taxpayer_name"].value == CO
    assert d.fields["taxpayer_name"].source.page and d.fields["taxpayer_name"].source.bbox   # evidence is still real
    assert d.fields["assessment_year"].method == "model" and d.fields["assessment_year"].value == "2024-25"
    assert client.calls >= 1


def test_a_value_that_is_not_on_the_cited_line_is_rejected(cfg):
    WRONG["taxpayer_name"] = "Some Other Company Limited"
    try:
        r, _ = run(cfg)
    finally:
        WRONG.clear()
    f = r.documents[0].fields["taxpayer_name"]
    assert f.status == "missing" and f.reason == "not_found_on_page"


def test_the_model_reads_the_first_page_and_the_pages_that_score_highest_for_its_fields(cfg):
    """Story 6.7 (scenario 31): no page pattern per type; the pages on which the fields still to read have a cue."""
    from ingestion.stages.read import read_document
    pages = read_document(fixture_doc(ITR), "pdf", cfg.quality, cfg.routing, None)
    rules = cfg.fields.types["income_tax_return"].fields
    hit = next(p.no for p in pages if re.search("COMPUTATION OF (?:TOTAL )?INCOME", p.text(), re.I))
    chosen = [p.no for p in cue_pages(rules, ["total_income", "gross_total_income"], pages, 1)]
    assert chosen[0] == pages[0].no and len(chosen) <= 2
    assert all(re.search("Total Income", next(p for p in pages if p.no == n).text(), re.I) for n in chosen[1:])
    assert [p.no for p in cue_pages(rules, ["total_income"], pages, len(pages))] == [p.no for p in pages]
    assert hit and cfg.fields.types["income_tax_return"].extraction == "model"


def test_itr_figures_are_checked_against_each_other(cfg):
    good = {"assessment_year": F("2024-25"), "financial_year": F("2023-24"), "gross_total_income": F(387402), "total_income": F(387400),
            "tax_payable": F(97501), "tax_paid": F(286854), "refund_amount": F(189350)}
    checks = validate_instance(cfg, "income_tax_return", [], good, {})
    assert all(get(checks, c)["outcome"] == "pass" for c in (
        "itr_assessment_year_form", "itr_financial_year_form", "itr_years_consecutive", "itr_gross_not_below_total", "itr_amounts_not_negative", "itr_tax_reconciles"))
    bad = {**good, "assessment_year": F("ITR6"), "gross_total_income": F(100), "tax_paid": F(-10101010)}
    checks = validate_instance(cfg, "income_tax_return", [], bad, {})
    failed = {c["id"] for c in checks if c["outcome"] == "fail"}
    assert {"itr_assessment_year_form", "itr_amounts_not_negative", "itr_gross_not_below_total", "itr_tax_reconciles"} <= failed
    wrong_years = validate_instance(cfg, "income_tax_return", [], {**good, "financial_year": F("2021-22")}, {})
    assert get(wrong_years, "itr_years_consecutive")["outcome"] == "fail"


def test_every_type_is_read_by_the_model_first_and_every_model_field_has_a_hint(cfg):
    """The published configuration reads every type model-first; a field the model reads says where it is printed.
    Identifier fields stay rule-based, and `llm: false` fields are never given to the model."""
    by_id = cfg.document_types.by_id()
    for tid, tf in cfg.fields.types.items():
        assert tf.extraction == "model", tid
        for f in by_id[tid].schema_.fields:
            rule = tf.fields.get(f.name)
            if rule and (rule.identifier or rule.llm is False):
                continue
            assert rule and rule.llm_hint, f"{tid}.{f.name} has no llm_hint"
