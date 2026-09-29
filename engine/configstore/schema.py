"""Pydantic schemas for each versioned config section.

Every section here is runtime policy: what the pipeline, the rule engine and
the checklist derivation consult. It is published as an immutable version,
never edited in place (docs/functional-requirements.md F-00). Contrast with
config/roles.yaml, which is deployment bootstrap config read directly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Provenance tag: where a value comes from. "provisional" marks an interim
# value awaiting RBL's own artefact.
Source = Literal["published_policy", "regulatory", "industry_standard", "provisional"]
Status = Literal["active", "provisional"]


class PolicyRatio(BaseModel):
    key: str
    label: str
    unit: Literal["x", "%", "days"]
    kind: Literal["min", "max"]
    acceptable: float
    marginal: float
    formula: str
    applies: str
    source: Source
    status: Status
    note: str
    hard_floor: str | None = None


class PolicySection(BaseModel):
    """config/policy.yaml"""

    ratios: list[PolicyRatio]
    available_ratios: list[PolicyRatio] = Field(default_factory=list)


class ChecklistItemDef(BaseModel):
    id: str
    name: str
    category: str
    constitutions: list[Literal["private_limited", "proprietorship", "partnership"]]
    why: str
    basis: str
    source: Source
    blocking: bool
    weight: int
    requires_attributes: list[str] = Field(default_factory=list)
    """Only applies when the case sets all of these attributes true
    (e.g. `collateral_present`). Empty means it always applies to its listed
    constitutions."""


class ChecklistTaxonomySection(BaseModel):
    """config/checklist_taxonomy.yaml"""

    sections: list[str]
    section_weight: dict[str, int]
    review_gate_threshold: int
    disbursement_gate_threshold: int
    items: list[ChecklistItemDef]


SECTION_MODELS: dict[str, type[BaseModel]] = {
    "policy": PolicySection,
    "checklist_taxonomy": ChecklistTaxonomySection,
}
