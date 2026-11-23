"""Typed configuration sections (FRD F-00; principle 3).

Everything the pipeline decides is read from these models, which are loaded
from a published, immutable version. Unknown keys are rejected so a typo in
a config file fails at publish time, not on a case.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..stages.extract.identifiers import PATTERNS as _IDENTIFIER_PATTERNS


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
    enabled: bool = True
    """A switched-off type is never offered to the classifier: not scored, not looked for by the second
    pass, not in the model's list. A person can still assign it, and its rules stay checked at publish."""
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

    def enabled_ids(self) -> set[str]:
        """The types the classifier may choose (`enabled`)."""
        return {d.document_type for d in self.documents if d.enabled}


# --- signals.yaml ------------------------------------------------------------------------------


class InstanceRule(Strict):
    """A file may hold several instances of one type (two directors, eight returns).
    Either `start` (a page matching it opens a new instance) or `key_pattern` (a page carrying a
    different value for the key than the instance before it opens a new one; pages without the key
    stay with the instance they follow). Earlier pages are front matter."""

    start: str | None = None
    key_pattern: str | None = None  # one capture group: the value that tells instances apart
    first_key_pattern: str | None = None
    """Tried before `key_pattern`: when it finds a key on any page it alone splits the file (an identifier printed
    in every page header is a steadier key than a value that schedules also mention)."""
    keys: list[str] = Field(default_factory=list)
    zone: Literal["head", "any"] = "any"
    """`head`: the start or key counts only in a page's opening lines (`head_lines`), its heading. A statement
    that names last year's date in its notes or comparative columns then does not open a new instance."""
    leading: Literal["front_matter", "first"] = "front_matter"
    """Pages before the first start or key: `front_matter` (a cover sheet), or `first`, part of the first instance
    (an auditor's report ahead of the statements it reports on)."""

    @model_validator(mode="after")
    def _one_way(self) -> "InstanceRule":
        if bool(self.start) == bool(self.key_pattern):
            raise ValueError("instances: give exactly one of `start` and `key_pattern`")
        if self.first_key_pattern:
            if not self.key_pattern:
                raise ValueError("instances: `first_key_pattern` goes with `key_pattern`")
            if re.compile(self.first_key_pattern).groups != 1:
                raise ValueError("instances: first_key_pattern needs exactly one capture group")
        return self


class Required(Strict):
    """One requirement of a type. It is met when any alternative matches. `zone: head` means the
    match must be in the opening lines of a page (a title), so a passing mention in the body does not count."""

    any: list[str] = Field(min_length=1)
    zone: Literal["head", "any"] = "any"


class Supporting(Strict):
    rx: str
    weight: float = Field(default=1.0, gt=0)


class Contrary(Strict):
    rx: str
    zone: Literal["head", "any"] = "any"


class TypeSignals(Strict):
    corroboration: float | None = Field(default=None, gt=0)  # supporting weight that counts as full corroboration (default: the section's)
    required: list[Required] = Field(default_factory=list)
    supporting: list[Supporting] = Field(default_factory=list)
    contrary: list[Contrary] = Field(default_factory=list)
    instances: InstanceRule | None = None

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)
        d["required"] = [{"any": [x]} if isinstance(x, str) else x for x in d.get("required", [])]
        d["supporting"] = [{"rx": x} if isinstance(x, str) else x for x in d.get("supporting", [])]
        d["contrary"] = [{"rx": x} if isinstance(x, str) else x for x in d.get("contrary", [])]
        return d


class Tier2Guard(Strict):
    """A model's choice of type is accepted only if the document still agrees with that type's own
    signals: the model never overrides a contrary signal, and the type's required signals must mostly
    be present. Otherwise the file goes to review with the model's suggestion as a candidate."""

    block_on_contrary: bool = True
    min_required_fraction: float = 0.5


_MACRO = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class SignalsConfig(Strict):
    tier1_margin: float = 0.2
    classify_threshold: float = 0.6
    tier2_confidence: float = 0.7
    tier2_guard: Tier2Guard = Field(default_factory=Tier2Guard)
    corroboration: float = Field(default=3.0, gt=0)  # supporting weight that counts as full corroboration
    signal_pages: int = 20      # non-blank pages read for classification
    head_lines: int = 6         # the opening lines of a page that count as its title zone
    mixed_content_check: bool = True
    mixed_min_score: float = 0.75
    patterns: dict[str, str] = Field(default_factory=dict)  # named fragments, used as {NAME} inside any signal
    types: dict[str, TypeSignals]

    @model_validator(mode="after")
    def _expand_patterns(self) -> "SignalsConfig":
        """Named fragments (a PAN, a GSTIN) are written once and expanded here, so the matching code
        only ever sees plain regular expressions."""
        def sub(rx: str, where: str) -> str:
            def one(m: re.Match) -> str:
                if m[1] not in self.patterns:
                    raise ValueError(f"{where}: unknown pattern {{{m[1]}}}")
                return f"(?:{self.patterns[m[1]]})"
            return _MACRO.sub(one, rx)

        for tid, ts in self.types.items():
            for r in ts.required:
                r.any = [sub(x, f"signals.{tid}.required") for x in r.any]
            for x in ts.supporting:
                x.rx = sub(x.rx, f"signals.{tid}.supporting")
            for x in ts.contrary:
                x.rx = sub(x.rx, f"signals.{tid}.contrary")
            if ts.instances:
                i = ts.instances
                i.start = sub(i.start, f"signals.{tid}.instances") if i.start else None
                i.key_pattern = sub(i.key_pattern, f"signals.{tid}.instances") if i.key_pattern else None
        return self


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
    attach: Literal["nearest", "heading"] = "nearest"   # heading: a label-only line heads the next row; any other line outside a row is dropped
    skip_rows: list[str] = Field(default_factory=list)
    drop_lines: list[str] = Field(default_factory=list)   # lines that are no part of the table: neither a row nor a heading (a filed statement's [Abstract] markers)
    max_attach: float = 24.0   # points; a line farther than this from every row is not part of the table
    multi_page: bool = False
    optional: bool = False   # a statement the document type may legitimately lack: still reported missing, but not a reason for review
    y_tol: float | None = None
    dash_is_zero: bool = False   # a statement prints nil as a dash: the cell is 0, not unread
    repair: dict | None = None  # {kind: running_balance, debit, credit, balance}: arithmetic repair, recorded


IDENTITY_KEYS = {"name", "pan", "din", "dob", "gstin", "cin"}
#: Identifier kinds a field rule may scan for, and that `format:` validators check (stages/extract/identifiers.py).
IDENTIFIER_KINDS = set(_IDENTIFIER_PATTERNS)
#: Normalisers a field rule may name (stages/extract/normalise.py); the default follows the field type.
NORMALISERS = {"date", "number", "text", "present"}


class PageScope(Strict):
    """A section the model reads: the first page whose text matches, and the pages that follow it."""

    match: str
    span: int = 1


class ModelTable(Strict):
    """A table the model may map when no configured layout finds it (FRD F-15.2, F-15.3). The model is shown the
    candidate pages and names, for each row, the line its label is on and which figure on which line belongs to
    each column; it never writes a figure. Code reads every figure from the line named and rejects what is not
    there (F-15.4)."""

    pages: list[str]
    """A page is a candidate when one of its opening lines matches one of these (the statement's title)."""
    head_lines: int = 8
    span: int = 1
    """Pages read from each candidate page on, so a table that runs over the page is read whole."""
    max_pages: int = 4
    label_column: str = "particulars"
    hints: dict[str, str] = Field(default_factory=dict)
    """What each column holds, in words, for the model (column name -> hint)."""


class TypeFields(Strict):
    extraction: Literal["rules", "model"] = "rules"
    """`model`: the model reads every field that has no identifier rule (and is not `llm: false`) from the
    pages in `model_pages`, plus the first page; code verifies each value on its page. Validators then check it."""
    model_pages: list[PageScope] = Field(default_factory=list)
    fields: dict[str, FieldRule] = Field(default_factory=dict)
    identity: dict[str, str] = Field(default_factory=dict)  # identity key (name, pan, din, dob, gstin, cin) -> schema field
    tables: dict[str, TableRule | list[TableRule]] = Field(default_factory=dict)   # a list is layout variants, tried in order
    model_tables: dict[str, ModelTable] = Field(default_factory=dict)
    """Tables the model maps when every layout above fails to find them (and a model is configured)."""


class IdentifierReading(Strict):
    """Story 2.6: the characters a scan confuses, read as an identifier's position requires, to find a PAN or GSTIN the
    format misses as printed. A reading counts only when a check confirms it, and it always goes to review."""

    digit_as_letter: dict[str, str] = Field(default_factory=dict)
    letter_as_digit: dict[str, str] = Field(default_factory=dict)
    max_corrections: int = Field(default=2, ge=1, le=4)


class FieldsConfig(Strict):
    types: dict[str, TypeFields]
    identifier_reading: IdentifierReading | None = None
    gap_fields: dict[str, FieldRule] = Field(default_factory=dict)
    """F-15.9: the fields the cross-checks read from any document, whatever its type. A document of a
    case document type is read for each of them, the same request for every document (field names and
    hints, never another document's value), and every value found waits for a person (F-17.7)."""


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
    max_pages: int = 400
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


# --- integrity.yaml (FRD F-07A) ----------------------------------------------------------------


class IntegrityCheck(Strict):
    family: Literal["metadata", "font", "layout", "visual", "history", "identifier", "arithmetic", "signature"]
    tier: Literal["T0", "T1", "T2", "T3"]
    impact: Literal["low", "medium", "high"]
    library: str = ""
    rule: str = ""
    limitations: str = ""
    next_step: str = ""
    context: bool = False
    """Listed for a reader, never counted as a signal."""
    prompts_review: bool = False
    """For a context check: when it observes something, a person should look
    (review recommended), though it is never a signal and never queues the file."""


class EditingTool(Strict):
    match: str
    name: str


class EditingTools(Strict):
    version: str = "editing_tools_v1"
    editors: list[EditingTool] = Field(default_factory=list)
    re_renderers: list[EditingTool] = Field(default_factory=list)


class MetadataPeriod(Strict):
    grace_days: int = 0


class IntegrityRouting(Strict):
    strong_tiers: list[str] = Field(default_factory=lambda: ["T0", "T1"])
    multi_family_min_impact: Literal["low", "medium", "high"] = "medium"


class ScanRegions(Strict):
    tile_px: int = 48
    min_ink_share: float = 0.03
    noise_z: float = 4.0
    sharpness_z: float = 4.0
    min_tiles: int = 2
    min_page_grain: float = 1.5
    max_regions_per_page: int = 3


class ScanTextLayer(Strict):
    min_dpi: float = 200.0
    confirm_confidence: float = 0.80
    min_agreement: float = 0.5


class ScanFigurePicture(Strict):
    max_page_fraction: float = 0.05
    min_digits: int = 4
    max_words: int = 3


class ScanOrigin(Strict):
    dpi_differ: float = 0.15
    dpi_agree: float = 0.05
    max_odd_pages: int = 2


class ScanTypeStyle(Strict):
    bold_ratio: float = 1.3
    italic_deg: float = 8.0
    min_confidence: float = 0.80
    max_words: int = 120
    column_tol_pt: float = 2.0
    column_min: int = 3
    column_majority: float = 0.6


class IntegrityScan(Strict):
    """Thresholds for the checks that read a scan's pixels (use case 2)."""

    max_pages: int = 10
    render_dpi_max: float = 300.0
    regions: ScanRegions = Field(default_factory=ScanRegions)
    text_layer: ScanTextLayer = Field(default_factory=ScanTextLayer)
    figure_picture: ScanFigurePicture = Field(default_factory=ScanFigurePicture)
    origin: ScanOrigin = Field(default_factory=ScanOrigin)
    type_style: ScanTypeStyle = Field(default_factory=ScanTypeStyle)


class ArithmeticColumns(Strict):
    debit: str = "debit"
    credit: str = "credit"
    balance: str = "balance"


class ArithmeticLabels(Strict):
    total_credits: str = r"\btotal\s+(?:credits?|deposits?|cr\b)"
    total_debits: str = r"\btotal\s+(?:debits?|withdrawals?|dr\b)"
    count: str = r"\b(?:no\.?|number|count)\s+of\s+(?:transactions|txns?|entries)\b"
    brought_forward: str = r"\b(?:brought\s+forward|b/f)\b"
    carried_forward: str = r"\b(?:carried\s+forward|c/f)\b"


class IntegrityArithmetic(Strict):
    """Whether a statement's printed figures and a balance sheet's totals add up (T0)."""

    statement_types: list[str] = Field(default_factory=lambda: ["bank_statement"])
    statement_table: str = "transactions"
    columns: ArithmeticColumns = Field(default_factory=ArithmeticColumns)
    opening_field: str = "opening_balance"
    closing_field: str = "closing_balance"
    tolerance_paise: int = 0
    max_breaks: int = 3
    max_break_share: float = 0.05
    labels: ArithmeticLabels = Field(default_factory=ArithmeticLabels)
    balance_sheet_types: list[str] = Field(default_factory=lambda: ["audited_financial_statements"])
    balance_sheet_table: str = "balance_sheet"
    balance_sheet_totals: str = (r"^\s*total(?:\s+(?:equity\s+(?:&|and)\s+liabilities|assets|liabilities|"
                                 r"sources\s+of\s+funds|application\s+of\s+funds|funds\s+employed))?\s*$")
    balance_sheet_columns: list[str] = Field(default_factory=lambda: ["current_period", "previous_period"])
    balance_sheet_tolerance_units: float = 1.0


class IntegritySignatures(Strict):
    trust_roots: str | None = None


class IntegrityScore(Strict):
    """Evidence strength, 0 to `cap`: worked out by the engine for a reader (uncalibrated)."""

    impact_points: dict[str, float] = Field(default_factory=lambda: {"high": 60, "medium": 35, "low": 15})
    tier_factor: dict[str, float] = Field(default_factory=lambda: {"T0": 1.0, "T1": 1.0, "T2": 0.75, "T3": 0.5})
    same_family_share: float = 0.25
    other_family_share: float = 0.75
    cap: int = 95
    bands: dict[str, int] = Field(default_factory=lambda: {"strong": 70, "moderate": 40})


class IntegrityPage(Strict):
    """Thresholds for the checks that read what each page draws (phase 2)."""

    max_pages: int = 60
    tiny_pt: float = 2.0
    writer_credits: list[str] = Field(default_factory=lambda: ["poweredbytcpdf"])
    picture_max_page_fraction: float = 0.10
    picture_min_chars_under: int = 3
    word_gap_em: float = 0.15
    baseline_tol_pt: float = 0.5
    superscript_size_ratio: float = 0.75
    max_offset_line_ratio: float = 0.5
    layout_style_min: int = 3
    layout_style_ratio: float = 2
    column_tolerance_pt: float = 2.5
    column_min_values: int = 4
    column_majority: float = 0.75
    column_size_tol_pt: float = 0.3


class IntegrityConfig(Strict):
    """What a file says about its own history, before anything is extracted."""

    version: str
    checks: dict[str, IntegrityCheck]
    metadata_period: MetadataPeriod = Field(default_factory=MetadataPeriod)
    expected_producers: dict[str, list[str]] = Field(default_factory=dict)
    skip_for_type: dict[str, dict[str, str]] = Field(default_factory=dict)
    routing: IntegrityRouting = Field(default_factory=IntegrityRouting)
    editing_tools: EditingTools = Field(default_factory=EditingTools)
    page: IntegrityPage = Field(default_factory=IntegrityPage)
    score: IntegrityScore = Field(default_factory=IntegrityScore)
    scan: IntegrityScan = Field(default_factory=IntegrityScan)
    arithmetic: IntegrityArithmetic = Field(default_factory=IntegrityArithmetic)
    signatures: IntegritySignatures = Field(default_factory=IntegritySignatures)


class OcrConfig(Strict):
    engine: Literal["paddle", "none"] = "paddle"
    dpi: int = 200
    det_limit_side: int = 1600
    det_model: str | None = None
    rec_model: str | None = None
    dash_marks: bool = False   # read a lone dash the engine skips (a statement's nil) from the image


class ReadingConfig(Strict):
    drop_rotated_text: bool = True
    max_rotation_deg: float = 2.0
    x_tolerance: float = 1.5
    y_tolerance: float = 2.0
    line_y_tol: float = 3.0
    line_overlap: float = Field(default=0.0, ge=0, le=1)  # share of the shorter box two words must overlap vertically to share a line (0: off)
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


class TransactionsLlm(Strict):
    """How bank-statement transactions are put to the model (`POST /v1/classify-transactions`)."""

    batch_size: int = Field(default=40, ge=1, le=200)


class SiblingsConfig(Strict):
    """The second pass (FRD F-08.1, F-08.2): the other document types of the classified type's category,
    looked for in the same file. A type counts as present only where a page carries its own signals and
    its key fields are read and verified on those pages."""

    enabled: bool = True
    page_min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    """A page opens a part of type T when T's signals are met on that page alone and score at least this."""
    min_key_fields: int = Field(default=1, ge=1)
    """Key fields (required, or named in the type's identity) that must be found for the part to count."""


class RetryConfig(Strict):
    """How a failed model call is retried, by the kind of failure (llm/errors.py). Operational waits,
    not decision rules (CLAUDE.md rule 5 is about rules): the published version holds them."""

    server_attempts: int = Field(3, ge=1)            # total attempts for server_unavailable / timeout
    server_backoff_s: list[float] = Field(default_factory=lambda: [2.0, 4.0], min_length=1)
    """Waits between those attempts, in order (the last repeats); never a wait after the last attempt."""
    backoff_jitter: float = Field(0.2, ge=0, lt=1)  # each wait is moved by up to this share, either way
    rate_limit_attempts: int = Field(3, ge=1)
    rate_limit_wait_s: float = Field(60, gt=0)       # when a per-minute limit names no wait
    max_wait_s: float = Field(90, gt=0)              # a longer wait asked for is not waited: the call fails
    breaker_failures: int = Field(5, ge=1)           # server failures in a row, across calls, that open the breaker
    breaker_cooldown_s: float = Field(120, gt=0)     # while open, calls fail at once; then one trial call


class LlmConfig(Strict):
    """The model layer (FRD AD-5a). Prompt text and sampling settings are part of the published version."""

    provider: Literal["openai", "azure", "stub"] = "openai"
    model: str = "gpt-5.4-nano"
    """The model id. The call log, the prices and the names on Model usage use it, whatever the deployment is called."""
    deployment: str | None = None
    """Azure only: the deployment's name, sent as the request's `model` (base_url is then <endpoint>/openai/v1)."""
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_s: float = 120
    max_retries: int | None = None
    """Superseded by `retry`; still read from versions published before it (server_attempts = max_retries + 1)."""
    retry: RetryConfig | None = None
    classify_chars: int = 6000
    window_chars: int = 12000
    temperature: float | None = None
    """Sent to the model when set (FRD principle 6, amended 6 Oct 2026). With `seed`, the only sampling parameters sent."""
    seed: int | None = None
    fill: Literal["missing", "flagged"] = "missing"  # which unfilled fields the model may read
    prompts: dict[str, Prompt]
    transactions: TransactionsLlm = Field(default_factory=TransactionsLlm)
    siblings: SiblingsConfig = Field(default_factory=SiblingsConfig)
    discover_max_fields: int = Field(default=12, ge=1, le=40)
    """The most fields the model may propose for a case document type with no named fields (F-15.8)."""

    @model_validator(mode="after")
    def _retry(self) -> "LlmConfig":
        """A version published before the `retry` block had `max_retries` (retries after the first attempt)."""
        if self.provider == "azure" and not self.deployment:
            raise ValueError("provider azure needs `deployment`: the name the model was deployed under")
        if self.retry is None:
            self.retry = RetryConfig(**({"server_attempts": self.max_retries + 1} if self.max_retries is not None else {}))
        return self


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


# --- keywords.yaml (page typing by keywords, FRD F-09, decision 14) -----------------------------------------------


class KwEntry(Strict):
    """One phrase, or one identifier format, with its weight. A plain string is a phrase of weight 1."""

    phrase: str | None = None
    identifier: str | None = None
    weight: float = Field(default=1.0, gt=0)
    zone: Literal["title"] | None = None
    """For a warning: `title` rules the part or type out when the phrase is in the title zone; without it the
    phrase only takes its weight off the score."""

    @model_validator(mode="before")
    @classmethod
    def _plain(cls, v):
        return {"phrase": v} if isinstance(v, str) else v

    @model_validator(mode="after")
    def _one(self):
        if (self.phrase is None) == (self.identifier is None):
            raise ValueError("a keyword entry gives exactly one of `phrase` and `identifier`")
        return self


class KwWords(Strict):
    title: list[KwEntry] = Field(default_factory=list)
    content: list[KwEntry] = Field(default_factory=list)
    warning: list[KwEntry] = Field(default_factory=list)
    full: float | None = Field(default=None, gt=0)
    """The evidence that scores 1.0 (default: settings.full)."""

    def has_words(self) -> bool:
        return bool(self.title or self.content or self.warning)


class KwPart(KwWords):
    needs_title: bool = False
    """The part scores 0 unless one of its title phrases is in the title zone."""


class KwType(KwWords):
    parts: list[str] = Field(min_length=1)
    needs_part: list[str] = Field(default_factory=list)
    """The type takes a run of pages only when one of these parts is placed in it."""
    unverified: bool = False
    """Drafted without a sample page."""
    default: bool = False
    """Takes the pages of the parts it shares with look-alike types when none of them has its own words in the run
    (audited statements: provisional and projected statements say what they are)."""


class KwZones(Strict):
    header_band: float = Field(gt=0, lt=0.5)
    footer_band: float = Field(gt=0, lt=0.5)
    title_size_ratio: float = Field(gt=1)
    title_bold_share: float = Field(gt=0, le=1)
    title_height_ratio: float = Field(gt=1)


class KwFuzzy(Strict):
    min_length: int = Field(ge=1)
    min_ratio: float = Field(gt=0, le=1)


class KwCategories(Strict):
    first_pages: int = Field(ge=1)
    threshold: float = Field(gt=0, le=1)


class KwSettings(Strict):
    classifier: Literal["keywords", "signals"] = "signals"
    """Which scorer types documents: the keyword lists here, or the patterns of signals.yaml (kept until the
    page typing of Epic 3 passes)."""
    zones: KwZones
    zone_weights: dict[Literal["title", "footer"], float]
    full: float = Field(gt=0)
    page_threshold: float = Field(gt=0, le=1)
    margin: float = Field(ge=0, lt=1)
    fuzzy: KwFuzzy
    categories: KwCategories
    max_gap: int = Field(ge=0)
    model_guard_min_score: float = Field(default=0.2, ge=0, le=1)
    """The model's choice stands only when the document shows at least this much of that type's words."""


class KeywordsConfig(Strict):
    settings: KwSettings
    parts: dict[str, KwPart]
    types: dict[str, KwType]


class IngestionConfig(Strict):
    version: str
    hash: str
    document_types: DocumentTypesConfig
    signals: SignalsConfig
    fields: FieldsConfig
    validators: ValidatorsConfig
    quality: QualityConfig
    routing: RoutingConfig
    integrity: IntegrityConfig
    llm: LlmConfig
    confidence: ConfidenceConfig
    decision: DecisionConfig
    keywords: KeywordsConfig | None = None
    """Absent in a version published before keywords.yaml existed: that version types documents by its signals."""

    def uses_keywords(self) -> bool:
        return self.keywords is not None and self.keywords.settings.classifier == "keywords"

    def check_consistency(self) -> list[str]:
        """Cross-section checks run at publish: every reference points at something real."""
        problems: list[str] = []
        types = self.document_types.by_id()
        if self.keywords is not None:
            problems += self._check_keywords(set(types))
        for tid in types:
            if tid not in self.signals.types:
                problems.append(f"signals: no entry for document type {tid}")
        for tid, ts in self.signals.types.items():
            if tid not in types:
                problems.append(f"signals: unknown document type {tid}")
            for r in ts.required:
                for rx in r.any:
                    _compile(rx, f"signals.{tid}.required", problems)
            for x in (*ts.supporting, *ts.contrary):
                _compile(x.rx, f"signals.{tid}", problems)
            if ts.instances:
                for label, rx in (("start", ts.instances.start), ("key_pattern", ts.instances.key_pattern)):
                    if rx:
                        _compile(rx, f"signals.{tid}.instances.{label}", problems)
                if ts.instances.key_pattern:
                    try:
                        if re.compile(ts.instances.key_pattern).groups != 1:
                            problems.append(f"signals.{tid}.instances.key_pattern: needs exactly one capture group")
                    except re.error:
                        pass  # already reported by _compile
                for k in ts.instances.keys:
                    if tid in types and k not in {f.name for f in types[tid].schema_.fields}:
                        problems.append(f"signals.{tid}.instances.keys: unknown field {k}")
        from ..stages.extract.identifiers import PATTERNS as IDENTIFIER_PATTERNS
        for gname, grule in self.fields.gap_fields.items():
            if grule.identifier and grule.identifier not in IDENTIFIER_PATTERNS:
                problems.append(f"fields.gap_fields.{gname}: unknown identifier {grule.identifier}")
            if not (grule.identifier or grule.aliases or grule.patterns or grule.llm_hint):
                problems.append(f"fields.gap_fields.{gname}: needs an identifier, aliases, patterns or a hint for the model")
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
                if rule.identifier and rule.identifier not in IDENTIFIER_KINDS:
                    problems.append(f"fields.{tid}.{fname}.identifier: unknown kind {rule.identifier}")
                for v in rule.validators:
                    kind, _, arg = v.partition(":")
                    if kind == "format" and arg not in IDENTIFIER_KINDS:
                        problems.append(f"fields.{tid}.{fname}.validators: no format defined for {arg}")
                if rule.normaliser and rule.normaliser not in NORMALISERS:
                    problems.append(f"fields.{tid}.{fname}.normaliser: unknown normaliser {rule.normaliser}")
            for tname, trs in tf.tables.items():
                if tname not in tnames:
                    problems.append(f"fields.{tid}.tables.{tname}: not in the type's schema")
                    continue
                cols = {c.name for c in tnames[tname].columns}
                for tr in trs if isinstance(trs, list) else [trs]:
                    emitted = {c.name for c in tr.columns if c.emit}
                    if emitted - cols:
                        problems.append(f"fields.{tid}.tables.{tname}: unknown columns {sorted(emitted - cols)}")
                    for rx in [tr.start, tr.end, tr.row_start, tr.page_match, *tr.skip_rows, *tr.drop_lines, *[c.header for c in tr.columns]]:
                        if rx:
                            _compile(rx, f"fields.{tid}.tables.{tname}", problems)
            for tname, mt in tf.model_tables.items():
                if tname not in tnames:
                    problems.append(f"fields.{tid}.model_tables.{tname}: not in the type's schema")
                    continue
                cols = {c.name for c in tnames[tname].columns}
                if mt.label_column not in cols:
                    problems.append(f"fields.{tid}.model_tables.{tname}.label_column: unknown column {mt.label_column}")
                if set(mt.hints) - cols:
                    problems.append(f"fields.{tid}.model_tables.{tname}.hints: unknown columns {sorted(set(mt.hints) - cols)}")
                for rx in mt.pages:
                    _compile(rx, f"fields.{tid}.model_tables.{tname}.pages", problems)
                if "table" not in self.llm.prompts:
                    problems.append("llm.prompts: missing 'table' (model_tables needs it)")
        for r in self.validators.rules:
            for t in r.types:
                if t not in types:
                    problems.append(f"validators.{r.id}: unknown type {t}")
        for name in ("classify", "extract", "sibling", "transactions", "discover"):
            if name not in self.llm.prompts:
                problems.append(f"llm.prompts: missing '{name}'")
        for rx in self.routing.reading.boilerplate:
            _compile(rx, "routing.reading.boilerplate", problems)
        return problems

    def _check_keywords(self, type_ids: set[str]) -> list[str]:
        """keywords.yaml: every document type is listed, every part and identifier it names exists, and no phrase
        is both a keyword and a warning word of the same part or type (Story 1.9)."""
        from ..stages.extract.identifiers import PATTERNS as IDENTIFIER_PATTERNS
        kw = self.keywords
        assert kw is not None
        out = [f"keywords: no entry for document type {t}" for t in sorted(type_ids - set(kw.types))]
        out += [f"keywords: unknown document type {t}" for t in sorted(set(kw.types) - type_ids)]
        for where, words in [*((f"keywords.parts.{n}", p) for n, p in kw.parts.items()),
                             *((f"keywords.types.{n}", t) for n, t in kw.types.items())]:
            for e in (*words.title, *words.content, *words.warning):
                if e.identifier and e.identifier not in IDENTIFIER_PATTERNS:
                    out.append(f"{where}: unknown identifier {e.identifier}")
            plus = {e.phrase.lower() for e in (*words.title, *words.content) if e.phrase}
            out += [f"{where}: {e.phrase!r} is both a keyword and a warning word" for e in words.warning
                    if e.phrase and e.phrase.lower() in plus]
        for n, t in kw.types.items():
            out += [f"keywords.types.{n}: unknown part {p}" for p in t.parts if p not in kw.parts]
            out += [f"keywords.types.{n}.needs_part: {p} is not one of its parts" for p in t.needs_part if p not in t.parts]
            if not any(kw.parts[p].title for p in t.parts if p in kw.parts) and not t.title:
                out.append(f"keywords.types.{n}: no title phrase in any of its parts")
        used = {p for t in kw.types.values() for p in t.parts}
        out += [f"keywords.parts.{p}: used by no document type" for p in sorted(set(kw.parts) - used)]
        return out


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
