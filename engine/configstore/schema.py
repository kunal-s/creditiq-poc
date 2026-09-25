"""Pydantic schemas for each versioned config section.

Every section here is runtime policy: what the pipeline, the rule engine and
the checklist derivation actually consult. It is published as an immutable
version (plan.md section 3), never edited in place. Contrast with
config/roles.yaml and config/deployment-features.yaml, which are deployment
bootstrap config read directly — nothing a credit policy "administrative
publish" (C1) governs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# "source"/"status" provenance tags (plan.md C14): admin screens show a
# neutral provenance tag instead of narrating why a value is what it is.
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


class RatingGrade(BaseModel):
    grade: str
    label: str
    band: str
    score_from: int
    score_to: int
    watch: bool
    guidance: str


class PolicySection(BaseModel):
    """config/policy.yaml"""

    grade_prefix: str
    ratios: list[PolicyRatio]
    available_ratios: list[PolicyRatio] = Field(default_factory=list)
    grid: list[RatingGrade]


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
    """Only applies when the case descriptor sets all of these attributes true
    (e.g. `collateral_present`). Empty means it always applies to its listed
    constitutions."""


class ChecklistTaxonomySection(BaseModel):
    """config/checklist_taxonomy.yaml"""

    sections: list[str]
    section_weight: dict[str, int]
    review_gate_threshold: int
    disbursement_gate_threshold: int
    items: list[ChecklistItemDef]


class DictionaryVariable(BaseModel):
    var: str
    group: str
    label: str
    type: Literal["money_inr", "date", "text", "percent", "count", "ratio", "boolean"]
    key_variable: bool
    constitutions: list[Literal["private_limited", "proprietorship", "partnership"]] = Field(
        default_factory=lambda: ["private_limited", "proprietorship", "partnership"]
    )


class DictionarySection(BaseModel):
    """config/dictionaries/<case_id>.yaml"""

    case_id: str
    variables: list[DictionaryVariable]


SECTION_MODELS: dict[str, type[BaseModel]] = {
    "policy": PolicySection,
    "checklist_taxonomy": ChecklistTaxonomySection,
}
