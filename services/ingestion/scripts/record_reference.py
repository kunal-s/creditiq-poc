"""Record the live model's answers for the reference documents, and report what it did.

    set -a; . ../../.env.local; set +a
    PYTHONPATH=. .venv/bin/python scripts/record_reference.py [--fresh]

Runs every reference document through the pipeline with the configured model in `record` mode and
stores each request and answer in tests/fixtures/recordings/reference.sqlite3. A later run replays
them (INGEST_MODEL_MODE=replay) without the network. Prints the model's classification of files the
signals could not place, every field the model supplied (with the line it cited), and every value the
page check rejected."""

import json
import os
import sys
from pathlib import Path

from ingestion.config.loader import load_dir
from ingestion.contracts import FileSpec
from ingestion.llm.openai import OpenAIProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.store import Store
from ingestion.util import sha256_hex

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parents[1] / "workflow" / "docs" / "reference" / "fixtures" / "southgate"
DB = ROOT / "tests" / "fixtures" / "recordings" / "reference.sqlite3"


def main() -> None:
    if "--fresh" in sys.argv:
        for p in DB.parent.glob("reference.sqlite3*"):
            p.unlink()
    cfg = load_dir(ROOT.parents[1] / "config" / "ingestion", version="dev", overlay=ROOT / "tests" / "fixtures" / "southgate_config")
    store = Store(DB)
    mode = os.environ.get("INGEST_MODEL_MODE", "record")
    model = ModelClient(OpenAIProvider(cfg.llm, os.environ.get(cfg.llm.api_key_env)), mode, store)
    ing = Ingestor(cfg, store, model, None)
    for pdf in sorted(DOCS.glob("*.pdf")):
        data = pdf.read_bytes()
        r = ing.process_file("REF", FileSpec(file_id="f", sha256=sha256_hex(data), original_name=pdf.name, content_type="application/pdf"), data)
        c = r.classification
        print(f"\n== {pdf.name}: {c.type or 'UNASSIGNED'} ({c.tier})" + (f" | {c.reason[:150]}" if c.tier != "signals" and c.reason else ""))
        for d in r.documents:
            for name, f in d.fields.items():
                if f.method == "model":
                    print(f"   model filled {name} = {json.dumps(f.value, ensure_ascii=False)[:110]}  [p{f.source.page}: {(f.source.text or '')[:70]!r}]")
                elif f.status == "missing" and f.reason not in ("not_found",):
                    print(f"   {name}: missing, {f.reason}")
    print(f"\nlive calls this run: {model.calls}")
    rows = store._q("SELECT task, json_extract(response,'$.usage.prompt_tokens'), json_extract(response,'$.usage.completion_tokens'), json_extract(response,'$.model'), origin FROM llm_calls")
    print(f"recorded calls: {len(rows)} | prompt tokens {sum(r[1] or 0 for r in rows)} | completion tokens {sum(r[2] or 0 for r in rows)} | models {sorted({r[3] for r in rows})} | origins {sorted({r[4] for r in rows})}")


if __name__ == "__main__":
    main()
