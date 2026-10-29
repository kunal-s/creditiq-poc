"""Command line: validate a configuration directory."""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="copilot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("config-validate")
    v.add_argument("dir")
    sub.add_parser("serve")
    r = sub.add_parser("import-recordings", help="load recorded model answers (JSON from the record scripts) into the store")
    r.add_argument("file")
    a = ap.parse_args(argv)
    if a.cmd == "import-recordings":
        import json
        from pathlib import Path

        from .settings import Settings, utc_now
        from .store import Store

        store = Store(Settings.from_env().data_dir / "copilot.sqlite3")
        calls = json.loads(Path(a.file).read_text())
        for c in calls:
            store.put_llm_call(c["request_key"], c["model"], utc_now(), c["request"], c["response"], replace=True)
        print(f"imported {len(calls)} recordings")
        return 0
    if a.cmd == "serve":
        import uvicorn

        from .api import create_app
        from .settings import Settings

        st = Settings.from_env()
        if st.host not in ("127.0.0.1", "::1", "localhost"):
            print("refusing to listen on a non-loopback interface", file=sys.stderr)
            return 2
        uvicorn.run(create_app(st), host=st.host, port=st.port)
        return 0
    try:
        cfg = load_dir(a.dir)
    except ConfigError as e:
        print(f"configuration error: {e}", file=sys.stderr)
        return 1
    print(f"ok: {len(cfg.registry.use_cases)} use cases, {len(cfg.tools.tools)} tools, hash {cfg.hash[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
