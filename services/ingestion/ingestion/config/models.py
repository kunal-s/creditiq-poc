"""Typed configuration sections (FRD F-00; principle 3).

Everything the pipeline decides is read from these models, which are loaded
from a published, immutable version. Unknown keys are rejected so a typo in
a config file fails at publish time, not on a case.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- document_types.json (the supplied schema) -------------------------------------------------

FieldType = Literal["string", "number", "date", "array", "boolean"]


class SubField(Strict):
    name: str
    type: FieldType = "string"


class Items(Strict):
    type: Literal["object", "string", "number"] = "string"
    fields: list[SubField] = Field(default_factory=list)


class FieldDef(Strict):
    name: str
    type: FieldType
    required: bool = False
    description: str | None = None
    items: Items | None = None


class ColumnDef(Strict):
    name: str
    type: FieldType = "string"


class TableDef(Strict):
    name: str
    description: str | None = None
    columns: list[ColumnDef]


class SchemaDef(Strict):
    fields: list[FieldDef] = Field(default_factory=list)
    tables: list[TableDef] = Field(default_factory=list)


class DocumentTypeDef(Strict):
    document_type: str
    display_name: str
    category: str
    priority: Literal["mandatory", "optional"] = "mandatory"
    schema_: SchemaDef = Field(alias="schema")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DocumentTypesConfig(Strict):
    version: str
    bank: str | None = None
    use_case: str | None = None
    output_contract: dict | None = None
    documents: list[DocumentTypeDef]

    def by_id(self) -> dict[str, DocumentTypeDef]:
        return {d.document_type: d for d in self.documents}


# --- signals.yaml ------------------------------------------------------------------------------


class InstanceRule(Strict):
    """A file may hold several instances of one type (two directors, eight returns).
    A page matching `start` opens a new instance; earlier pages are front matter."""

    start: str
    keys: list[str] = Field(default_factory=list)


class TypeSignals(Strict):
    required: list[str] = Field(default_factory=list)
    supporting: list[str] = Field(default_factory=list)
    contrary: list[str] = Field(default_factory=list)
    instances: InstanceRule | None = None


class Tier2Guard(Strict):
    """A model's choice of type is accepted only if the document still agrees with that type's own
    signals: the model never overrides a contrary signal, and the type's required signals must mostly
    be present. Otherwise the file goes to review with the model's suggestion as a candidate."""

    block_on_contrary: bool = True
    min_required_fraction: float = 0.5


class SignalsConfig(Strict):
    tier1_margin: float = 0.2
    classify_threshold: float = 0.6
    tier2_confidence: float = 0.7
    tier2_guard: Tier2Guard = Field(default_factory=Tier2Guard)
    signal_pages: int = 3
    mixed_content_check: bool = True
    mixed_min_score: float = 0.75
    types: dict[str, TypeSignals]


# --- fields.yaml -------------------------------------------------------------------------------


class Pattern(Strict):
    regex: str
    group: int = 1
    flags: str = "im"
    multi: bool = False  # every match becomes one list element (array fields)
    span_pages: bool = False   # search the instance's pages as one text (a value that runs over a page break)
    split: str | None = None   # split a captured group into several list elements
    strip: str | None = None   # regex removed from the start of each element


class FieldRule(Strict):
    aliases: list[str] = Field(default_factory=list)
    patterns: list[Pattern | str] = Field(default_factory=list)
    identifier: str | None = None
    normaliser: str | None = None
    next_line: bool = True
    take: Literal["segment", "rest"] = "segment"
    validators: list[str] = Field(default_factory=list)
    key_field: bool | None = None
    page_match: str | None = None
    llm: bool | None = None   # None: follows llm.fill; true: always allowed; false: never
    llm_hint: str | None = None

    def pattern_list(self) -> list[Pattern]:
        return [p if isinstance(p, Pattern) else Pattern(regex=p) for p in self.patterns]


class ColRule(Strict):
    name: str
    header: str
    nth: int = 0
    align: Literal["left", "right"] = "left"
    emit: bool = True
    join: str = " "   # how text from wrapped lines is joined


class TableRule(Strict):
    page_match: str | None = None
    start: str
    end: str | None = None
    header_lines: int = 0   # lines after the start line that still belong to the header
    columns: list[ColRule]
    row_start: str | None = None
    row_start_col: str | None = None
    text_only: Literal["row", "continuation"] = "row"
    skip_rows: list[str] = Field(default_factory=list)
    max_attach: float = 24.0   # points; a line farther than this from every row is not part of the table
    multi_page: bool = False
    y_tol: float | None = None
    repair: dict | None = None  # {kind: running_balance, debit, credit, balance}: arithmetic repair, recorded


IDENTITY_KEYS = {"name", "pan", "din", "dob", "gstin", "cin"}


class TypeFields(Strict):
    fields: dict[str, FieldRule] = Field(default_factory=dict)
    identity: dict[str, str] = Field(default_factory=dict)  # identity key (name, pan, din, dob, gstin, cin) -> schema field
    tables: dict[str, TableRule] = Field(default_factory=dict)


class FieldsConfig(Strict):
    types: dict[str, TypeFields]


# --- validators.yaml ---------------------------------------------------------------------------


class ValidatorRule(Strict):
    id: str
    types: list[str]
    kind: str
    params: dict = Field(default_factory=dict)
    severity: Literal["warn", "fail"] = "warn"
    label: str | None = None
    defect: Literal["pages_absent", "period_gap", "unsigned", "unstamped", "plain_paper", "pagination_break"] | None = None
    """When this check does not pass, the document carries this defect (F-13.3)."""


class ValidatorsConfig(Strict):
    rules: list[ValidatorRule] = Field(default_factory=list)


# --- quality.yaml, routing.yaml ----------------------------------------------------------------


class QualityConfig(Strict):
    max_file_bytes: int = 40 * 1024 * 1024
    max_pages: int = 300
    max_sheet_cells: int = 500_000
    min_dpi: int = 150
    ocr_confidence_floor: float = 60
    ocr_confidence_degraded: float = 80
    min_chars_text_layer: int = 40
    garbage_ratio_max: float = 0.05
    blur_sharpness_min: float = 900
    skew_degrees_max: float = 1.5
    shadow_spread_max: float = 70
    blank_ink_max: float = 0.0008
    reason_codes: dict[str, str] = Field(default_factory=dict)


class OcrConfig(Strict):
    engine: Literal["paddle", "none"] = "paddle"
    dpi: int = 200
    det_limit_side: int = 1600
    det_model: str | None = None
    rec_model: str | None = None


class ReadingConfig(Strict):
    drop_rotated_text: bool = True
    max_rotation_deg: float = 2.0
    x_tolerance: float = 1.5
    y_tolerance: float = 2.0
    line_y_tol: float = 3.0
    column_gap: float = 12.0
    boilerplate: list[str] = Field(default_factory=list)
    accepted_formats: list[str] = Field(default_factory=lambda: ["pdf", "png", "jpg", "tiff", "bmp", "webp", "xlsx", "csv"])


class RoutingConfig(Strict):
    reading: ReadingConfig = Field(default_factory=ReadingConfig)
    ocr: OcrConfig = Field(default_factory=OcrConfig)


# --- llm.yaml ----------------------------------------------------------------------------------


class Prompt(Strict):
    system: str
    user: str


class LlmConfig(Strict):
    """The model layer (FRD AD-5a). Prompt text and sampling settings are part of the published version."""

    provider: Literal["openai", "stub"] = "openai"
    model: str = "gpt-5.4-nano"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_s: float = 120
    max_retries: int = 2
    classify_chars: int = 6000
    window_chars: int = 12000
    temperature: float | None = None
    """Sent to the model when set (FRD principle 6, amended 6 Oct 2026). With `seed`, the only sampling parameters sent."""
    seed: int | None = None
    fill: Literal["missing", "flagged"] = "missing"  # which unfilled fields the model may read
    prompts: dict[str, Prompt]


# --- confidence.yaml, decision.yaml ------------------------------------------------------------


class ConfidenceConfig(Strict):
    weights: dict[str, float]
    caps: dict[str, float]
    grade_scores: dict[str, float] = Field(default_factory=lambda: {"A": 1.0, "B": 0.8, "C": 0.5, "U": 0.0})
    single_read: float = 0.8
    disagree: float = 0.2
    key_field_review_threshold: float = 0.80
    manual_entry_cap: float = 0.70

    @model_validator(mode="after")
    def _weights_sum(self) -> "ConfidenceConfig":
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"confidence weights must sum to 1, got {total}")
        return self


class DecisionConfig(Strict):
    accept_min_document_confidence: float = 0.85
    review_min_document_confidence: float = 0.5
    reject_grades: list[str] = Field(default_factory=lambda: ["U"])
    review_on_failed_check: bool = True
    review_on_missing_required: bool = True


# --- the whole thing ---------------------------------------------------------------------------


class IngestionConfig(Strict):
    version: str
    hash: str
    document_types: DocumentTypesConfig
    signals: SignalsConfig
    fields: FieldsConfig
    validators: ValidatorsConfig
    quality: QualityConfig
    routing: RoutingConfig
    llm: LlmConfig
    confidence: ConfidenceConfig
    decision: DecisionConfig

    def check_consistency(self) -> list[str]:
        """Cross-section checks run at publish: every reference points at something real."""
        problems: list[str] = []
        types = self.document_types.by_id()
        for tid in types:
            if tid not in self.signals.types:
                problems.append(f"signals: no entry for document type {tid}")
        for tid, ts in self.signals.types.items():
            if tid not in types:
                problems.append(f"signals: unknown document type {tid}")
            for kind in ("required", "supporting", "contrary"):
                for rx in getattr(ts, kind):
                    _compile(rx, f"signals.{tid}.{kind}", problems)
            if ts.instances:
                _compile(ts.instances.start, f"signals.{tid}.instances.start", problems)
                for k in ts.instances.keys:
                    if tid in types and k not in {f.name for f in types[tid].schema_.fields}:
                        problems.append(f"signals.{tid}.instances.keys: unknown field {k}")
        for tid, tf in self.fields.types.items():
            if tid not in types:
                problems.append(f"fields: unknown document type {tid}")
                continue
            names = {f.name for f in types[tid].schema_.fields}
            tnames = {t.name: t for t in types[tid].schema_.tables}
            for ikey, fname in tf.identity.items():
                if ikey not in IDENTITY_KEYS:
                    problems.append(f"fields.{tid}.identity: unknown key {ikey}")
                if fname not in names:
                    problems.append(f"fields.{tid}.identity.{ikey}: {fname} is not in the type's schema")
            for fname, rule in tf.fields.items():
                if fname not in names:
                    problems.append(f"fields.{tid}.{fname}: not in the type's schema")
                for p in rule.pattern_list():
                    _compile(p.regex, f"fields.{tid}.{fname}", problems, p.flags)
                if rule.page_match:
                    _compile(rule.page_match, f"fields.{tid}.{fname}.page_match", problems)
            for tname, tr in tf.tables.items():
                if tname not in tnames:
                    problems.append(f"fields.{tid}.tables.{tname}: not in the type's schema")
                    continue
                cols = {c.name for c in tnames[tname].columns}
                emitted = {c.name for c in tr.columns if c.emit}
                if emitted - cols:
                    problems.append(f"fields.{tid}.tables.{tname}: unknown columns {sorted(emitted - cols)}")
                for rx in [tr.start, tr.end, tr.row_start, tr.page_match, *tr.skip_rows, *[c.header for c in tr.columns]]:
                    if rx:
                        _compile(rx, f"fields.{tid}.tables.{tname}", problems)
        for r in self.validators.rules:
            for t in r.types:
                if t not in types:
                    problems.append(f"validators.{r.id}: unknown type {t}")
        for name in ("classify", "extract"):
            if name not in self.llm.prompts:
                problems.append(f"llm.prompts: missing '{name}'")
        for rx in self.routing.reading.boilerplate:
            _compile(rx, "routing.reading.boilerplate", problems)
        return problems


def _compile(rx: str, where: str, problems: list[str], flags: str = "i") -> None:
    try:
        re.compile(rx, _flags(flags))
    except re.error as e:
        problems.append(f"{where}: bad regex {rx!r}: {e}")


def _flags(spec: str) -> int:
    f = 0
    for ch in spec:
        f |= {"i": re.I, "m": re.M, "s": re.S}.get(ch, 0)
    return f


def re_flags(spec: str) -> int:
    return _flags(spec)
