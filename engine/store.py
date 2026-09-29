"""Read-only access to the case store under CREDITIQ_DATA_ROOT.

Layout: <root>/cases/<id>/case.json. Nothing writes cases yet; the writable
case store is FRD F-01 (docs/functional-requirements.md). Until then
`list_cases` returning `[]` is the expected state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
# The git-ignored local workflow area; the data root is its data/ subfolder
# unless CREDITIQ_DATA_ROOT says otherwise. RBL case data lives only here.
DEFAULT_DATA_ROOT = REPO_ROOT / "workflow" / "data"


def data_root() -> Path:
    return Path(os.environ.get("CREDITIQ_DATA_ROOT", str(DEFAULT_DATA_ROOT)))


def cases_dir() -> Path:
    return data_root() / "cases"


def list_cases() -> list[dict]:
    root = cases_dir()
    if not root.is_dir():
        return []
    cases = []
    for case_dir in sorted(root.iterdir()):
        case_file = case_dir / "case.json"
        if case_file.is_file():
            cases.append(json.loads(case_file.read_text(encoding="utf-8")))
    return cases


def get_case(case_id: str) -> dict | None:
    case_file = cases_dir() / case_id / "case.json"
    if not case_file.is_file():
        return None
    return json.loads(case_file.read_text(encoding="utf-8"))
