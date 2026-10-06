"""Command line: validate configuration, ingest a file, serve. Publishing is the engine's (`creditiq config publish`)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config.loader import ConfigError, load_dir
from .contracts import FileSpec, IngestRequest
from .llm.openai import OpenAIProvider
from .llm.recorder import ModelClient
from .pipeline import Ingestor
from .readers.ocr import get_engine
from .settings import Settings
from .store import Store
from .util import sha256_hex


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ingestion")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("config-validate"); v.add_argument("dir")
    i = sub.add_parser("ingest"); i.add_argument("files", nargs="+"); i.add_argument("--case", default="CASE"); i.add_argument("--config-dir", required=True)
    i.add_argument("--overlay"); i.add_argument("--db", default=":memory:"); i.add_argument("--mode", default="replay"); i.add_argument("--no-ocr", action="store_true"); i.add_argument("--no-model", action="store_true")
    sub.add_parser("serve")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "config-validate":
            cfg = load_dir(a.dir)
            print(f"ok: {len(cfg.document_types.documents)} document types, hash {cfg.hash[:12]}")
        elif a.cmd == "ingest":
            cfg = load_dir(a.config_dir, version="dev", overlay=a.overlay)
            store = Store(a.db)
            model = None if a.no_model else ModelClient(OpenAIProvider(cfg.llm, os.environ.get(cfg.llm.api_key_env)), a.mode, store)
            ing = Ingestor(cfg, store, model, None if a.no_ocr else get_engine(cfg.routing.ocr))
            specs, payloads = [], {}
            for n, f in enumerate(a.files):
                b = Path(f).read_bytes()
                specs.append(FileSpec(file_id=f"f{n}", sha256=sha256_hex(b), original_name=Path(f).name))
                payloads[f"f{n}"] = b
            res = ing.process_request(IngestRequest(case_ref=a.case, config_version="dev", files=specs), payloads)
            print(json.dumps(res.model_dump(mode="json"), indent=2, ensure_ascii=False))
        elif a.cmd == "serve":
            import uvicorn

            s = Settings.from_env()
            if s.host not in ("127.0.0.1", "::1", "localhost") and not s.api_key:
                print("refusing to listen on a non-loopback interface without INGEST_API_KEY", file=sys.stderr)
                return 2
            from .api import create_app

            uvicorn.run(create_app(s), host=s.host, port=s.port)
    except ConfigError as e:
        print(f"configuration error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
