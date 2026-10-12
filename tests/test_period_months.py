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
    ("Jan-Mar", None, []),   # no year to place it in: never guessed
    ("not a period", "2025-26", []),
])
def test_period_months(value, fy, expected):
    assert period_months(value, fy) == expected
