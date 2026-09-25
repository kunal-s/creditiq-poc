"""Config loading for the engine (roles + terminology).

Authored YAML, read-only here. The configuration *writer* (drafts, publish,
versioning under the data root) is a separate package this module must
never import (CLAUDE.md rule 4).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


@lru_cache
def load_roles_config() -> dict:
    path = REPO_ROOT / "config" / "roles.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache
def load_terminology() -> dict:
    path = REPO_ROOT / "terminology" / "rbl.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def role_label(role_id: str) -> str:
    for role in load_roles_config()["roles"]:
        if role["id"] == role_id:
            return role["label"]
    raise KeyError(f"unknown role id {role_id!r}")


def find_user(email: str) -> dict | None:
    email = email.strip().lower()
    for user in load_roles_config()["users"]:
        if user["email"].lower() == email:
            return user
    return None
