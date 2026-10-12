"""Approving authority (FRD F-21; decision C.4-9)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AuthorityRef(BaseModel):
    """An approving authority: a role or committee, never a person."""

    key: str
    label: str
    level: int


class AuthorityStep(BaseModel):
    """One rule of the matrix that applied to the case, and the authority it needs."""

    kind: Literal["amount", "deviation"]
    rule: str
    """Where in the matrix: "bands.working_capital[2]" or "deviations.financial"."""
    product: str | None = None
    product_label: str | None = None
    band_from_inr: int | None = None
    """kind amount: the band's lower bound (exclusive); None for the first band."""
    band_to_inr: int | None = None
    """kind amount: the band's upper bound (inclusive); None for the last, open band."""
    category: str | None = None
    category_label: str | None = None
    norms: list[str] = Field(default_factory=list)
    """kind deviation: the norms in deviation in this category."""
    norm_labels: list[str] = Field(default_factory=list)
    levels_above: int | None = None
    at_least: AuthorityRef | None = None
    capped: bool = False
    """The rule asked for more than the highest authority in the matrix."""
    authority: AuthorityRef
    governs: bool = False
    """The first step that needs the required authority."""


class ApprovingAuthority(BaseModel):
    """The authority the case needs under the published matrix (F-21)."""

    case_id: str
    outcome: Literal["determined", "cannot_determine"]
    required: AuthorityRef | None
    reason: Literal["no_product"] | None = None
    unmapped_facilities: list[str] = Field(default_factory=list)
    amount_inr: int
    amount_basis: Literal["amount_requested"]
    products: list[str]
    product_labels: list[str]
    steps: list[AuthorityStep]
    lower_bound: bool
    """Some norms could not be assessed, so the authority may yet rise."""
    unevaluated: list[str]
    unevaluated_labels: list[str]
    could_rise_to: AuthorityRef | None
    """The authority if every norm not yet assessed turned out a deviation."""
    provisional: bool
    """The matrix, or a row of it that was used, is an interim proposal (FRD §393)."""
    source: str
    config_version: str
