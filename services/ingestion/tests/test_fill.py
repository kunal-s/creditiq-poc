"""Epic 6, the service's side: a case's pending fields read from pages the engine names (scenarios 19 and 33)."""

import re

from ingestion.contracts import FillField, FillRequest
from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.store import Store

from .conftest import fixture_doc, spec

AFS = "Southgate_Audited_FS_FY2025.pdf"


def ask(cfg, fields, pages, model=None):
    data = fixture_doc(AFS)
    req = FillRequest(case_ref="C", config_version="dev", file=spec(AFS, data), pages=pages, fields=fields)
    return Ingestor(cfg, Store(), model, None).fill(req, data)


def test_scenario_33_the_cin_is_read_by_its_form_from_the_auditors_report(cfg):
    got = ask(cfg, [FillField(name="cin")], list(range(1, 10)))
    (v,) = got.found
    assert (v.field, v.value, v.method, v.page) == ("cin", "U17291TZ2016PTC027431", "rules", 1)


def test_only_the_pages_named_are_read(cfg):
    assert ask(cfg, [FillField(name="cin")], [2, 3]).found == []


def test_scenario_19_a_yearly_figure_is_read_for_its_year_by_the_model_and_checked_on_its_line(cfg):
    asked = []

    def answer(req):
        asked.append(req.user)
        lines = dict(re.findall(r"^(p\d+\.l\d+): (.*)$", req.user, re.M))
        lid = next((i for i, t in lines.items() if "Revenue from operations" in t), None)
        # The model writes the figure in its own form: the page prints "23,17,84,900".
        got = {"value": "231784900", "line_ids": [lid]} if lid else {"value": None, "line_ids": []}
        return {"fields": {"revenue_from_operations__20250331": got}}

    model = ModelClient(FixtureProvider(cfg.llm, answer), "record", Store())
    got = ask(cfg, [FillField(name="revenue_from_operations", period_end="2025-03-31")], list(range(1, 10)), model)
    (v,) = got.found
    assert (v.value, v.raw_text, v.page, v.method) == (231784900, "23,17,84,900", 6, "model")
    assert "financial year ended 31 March 2025" in asked[0] and 6 in got.pages_read


def test_a_field_not_on_the_list_is_not_read(cfg):
    assert ask(cfg, [FillField(name="auditor_name")], list(range(1, 10))).found == []


def test_the_sweep_does_not_read_a_file_that_never_names_the_field(cfg):
    calls = []
    model = ModelClient(FixtureProvider(cfg.llm, lambda req: calls.append(req) or {"fields": {}}), "record", Store())
    got = ask(cfg, [FillField(name="revenue_from_operations", period_end="2025-03-31")], [2, 3], model)
    assert got.found == [] and calls == [] and got.trace[-1]["skipped"]
