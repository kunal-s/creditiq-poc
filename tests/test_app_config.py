"""config/app.yaml is well formed: the case-field option lists (T2.1)."""

from __future__ import annotations

import re

import pytest

from engine.config import (
    branch_for_label,
    load_app_config,
    load_roles_config,
    option_default,
    option_ids,
    option_list,
)

LISTS = ["channels", "constitutions", "facilities", "products", "case_types", "branches", "bank_stages"]


@pytest.mark.parametrize("key", LISTS)
def test_option_ids_are_unique_and_labelled(key: str) -> None:
    items = option_list(key)
    ids = [item["id"] for item in items]
    assert ids, f"{key} is empty"
    assert len(ids) == len(set(ids)), f"{key} has duplicate ids"
    assert all(item.get("label") for item in items), f"{key} has an option with no label"


@pytest.mark.parametrize("key", ["products", "bank_stages"])
def test_defaults_are_listed(key: str) -> None:
    assert option_default(key) in option_ids(key)


def test_lists_without_default() -> None:
    assert option_default("case_types") is None
    assert option_default("branches") is None


def test_case_types_keep_unknown() -> None:
    # An unconfirmed case type keeps the checklist provisional, as constitution does.
    assert "unknown" in option_ids("case_types")


def test_case_type_aliases_name_one_type() -> None:
    seen: dict[str, str] = {}
    for item in option_list("case_types"):
        for alias in item.get("aliases", []):
            key = alias.lower()
            assert key not in seen, f"alias {alias!r} names both {seen[key]} and {item['id']}"
            seen[key] = item["id"]


def test_every_user_branch_is_a_configured_branch() -> None:
    for user in load_roles_config()["users"]:
        assert branch_for_label(user["branch"]) is not None, user["branch"]


def test_branch_for_label() -> None:
    assert branch_for_label("mumbai HUB") == "mumbai_hub"
    assert branch_for_label("Nowhere") is None
    assert branch_for_label(None) is None


@pytest.mark.parametrize("key", ["application_id", "customer_id"])
def test_identifier_patterns_compile(key: str) -> None:
    pattern = load_app_config()["case_identifiers"][key]["pattern"]
    if pattern is not None:
        re.compile(pattern)
