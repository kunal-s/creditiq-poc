"""Export the API contract (docs/functional-requirements.md AD-4).

Writes:
- contracts/openapi.json                 the engine's OpenAPI schema
- contracts/ingest-result.schema.json    the sidecar's result schema
- contracts/ingest-request.schema.json   the sidecar's request schema

`npm run gen:api` runs this, then generates src/api/schema.gen.ts from
contracts/openapi.json. Commit all generated files; a check fails if they
are stale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.api import app  # noqa: E402
from engine.contracts import IngestRequest, IngestResult  # noqa: E402

OUT = ROOT / "contracts"


def write(name: str, data: dict) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    write("openapi.json", app.openapi())
    write("ingest-result.schema.json", IngestResult.model_json_schema())
    write("ingest-request.schema.json", IngestRequest.model_json_schema())
    print(f"wrote {OUT.relative_to(ROOT)}/openapi.json, ingest-result.schema.json, ingest-request.schema.json")


if __name__ == "__main__":
    main()
