"""Stage 1b: document integrity from the file's bytes (FRD F-07A, use case 1).

Runs after the quality gate and before the file is read, so a file that was
saved again, or that still carries an earlier figure, is flagged before a page
is rendered or read optically. Deterministic; no OCR and no model.

It never rejects. Its findings are indicators for a person, and at most they
move the decision to human review — extraction always runs, because a wrong
figure that is extracted and flagged is more use to a credit officer than a
document that disappeared.
"""

from __future__ import annotations

from typing import Any

from ..config.models import IntegrityConfig
from ..contracts import IntegrityFinding
from ..integrity import file_checks, recommend

__all__ = ["run_integrity_file", "IntegrityResult"]


class IntegrityResult:
    __slots__ = ("findings", "recommendation")

    def __init__(self, findings: list[IntegrityFinding], recommendation: dict[str, Any]):
        self.findings = findings
        self.recommendation = recommendation

    def to_json(self) -> dict[str, Any]:
        return {"recommendation": self.recommendation,
                "findings": [f.model_dump(mode="json") for f in self.findings]}


def run_integrity_file(data: bytes, kind: str | None, cfg: IntegrityConfig,
                       doc_type: str | None = None) -> IntegrityResult:
    """Every use-case-1 check the file answers from its bytes.

    Only a PDF carries revisions, an identifier pair and a metadata record, so
    for anything else this says so rather than returning a silent pass.
    """
    policy = cfg.model_dump(mode="python")
    if kind != "pdf":
        return IntegrityResult([], {"code": "not_applicable",
                                    "label": "Not applicable",
                                    "families": [], "signals": [],
                                    "why": f"Integrity from the file's structure applies to a PDF; this is a {kind or 'file of unknown kind'}.",
                                    "policy_version": cfg.version})
    found = file_checks(data, policy, doc_type)
    return IntegrityResult(found, recommend(found, policy))
