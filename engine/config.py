"""Bootstrap config for the engine: roles, permissions, the sign-in
directory (config/roles.yaml) and operational settings (config/app.yaml).

Authored YAML, read-only here. The configuration *writer* (publish and
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
def load_app_config() -> dict:
    path = REPO_ROOT / "config" / "app.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def role_label(role_id: str) -> str:
    for role in load_roles_config()["roles"]:
        if role["id"] == role_id:
            return role["label"]
    raise KeyError(f"unknown role id {role_id!r}")


def role_permissions(role_id: str) -> list[str]:
    return list(load_roles_config().get("permissions", {}).get(role_id, []))


def find_user(email: str) -> dict | None:
    email = email.strip().lower()
    for user in load_roles_config()["users"]:
        if user["email"].lower() == email:
            return user
    return None


def find_user_by_id(user_id: str) -> dict | None:
    for user in load_roles_config()["users"]:
        if user["id"] == user_id:
            return user
    return None


def option_ids(key: str) -> set[str]:
    """Ids of an option list in app.yaml (channels, constitutions, facilities)."""
    return {item["id"] for item in load_app_config()[key]}
