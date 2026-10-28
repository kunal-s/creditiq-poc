"""The unit financial figures are written in (config/statements.yaml `display_unit`): one published
setting an Administrator changes on the Administration screen, followed by the engine's own wording
and read by the screens from /api/config/display-unit. Every name is fictional."""

import pytest

from engine.units import money
from tests.conftest import ANALYST, sign_in
from tests.test_admin_settings import ADMIN, _publish, _settings
from tests.test_cam import _cam, _full_case, _rows, _section, _table


@pytest.mark.parametrize("unit,value,written", [
    ("crore", 42_000_000, "INR 4.20 cr"),
    ("crore", 4_000, "INR 0.00 cr"),
    ("crore", -1_234_567, "INR -0.12 cr"),
    ("lakh", 42_000_000, "INR 420.00 lakh"),
    ("lakh", 1_000_000_000, "INR 10,000.00 lakh"),
    ("thousand", 42_000_000, "INR 42,000.00 thousand"),
    ("thousand", 1_500_000_000, "INR 15,00,000.00 thousand"),
    ("rupee", 42_000_000, "INR 4,20,00,000"),
    ("rupee", -0.4, "INR 0"),
])
def test_a_figure_is_written_in_the_unit_whatever_its_size(unit, value, written):
    assert money(value, unit) == written


def test_a_figure_that_rounds_to_nothing_is_not_negative_zero():
    assert money(-400, "crore") == "INR 0.00 cr"


def test_the_published_unit_is_crore_until_an_administrator_changes_it(client, published_data_root):
    headers = sign_in(client, ANALYST)
    unit = client.get("/api/config/display-unit", headers=headers).json()
    assert (unit["unit"], unit["divisor"], unit["decimals"], unit["suffix"]) == ("crore", 1e7, 2, " cr")
    admin = sign_in(client, ADMIN)
    display = _settings(client, admin)["display"]
    assert display["unit"] == "crore"
    assert [(o["id"], o["example"]) for o in display["options"]] == [
        ("rupee", "INR 4,20,00,000"), ("thousand", "INR 42,000.00 thousand"),
        ("lakh", "INR 420.00 lakh"), ("crore", "INR 4.20 cr"),
    ]


def test_a_unit_change_is_previewed_published_and_followed_by_the_memo(client, published_data_root):
    analyst = sign_in(client, ANALYST)
    admin = sign_in(client, ADMIN)
    case_id, _ = _full_case(client, analyst, published_data_root)
    revenue = lambda: {r[0]: r[1:] for r in _rows(_table(_section(_cam(  # noqa: E731
        client, analyst, published_data_root, case_id), "financials")))}["Revenue from operations"]
    assert revenue() == ["INR 9.44 cr", "INR 11.80 cr"]

    preview = client.post("/api/admin/settings/preview", headers=admin, json={"display_unit": "lakh"}).json()
    assert preview["problems"] == []
    assert [(c["section"], c["item"], c["field"], c["before"], c["after"]) for c in preview["changes"]] == [
        ("statements", "display_unit", "display_unit", "Crore", "Lakh")]
    # Previewing publishes nothing.
    assert client.get("/api/config/display-unit", headers=analyst).json()["unit"] == "crore"

    response = _publish(client, admin, {"display_unit": "lakh"}, note="Credit prefers lakh for small borrowers")
    assert response.status_code == 200, response.text
    assert client.get("/api/config/display-unit", headers=analyst).json()["unit"] == "lakh"
    assert _settings(client, admin)["display"]["unit"] == "lakh"
    assert revenue() == ["INR 944.00 lakh", "INR 1,180.00 lakh"]


def test_the_unit_left_as_published_is_not_a_change(client, published_data_root):
    admin = sign_in(client, ADMIN)
    response = client.post("/api/admin/settings/preview", headers=admin, json={"display_unit": "crore"})
    assert response.json()["problems"] == ["Nothing has changed."]


def test_a_unit_that_does_not_exist_is_refused(client):
    admin = sign_in(client, ADMIN)
    response = client.post("/api/admin/settings/preview", headers=admin, json={"display_unit": "million"})
    assert response.status_code == 422
