from pathlib import Path

import httpx
import pytest

from copilot import compute
from copilot.config import ConfigError, load_dir
from copilot.identity import Principal
from copilot.tools import ToolCaller, _json_schema

CONFIG = Path(__file__).resolve().parent.parent / "config"
CFG = load_dir(CONFIG)
TOOL = CFG.tool("calculate_ratio")
P = Principal("u1", "analyst", frozenset({"output.read"}), "tok")


def spread(**lines):
    """A host answer shaped like the engine's spread: two audited years, one row per line (rupees)."""
    return {
        "columns": [{"fy": "FY 2024-25", "basis": "audited"}, {"fy": "FY 2025-26", "basis": "audited"}],
        "rows": [{"key": k, "label": k.replace("_", " ").capitalize(), "cells": [{"value": v} for v in vs]} for k, vs in lines.items()],
    }


QUICK = dict(current_assets=[63_800_000, 65_100_000], inventories=[21_600_000, 21_600_000], current_liabilities=[32_100_000, 32_100_000])


def test_quick_ratio_per_year_with_inputs_and_working():
    out = compute.run(TOOL.compute, "quick_ratio", spread(**QUICK))
    assert out["ratio"] == "Quick ratio" and out["formula"] == "(Current assets − Inventories) ÷ Current liabilities"
    assert out["results"][0] == {
        "period": "FY 2024-25 (audited)",
        "inputs": "Current assets 6.38 cr; Inventories 2.16 cr; Current liabilities 3.21 cr",
        "working": "(6.38 − 2.16) ÷ 3.21",
        "value": "1.31x",
    }
    assert out["results"][1]["value"] == "1.36x"


@pytest.mark.parametrize("ratio,lines,value", [
    ("debt_to_ebitda", dict(total_borrowings=[31_800_000], ebitda=[26_604_992]), "1.20x"),
    ("return_on_equity", dict(profit_after_tax=[1_000_000], net_worth=[8_000_000]), "12.5%"),
    ("receivable_days", dict(trade_receivables=[31_900_000], revenue_from_operations=[219_856_000]), "53 days"),
])
def test_each_configured_ratio(ratio, lines, value):
    assert compute.run(TOOL.compute, ratio, spread(**lines))["results"][0]["value"] == value


def test_a_missing_input_gives_no_number_and_names_it():
    lines = dict(QUICK, inventories=[None, 21_600_000])
    row = compute.run(TOOL.compute, "quick_ratio", spread(**lines))["results"][0]
    assert row["value"] == "" and row["working"] == "Not worked out: Inventories not on file"
    assert "Inventories" not in row["inputs"]


def test_a_line_the_host_does_not_list_is_missing():
    row = compute.run(TOOL.compute, "debt_to_ebitda", spread(total_borrowings=[1]))["results"][0]
    assert row["working"] == "Not worked out: Ebitda not on file"


def test_a_zero_divisor_gives_no_number_and_names_it():
    row = compute.run(TOOL.compute, "debt_to_ebitda", spread(total_borrowings=[1], ebitda=[0]))["results"][0]
    assert row["value"] == "" and row["working"] == "Not worked out: Ebitda is zero"


def test_negative_figures_keep_their_sign_in_the_working():
    row = compute.run(TOOL.compute, "return_on_equity", spread(profit_after_tax=[-1_000_000], net_worth=[8_000_000]))["results"][0]
    assert row["working"] == "-0.10 ÷ 0.80 × 100" and row["value"] == "-12.5%"


@pytest.mark.parametrize("expr", ["__import__('os')", "a ** 2", "a.b", "a[0]", "f(a)", "a if b else c", "'x'", "True"])
def test_only_arithmetic_is_allowed(expr):
    with pytest.raises(compute.FormulaError):
        compute.parse(expr)


def test_inputs_follow_the_formula():
    assert compute.names("(current_assets - inventories) / current_liabilities") == ["current_assets", "inventories", "current_liabilities"]


def _broken(tmp_path, old, new):
    for f in CONFIG.rglob("*"):
        if f.is_file():
            (tmp_path / f.relative_to(CONFIG)).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / f.relative_to(CONFIG)).write_text(f.read_text())
    t = tmp_path / "tools.yaml"
    assert old in t.read_text()
    t.write_text(t.read_text().replace(old, new))
    return tmp_path


@pytest.mark.parametrize("old,new", [
    ("expression: total_borrowings / ebitda", "expression: total_borrowings ** ebitda"),
    ("enum: [quick_ratio, debt_to_ebitda, return_on_equity, receivable_days]", "enum: [quick_ratio, debt_to_ebitda]"),
])
def test_config_refuses_a_bad_formula_or_a_mismatched_choice(tmp_path, old, new):
    with pytest.raises(ConfigError):
        load_dir(_broken(tmp_path, old, new))


def test_the_model_sees_the_choices_but_not_the_case():
    schema = _json_schema(TOOL)
    assert set(schema["properties"]) == {"ratio"}
    assert schema["properties"]["ratio"]["enum"] == ["quick_ratio", "debt_to_ebitda", "return_on_equity", "receivable_days"]


def caller(handler):
    return ToolCaller(CFG, httpx.AsyncClient(base_url=CFG.host.base_url, transport=httpx.MockTransport(handler)), now=lambda: "T")


async def test_the_tool_reads_the_spread_with_the_users_token_and_does_the_math():
    seen = {}

    def h(req):
        seen.update(path=req.url.path, q=dict(req.url.params), auth=req.headers["authorization"])
        return httpx.Response(200, json=spread(**QUICK))

    r = await caller(h).call(TOOL, P, {"case_id": "1042"}, {"ratio": "quick_ratio"})
    assert r.ok and r.data["results"][0]["value"] == "1.31x"
    assert seen == {"path": "/api/cases/1042/spread", "q": {}, "auth": "Bearer tok"}  # the choice is not sent to the host


async def test_a_ratio_not_offered_is_refused_without_a_call():
    calls = []
    r = await caller(lambda req: calls.append(req) or httpx.Response(200, json={})).call(TOOL, P, {"case_id": "1042"}, {"ratio": "current_ratio"})
    assert not r.ok and r.error == "NEEDS_INPUT" and "quick_ratio" in r.message and calls == []


async def test_no_statements_on_file_is_not_found():
    r = await caller(lambda req: httpx.Response(200, json={"columns": [], "rows": []})).call(TOOL, P, {"case_id": "1042"}, {"ratio": "quick_ratio"})
    assert not r.ok and r.error == "NOT_FOUND"
