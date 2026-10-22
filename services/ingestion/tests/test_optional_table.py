"""A table the document type may legitimately lack is reported missing but is not a reason for review."""

from pathlib import Path

from ingestion.config.loader import load_dir
from ingestion.stages.score import decide

CFG = load_dir(Path(__file__).resolve().parents[3] / "config" / "ingestion", version="dev")
CLS = {"type": "audited_financial_statements", "confidence": 1.0, "mixed_content": []}
MISSING = {"status": "missing", "reason": "table_not_found", "rows": []}


def _reasons(tables: dict) -> list[dict]:
    return decide(CFG, "A", CLS, {}, [], tables)["reasons"]


def test_an_optional_missing_table_is_not_a_review_reason():
    assert not any(r.get("table") == "cash_flow" for r in _reasons({"cash_flow": MISSING}))


def test_a_required_missing_table_still_is():
    assert {"kind": "table_missing", "table": "balance_sheet"} in _reasons({"balance_sheet": MISSING})
