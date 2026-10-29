"""Record the real model's answers for the golden set and the end-to-end spec's questions (golden.SETS) and report each case.

All data is invented; nothing from a case is sent. The key is read from the environment variable named in llm.yaml,
falling back to a line in <repo>/.env.local; its value is never printed. Run from services/copilot:
    PYTHONPATH=. .venv/bin/python scripts/record_golden.py [--write] [--only golden|e2e]
Without --write it only reports. With it, the recordings replace the *_recordings.json files in tests/fixtures/.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from copilot.config import load_dir
from copilot.settings import DEFAULT_CONFIG_DIR
from copilot.store import Store
from tests import golden


def load_key(name: str) -> None:
    if os.environ.get(name):
        return
    env = Path(__file__).resolve().parents[3] / ".env.local"
    for line in env.read_text().splitlines() if env.exists() else []:
        k, _, v = line.partition("=")
        if k.strip() == name:
            os.environ[name] = v.strip().strip("'\"")


async def main(write: bool) -> int:
    cfg = load_dir(DEFAULT_CONFIG_DIR)
    load_key(cfg.llm.api_key_env)
    if not os.environ.get(cfg.llm.api_key_env):
        print(f"{cfg.llm.api_key_env} is not set and not found in .env.local")
        return 1
    bad = 0
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for cases_file, recordings in golden.SETS:
        if only and cases_file.stem != only:
            continue
        bad += await record_set(cfg, cases_file, recordings, write)
    return 1 if bad else 0


async def record_set(cfg, cases_file: Path, recordings: Path, write: bool) -> int:
    spec = golden.load(cases_file)
    store = Store(Path(tempfile.mkdtemp(prefix="copilot-golden-")) / "c.sqlite3")
    bad = 0
    print(f"-- {cases_file.name}")
    for case in spec["cases"]:
        try:
            res, trace = await golden.run_case(cfg, spec, case, store, "record")
        except Exception as e:  # the kind of failure, not request details
            print(f"FAILED  {case['id']}: {type(e).__name__}: {str(e)[:200]}")
            bad += 1
            continue
        found = golden.problems(cfg, case, res, trace)
        bad += bool(found)
        print(f"{'ok    ' if not found else 'DIFFERS'}  {case['id']}: {res.terminal} / {res.use_case}  {res.text[:90]!r}")
        for f in found:
            print(f"          - {f}")
    if write:
        with store._conn() as c:
            calls = [dict(r) for r in c.execute("SELECT request_key, model, request, response FROM llm_calls ORDER BY request_key")]
        recordings.write_text(json.dumps(calls, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote {len(calls)} recordings to {recordings.name}")
    return bad


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--write" in sys.argv)))
