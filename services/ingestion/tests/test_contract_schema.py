import json
from pathlib import Path

from ingestion.contracts import IngestRequest, IngestResult

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def test_the_exported_schemas_are_current():
    """Regenerate with `PYTHONPATH=. .venv/bin/python scripts/export_contracts.py`."""
    for name, model in (("ingest-result.v2.schema.json", IngestResult), ("ingest-request.v2.schema.json", IngestRequest)):
        assert json.loads((CONTRACTS / name).read_text()) == model.model_json_schema(), name
