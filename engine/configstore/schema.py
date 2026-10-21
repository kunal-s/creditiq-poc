"""Pydantic schemas for each versioned config section.

Every section here is runtime policy: what the pipeline, the rule engine and
the checklist derivation consult. It is published as an immutable version,
never edited in place (docs/functional-requirements.md F-00). Contrast with
config/roles.yaml, which is deployment bootstrap config read directly.
"""

from __future__ import annotations

import ast
import re
from typing import Literal

from pydantic import BaseModel, Field

# Provenance tag: where a value comes from. "provisional" marks an interim
# value awaiting RBL's own artefact; "rbl_supplied" a value RBL supplied.
Source = Literal["published_policy", "regulatory", "industry_standard", "provisional", "rbl_supplied"]
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


class WorkingCapitalPolicy(BaseModel):
    mpbf_above_limit_inr: int
    """Fund-based working-capital limits above this use the MPBF method and
    need CMA data; at or below it, the turnover method (F-12.2)."""
    source: Source
    status: Status
    turnover_requirement_pct: float = 25
    """Turnover method (F-22.2): working-capital requirement as a share of projected turnover."""
    turnover_margin_pct: float = 5
    """Turnover method: the borrower's minimum margin, as a share of projected turnover."""
    mpbf_margin_pct: float = 25
    """MPBF (second method): the borrower's margin, as a share of current assets."""


# The inputs a norm's expression may use (F-20.1), computed by
# engine/policy.py from the aligned facts and the case.
POLICY_INPUTS = {
    # Latest audited financial statements.
    "revenue_from_operations", "other_income", "ebitda", "depreciation", "finance_costs", "profit_before_tax",
    "profit_after_tax", "share_capital", "reserves_and_surplus", "net_worth", "long_term_borrowings",
    "short_term_borrowings", "total_borrowings", "inventories", "trade_receivables", "trade_payables",
    "current_assets", "current_liabilities",
    # The case, the documents and the other stages.
    "amount_requested", "vintage_years", "bureau_rank", "market_value", "realisable_value",
    "annual_instalments", "proposed_instalments", "blocking_items_open", "audited_years",
}

# The only expression nodes a norm may use (F-20.1): arithmetic over inputs and numbers.
ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub,
                 ast.Constant, ast.Name, ast.Load)


def unsupported_nodes(tree: ast.AST) -> list[str]:
    """The node types in a parsed expression that a norm may not use."""
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES) or (
            isinstance(node, ast.Constant)
            and (isinstance(node.value, bool) or not isinstance(node.value, (int, float)))
        ):
            bad.append(type(node).__name__)
    return bad


class DeviationCategory(BaseModel):
    key: str
    label: str


class PolicyNorm(BaseModel):
    """One norm (F-20.1): an expression over POLICY_INPUTS, a threshold, the
    deviation category a breach falls under, and its source. A ratio norm
    takes its label, unit, direction and threshold from `ratios`."""

    id: str
    family: Literal["eligibility", "ratios", "security_cover", "documentation"]
    expression: str
    ratio: str | None = None
    label: str | None = None
    unit: Literal["x", "%", "days", "years", "inr", "count", "rank"] | None = None
    kind: Literal["min", "max"] | None = None
    threshold: float | None = None
    category: str
    applies_when: Literal["always", "working_capital", "turnover_method", "term_debt", "collateral"] = "always"
    """turnover_method: a working-capital request at or below working_capital.mpbf_above_limit_inr."""
    constitutions: list[Literal["private_limited", "proprietorship", "partnership"]] | None = None
    """When set, the norm does not apply to a case of another known constitution."""
    non_positive_denominator: Literal["cannot_evaluate", "deviation"] = "cannot_evaluate"
    """A divisor that is zero or negative: the norm cannot be evaluated, or is a deviation
    (leverage on a non-positive net worth is never a pass)."""
    pd_gap: Literal["ask", "skip"] = "ask"
    """skip: when the norm cannot be evaluated, the promoter is not asked (the bank obtains the input)."""
    source: Source | None = None
    status: Status | None = None
    note: str | None = None
    pd_question: str | None = None
    """Overrides the family's personal-discussion question for a deviation (F-24.1)."""
    pd_gap_question: str | None = None
    """Overrides `pd_questions.cannot_evaluate` when the norm cannot be evaluated for want of an input
    (F-24.1), with the same placeholders. A version published before it existed reads as None."""


class PolicySection(BaseModel):
    """config/policy.yaml"""

    working_capital: WorkingCapitalPolicy
    ratios: list[PolicyRatio]
    available_ratios: list[PolicyRatio] = Field(default_factory=list)
    deviation_categories: list[DeviationCategory] = Field(default_factory=list)
    norms: list[PolicyNorm] = Field(default_factory=list)
    pd_questions: dict[str, str] = Field(default_factory=dict)
    """Per norm family, what to ask the promoter about a deviation, and per reason, about a norm that
    could not be evaluated (F-24.1); may use {label}, {subject} (the label as it reads inside a
    sentence), {actual}, {required}, {period}, {missing}, {inputs} and, for a norm that could not be
    evaluated, {reason} (the memo's sentence saying why)."""


class CoverageRule(BaseModel):
    """What "complete" means for an item beyond presence (F-13.2), always
    measured from the case's fixed as_of date (principle 8)."""

    kind: Literal["financial_year", "assessment_years", "monthly_periods", "account_months", "parties", "statements"]
    offset: int = 0
    """financial_year: 1 is the latest financial year ended before as_of, 2 the one before."""
    count: int = 0
    """assessment_years: how many, counting back from the latest."""
    months: int = 0
    """monthly_periods / account_months: complete calendar months before the as_of month."""
    statements: list[str] = Field(default_factory=list)
    """statements (and financial_year): sections that must be present, e.g.
    balance_sheet, profit_and_loss."""


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
    coverage: CoverageRule | None = None
    """Completeness rule; None means one valid document suffices."""
    request: str | None = None
    """How to ask for it when missing, in plain language (F-14.2)."""


class ChecklistTaxonomySection(BaseModel):
    """config/checklist_taxonomy.yaml"""

    sections: list[str]
    section_weight: dict[str, int]
    review_gate_threshold: int
    disbursement_gate_threshold: int
    items: list[ChecklistItemDef]


DocumentGroup = Literal[
    "origination",
    "constitution",
    "registration",
    "kyc",
    "financials",
    "tax",
    "banking",
    "working_capital",
    "collateral",
    "bureau",
    "other_known",
]

InstanceKey = Literal["none", "period", "year", "account", "person", "property"]


class PartyList(BaseModel):
    """A list of people a document names (F-10.2): the field that holds them and, for a list of
    objects, the key of each part. A plain list of names has no `name_key`."""

    field: str
    name_key: str | None = None
    din_key: str | None = None
    pan_key: str | None = None
    designation_key: str | None = None
    din_field: str | None = None
    """For a plain list of names: a parallel list of DINs, used only when it has one per name."""
    role: str | None = None
    """The party's role when the document does not say (director, partner, proprietor)."""


class DocumentTypeDef(BaseModel):
    id: str
    name: str
    group: DocumentGroup
    description: str
    """What the document is, in one sentence; also the model's description."""
    satisfies: list[str] = Field(default_factory=list)
    """Checklist item ids this type can satisfy (F-09.6). Empty for types
    that satisfy nothing (origination and other known types)."""
    instance_key: InstanceKey = "none"
    personal: bool = False
    """Belongs to a person and is attributed to a party (F-10)."""
    partner_output: bool = False
    """A report from RBL's GST, bank-statement analysis or bureau partner (F-11)."""
    provenance: Literal["declared", "borrower_supplied", "independent"] | None = None
    """Where the document comes from, as the cross-verification board tags it: declared (the
    RM's message, the borrower's declaration), borrower-supplied (uploaded financials, returns,
    statements) or independent (bureau, partner GST and bank-statement analysis reports).
    Required when publishing (cross_check); a version published before it existed reads as None."""
    party_list: PartyList | None = None
    """People this document names, for the case's party set (F-10.2)."""


class DocumentTypesSection(BaseModel):
    """config/document_types.yaml (F-00.4)."""

    types: list[DocumentTypeDef]
    """The closed list. Signals, fields and tables of each type are in the ingestion sections
    (config/ingestion/), published in the same version (FRD AD-2a)."""


class DocumentAge(BaseModel):
    type_id: str
    max_age_days: int
    measured_from: Literal["document_date", "period_end", "as_at_date", "valuation_date"]
    source: Source


class DocumentValidity(BaseModel):
    """A date printed on a document that must hold at the case's as_of date.

    expires: the date is the last day the document is valid (ID expiry, validity end);
    a date before as_of makes it expired. not_future: the date is when the document was
    made; a date after as_of is suspect. An absent date is no finding.
    """

    type_id: str
    field: str
    kind: Literal["expires", "not_future"]
    source: Source


class DocumentAgesSection(BaseModel):
    """config/document_ages.yaml (F-13.2)."""

    ages: list[DocumentAge]
    validity: list[DocumentValidity] = []


class Tolerance(BaseModel):
    key: str
    label: str
    value: float
    unit: Literal["%", "inr", "days", "ratio"]
    source: Source


class TolerancesSection(BaseModel):
    """config/tolerances.yaml (F-19)."""

    tolerances: list[Tolerance]


class CreditExclusion(BaseModel):
    """One bank-credit exclusion rule (F-18.2)."""

    id: str
    label: str
    narration_any: list[str] = Field(default_factory=list)
    own_account: bool = False
    """Also match a narration naming another account in the account set."""


class AlignmentSection(BaseModel):
    """config/alignment.yaml (F-18)."""

    financial_year_start_month: int = Field(ge=1, le=12)
    bank_credit_exclusions: list[CreditExclusion]
    obligation_narration_any: list[str]
    name_noise_words: list[str]
    own_bank_names: list[str] = Field(default_factory=list)
    """The names a board resolution in favour of this bank may use (BR-03)."""


TxnDirection = Literal["credit", "debit"]
TxnLookup = Literal["own_account_number", "borrower_name", "lender_name", "director_name"]


class TxnCategory(BaseModel):
    id: str
    direction: TxnDirection
    label: str


class TxnChannel(BaseModel):
    id: str
    pattern: str


class TxnCounterparty(BaseModel):
    strip: list[str]
    noise_words: list[str]
    lender_cues: list[str]


class TxnPairing(BaseModel):
    days: int = Field(ge=0)


class TxnRule(BaseModel):
    """One narration rule (config/txn_classification.yaml). It matches when the direction agrees, some
    `any` pattern is found (or none is asked for), no `none` pattern is found, and, when `lookup`
    names something the case supplies, the narration mentions it."""

    id: str
    category: str
    tier: int = Field(ge=1, le=3)
    direction: TxnDirection
    any: list[str] = Field(default_factory=list)
    none: list[str] = Field(default_factory=list)
    lookup: TxnLookup | None = None
    counterparty: str = "none"
    """`none`, `auto` (what is left after the strip patterns), or a pattern with one capture group."""
    confidence: float = Field(gt=0, le=1)


class TxnClassificationSection(BaseModel):
    """config/txn_classification.yaml: the deterministic pass over bank-statement transactions."""

    categories: list[TxnCategory]
    channels: list[TxnChannel]
    counterparty: TxnCounterparty
    round_amount_multiple: int = Field(gt=0)
    pairing: TxnPairing
    model_threshold: float = Field(ge=0, le=1)
    rules: list[TxnRule]

    def problems(self) -> list[str]:
        out: list[str] = []
        cats = {c.id: c for c in self.categories}
        if len(cats) != len(self.categories):
            out.append("txn_classification: duplicate category ids")
        for fallback in ("other_credit", "other_debit"):
            if fallback not in cats:
                out.append(f"txn_classification: needs the category {fallback!r}")
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            out.append("txn_classification: duplicate rule ids")

        def compiles(where: str, pattern: str, groups: int | None = None) -> None:
            try:
                rx = re.compile(pattern, re.I)
            except re.error as e:
                out.append(f"{where}: bad pattern {pattern!r} ({e})")
                return
            if groups is not None and rx.groups != groups:
                out.append(f"{where}: pattern {pattern!r} needs exactly {groups} capture group(s)")

        for ch in self.channels:
            compiles(f"txn_classification.channels.{ch.id}", ch.pattern)
        for p in self.counterparty.strip:
            compiles("txn_classification.counterparty.strip", p)
        for r in self.rules:
            where = f"txn_classification.rules.{r.id}"
            cat = cats.get(r.category)
            if cat is None:
                out.append(f"{where}: unknown category {r.category!r}")
            elif cat.direction != r.direction:
                out.append(f"{where}: a {r.direction} rule cannot give the {cat.direction} category {r.category!r}")
            if not r.any and not r.lookup:
                out.append(f"{where}: needs `any` patterns or a `lookup`")
            for p in [*r.any, *r.none]:
                compiles(where, p)
            if r.counterparty not in ("none", "auto"):
                compiles(f"{where}.counterparty", r.counterparty, groups=1)
        return out


CrossCheckVariable = Literal[
    "entity_pan",
    "gstin",
    "legal_name",
    "cin",
    "promoter_set",
    "director_identifiers",
    "incorporation_particulars",
    "memorandum_directors",
    "person_names",
    "borrowing_limit",
    "signatories_are_directors",
    "resolution_lender",
    "resolution_date",
    "turnover_audited_vs_gst",
    "turnover_gst_vs_bank",
    "turnover_audited_vs_bank",
    "turnover_declared_vs_evidenced",
    "turnover_itr_vs_audited",
    "turnover_itr_vs_gst",
    "turnover_itr_vs_bank",
    "turnover_gst_vs_bank_window",
    "itr_years",
    "itr_profit",
    "comparatives",
    "year_end_balance",
    "declared_accounts_with_statements",
    "evidenced_accounts_declared",
    "facilities_reconcile",
    "emis_to_declared_lenders",
    "borrowings_serviced",
]

# Where a rule's outcome is shown and reported (the Cross-verification tab, the CAM).
CheckArea = Literal["identity", "authority", "turnover", "tax", "financials", "accounts", "obligations"]


class CrossCheckRule(BaseModel):
    """One cross-check (F-19.1)."""

    id: str
    title: str
    """What the rule compares, in words ("Audited turnover against GST outward supplies")."""
    finding_title: str | None = None
    """The finding in plain English when the rule fails ("Audited turnover not supported by bank credits").
    Required when publishing (cross_check); a version published before it existed reads as None."""
    policy_ref: str | None = None
    """The credit policy clause the rule enforces, when RBL supplies one."""
    area: CheckArea
    variable: CrossCheckVariable
    sources: list[str]
    comparison: Literal["exact", "tolerance", "set_equal", "set_contains", "presence", "bound", "order"]
    """F-19.1's five comparisons, plus `bound` (one value at least or at most
    another) and `order` (dates in sequence)."""
    tolerance: str | None = None
    severity: Literal["serious", "moderate", "mild"]
    blocking: bool
    """Blocks submission: the memo cannot be drafted while a failure is not accepted or dismissed."""
    explanation: str
    query: str | None = None
    pd_question: str | None = None
    """What to ask the promoter in the personal discussion when the rule
    fails (F-24.1); may use {explanation}."""
    enabled: bool = True
    """A switched-off rule stays in configuration, and is still validated, but is not run: it gives
    no finding, so no review item, query, CAM or PD-note entry, and blocks nothing. A version
    published before the switch existed reads every rule as enabled."""


class CrossChecksSection(BaseModel):
    """config/crosschecks.yaml (F-19)."""

    rules: list[CrossCheckRule]
    pd_incomplete: str = "{title}: {explanation}"
    """The personal-discussion question for a check left incomplete (F-24.1); may use {title},
    {explanation} and {request} (what would complete the check)."""
    pd_finding: str = "{explanation} What is the position, and what will be provided?"
    """The personal-discussion question for a failed finding, not found not valid, whose rule has no
    `pd_question` of its own (F-24.1); may use {explanation}. A version published before it existed
    reads this default."""

    @property
    def enabled_rules(self) -> list[CrossCheckRule]:
        """The rules that run, in their configured order."""
        return [r for r in self.rules if r.enabled]


CamKind = Literal[
    "snapshot", "borrower_profile", "proposal", "promoters", "financial_performance", "working_capital",
    "turnover", "banking", "existing_facilities", "cross_verification", "policy", "documentation",
]


class CamPartDef(BaseModel):
    """One part of a memo section: what it is drafted from, under its own subheading."""

    id: str
    kind: CamKind
    title: str


class CamSectionDef(BaseModel):
    """A memo section: drafted from one kind (`kind`, a version published before parts existed), or
    from several parts in order, each under its subheading."""

    id: str
    kind: CamKind | None = None
    title: str
    purpose: str | None = None
    """One line under the section's title on the screen: what the section is for."""
    parts: list[CamPartDef] = Field(default_factory=list)

    def drafted_from(self) -> list[CamPartDef]:
        if self.parts:
            return self.parts
        return [CamPartDef(id=self.id, kind=self.kind, title=self.title)] if self.kind else []


class CamCopilotConfig(BaseModel):
    """The model that redrafts a memo section in other words (Regenerate with copilot). Only the
    sampling parameters named here are sent; every answer is recorded and replayed for the same
    request, so a section reads the same each time it is shown."""

    enabled: bool = False
    provider: Literal["openai"] = "openai"
    model: str = ""
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float | None = None
    seed: int | None = None
    timeout_s: int = 60
    system: str = ""
    user: str = ""


PdTopicArea = Literal["identity", "turnover", "accounts", "obligations", "policy"]


class PdNoteConfig(BaseModel):
    """The PD question note's wording (F-24): its title, the blank lines for the record of the
    discussion, the title of each topic the questions are asked under, the sign-off and the labels in
    the downloaded note."""

    title: str = "Personal discussion — question note"
    record_fields: list[str] = Field(default_factory=list)
    topics: dict[PdTopicArea, str] = Field(default_factory=lambda: {
        "identity": "Identity and KYC", "turnover": "Turnover, tax and sales", "accounts": "Bank accounts",
        "obligations": "Existing borrowings", "policy": "Policy norms"})
    """Each topic's title, by area. The note asks the topics in the order of PdTopicArea: a published
    version keeps no order of keys."""
    sign_off: list[str] = Field(default_factory=lambda: ["Discussion held by"])
    """The sign-off block's roles, in order."""
    labels: dict[str, str] = Field(default_factory=dict)
    """The headings and labels inside the downloaded note, by key (people_to_meet, why_we_ask, …); a
    key not given keeps the download's own wording."""


class CamSectionConfig(BaseModel):
    """config/cam.yaml (F-23.1, F-24). A version published before the title, the template note, the
    recommendation prompts, the sign-off, the labels and the PD note's wording existed reads them as
    these defaults."""

    interim_template: bool
    title: str = "Credit Approval Memo"
    template_note: str | None = None
    """Said on the memo while its layout is assumed."""
    sections: list[CamSectionDef]
    summary_title: str
    summary_purpose: str | None = None
    recommendation_title: str
    recommendation_purpose: str | None = None
    rating_note: str | None = None
    """Said where a rating would be, while no rating model is configured."""
    copilot: CamCopilotConfig = Field(default_factory=CamCopilotConfig)
    recommendation_prompts: list[str] = Field(default_factory=list)
    """The headings credit completes under the recommendation, each left blank."""
    sign_off: list[str] = Field(default_factory=list)
    """The sign-off block's roles, in order."""
    labels: dict[str, str] = Field(default_factory=dict)
    """The headings and labels inside the downloaded memo, by key (case_id, sources, summary_findings,
    …); a key not given keeps the download's own wording."""
    pd_note: PdNoteConfig = Field(default_factory=PdNoteConfig)


class StatementLine(BaseModel):
    """A row of a statement table, found by its printed label."""

    table: str
    row: str
    """Regular expression, case-insensitive, matched against the row's first column."""
    column: str | None = None
    """Overrides the section's column (for example `previous_period`)."""
    label: str = "particulars"
    """The column that holds the row's printed label."""


class GstLine(BaseModel):
    table: str
    row: str
    column: str
    label: str = "description"


class StatementsSection(BaseModel):
    """config/statements.yaml: where the canonical financial lines are printed (F-18, F-20, F-22).

    The document-processing service returns each statement as a table of printed rows. The
    engine reads lines from those rows by label, and derives the rest, so the policy ratios, the
    spread and the turnover facts all use the same figures."""

    column: str = "current_period"
    """The column holding the statement's own year; the other column is the comparative."""
    lines: dict[str, StatementLine]
    derived: dict[str, str] = Field(default_factory=dict)
    """Line key to an expression over other lines (summed from the lines it names)."""
    gst_outward: GstLine
    """GST turnover: every row of the return's table that matches is summed."""
    itr_lines: dict[str, StatementLine] = Field(default_factory=dict)
    """Lines of an income tax return's computation, compared with the books (TX-02, TX-03)."""


class MatrixAuthority(BaseModel):
    """An approving authority: a role or committee, never a person (F-21)."""

    key: str
    level: int = Field(ge=1)
    label: str
    status: Status


class ProductGroup(BaseModel):
    key: str
    label: str
    facilities: list[str] = Field(min_length=1)


class AmountBand(BaseModel):
    up_to_inr: int | None = Field(default=None, gt=0)
    """Inclusive upper bound; None for the last, open band."""
    authority: str
    status: Status


class DeviationRule(BaseModel):
    category: str
    levels_above: int = Field(default=1, ge=0)
    at_least: str | None = None
    status: Status


class ApprovalMatrixSection(BaseModel):
    """config/approval_matrix.yaml (F-00.1, F-21): who must approve a case, by amount, product
    and the categories of its policy deviations."""

    source: Source
    status: Status
    note: str
    amount_basis: Literal["amount_requested"] = "amount_requested"
    authorities: list[MatrixAuthority] = Field(min_length=1)
    products: list[ProductGroup] = Field(min_length=1)
    bands: dict[str, list[AmountBand]]
    deviations: list[DeviationRule]


def matrix_problems(matrix: ApprovalMatrixSection, categories: set[str], facilities: set[str] | None = None) -> list[str]:
    """What is wrong with an approval matrix, one problem per line."""
    problems: list[str] = []
    where = "approval_matrix"
    keys = [a.key for a in matrix.authorities]
    levels = [a.level for a in matrix.authorities]
    if len(keys) != len(set(keys)):
        problems.append(f"{where}: duplicate authority keys")
    if len(levels) != len(set(levels)):
        problems.append(f"{where}: duplicate authority levels")
    elif sorted(levels) != list(range(1, len(levels) + 1)):
        # Escalation counts levels ("one level above the amount authority"): a gap would name no authority.
        problems.append(f"{where}: authority levels must be consecutive from 1")
    if levels != sorted(levels):
        problems.append(f"{where}: authority levels must ascend in list order")
    level_of = {a.key: a.level for a in matrix.authorities}
    product_keys = [p.key for p in matrix.products]
    if len(product_keys) != len(set(product_keys)):
        problems.append(f"{where}: duplicate product keys")
    if set(matrix.bands) != set(product_keys):
        problems.append(f"{where}: bands must be given for exactly the products {sorted(product_keys)}")
    for product, bands in matrix.bands.items():
        bounds = [b.up_to_inr for b in bands]
        if bounds.count(None) != 1 or bounds[-1] is not None:
            problems.append(f"{where}.bands.{product}: exactly one open band, and it last")
        closed = [b for b in bounds if b is not None]
        if closed != sorted(set(closed)) or len(closed) != len(set(closed)):
            problems.append(f"{where}.bands.{product}: up_to_inr must strictly ascend")
        for band in bands:
            if band.authority not in level_of:
                problems.append(f"{where}.bands.{product}: unknown authority {band.authority!r}")
        band_levels = [level_of.get(b.authority, 0) for b in bands]
        if band_levels != sorted(band_levels):
            problems.append(f"{where}.bands.{product}: the authority must not fall as the amount rises")
    rule_categories = [r.category for r in matrix.deviations]
    if len(rule_categories) != len(set(rule_categories)):
        problems.append(f"{where}: duplicate deviation rule category")
    for rule in matrix.deviations:
        if rule.category not in categories:
            problems.append(f"{where}: deviation rule for unknown category {rule.category!r}")
        if rule.at_least and rule.at_least not in level_of:
            problems.append(f"{where}: deviation rule {rule.category!r} names unknown authority {rule.at_least!r}")
    for category in sorted(categories - set(rule_categories)):
        problems.append(f"{where}: deviation category {category!r} has no rule")
    if facilities is not None:
        seen: dict[str, int] = {}
        for p in matrix.products:
            for f in p.facilities:
                seen[f] = seen.get(f, 0) + 1
                if f not in facilities:
                    problems.append(f"{where}.products.{p.key}: unknown facility {f!r}")
        for f in sorted(facilities):
            if seen.get(f, 0) != 1:
                problems.append(f"{where}: facility {f!r} must belong to exactly one product")
    if matrix.status == "active":
        rows = [*matrix.authorities, *[b for bands in matrix.bands.values() for b in bands], *matrix.deviations]
        if any(r.status == "provisional" for r in rows):
            problems.append(f"{where}: an active matrix may not keep provisional rows")
    return problems


SECTION_MODELS: dict[str, type[BaseModel]] = {
    "policy": PolicySection,
    "checklist_taxonomy": ChecklistTaxonomySection,
    "document_types": DocumentTypesSection,
    "document_ages": DocumentAgesSection,
    "tolerances": TolerancesSection,
    "alignment": AlignmentSection,
    "txn_classification": TxnClassificationSection,
    "crosschecks": CrossChecksSection,
    "cam": CamSectionConfig,
    "statements": StatementsSection,
    "approval_matrix": ApprovalMatrixSection,
}


def cross_check(sections: dict[str, BaseModel], ingestion: dict[str, dict] | None = None,
                facilities: set[str] | None = None) -> list[str]:
    """References between sections that must resolve. Returns problems."""
    problems: list[str] = []
    txn = sections.get("txn_classification")
    if isinstance(txn, TxnClassificationSection):
        problems += txn.problems()
    checklist = sections["checklist_taxonomy"]
    types = sections["document_types"]
    assert isinstance(checklist, ChecklistTaxonomySection) and isinstance(types, DocumentTypesSection)
    item_ids = {item.id for item in checklist.items}
    type_ids = [t.id for t in types.types]
    if len(type_ids) != len(set(type_ids)):
        problems.append("document_types: duplicate type ids")
    for t in types.types:
        for item in t.satisfies:
            if item not in item_ids:
                problems.append(f"document_types.{t.id}: satisfies unknown checklist item {item!r}")
        if t.provenance is None:
            problems.append(f"document_types.{t.id}: needs a provenance")
    if ingestion is not None:
        ingest_ids = [d["document_type"] for d in ingestion["document_types"]["documents"]]
        engine_only = {t.id for t in types.types if t.group == "origination"}
        if sorted(ingest_ids) != sorted(set(type_ids) - engine_only):
            problems.append(f"document_types: ids differ from config/ingestion/document_types.json "
                            f"(only in one: {sorted(set(ingest_ids) ^ (set(type_ids) - engine_only))})")
    covered = {item for t in types.types for item in t.satisfies}
    for item in sorted(item_ids - covered):
        problems.append(f"checklist item {item!r} is satisfied by no document type")
    ages = sections["document_ages"]
    assert isinstance(ages, DocumentAgesSection)
    for age in ages.ages:
        if age.type_id not in type_ids:
            problems.append(f"document_ages: unknown type {age.type_id!r}")
    for rule in ages.validity:
        if rule.type_id not in type_ids:
            problems.append(f"document_ages: validity rule for unknown type {rule.type_id!r}")
    policy = sections["policy"]
    assert isinstance(policy, PolicySection)
    ratio_keys = {r.key for r in policy.ratios}
    categories = {c.key for c in policy.deviation_categories}
    norm_ids = [n.id for n in policy.norms]
    if len(norm_ids) != len(set(norm_ids)):
        problems.append("policy: duplicate norm ids")
    for norm in policy.norms:
        where = f"policy.norms.{norm.id}"
        if norm.ratio and norm.ratio not in ratio_keys:
            problems.append(f"{where}: unknown ratio {norm.ratio!r}")
        if not norm.ratio and (norm.label is None or norm.kind is None or norm.threshold is None):
            problems.append(f"{where}: a norm without a ratio needs label, kind and threshold")
        if norm.category not in categories:
            problems.append(f"{where}: unknown deviation category {norm.category!r}")
        if not norm.ratio and (norm.source is None or norm.status is None):
            problems.append(f"{where}: needs a source and status")
        try:
            tree = ast.parse(norm.expression, mode="eval")
        except SyntaxError as e:
            problems.append(f"{where}: expression does not parse ({e.msg})")
            continue
        if unsupported_nodes(tree):
            problems.append(f"{where}: unsupported expression ({', '.join(sorted(set(unsupported_nodes(tree))))})")
            continue
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for name in sorted(names - POLICY_INPUTS):
            problems.append(f"{where}: unknown input {name!r}")
        if norm.non_positive_denominator == "deviation" and not any(
                isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) for n in ast.walk(tree)):
            problems.append(f"{where}: non_positive_denominator needs a division")
        if norm.applies_when == "turnover_method":
            expected = policy.working_capital.turnover_requirement_pct - policy.working_capital.turnover_margin_pct
            if norm.unit != "%" or norm.threshold != expected:
                problems.append(f"{where}: threshold differs from the turnover method ({expected:g}%)")
    matrix = sections.get("approval_matrix")
    if matrix is not None:
        assert isinstance(matrix, ApprovalMatrixSection)
        problems += matrix_problems(matrix, categories, facilities)
    tolerances = sections["tolerances"]
    checks = sections["crosschecks"]
    assert isinstance(tolerances, TolerancesSection) and isinstance(checks, CrossChecksSection)
    tolerance_keys = {tol.key for tol in tolerances.tolerances}
    rule_ids = [rule.id for rule in checks.rules]
    if len(rule_ids) != len(set(rule_ids)):
        problems.append("crosschecks: duplicate rule ids")
    for rule in checks.rules:
        if not (rule.finding_title or "").strip():
            problems.append(f"crosschecks.{rule.id}: needs a finding_title")
        if rule.tolerance and rule.tolerance not in tolerance_keys:
            problems.append(f"crosschecks.{rule.id}: unknown tolerance {rule.tolerance!r}")
        if rule.comparison == "tolerance" and not rule.tolerance:
            problems.append(f"crosschecks.{rule.id}: a tolerance comparison needs a tolerance")
        # The application message is not a document type but a source (F-04).
        for source in rule.sources:
            if source not in type_ids:
                problems.append(f"crosschecks.{rule.id}: unknown source {source!r}")
    return problems
