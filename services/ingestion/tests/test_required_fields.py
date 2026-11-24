"""Story 1.7: the case's required fields are configuration, and every source they name exists."""

import copy
from pathlib import Path

import pytest
import yaml

from ingestion.config.loader import load_dir

CONFIG = Path(__file__).resolve().parents[3] / "config" / "ingestion"


def test_the_published_list_loads_and_its_case_document_fields_are_the_former_gap_fields():
    cfg = load_dir(CONFIG)
    assert set(cfg.fields.gap_fields) == {"legal_name", "cin", "pan", "gstin"}
    swept = {k for k, f in cfg.fields.required_fields.items() if f.sweep}
    assert "cin" in swept and "revenue_from_operations" in swept and "account_number" not in swept


@pytest.mark.parametrize("source, problem", [("no_such_type.x", "unknown document type no_such_type"),
                                             ("bank_statement.no_field", "bank_statement has no field no_field"),
                                             ("gstr_3b.table:nothing", "gstr_3b has no table nothing")])
def test_a_source_that_does_not_exist_is_refused(tmp_path, source, problem):
    for f in CONFIG.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())
    data = yaml.safe_load((CONFIG / "fields.yaml").read_text())
    data["required_fields"]["cin"]["from"] = [source]
    (tmp_path / "fields.yaml").write_text(yaml.safe_dump(data, allow_unicode=True))
    with pytest.raises(Exception, match=problem):
        load_dir(tmp_path)
