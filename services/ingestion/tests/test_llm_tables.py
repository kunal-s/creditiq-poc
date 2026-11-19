"""A statement no configured layout finds is mapped by the model (stages/extract/llm_tables.py, FRD F-15.3): the model
names the lines and which figure on each, never a figure; code reads every label and figure from the page and
rejects what is not there (F-15.4). Layouts still come first: the model is not asked when one finds the table."""

from __future__ import annotations

from ingestion.llm.provider import ModelRequest
from ingestion.stages.extract.run import extract_instance
from ingestion.stages.score import decide

from tests.test_xbrl_statements import _page

TYPE = "audited_financial_statements"


class Reader:
    """A stand-in for the model: answers each table request with the rows given, and counts the calls."""

    def __init__(self, rows_for):
        self.rows_for, self.requests = rows_for, []

    def call(self, req: ModelRequest) -> dict:
        self.requests.append(req)
        if req.task != "table":
            return {"fields": {}} if req.task == "extract" else {"type": "none_of_these", "reason": ""}
        return {"rows": self.rows_for(req)}


def _statement():
    # A layout none of the configured ones knows: its own title and column heading.
    return _page(1, [
        (20, "STATEMENT OF ASSETS AND LIABILITIES AS ON 31-03-2026"),
        (40, "Item", "FY26", "FY25"),
        (60, "Share capital", "1,000", "900"),
        (71, "Reserves", "(A) 2,000", "1,500"),
        (82, "Long-term borrowings", "-", "300"),
        (93, "Total", "3,000", "2,700"),
    ])


def _row(label_id, cur=(None, None), prev=(None, None)):
    return {"label_line_ids": [label_id], "cells": {"current_period": {"line_id": cur[0], "figure": cur[1]},
                                                    "previous_period": {"line_id": prev[0], "figure": prev[1]}}}


def test_the_model_maps_the_rows_and_the_figures_come_from_the_page(cfg):
    page = _statement()
    line = {l.text.split()[0]: l.id for l in page.content_lines()}
    reader = Reader(lambda req: [
        _row(line["Share"], (line["Share"], 1), (line["Share"], 2)),
        _row(line["Reserves"], (line["Reserves"], 1), (line["Reserves"], 2)),
        _row(line["Long-term"], (line["Long-term"], 1), (line["Long-term"], 2)),
        _row(line["Total"], (line["Total"], 1), (line["Total"], 2)),
    ])
    out = extract_instance(cfg, TYPE, [page], reader)
    t = out["tables"]["balance_sheet"]
    assert t["status"] == "found" and t["method"] == "model"
    assert [(r["cells"]["particulars"], r["cells"]["current_period"], r["cells"]["previous_period"]) for r in t["rows"]] == [
        ("Share capital", 1000, 900), ("Reserves", 2000, 1500), ("Long-term borrowings", 0, 300), ("Total", 3000, 2700)]
    assert t["rows"][1]["raw"]["current_period"] == "2,000", "the figure as printed, without its footnote reference"
    assert t["rows"][0]["source"]["page"] == 1 and t["rows"][0]["source"]["line"].startswith("Share capital")
    # Only the statement a page names is asked for: no page here names a P&L or a cash flow statement.
    assert [r.task for r in reader.requests if r.task == "table"] == ["table"]
    skipped = {e["table"] for e in out["trace"] if e.get("skipped") == "no_candidate_page"}
    assert skipped == {"profit_and_loss", "cash_flow"}
    assert "1,000" not in str(reader.requests[0].schema), "the answer has no place for a figure"


def test_what_the_page_does_not_hold_is_rejected(cfg):
    page = _statement()
    line = {l.text.split()[0]: l.id for l in page.content_lines()}
    reader = Reader(lambda req: [
        _row(line["Share"], (line["Share"], 1), (line["Share"], 3)),   # no third figure on the line
        _row("p9.l99", (line["Reserves"], 1)),                          # a line that is not on the pages shown
        _row(line["Total"], (line["Total"], 1), (line["Total"], 2)),
    ])
    out = extract_instance(cfg, TYPE, [page], reader)
    rows = out["tables"]["balance_sheet"]["rows"]
    assert [(r["cells"]["particulars"], r["cells"]["current_period"], r["cells"]["previous_period"]) for r in rows] == [
        ("Share capital", 1000, None), ("Total", 3000, 2700)]
    assert out["tables"]["balance_sheet"]["unparsed"] == 1
    rejected = {(e.get("row"), e.get("rejected")) for e in out["trace"] if e.get("table") == "balance_sheet"}
    assert (0, "figure_not_on_line") in rejected and (1, "bad_label_line") in rejected


def test_a_table_a_layout_finds_is_not_sent_to_the_model(cfg):
    from tests.test_xbrl_statements import _dates

    bs = _page(1, [
        (20, "SAMPLE TRADERS PRIVATE LIMITED Standalone Financial Statements for period 01/04/2025 to 31/03/2026"),
        (40, "[110000] Balance sheet"),
        *_dates(80, "31/03/2026", "31/03/2025"),
        (91, "Balance sheet [Abstract]"),
        (102, "Total assets", "45,853.06", "36,250.8"),
    ])
    reader = Reader(lambda req: [])
    out = extract_instance(cfg, TYPE, [bs], reader)
    assert out["tables"]["balance_sheet"]["method"] == "rules"
    asked = [r for r in reader.requests if r.task == "table"]
    assert all("Balance sheet / statement of financial position" not in r.user for r in asked)


def test_without_a_model_the_table_stays_missing(cfg):
    out = extract_instance(cfg, TYPE, [_statement()], None)
    assert out["tables"]["balance_sheet"]["status"] == "missing"


def test_a_table_the_model_mapped_sends_the_document_to_a_person(cfg):
    tables = {"balance_sheet": {"status": "found", "method": "model", "rows": [], "unparsed": 0},
              "profit_and_loss": {"status": "found", "method": "rules", "rows": [], "unparsed": 0},
              "cash_flow": {"status": "found", "method": "rules", "rows": [], "unparsed": 0}}
    out = decide(cfg, "A", {"type": TYPE, "confidence": 1.0}, {}, [], tables)
    assert {"kind": "table_by_model", "table": "balance_sheet"} in out["reasons"] and out["decision"] == "human_review"
