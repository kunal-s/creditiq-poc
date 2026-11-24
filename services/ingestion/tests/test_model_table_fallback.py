"""The model fallback for tables (Epic 5b of the classification restructure; FRD F-15.3, F-15.13): when no header is
found, the model maps the rows from the pages the keyword scorer chooses, and code reads every value from the line the
model names."""

import re

from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.stages.extract.run import extract_instance
from ingestion.store import Store

from .test_tables_keywords import grid


def lines_of(req):
    return dict(re.findall(r"^(p\d+\.l\d+): (.*)$", req.user, re.M))


def client(cfg, answer):
    return ModelClient(FixtureProvider(cfg.llm, answer), "record", Store())


PL = [[(40, "Item"), (300, "Figure A"), (420, "Figure B")],            # headings no configuration names
      [(40, "Revenue from operations"), (300, "23,60,00,000"), (420, "21,10,00,000")],
      [(40, "Finance costs"), (300, "32,00,000"), (420, "30,00,000")]]


def test_scenario_23_a_statement_in_a_layout_no_heading_names_is_mapped_by_the_model(cfg):
    pages = [grid(1, PL, title="Statement of Profit and Loss"), grid(2, [[(40, "Notes to accounts")]], title="Notes")]
    seen = []

    def answer(req):
        if req.task != "table":
            return {}
        ls = lines_of(req)
        seen.append(sorted({i.split(".")[0] for i in ls}))
        if "Profit and Loss" not in req.user.split("Columns")[0] and "profit" not in req.user.lower():
            return {"rows": []}
        rows = []
        for lid, text in ls.items():
            if text.startswith(("Revenue", "Finance")):
                rows.append({"label_line_ids": [lid], "cells": {"current_period": {"line_id": lid, "figure": 1},
                                                                "previous_period": {"line_id": lid, "figure": 2}}})
        return {"rows": rows}

    out = extract_instance(cfg, "audited_financial_statements", pages, client(cfg, answer))
    t = out["tables"]["profit_and_loss"]
    assert t["method"] == "model"
    assert [(r["cells"]["particulars"], r["cells"]["current_period"], r["cells"]["previous_period"]) for r in t["rows"]] == [
        ("Revenue from operations", 236000000, 211000000), ("Finance costs", 3200000, 3000000)]
    assert all(s == ["p1"] for s in seen if s)        # only the page the profit and loss part scores on is shown


def test_a_value_not_on_the_line_the_model_names_is_rejected(cfg):
    pages = [grid(1, PL, title="Statement of Profit and Loss")]

    def answer(req):
        if req.task != "table":
            return {}
        lid = next(i for i, t in lines_of(req).items() if t.startswith("Revenue"))
        return {"rows": [{"label_line_ids": [lid], "cells": {"current_period": {"line_id": lid, "figure": 7},
                                                             "previous_period": {"line_id": lid, "figure": 2}}}]}

    out = extract_instance(cfg, "audited_financial_statements", pages, client(cfg, answer))
    row = out["tables"]["profit_and_loss"]["rows"][0]["cells"]
    assert row["current_period"] is None and row["previous_period"] == 211000000


def test_a_text_table_is_mapped_cell_by_cell(cfg):
    pages = [grid(1, [[(40, "Person"), (200, "Role"), (340, "Tax ID")],
                      [(40, "Meera Sathe"), (200, "Director"), (340, "AXXXX4321K")],
                      [(40, "Rohan Sathe"), (200, "Director"), (340, "BXXXX5678L")]], title="Commercial Credit Information Report")]

    def answer(req):
        if req.task != "table" or "relationship" not in req.user:
            return {"rows": []} if req.task == "table" else {}
        rows = []
        for lid, text in lines_of(req).items():
            if text.startswith(("Meera", "Rohan")):
                rows.append({"label_line_ids": [lid], "cells": {"relationship": {"line_id": lid, "segment": 2},
                                                                "pan": {"line_id": lid, "segment": 3}}})
        return {"rows": rows}

    out = extract_instance(cfg, "commercial_bureau_report", pages, client(cfg, answer))
    t = out["tables"]["related_parties"]
    assert t["method"] == "model"
    assert [(r["cells"]["name"], r["cells"]["relationship"], r["cells"]["pan"]) for r in t["rows"]] == [
        ("Meera Sathe", "Director", "AXXXX4321K"), ("Rohan Sathe", "Director", "BXXXX5678L")]
