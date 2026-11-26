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


class RequiredField(FieldRule):
    """A field the case needs (Story 1.7): what reads it, where it comes from, its scope, and how it may be found when
    its own documents leave it empty (Epic 6). The reading settings (aliases, identifier, llm_hint) are a FieldRule's."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["text", "identifier", "date", "date_range", "amount", "list", "table"]
    per: Literal["case", "financial_year", "month", "account", "person", "facility"]
    sweep: bool = False
    """Whether other document types' pages may be searched for it (always sent to review)."""
    case_documents: bool = False
    """Also read from every document of a case document type (F-15.9)."""
    used_by: list[str] = Field(min_length=1)
    sources: list[str] = Field(alias="from", min_length=1)
    """type.field, type.line:<statement line> or type.table:<table>."""


class ColRule(Strict):
    name: str
    header: str
    nth: int = 0
    align: Literal["left", "right"] = "left"
    emit: bool = True
    join: str = " "   # how text from wrapped lines is joined


class KwTable(Strict):
    """A table found by its column headings (Epic 5 of the classification restructure), for every layout of it: the
    header is the line, with the lines just below it, where most configured headings match (fuzzily, as keywords do);
    each column sits under its heading; year columns are told apart by the dates in their headings, latest first."""

    label: str
    """The column of the row labels; it sits at the left when no heading names it."""
    headings: dict[str, list[str]] = Field(default_factory=dict)
    """Each column's headings as printed in its layouts ("Particulars", "Narration", "Withdrawal Amt.")."""
    periods: list[str] = Field(default_factory=list)
    """Year columns, latest first: each takes the heading whose date or year comes in that order."""
    ignore: list[str] = Field(default_factory=list)
    """Columns read to place the others (a Notes column), not reported."""
    part: str | None = None
    """The keyword part the table is (keywords.yaml): a title line of another part ends it."""
    start_words: list[str] = Field(default_factory=list)
    """A line holding one of these opens the region the header is looked for in (a return's "3.1")."""
    end_words: list[str] = Field(default_factory=list)
    """A line holding one of these ends the table."""
    end_starts: list[str] = Field(default_factory=list)
    """A line opening with one of these ends the table (the signature block's "For <company>")."""
    header_span: int = Field(default=2, ge=0, le=4)
    """Lines below the header line that may still be its headings (headings that wrap)."""
    min_headings: int = Field(default=2, ge=1)
    """How many columns a line's headings must name to be the header."""
    heading_cover: float = Field(default=0.5, gt=0, le=1)
    """A heading counts only when it makes up at least this share of its segment's letters: "Tax Payable" heads a
    column, "6.1 Payment of tax" does not."""
    align: dict[str, Literal["left", "right"]] = Field(default_factory=dict)
    """A column's alignment where its type does not say (numbers are right-aligned, text left)."""
    join: dict[str, str] = Field(default_factory=dict)
    row_start: str | None = None
    row_start_col: str | None = None
    text_only: Literal["row", "continuation"] = "row"
    attach: Literal["nearest", "heading"] = "nearest"
    skip_rows: list[str] = Field(default_factory=list)
    drop_lines: list[str] = Field(default_factory=list)
    max_attach: float = 24.0
    multi_page: bool = False
    optional: bool = False
    dash_is_zero: bool = False
    repair: dict | None = None
    y_tol: float | None = None
    model: bool = True
    """When no header is found, the model maps the table from the pages the keyword scorer chooses for it (its part,
    or its headings); every value is read from the line it names, and the document goes to a person once for it."""
    hints: dict[str, str] = Field(default_factory=dict)
    """What a column holds, in words, for the model, where its name does not say."""
    model_pages: int = Field(default=4, ge=1)
    """The most pages shown to the model for the table."""
    signed: dict[str, str] | None = None
    """One amount column for both directions (Story 5.10): {amount, marker, debit, credit}, the columns by role. Each
    row's amount goes to debit or credit by its marker column or the marker printed with it (numbers.debit_markers,
    credit_markers), or by its sign; then the running balance is checked."""


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

    pages: list[str] = Field(default_factory=list)
    """A page is a candidate when one of its opening lines matches one of these. Empty: the keyword scorer chooses the
    pages (the table's part, or its headings), as every table in table_keywords does."""
    head_lines: int = 8
    span: int = 1
    """Pages read from each candidate page on, so a table that runs over the page is read whole."""
    max_pages: int = 4
    label_column: str = "particulars"
    hints: dict[str, str] = Field(default_factory=dict)
    """What each column holds, in words, for the model (column name -> hint)."""
    text_columns: bool = True
    """Text columns other than the label are mapped too (the model names their line and piece of text)."""


_IDENTITY_TERM = re.compile(r"\s*([+-])?\s*([a-z][a-z0-9_]*)\s*")


def parse_identity(text: str) -> tuple[str, list[tuple[int, str]]] | None:
    """"total_income = revenue + other_income - x" as (left row, [(sign, row), ...]); None when it does not parse."""
    left, eq, right = text.partition("=")
    if not eq or not re.fullmatch(r"\s*[a-z][a-z0-9_]*\s*", left):
        return None
    terms: list[tuple[int, str]] = []
    pos = 0
    while pos < len(right):
        m = _IDENTITY_TERM.match(right, pos)
        if not m or m.end() == pos or (terms and not m.group(1)):
            return None
        terms.append((-1 if m.group(1) == "-" else 1, m.group(2)))
        pos = m.end()
    return (left.strip(), terms) if terms else None


class TableContract(Strict):
    """What a right reading of a table holds. Every reader proposes the table (its headings, wherever they are; each
    configured layout; the model last); the reading that meets this best is kept, and one that does not meet it is
    reported as such, naming what failed. The same contract holds for every document of the type."""

    label: str
    """The column of the row labels."""
    columns: list[str]
    """The figure columns the rows are read in and the identities are checked in (each one on its own)."""
    rows: dict[str, list[str]] = Field(default_factory=dict)
    """A row's name and the labels it is printed with. A label counts when it holds one of these as whole words, with
    case, punctuation, "&" for "and" and a leading list marker ("I", "(a)", "1.") set aside; one written "=total" must be
    the whole label. The first row that matches and prints a figure is the one used."""
    must_have: list[str] = Field(default_factory=list)
    """Rows the reading must hold, each with a figure in one of `columns`."""
    identities: list[str] = Field(default_factory=list)
    """Sums the printed figures make ("total_income = revenue_from_operations + other_income"), over row names. An
    identity is checked in each column where all its rows have a figure; one whose rows are not printed is not checked."""
    min_rows: int = Field(default=1, ge=1)
    tolerance: float = Field(default=1.0, ge=0)
    """How far apart the two sides may be, in the table's own unit (rounding of printed figures)."""
    tolerance_ratio: float = Field(default=0.0005, ge=0, le=0.05)
    """Or this share of the larger side, whichever is more."""

    @model_validator(mode="after")
    def _names(self) -> "TableContract":
        problems = [f"must_have: unknown row {n}" for n in self.must_have if n not in self.rows]
        for text in self.identities:
            parsed = parse_identity(text)
            if parsed is None:
                problems.append(f"identities: cannot read {text!r} (write it as 'a = b + c - d' over row names)")
                continue
            left, terms = parsed
            problems += [f"identities: unknown row {n} in {text!r}" for n in [left, *(n for _, n in terms)] if n not in self.rows]
        problems += [f"rows.{n}: no labels" for n, labels in self.rows.items() if not labels]
        if problems:
            raise ValueError("; ".join(problems))
        return self


class TypeFields(Strict):
    extraction: Literal["rules", "model"] = "rules"
    """`model`: the model reads every field that has no identifier rule (and is not `llm: false`) from the first
    page and the pages that score highest for the fields it reads (Story 6.7: llm.fill_pages); code verifies each
    value on its page. Validators then check it."""
    model_pages: list[PageScope] = Field(default_factory=list)
    """Superseded by scoring (Story 6.7) and no longer read; accepted so that versions published before it load."""
    fields: dict[str, FieldRule] = Field(default_factory=dict)
    identity: dict[str, str] = Field(default_factory=dict)  # identity key (name, pan, din, dob, gstin, cin) -> schema field
    tables: dict[str, TableRule | list[TableRule]] = Field(default_factory=dict)   # a list is layout variants, tried in order
    table_keywords: dict[str, KwTable] = Field(default_factory=dict)
    """Tables found by their column headings, for any layout (Epic 5); tried before the layouts above, which stay as
    a fallback until the keyword reading reads every table they do."""
    model_tables: dict[str, ModelTable] = Field(default_factory=dict)
    """Tables the model maps when every layout above fails to find them (and a model is configured)."""
    table_contracts: dict[str, TableContract] = Field(default_factory=dict)
    """What a right reading of each table holds. A table with a contract is read by every reader that applies and the
    reading that meets the contract best is kept; a table without one is read as above, the first reader that finds
    it."""


class IdentifierReading(Strict):
    """Story 2.6: the characters a scan confuses, read as an identifier's position requires, to find a PAN or GSTIN the
    format misses as printed. A reading counts only when a check confirms it, and it always goes to review."""

    digit_as_letter: dict[str, str] = Field(default_factory=dict)
    letter_as_digit: dict[str, str] = Field(default_factory=dict)
    max_corrections: int = Field(default=2, ge=1, le=4)


class NumberForms(Strict):
    """How amounts are printed (Story 5.4): what reads as nil, the debit and credit markers, and how a scan's broken
    figures are put back. Brackets and a leading minus are always negative."""

    nil_words: list[str] = Field(default_factory=lambda: ["nil"])
    """A cell holding only one of these is 0."""
    debit_markers: list[str] = Field(default_factory=lambda: ["dr"])
    """Before or after a figure, with or without a full stop ("Dr 1,234", "1,234 Dr."): it is negative."""
    credit_markers: list[str] = Field(default_factory=lambda: ["cr"])
    """Before or after a figure: it stays positive; the marker is dropped."""
    trailing_minus: bool = True
    """"1,234-" is negative, as accounting software prints it."""
    space_grouping: bool = True
    """Digits a scan split with spaces ("1 23 456") are one figure when the pieces form a valid Indian or Western
    grouping and no comma is printed; otherwise the cell is left unread rather than two figures joined."""


class Units(Strict):
    """The unit a document's amounts are printed in (Story 5.3): each unit's printed forms, its name the engine reads
    (the key), and which document types must state one."""

    words: dict[str, list[str]] = Field(default_factory=lambda: {
        "thousand": ["thousand", "thousands", "'000", "000s", "000's", "000"],
        "lakh": ["lakh", "lakhs", "lac", "lacs"],
        "crore": ["crore", "crores", "cr"],
        "million": ["million", "millions", "mn"],
        "rupee": ["rupees", "rupee", "indian rupees", "inr", "rs", "₹"]})
    currency: list[str] = Field(default_factory=lambda: ["rs", "inr", "₹", "rupees"])
    """Currency words that may stand beside a unit in a bracket: "(Rs. '000)"."""
    reach: int = Field(default=4, ge=1)
    """A unit word counts when it is at most this many words after "in" ("Amount in Rs. Lacs")."""
    required: list[str] = Field(default_factory=list)
    """Document types whose amounts must state their unit: one that does not goes to review, never read as rupees."""


class ExtraDataConfig(Strict):
    """What counts as a document's extra data (Story 6.4)."""

    min_table_rows: int = Field(default=3, ge=2)
    """Consecutive label-and-value lines no field or table claimed that make a table rather than separate pairs."""
    max_label_chars: int = Field(default=80, ge=10)
    max_value_chars: int = Field(default=60, ge=5)
    """Longer text after a colon is a sentence, not a value."""
    heading_reach: int = Field(default=3, ge=0)
    """How many lines above such a table its heading may be printed."""


class FieldsConfig(Strict):
    types: dict[str, TypeFields]
    numbers: NumberForms = Field(default_factory=NumberForms)
    units: Units = Field(default_factory=Units)
    identifier_reading: IdentifierReading | None = None
    required_fields: dict[str, RequiredField] = Field(default_factory=dict)
    """The case's required fields (Story 1.7, Epic 6)."""
    extra_data: ExtraDataConfig = Field(default_factory=ExtraDataConfig)

    @property
    def gap_fields(self) -> dict[str, RequiredField]:
        """F-15.9: the required fields read from any document of a case document type, the same request for every
        document (field names and hints, never another document's value); every value found waits for a person."""
        return {k: f for k, f in self.required_fields.items() if f.case_documents}


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
    """No longer read: every page is typed on its own (F-09, decision 14), so a document of another type inside a
    file is found by its pages. Accepted so that versions published with it still load."""

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
    evidence_text_ratio: float = Field(default=90, ge=50, le=100)
    """How close (rapidfuzz partial ratio, 0-100) a model's text value must be to the line it names (Story 6.6).
    Numbers and dates are matched by value, not by this ratio; the printed text is what is kept."""
    fill_pages: int = Field(default=6, ge=1)
    """Story 6.7: besides the first page, the most pages the model reads for a document's fields: those on which the
    most of the fields still to read have a cue (an alias, pattern or identifier). A shorter document is read whole."""
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


class KwIdentity(Strict):
    """How a document of the type is told from another of the same type in one file, and the period it covers."""

    by: Literal["period", "account", "person", "none"] = "none"
    period: list[Literal["year_end", "period_end", "as_of", "range", "financial_year", "assessment_year", "month",
                         "quarter", "columns"]] = Field(default_factory=list)
    """The kinds of period the type prints (stages/periods.py); empty: the type has no period."""
    body: bool = False
    """Look for the period in the body too, after the title and footer (a bank statement's details block)."""
    columns: bool = False
    """Fall back to the latest of its tables' year columns, and flag a title that disagrees with them."""
    derive_from_rows: bool = False
    """With no period printed, take the first and last transaction dates, marked as derived."""


class KwType(KwWords):
    parts: list[str] = Field(min_length=1)
    needs_part: list[str] = Field(default_factory=list)
    """The type takes a run of pages only when one of these parts is placed in it."""
    unverified: bool = False
    """Drafted without a sample page."""
    identity: KwIdentity | None = None
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


class KwPeriods(Strict):
    """The words a period is printed with (stages/periods.py). Each phrase matches across any spacing; a "." in it may be
    left out ("a.y." reads AY, A.Y., A. Y.), and a "-" may be a space ("half-year"). Dates, month names and the
    financial year's start are read separately."""

    range_joiners: list[str] = Field(default_factory=lambda: ["to", "till", "until", "-", "–", "—"])
    """What joins two dates into a range: "01 Apr 2025 to 31 Mar 2026"."""
    year_end: list[str] = Field(default_factory=lambda: ["year ended"])
    """Before a date: the financial year that ends on it."""
    period_end: dict[str, int] = Field(default_factory=lambda: {"period ended": 12, "quarter ended": 3, "half-year ended": 6})
    """Before a date: the months, so many, that end on it."""
    count_units: dict[str, int] = Field(default_factory=lambda: {"months": 1, "month": 1, "year": 12})
    """After a number ("nine months ended"): how many months one unit is."""
    count_ended: list[str] = Field(default_factory=lambda: ["ended", "period ended"])
    """What follows the unit: "nine months ended", "nine months period ended"."""
    number_words: dict[str, int] = Field(default_factory=lambda: {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "half": 6})
    as_of: list[str] = Field(default_factory=lambda: ["as at", "as on"])
    """Before a date: that one day."""
    column_headings: list[str] = Field(default_factory=lambda: ["as at", "as on", "year ended", "period ended"])
    """Printed twice or more on one line, these make it a table's column headings, not a heading's period."""
    heading_words: list[str] = Field(default_factory=lambda: ["ended", "as at", "as on", "dated", "from"])
    """Just before two dates, these make them a heading's dates, not a table's year columns."""
    assessment_year: list[str] = Field(default_factory=lambda: ["assessment year", "a.y."])
    financial_year: list[str] = Field(default_factory=lambda: ["financial year", "f.y."])
    period_labels: list[str] = Field(default_factory=lambda: ["tax period", "return period", "period"])
    """Before a month: "Return Period 12/2025", "Period Apr"."""
    year_labels: list[str] = Field(default_factory=lambda: ["year", "financial year", "f.y."])
    """Before the year a page names, for a month or quarter printed alone: "Year 2025-26"."""
    quarter_labels: list[str] = Field(default_factory=lambda: ["quarter", "q"])
    quarter_joiners: list[str] = Field(default_factory=lambda: ["-", "–", "to"])
    """Between a quarter's first and last month: "Apr-Jun 2025"."""


class KwPersonRules(Strict):
    """How a personal document (a director's KYC) names its person, in order."""

    din_labels: list[str] = Field(default_factory=lambda: ["director identification number", "din"])
    """Before a DIN: the person's DIN."""
    individual_pan_letter: str = Field(default="P", min_length=1, max_length=1)
    """The fourth letter of an individual's PAN (a company's is C): a PAN with it is the person's."""
    masked_pan: bool = True
    """With neither, a masked PAN (AXXXX1234K) names the person."""


class KwIdentitySettings(Strict):
    financial_year_start_month: int = Field(default=4, ge=1, le=12)
    """The month a financial year starts in: April, so "FY 2025-26" is 1 April 2025 to 31 March 2026."""
    account_labels: list[str] = Field(default_factory=lambda: ["account number", "account no", "a/c no", "a/c number"])
    """The labels an account number follows on a bank statement."""
    account_digits: tuple[int, int] = (9, 20)
    """The length of an account number after its label, fewest and most digits (or masked digits)."""
    row_date_chars: int = Field(default=24, ge=8)
    """How far into a table row its date is looked for, for a statement's period derived from its transactions."""
    person: KwPersonRules = Field(default_factory=KwPersonRules)
    cover_min_periods: int = Field(default=3, ge=2)
    """A page at the head of a run listing this many periods of its type is a cover (a compilation of returns), not
    the first of them."""


class KwScoring(Strict):
    """The constants of the keyword scorer (stages/keywords.py)."""

    lookalike_base: float = Field(default=0.5, ge=0, le=1)
    """A type with its own words scores its best part times (base + (1 - base) x its own words' score over the run):
    with none of them, it keeps this share of its part's score."""
    missing_part_factor: float = Field(default=0.5, ge=0, le=1)
    """A type lacking a part it needs (a return without its computation) keeps this share of its score."""
    subsumed_factor: float = Field(default=0.5, ge=0, le=1)
    """A type all of whose parts another eligible type has keeps this share of its score."""
    model_confidence: float = Field(default=0.7, ge=0, le=1)
    """The confidence a document carries when the model placed its pages (it has no keyword score of its own)."""


class KwMatching(Strict):
    confused_digits: dict[str, str] = Field(default_factory=lambda: {"0": "o", "1": "l", "5": "s", "8": "b"})
    """Inside a word with letters, a digit a scan confuses with a letter is read as that letter ("B0ARD" is board); a
    number, or a code that starts with a digit (3b, 26as), is left as it is. For matching words only; identifiers have
    their own map (fields.yaml identifier_reading)."""
    table_row: str = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?"
    """A line with an amount like this is a table row: never a title, and where a statement's transaction dates are."""


class KwSettings(Strict):
    classifier: str | None = None
    """No longer read: documents are always typed by the keyword lists. Accepted so that versions published with
    the switch still load."""
    zones: KwZones
    zone_weights: dict[Literal["title", "footer"], float]
    full: float = Field(gt=0)
    page_threshold: float = Field(gt=0, le=1)
    margin: float = Field(ge=0, lt=1)
    fuzzy: KwFuzzy
    categories: KwCategories
    max_gap: int = Field(ge=0)
    identity: KwIdentitySettings = Field(default_factory=KwIdentitySettings)
    scoring: KwScoring = Field(default_factory=KwScoring)
    matching: KwMatching = Field(default_factory=KwMatching)
    periods: KwPeriods = Field(default_factory=KwPeriods)
    index_min_types: int = Field(default=3, ge=2)
    """A page whose titles name this many parts or more, of more than one document type, is a cover or index page."""
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
    fields: FieldsConfig
    validators: ValidatorsConfig
    quality: QualityConfig
    routing: RoutingConfig
    integrity: IntegrityConfig
    llm: LlmConfig
    confidence: ConfidenceConfig
    decision: DecisionConfig
    keywords: KeywordsConfig
    """How pages are typed and documents told apart (F-09, decision 14)."""

    def check_consistency(self) -> list[str]:
        """Cross-section checks run at publish: every reference points at something real."""
        problems: list[str] = []
        types = self.document_types.by_id()
        problems += self._check_keywords(set(types))
        from ..stages.extract.identifiers import PATTERNS as IDENTIFIER_PATTERNS
        for gname, grule in self.fields.required_fields.items():
            where = f"fields.required_fields.{gname}"
            if grule.identifier and grule.identifier not in IDENTIFIER_PATTERNS:
                problems.append(f"{where}: unknown identifier {grule.identifier}")
            if not (grule.identifier or grule.aliases or grule.patterns or grule.llm_hint):
                problems.append(f"{where}: needs an identifier, aliases, patterns or a hint for the model")
            for src in grule.sources:
                tid, _, what = src.partition(".")
                if tid not in types:
                    problems.append(f"{where}.from: unknown document type {tid}")
                    continue
                if what.startswith("table:"):
                    if what[6:] not in {t.name for t in types[tid].schema_.tables}:
                        problems.append(f"{where}.from: {tid} has no table {what[6:]}")
                elif not what.startswith("line:") and what not in {f.name for f in types[tid].schema_.fields}:
                    problems.append(f"{where}.from: {tid} has no field {what}")
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
            for tname, tc in tf.table_contracts.items():
                if tname not in tnames:
                    problems.append(f"fields.{tid}.table_contracts.{tname}: not in the type's schema")
                    continue
                cols = {c.name for c in tnames[tname].columns}
                if tc.label not in cols:
                    problems.append(f"fields.{tid}.table_contracts.{tname}.label: unknown column {tc.label}")
                if set(tc.columns) - cols:
                    problems.append(f"fields.{tid}.table_contracts.{tname}.columns: unknown columns {sorted(set(tc.columns) - cols)}")
                if not (tname in tf.tables or tname in tf.table_keywords or tname in tf.model_tables):
                    problems.append(f"fields.{tid}.table_contracts.{tname}: no reader is configured for the table")
        for r in self.validators.rules:
            for t in r.types:
                if t not in types:
                    problems.append(f"validators.{r.id}: unknown type {t}")
        for name in ("extract", "transactions", "discover", "classify_page", "period"):
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
