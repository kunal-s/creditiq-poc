"""config/app.yaml is well formed: the case-field option lists (T2.1)."""

from __future__ import annotations

import re

import pytest

from engine.config import (
    branch_for_label,
    product,
    products,
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


@pytest.mark.parametrize("product_id", ["bbg", "lap"])
def test_case_type_aliases_name_one_type_per_product(product_id: str) -> None:
    """Within a product an alias names one case type; across products it may differ ("balance transfer"
    is a business's takeover and a loan against property's balance transfer)."""
    seen: dict[str, str] = {}
    for item in option_list("case_types"):
        if item["id"] not in product(product_id).case_types:
            continue
        for alias in item.get("aliases", []):
            key = alias.lower()
            assert key not in seen, f"alias {alias!r} names both {seen[key]} and {item['id']}"
            seen[key] = item["id"]


def test_products_are_well_formed() -> None:
    found = {p.id: p for p in products()}
    assert list(found) == ["bbg", "lap"]
    assert (found["bbg"].prefix, found["lap"].prefix) == ("BBG", "LAP")
    assert found["bbg"].constitution_based and not found["lap"].constitution_based
    assert found["bbg"].minimum == ("borrower", "facilities", "amount_inr")
    assert found["lap"].minimum == ("applicants", "customer_type", "amount_inr", "tenure_months", "properties")
    assert product(None).id == option_default("products") == "bbg"
    with pytest.raises(KeyError):
        product("car")


def test_every_product_has_a_form() -> None:
    from engine import intake

    forms = intake.schema()
    assert set(forms) == {p.id for p in products()}
    for pid, form in forms.items():
        assert form["start"]["documents"]["required"] and form["start"]["documents"]["min_files"] >= 1, pid
        assert form["start"]["message_required"] is False, pid


@pytest.mark.parametrize(("key", "value", "problem"), [
    ("case_types", ["refinance"], "unknown"),
    ("prefix", "lap", "capital letters"),
    ("minimum", ["shoe_size"], "unknown fields"),
])
def test_a_product_naming_what_is_not_defined_is_refused(monkeypatch, key, value, problem) -> None:
    import copy

    from engine import config

    cfg = copy.deepcopy(load_app_config())
    cfg["products"]["options"][1][key] = value
    monkeypatch.setattr(config, "load_app_config", lambda: cfg)
    with pytest.raises(config.ConfigError, match=problem):
        products()


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
