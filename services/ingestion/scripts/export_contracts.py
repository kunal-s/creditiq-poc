"""Write the JSON schemas of the service's contract (contracts/*.schema.json).

    PYTHONPATH=. .venv/bin/python scripts/export_contracts.py

The engine's mirror of these models is checked against them (tests/test_ingest_contract.py in the engine)."""

import json
from pathlib import Path

from ingestion.contracts import IngestRequest, IngestResult

OUT = Path(__file__).resolve().parents[1] / "contracts"
OUT.mkdir(exist_ok=True)
for name, model in (("ingest-result.v2.schema.json", IngestResult), ("ingest-request.v2.schema.json", IngestRequest)):
    (OUT / name).write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("wrote", *sorted(p.name for p in OUT.iterdir()))
