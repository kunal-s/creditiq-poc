"""Read-only access to the case store under CREDITIQ_DATA_ROOT.

Layout (plan.md section 3): <root>/sample/cases/<id>/case.json, .../real/...
Stage A: no cases exist yet (Stage B's generator creates Case A and B), so
`list_cases` returning `[]` is the expected, correct state — the frontend
seam renders its designed empty states from that.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
# The git-ignored local workflow area (plan.md "Working rule"); the data root
# is its data/ subfolder unless CREDITIQ_DATA_ROOT says otherwise.
DEFAULT_DATA_ROOT = REPO_ROOT / "workflow" / "data"


def data_root() -> Path:
    return Path(os.environ.get("CREDITIQ_DATA_ROOT", str(DEFAULT_DATA_ROOT)))


def sample_cases_dir() -> Path:
    return data_root() / "sample" / "cases"


def list_cases() -> list[dict]:
    cases_dir = sample_cases_dir()
    if not cases_dir.is_dir():
        return []
    cases = []
    for case_dir in sorted(cases_dir.iterdir()):
        case_file = case_dir / "case.json"
        if case_file.is_file():
            cases.append(json.loads(case_file.read_text(encoding="utf-8")))
    return cases


def get_case(case_id: str) -> dict | None:
    case_file = sample_cases_dir() / case_id / "case.json"
    if not case_file.is_file():
        return None
    return json.loads(case_file.read_text(encoding="utf-8"))
