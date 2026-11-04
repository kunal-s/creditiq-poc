"""Document integrity (FRD F-07A): what a file says about its own history.

Use case 1 — a digitally generated PDF edited after it was issued. Every check
is deterministic code plus a threshold from `config/ingestion/integrity.yaml`;
no model is called, so one configuration version gives one answer for a file.

A finding is an indicator for a person to look at, never a verdict.
"""

from .checks import file_checks
from .routing import recommend

__all__ = ["file_checks", "recommend"]
