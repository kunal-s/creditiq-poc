"""A return's period as the calendar months it covers: monthly, or quarterly with its financial year."""

import pytest

from engine.util import period_months


@pytest.mark.parametrize("value, fy, expected", [
    ("Jan-Mar", "2025-26", [(2026, 1), (2026, 2), (2026, 3)]),
    ("Apr-Jun", "2025-26", [(2025, 4), (2025, 5), (2025, 6)]),
    ("Oct-Dec", "2025-26", [(2025, 10), (2025, 11), (2025, 12)]),
    ("Jan-Mar | 2025-26", None, [(2026, 1), (2026, 2), (2026, 3)]),
    ("Jan-Mar 2026", None, [(2026, 1), (2026, 2), (2026, 3)]),
    ("December 2025", None, [(2025, 12)]),
    ("092025", None, [(2025, 9)]),
    # A monthly filer prints the month on its own; the financial year beside it places the year,
    # April to March, so a month before April belongs to the second of the two years.
    ("Oct", "2025-26", [(2025, 10)]),
    ("Apr", "2025-26", [(2025, 4)]),
    ("Mar", "2025-26", [(2026, 3)]),
    ("Jan", "2025-26", [(2026, 1)]),
    ("Oct | 2025-26", None, [(2025, 10)]),
    ("Jan-Mar", None, []),   # no year to place it in: never guessed
    ("Oct", None, []),       # likewise for a month on its own
    ("not a period", "2025-26", []),
])
def test_period_months(value, fy, expected):
    assert period_months(value, fy) == expected


def test_a_month_named_without_its_year_is_placed_by_the_financial_year():
    assert period_months("Sep", "2026-27") == [(2026, 9)]
    assert period_months("Feb", "2025-26") == [(2026, 2)]
    assert period_months("Apr", "2025-26") == [(2025, 4)]
    assert period_months("Sep") == []                       # no year to place it by
    assert period_months("Oct-Dec", "2025-26") == [(2025, 10), (2025, 11), (2025, 12)]
    assert period_months("Sep 2026") == [(2026, 9)]
