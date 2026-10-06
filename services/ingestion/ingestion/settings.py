"""Deployment settings from the environment. Behaviour lives in published configuration; this is
only where things are (paths, port, keys). Never logged."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_root: Path
    config_dir: Path | None   # development: a configuration directory served as version "dev"
    host: str
    port: int
    api_key: str
    model_mode: str

    @staticmethod
    def from_env() -> "Settings":
        root = os.environ.get("CREDITIQ_DATA_ROOT") or os.environ.get("INGEST_DATA_ROOT") or "./data"
        cd = os.environ.get("INGEST_CONFIG_DIR")
        return Settings(Path(root), Path(cd) if cd else None, os.environ.get("INGEST_HOST", "127.0.0.1"),
                        int(os.environ.get("INGEST_PORT", "3102")), os.environ.get("INGEST_API_KEY", ""),
                        os.environ.get("INGEST_MODEL_MODE", "replay"))

    @property
    def db_path(self) -> Path:
        return self.data_root / "ingestion" / "ingestion.sqlite3"
