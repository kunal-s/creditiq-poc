"""Keys the engine reads from the environment, set from git-ignored files under workflow/private/
(CLAUDE.md rule 3) when the environment does not already carry them. Values are never logged."""

from __future__ import annotations

import os
from pathlib import Path

PRIVATE = Path(__file__).resolve().parents[1] / "workflow" / "private"
FILES = ("openai.env",)


def load() -> None:
    for name in FILES:
        path = PRIVATE / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")
