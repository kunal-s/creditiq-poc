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
    "annual_instalments", "blocking_items_open", "audited_years",
}


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
    applies_when: Literal["always", "working_capital", "term_debt", "collateral"] = "always"
    source: Source | None = None
    status: Status | None = None
    note: str | None = None
    pd_question: str | None = None
    """Overrides the family's personal-discussion question (F-24.1)."""


class PolicySection(BaseModel):
    """config/policy.yaml"""

    working_capital: WorkingCapitalPolicy
    ratios: list[PolicyRatio]
    available_ratios: list[PolicyRatio] = Field(default_factory=list)
    deviation_categories: list[DeviationCategory] = Field(default_factory=list)
    norms: list[PolicyNorm] = Field(default_factory=list)
    pd_questions: dict[str, str] = Field(default_factory=dict)
    """Per norm family, what to ask the promoter about a deviation (F-24.1);
    may use {label}, {actual}, {required} and {period}."""


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


CrossCheckVariable = Literal[
    "entity_pan",
    "gstin",
    "legal_name",
    "cin",
    "promoter_set",
    "director_identifiers",
    "incorporation_particulars",
    "memorandum_directors",
    "borrowing_limit",
    "signatories_are_directors",
    "resolution_lender",
    "resolution_date",
    "turnover_audited_vs_gst",
    "turnover_gst_vs_bank",
    "turnover_audited_vs_bank",
    "turnover_declared_vs_evidenced",
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
    area: CheckArea
    variable: CrossCheckVariable
    sources: list[str]
    comparison: Literal["exact", "tolerance", "set_equal", "set_contains", "presence", "bound", "order"]
    """F-19.1's five comparisons, plus `bound` (one value at least or at most
    another) and `order` (dates in sequence)."""
    tolerance: str | None = None
    severity: Literal["serious", "moderate", "mild"]
    blocking: bool
    explanation: str
    query: str | None = None
    pd_question: str | None = None
    """What to ask the promoter in the personal discussion when the rule
    fails (F-24.1); may use {explanation}."""


class CrossChecksSection(BaseModel):
    """config/crosschecks.yaml (F-19)."""

    rules: list[CrossCheckRule]
    pd_incomplete: str = "{title}: {explanation}"
    """The personal-discussion question for a check left incomplete (F-24.1)."""


class CamSectionDef(BaseModel):
    id: str
    kind: Literal[
        "borrower_profile", "proposal", "promoters", "financial_performance", "working_capital", "banking",
        "existing_facilities", "cross_verification", "policy", "documentation",
    ]
    title: str


class CamSectionConfig(BaseModel):
    """config/cam.yaml (F-23.1)."""

    interim_template: bool
    sections: list[CamSectionDef]
    summary_title: str
    recommendation_title: str


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


SECTION_MODELS: dict[str, type[BaseModel]] = {
    "policy": PolicySection,
    "checklist_taxonomy": ChecklistTaxonomySection,
    "document_types": DocumentTypesSection,
    "document_ages": DocumentAgesSection,
    "tolerances": TolerancesSection,
    "alignment": AlignmentSection,
    "crosschecks": CrossChecksSection,
    "cam": CamSectionConfig,
    "statements": StatementsSection,
}


def cross_check(sections: dict[str, BaseModel], ingestion: dict[str, dict] | None = None) -> list[str]:
    """References between sections that must resolve. Returns problems."""
    problems: list[str] = []
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
        try:
            names = {n.id for n in ast.walk(ast.parse(norm.expression, mode="eval")) if isinstance(n, ast.Name)}
        except SyntaxError as e:
            problems.append(f"{where}: expression does not parse ({e.msg})")
            continue
        for name in sorted(names - POLICY_INPUTS):
            problems.append(f"{where}: unknown input {name!r}")
    tolerances = sections["tolerances"]
    checks = sections["crosschecks"]
    assert isinstance(tolerances, TolerancesSection) and isinstance(checks, CrossChecksSection)
    tolerance_keys = {tol.key for tol in tolerances.tolerances}
    rule_ids = [rule.id for rule in checks.rules]
    if len(rule_ids) != len(set(rule_ids)):
        problems.append("crosschecks: duplicate rule ids")
    for rule in checks.rules:
        if rule.tolerance and rule.tolerance not in tolerance_keys:
            problems.append(f"crosschecks.{rule.id}: unknown tolerance {rule.tolerance!r}")
        if rule.comparison == "tolerance" and not rule.tolerance:
            problems.append(f"crosschecks.{rule.id}: a tolerance comparison needs a tolerance")
        # The application message is not a document type but a source (F-04).
        for source in rule.sources:
            if source not in type_ids:
                problems.append(f"crosschecks.{rule.id}: unknown source {source!r}")
    return problems
