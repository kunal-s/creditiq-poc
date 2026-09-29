"""Locations under CREDITIQ_DATA_ROOT.

Layout (docs/functional-requirements.md AD-3):
- creditiq.sqlite3       the store (engine/db.py)
- cases/<id>/files/      uploaded files, named by SHA-256 (mode 700 tree)
- config_store/          published configuration versions
- recordings/            recorded model responses (AD-5)
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# The git-ignored local workflow area; the data root is its data/ subfolder
# unless CREDITIQ_DATA_ROOT says otherwise. RBL case data lives only here.
DEFAULT_DATA_ROOT = REPO_ROOT / "workflow" / "data"


def data_root() -> Path:
    return Path(os.environ.get("CREDITIQ_DATA_ROOT", str(DEFAULT_DATA_ROOT)))


def cases_dir(root: Path | None = None) -> Path:
    return Path(root or data_root()) / "cases"


def case_files_dir(case_id: str, root: Path | None = None) -> Path:
    return cases_dir(root) / case_id / "files"
