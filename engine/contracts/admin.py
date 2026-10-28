"""Administration and audit views (FRD §6), and the settings an Administrator edits (F-00.6)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ConfigVersion(BaseModel):
    version: str
    author: str
    note: str
    published_at: str
    prior_version: str | None
    sections_changed: list[str]
    """Sections whose content differs from the prior version; every section for the first."""
    current: bool
    origin: Literal["cli", "app"] = "cli"
    """Where it was published: from the configuration files on the command line, or edited on the
    Administration screen (F-00.6)."""


class DirectoryUser(BaseModel):
    id: str
    name: str
    role: str
    roleLabel: str
    email: str
    branch: str
    permissions: list[str]


class AuditEntry(BaseModel):
    seq: int
    at: str
    actor: str
    actor_name: str
    case_id: str | None
    action: str
    detail: dict


class AuditPage(BaseModel):
    entries: list[AuditEntry]
    next_before: int | None
    """Pass as `before` to read the next, older page; null at the end."""
    actors: list[str]
    actions: list[str]


# --- Settings an Administrator edits on the screen (F-00.6) ---

SettingsSection = Literal["tolerances", "policy", "crosschecks", "approval_matrix", "statements"]
Severity = Literal["serious", "moderate", "mild"]
SettingValue = float | int | bool | str | None


class EditableTolerance(BaseModel):
    key: str
    label: str
    value: float
    unit: Literal["%", "inr", "days", "ratio"]
    source: str
    rules: list[str]
    """The cross-checks that use it, in configured order."""


class EditableRatio(BaseModel):
    """A financial-ratio norm's thresholds: acceptable is the norm; marginal is shown beside it."""

    key: str
    label: str
    unit: Literal["x", "%", "days"]
    kind: Literal["min", "max"]
    acceptable: float
    marginal: float
    norms: list[str]
    """The policy norms that take their threshold from it (FR-01 …)."""


class EditableNorm(BaseModel):
    """A norm with its own threshold (eligibility, documentation, security cover)."""

    id: str
    family: Literal["eligibility", "ratios", "security_cover", "documentation"]
    label: str
    unit: Literal["x", "%", "days", "years", "inr", "count", "rank"] | None
    kind: Literal["min", "max"]
    threshold: float


class EditableRule(BaseModel):
    id: str
    title: str
    area: str
    severity: Severity
    blocking: bool
    enabled: bool


class EditableAuthority(BaseModel):
    key: str
    level: int
    label: str


class EditableBand(BaseModel):
    up_to_inr: int | None = Field(default=None, gt=0)
    """Inclusive upper bound; None for the last, open band."""
    authority: str


class EditableProduct(BaseModel):
    key: str
    label: str
    bands: list[EditableBand]


class EditableDeviation(BaseModel):
    category: str
    label: str
    levels_above: int = Field(ge=0)
    at_least: str | None
    """The lowest authority that may approve a deviation of this category, if any."""


class EditableMatrix(BaseModel):
    status: str
    authorities: list[EditableAuthority]
    products: list[EditableProduct]
    deviations: list[EditableDeviation]


class DisplayUnitOption(BaseModel):
    id: Literal["rupee", "thousand", "lakh", "crore"]
    label: str
    example: str
    """A figure of 4.2 crore written in the unit."""


class EditableDisplay(BaseModel):
    """The unit financial figures are written in."""

    unit: Literal["rupee", "thousand", "lakh", "crore"]
    options: list[DisplayUnitOption]


class EditableSettings(BaseModel):
    """What the Administration screen edits, as the published version has it."""

    version: str
    published_at: str
    author: str
    origin: Literal["cli", "app"]
    tolerances: list[EditableTolerance]
    ratios: list[EditableRatio]
    norms: list[EditableNorm]
    rules: list[EditableRule]
    matrix: EditableMatrix
    display: EditableDisplay


class RatioChange(BaseModel):
    acceptable: float | None = None
    marginal: float | None = None


class RuleChange(BaseModel):
    enabled: bool | None = None
    severity: Severity | None = None
    blocking: bool | None = None


class DeviationChange(BaseModel):
    levels_above: int | None = Field(default=None, ge=0)
    at_least: str | None = None
    """Set to an authority key, or to "" for no minimum authority; left out, it stays as it is."""


class SettingsChanges(BaseModel):
    """Only what changes; anything left out stays as published."""

    tolerances: dict[str, float] = Field(default_factory=dict)
    ratios: dict[str, RatioChange] = Field(default_factory=dict)
    norms: dict[str, float] = Field(default_factory=dict)
    """Norm id to its new threshold (a norm with its own threshold; ratio norms change through `ratios`)."""
    rules: dict[str, RuleChange] = Field(default_factory=dict)
    bands: dict[str, list[EditableBand]] = Field(default_factory=dict)
    """Product key to its bands, as many as it has now, lowest first."""
    deviations: dict[str, DeviationChange] = Field(default_factory=dict)
    display_unit: Literal["rupee", "thousand", "lakh", "crore"] | None = None
    """The unit financial figures are written in; left out, it stays as published."""


class SettingsPublishRequest(BaseModel):
    note: str
    """Why: recorded with the version and in the audit trail (at least 3 characters)."""
    changes: SettingsChanges


class SettingChange(BaseModel):
    """One value that changes: where it is, its label, and before and after as raw values."""

    section: SettingsSection
    item: str
    """The tolerance key, ratio key, norm id, rule id, product key or deviation category."""
    label: str
    field: str
    """value, acceptable, marginal, threshold, enabled, severity, blocking, up_to_inr, authority,
    levels_above, at_least or display_unit."""
    unit: str | None = None
    before: SettingValue
    after: SettingValue


class SettingsPreview(BaseModel):
    changes: list[SettingChange]
    problems: list[str]
    """Why the changes cannot be published; empty when they can."""


class SettingsPublished(BaseModel):
    version: str
    published_at: str
    changes: list[SettingChange]
    cases_rerun: int
    cases_failed: list[str]
