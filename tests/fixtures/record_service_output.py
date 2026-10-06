"""Record the real document-processing service's result for each reference document.

    .venv/bin/python -m tests.fixtures.record_service_output

Runs services/ingestion over the reference documents (workflow/docs/reference/fixtures/southgate/,
git-ignored) with the service's own CLI, no model and no OCR, and writes each file's result to
tests/fixtures/service_output/<name>.json. The contract test validates these with the engine's
models and stores them through the engine's own mapping, so a change on either side of the
contract shows up here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "workflow" / "docs" / "reference" / "fixtures" / "southgate"
OUT = ROOT / "tests" / "fixtures" / "service_output"
SERVICE = ROOT / "services" / "ingestion"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for pdf in sorted(DOCS.glob("*.pdf")):
        run = subprocess.run(
            [str(SERVICE / ".venv" / "bin" / "python"), "-m", "ingestion.cli", "ingest", str(pdf), "--case", "CASE",
             "--config-dir", str(ROOT / "config" / "ingestion"), "--overlay", str(SERVICE / "tests" / "fixtures" / "southgate_config"),
             "--no-ocr", "--no-model"],
            cwd=SERVICE, env={"PYTHONPATH": "."}, capture_output=True, text=True, check=True,
        )
        result = json.loads(run.stdout)["files"][0]
        (OUT / f"{pdf.stem}.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(pdf.name, result["status"], (result["classification"] or {}).get("type"), len(result["documents"]))


if __name__ == "__main__":
    main()
