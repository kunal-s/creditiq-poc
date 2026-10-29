"""Deployment settings from the environment. Behaviour is in the configuration directory, not here."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .recording import Mode

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


@dataclass(frozen=True)
class Settings:
    config_dir: Path
    data_dir: Path  # holds the session, trace and recording database; case content lives here, so never in the repo
    mode: Mode = "replay"
    host: str = "127.0.0.1"
    port: int = 8020
    host_url: str | None = None  # overrides host.yaml base_url
    cors_origins: tuple[str, ...] | None = None  # overrides host.yaml cors_origins

    @classmethod
    def from_env(cls, env: dict | None = None) -> Settings:
        e = os.environ if env is None else env
        data = e.get("COPILOT_DATA_DIR") or (str(Path(e["CREDITIQ_DATA_ROOT"]) / "copilot") if e.get("CREDITIQ_DATA_ROOT") else None)
        if not data:
            raise RuntimeError("set COPILOT_DATA_DIR (or CREDITIQ_DATA_ROOT): the database holds case content and must live outside the repository")
        mode = e.get("COPILOT_MODEL_MODE", "replay")
        if mode not in ("replay", "record", "live"):
            raise RuntimeError(f"COPILOT_MODEL_MODE must be replay, record or live, not {mode!r}")
        return cls(Path(e.get("COPILOT_CONFIG_DIR") or DEFAULT_CONFIG_DIR), Path(data), mode, e.get("COPILOT_HOST", "127.0.0.1"),  # type: ignore[arg-type]
                   int(e.get("COPILOT_PORT", "8020")), e.get("COPILOT_HOST_URL") or None,
                   tuple(o.strip() for o in e["COPILOT_CORS_ORIGINS"].split(",") if o.strip()) if e.get("COPILOT_CORS_ORIGINS") else None)
