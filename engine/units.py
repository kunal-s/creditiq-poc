"""The unit financial figures are written in (config/statements.yaml `display_unit`, edited on the
Administration screen). One setting, so the statement tables, the policy page, the memo and the
exports write the same figure the same way."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .util import format_inr

DisplayUnit = Literal["rupee", "thousand", "lakh", "crore"]
DEFAULT_UNIT: DisplayUnit = "crore"


@dataclass(frozen=True)
class UnitSpec:
    id: str
    label: str
    """Named in the Administration screen and under a table's heading ("INR crore")."""
    divisor: float
    decimals: int
    suffix: str
    """Written after a figure in a sentence: "INR 4.20 cr"."""


UNITS: dict[str, UnitSpec] = {
    "rupee": UnitSpec("rupee", "Rupees", 1, 0, ""),
    "thousand": UnitSpec("thousand", "Thousand", 1e3, 2, " thousand"),
    "lakh": UnitSpec("lakh", "Lakh", 1e5, 2, " lakh"),
    "crore": UnitSpec("crore", "Crore", 1e7, 2, " cr"),
}


def money(value: float | None, unit: str = DEFAULT_UNIT) -> str:
    """A financial figure in the configured unit, whatever its size: "INR 4.20 cr", "INR 0.04 cr",
    "INR 42,00,000". A negative figure keeps its sign."""
    if value is None:
        return "—"
    spec = UNITS[unit]
    if spec.divisor == 1:
        return f"INR {format_inr(0 if round(value) == 0 else value)}"
    scaled = value / spec.divisor
    text = f"{abs(scaled):,.{spec.decimals}f}"
    # Indian digit grouping for the whole part of the scaled figure (a thousand-unit figure can
    # run to lakhs): "4,20,000.00 thousand".
    whole, _, fraction = text.partition(".")
    grouped = format_inr(int(whole.replace(",", "")))
    sign = "-" if scaled < 0 and float(text.replace(",", "")) != 0 else ""
    return f"INR {sign}{grouped}.{fraction}{spec.suffix}" if fraction else f"INR {sign}{grouped}{spec.suffix}"
