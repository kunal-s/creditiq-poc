"""Model-primary extraction (fields.yaml `extraction: model`): the model reads, code verifies on the page, validators check the figures."""

import re

from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.store import Store
from ingestion.stages.extract.run import scoped_pages
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


def test_the_model_reads_only_the_first_page_and_the_configured_sections(cfg):
    from ingestion.config.models import PageScope
    from ingestion.stages.read import read_document
    pages = read_document(fixture_doc(ITR), "pdf", cfg.quality, cfg.routing, None)
    section = scoped_pages([PageScope(match="COMPUTATION OF (?:TOTAL )?INCOME", span=1)], pages)
    hit = next(p.no for p in pages if re.search("COMPUTATION OF (?:TOTAL )?INCOME", p.text(), re.I))
    assert [p.no for p in section] == sorted({pages[0].no, hit})
    assert [p.no for p in scoped_pages([], pages)] == [pages[0].no]
    assert cfg.fields.types["income_tax_return"].extraction == "model"


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


def test_a_header_identifier_keeps_one_return_whole_when_schedules_mention_other_years(cfg):
    """A schedule that mentions "assessment year 2025-26" inside a 2024-25 return must not open a second instance."""
    from types import SimpleNamespace

    from ingestion.stages.instances import split_instances

    def pg(no, body):
        return SimpleNamespace(no=no, blank=False, text=lambda b=body: b)

    head = "Acknowledgement Number : 633495911241125   Date of Filing : 13-Dec-2025\n"
    pages = [pg(1, head + "INDIAN INCOME TAX RETURN Assessment Year 2025-26"),
             pg(2, head + "Tax under section 115JB in assessment year 2024-25"),
             pg(3, head + "Schedule MATC assessment year 2025-26")]
    front, groups = split_instances(cfg, "income_tax_return", pages)
    assert front == [] and [[p.no for p in g] for g in groups] == [[1, 2, 3]]


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
