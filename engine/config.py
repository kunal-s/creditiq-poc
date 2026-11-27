"""Bootstrap config for the engine: roles, permissions, the sign-in
directory (config/roles.yaml) and operational settings (config/app.yaml).

Authored YAML, read-only here. The configuration *writer* (publish and
versioning under the data root) is a separate package this module must
never import (CLAUDE.md rule 4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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


def feature_enabled(name: str) -> bool:
    """Whether a feature is switched on in config/app.yaml `features:` (on when not named, so a
    deployment that predates the switch keeps what it had)."""
    return bool((load_app_config().get("features") or {}).get(name, True))


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


def option_list(key: str) -> list[dict]:
    """An option list in app.yaml. Lists with a default (products,
    bank_stages) keep their options under `options`."""
    node = load_app_config()[key]
    return node["options"] if isinstance(node, dict) else node


def option_ids(key: str) -> set[str]:
    """Ids of an option list in app.yaml (channels, constitutions, facilities,
    products, case_types, branches, bank_stages)."""
    return {item["id"] for item in option_list(key)}


def option_default(key: str) -> str | None:
    """The configured default of an option list, or None if it has none."""
    node = load_app_config()[key]
    return node.get("default") if isinstance(node, dict) else None


def branch_for_label(label: str | None) -> str | None:
    """The branch id whose label matches a user's branch (case-insensitive)."""
    if not label:
        return None
    needle = label.strip().lower()
    return next((b["id"] for b in option_list("branches") if b["label"].lower() == needle), None)


# --- Products (config/app.yaml `products`) and the form per product (config/intake.yaml) ---


class ConfigError(ValueError):
    """A deployment file names something that is not defined."""


@dataclass(frozen=True)
class ProductConfig:
    """What a case of one product may carry and needs before it can be created."""

    id: str
    label: str
    prefix: str
    case_types: tuple[str, ...]
    stages: tuple[str, ...]
    customer_types: tuple[str, ...]
    programs: tuple[str, ...]
    minimum: tuple[str, ...]

    @property
    def constitution_based(self) -> bool:
        """The product's customer types are constitutions (a business), not the separate list."""
        return set(self.customer_types) <= option_ids("constitutions")


#: The fields a product's `minimum` can name, and what each one means (engine/intake.py `missing_minimum`).
MINIMUM_FIELDS = ("borrower", "facilities", "amount_inr", "applicants", "customer_type", "tenure_months", "properties")


@lru_cache
def load_intake_config() -> dict:
    path = REPO_ROOT / "config" / "intake.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def customer_type_options() -> list[dict]:
    """Every customer type a product may use: the constitutions and the separate list."""
    cfg = load_app_config()
    return [*cfg.get("constitutions", []), *cfg.get("customer_types", [])]


def _check_product(raw: dict, cfg: dict) -> ProductConfig:
    pid = raw["id"]
    known = {
        "case_types": {o["id"] for o in cfg["case_types"]},
        "stages": {o["id"] for o in cfg["bank_stages"]["options"]},
        "customer_types": {o["id"] for o in customer_type_options()},
        "programs": {o["id"] for o in cfg.get("programs", [])},
    }
    for key, ids in known.items():
        unknown = [v for v in raw.get(key) or [] if v not in ids]
        if unknown:
            raise ConfigError(f"products.{pid}.{key}: unknown {unknown}")
    bad = [m for m in raw.get("minimum") or [] if m not in MINIMUM_FIELDS]
    if bad:
        raise ConfigError(f"products.{pid}.minimum: unknown fields {bad}")
    if not raw.get("prefix") or not re.fullmatch(r"[A-Z]{2,4}", raw["prefix"]):
        raise ConfigError(f"products.{pid}.prefix must be 2 to 4 capital letters")
    return ProductConfig(
        id=pid, label=raw["label"], prefix=raw["prefix"],
        case_types=tuple(raw.get("case_types") or ()), stages=tuple(raw.get("stages") or ()),
        customer_types=tuple(raw.get("customer_types") or ()), programs=tuple(raw.get("programs") or ()),
        minimum=tuple(raw.get("minimum") or ()),
    )


def products() -> list[ProductConfig]:
    """The configured products, validated: every list names ids that are defined, prefixes are unique,
    the default is a product, and every product has a form in config/intake.yaml."""
    cfg = load_app_config()
    found = [_check_product(raw, cfg) for raw in cfg["products"]["options"]]
    ids = [p.id for p in found]
    if len(ids) != len(set(ids)):
        raise ConfigError("products: duplicate ids")
    prefixes = [p.prefix for p in found]
    if len(prefixes) != len(set(prefixes)):
        raise ConfigError("products: duplicate prefixes")
    if cfg["products"].get("default") not in ids:
        raise ConfigError("products.default is not a product")
    intake = load_intake_config()
    missing = [i for i in ids if i not in intake]
    if missing:
        raise ConfigError(f"config/intake.yaml has no form for {missing}")
    return found


def product(product_id: str | None) -> ProductConfig:
    """A product by id; None is the configured default."""
    wanted = product_id or option_default("products")
    for p in products():
        if p.id == wanted:
            return p
    raise KeyError(f"unknown product id {product_id!r}")
