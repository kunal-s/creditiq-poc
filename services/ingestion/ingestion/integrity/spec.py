"""How a check was made, as every integrity finding carries it (F-07A).

From the check's own configuration: the engine and rule, the configuration
version, and — so a reader is told, not left to guess — why the result matters
and what to do next. `execution_failed` marks a check that could not run (the
file or its pages could not be read), which is never the same as a check with
nothing to look at.
"""

from __future__ import annotations

from typing import Any

__all__ = ["method"]


def method(spec: dict[str, Any], version: str, *, failed: bool = False) -> dict[str, str]:
    out = {"engine": "parser", "library": spec.get("library", ""), "rule": spec.get("rule", ""),
           "policy_version": version, "limitations": spec.get("limitations", ""),
           "next_step": spec.get("next_step", "")}
    if failed:
        out["execution_failed"] = "true"
    return out
