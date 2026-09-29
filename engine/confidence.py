"""Field confidence (F-17.1):

    confidence = min(applicable caps) x sum(weight_i x component_i)

Weights, caps and the review threshold come from the published
config/confidence.yaml. Components come from the sidecar; where it sent
none, the engine fills the ones it can derive itself (classification
confidence, page grade, identifier validation) and counts the rest as 0,
so an unsupported value is routed to review rather than accepted
(principle 5). A model's self-reported confidence is never an input.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import identifiers
from .configstore.schema import ConfidenceSection

GRADE_SCORE = {"A": 1.0, "B": 0.8, "C": 0.5, "U": 0.0}

# Flags a sidecar may send among the components to ask for a cap.
CAP_FLAGS = ("anchor_zone_only",)

_VALIDATORS = {
    "pan": identifiers.validate_pan_format,
    "gstin": identifiers.validate_gstin,
    "cin": identifiers.validate_cin,
    "udyam": identifiers.validate_udyam,
    "din": identifiers.validate_din,
    "ifsc": identifiers.validate_ifsc,
    "tan": identifiers.validate_tan,
    "udin": identifiers.validate_udin,
    "itr_ack": identifiers.validate_itr_ack,
}


def identifier_valid(kind: str | None, value: object) -> bool | None:
    """None when the field is not an identifier or the kind is unknown."""
    if kind is None or value is None or kind not in _VALIDATORS:
        return None
    return _VALIDATORS[kind](str(value).strip().upper())


@dataclass
class Scored:
    confidence: float
    components: dict[str, float]
    """The components used, plus "cap.<name>" for every cap applied."""


def score(
    cfg: ConfidenceSection,
    *,
    components: dict[str, float],
    classification_confidence: float,
    page_grade: str | None,
    identifier_kind: str | None,
    value: object,
    has_page: bool,
) -> Scored:
    comps = {k: float(v) for k, v in components.items() if k not in CAP_FLAGS}
    flags = {k for k in CAP_FLAGS if components.get(k)}
    comps.setdefault("classification", float(classification_confidence))
    if page_grade is not None:
        comps.setdefault("page_grade", GRADE_SCORE.get(page_grade, 0.0))
    valid = identifier_valid(identifier_kind, value)
    if valid is not None:
        # The engine's own check outranks anything reported for validation.
        comps["validation"] = 1.0 if valid else 0.0

    caps: dict[str, float] = {}
    if valid is False and "checksum_fail" in cfg.caps:
        caps["checksum_fail"] = cfg.caps["checksum_fail"]
    if not has_page and "not_found_on_page" in cfg.caps:
        caps["not_found_on_page"] = cfg.caps["not_found_on_page"]
    if page_grade == "C" and "grade_c_page" in cfg.caps:
        caps["grade_c_page"] = cfg.caps["grade_c_page"]
    for flag in flags:
        if flag in cfg.caps:
            caps[flag] = cfg.caps[flag]

    weighted = sum(weight * min(max(comps.get(name, 0.0), 0.0), 1.0) for name, weight in cfg.weights.items())
    value_conf = round(min([1.0, *caps.values()]) * weighted, 4)
    used = {name: round(comps.get(name, 0.0), 4) for name in cfg.weights}
    used.update({f"cap.{name}": cap for name, cap in caps.items()})
    return Scored(confidence=value_conf, components=used)
