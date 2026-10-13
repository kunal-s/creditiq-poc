"""Outputs: the spread, the draft CAM and the PD note (FRD F-22 to F-24)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import Evidence


class SpreadCell(BaseModel):
    value: float | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    relies_on_manual: bool = False


class SpreadColumn(BaseModel):
    """One year of one kind of statement."""

    key: str
    fy: str
    period_end: str
    basis: Literal["audited", "provisional", "projected"]


class SpreadRow(BaseModel):
    key: str
    label: str
    section: Literal["profit_and_loss", "balance_sheet", "ratios"]
    kind: Literal["line", "derived", "ratio"]
    unit: Literal["inr", "x", "%", "days"]
    formula: str | None = None
    """For derived lines and ratios: the working, in words (F-22.3)."""
    cells: list[SpreadCell]
    """One per column, in column order."""


class Working(BaseModel):
    """One step of the working-capital assessment (F-22.2)."""

    label: str
    value: float | None
    unit: Literal["inr", "%"] = "inr"
    basis: str | None = None
    """How the step is computed, in words."""
    evidence: list[Evidence] = Field(default_factory=list)


class WorkingCapitalAssessment(BaseModel):
    method: Literal["turnover", "mpbf", "not_applicable"]
    reason: str
    """Why this method (the configured limit) or why none applies."""
    column: str | None = None
    """The spread column the figures come from."""
    steps: list[Working] = Field(default_factory=list)
    eligible: float | None = None
    requested: float
    missing: list[str] = Field(default_factory=list)


class Spread(BaseModel):
    case_id: str
    interim: bool = True
    """Laid out before RBL's template arrived (decision C.4-8)."""
    columns: list[SpreadColumn]
    rows: list[SpreadRow]
    working_capital: WorkingCapitalAssessment


Severity = Literal["serious", "moderate", "mild"]
PdArea = Literal["identity", "turnover", "accounts", "obligations", "policy"]


class OutputSource(BaseModel):
    """A document the memo or the note cites, numbered in the order it is first cited, so the screen
    and the downloads refer to it the same way (F-23.2, F-24.2)."""

    number: int
    document_id: str
    label: str
    """The document as the case lists it, e.g. "Audited financial statements · FY 2025-26"."""
    file_name: str | None = None
    """The file it was read from."""
    pages: list[int]
    """The pages cited, ascending."""


class PdRef(BaseModel):
    """Another finding a merged question also rests on (F-24.2)."""

    ref: str
    xv_ref: str | None = None
    rule: str
    title: str
    status: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class PdQuestion(BaseModel):
    """One question for the personal discussion (F-24)."""

    id: str
    number: int
    """Its number in the note, 1 first, in the order the note asks them."""
    question: str
    """What to ask the promoter, in plain words."""
    context: str
    """Why: the finding, deviation or gap it comes from, in words."""
    text: str
    """The context and the question together, as one paragraph."""
    severity: Severity
    source: Literal["finding", "deviation", "gap"]
    ref: str
    """The finding id or norm id it comes from (F-24.2)."""
    xv_ref: str | None = None
    """For a finding: its board reference (XV-…)."""
    rule: str
    """The rule or norm id, e.g. OB-02, FR-05."""
    title: str
    """The finding's title (what is wrong) or the norm's label."""
    area: PdArea
    """The topic it is asked under."""
    status: str | None = None
    """For a finding: Accepted as valid, Escalated or Open."""
    evidence: list[Evidence] = Field(default_factory=list)
    target: Literal["cross_verification", "policy"] = "policy"
    """The tab the question links to."""
    also: list[PdRef] = Field(default_factory=list)
    """Other findings the same question covers, when one question is asked for several."""


class PdTopic(BaseModel):
    """The questions asked under one topic, in order."""

    area: PdArea
    title: str
    question_ids: list[str]


class PdPerson(BaseModel):
    """Someone to meet: a promoter or director the documents name."""

    name: str
    role: str | None = None
    din: str | None = None
    """Their DIN; where documents differ, each value with the document it comes from."""
    sources: list[str] = Field(default_factory=list)
    """The documents that name them."""
    evidence: list[Evidence] = Field(default_factory=list)
    """The pages that name them and give their DIN."""


class PdNote(BaseModel):
    """The PD question note (F-24): ranked questions, each tied to its finding and evidence."""

    case_id: str
    title: str
    borrower: str
    as_of: str
    """The date the case's data is read as of."""
    config_version: str
    config_label: str = ""
    """The configuration version as people know it, e.g. "Version 15 (published 13 Oct 2026)"."""
    header: list[CamFact] = Field(default_factory=list)
    """The note's header facts: borrower, case, constitution, proposal, data as of, configuration."""
    people: list[PdPerson] = Field(default_factory=list)
    questions: list[PdQuestion]
    """Every question, in the order the note asks them."""
    topics: list[PdTopic] = Field(default_factory=list)
    documents_to_collect: list[CamText] = Field(default_factory=list)
    """Documents still to be obtained (the open query list), to collect at the discussion."""
    record_fields: list[str] = Field(default_factory=list)
    """Blank lines for the record of the discussion: its date, place, who attended."""
    sign_off: list[CamSignOff] = Field(default_factory=list)
    """Left blank for whoever holds the discussion."""
    labels: dict[str, str] = Field(default_factory=dict)
    """The wording printed inside the downloads (headings and field labels), from configuration."""
    sources: list[OutputSource] = Field(default_factory=list)


class CamText(BaseModel):
    """A statement in the memo with the pages it rests on (F-23.2)."""

    text: str
    citations: list[Evidence] = Field(default_factory=list)


class CamFact(BaseModel):
    """One labelled value in a block of key facts."""

    label: str
    value: CamText


class CamTable(BaseModel):
    title: str | None = None
    columns: list[str]
    rows: list[list[CamText]]
    numeric: list[int] = Field(default_factory=list)
    """The columns of figures (aligned right), by position."""
    note: str | None = None
    """A line under the table: a basis, a source, what is not yet on file."""


class CamBlock(BaseModel):
    """One block of a section, in reading order."""

    kind: Literal["paragraph", "facts", "table", "subheading", "note"]
    paragraph: CamText | None = None
    facts: list[CamFact] = Field(default_factory=list)
    table: CamTable | None = None
    text: str | None = None
    """A subheading's or a note's words."""


class CamSection(BaseModel):
    id: str
    number: int
    """Its number in the memo, 1 first."""
    title: str
    blocks: list[CamBlock] = Field(default_factory=list)
    empty: str | None = None
    """What is shown when the section has nothing on file yet."""


class CamSummaryItem(BaseModel):
    kind: Literal["finding", "incomplete", "deviation", "unassessed", "query"]
    """incomplete: a check that could not be completed, with what would complete it."""
    text: str
    severity: Severity | None = None
    ref: str
    """The finding's board reference (XV-…), the norm id or the query id."""
    rule: str | None = None
    """The rule or norm id."""
    title: str | None = None
    """The finding's title or the norm's label."""
    status: str | None = None
    """For a finding: Accepted as valid, Escalated or Open."""
    blocking: bool = False
    """A finding that blocks submission until it is accepted or dismissed."""
    group: Literal["documents_needed", "documents_to_redo", "clarifications"] | None = None
    """For a query: the query-list group it sits in."""
    request: str | None = None
    """For a check that could not be completed: what would complete it."""
    citations: list[Evidence] = Field(default_factory=list)


class CamSignOff(BaseModel):
    """A line of the sign-off block, left for the people who sign."""

    role: str


class Cam(BaseModel):
    """The draft Credit Approval Memo (F-23)."""

    case_id: str
    title: str
    borrower: str
    as_of: str
    """The date the case's data is read as of: the memo says what was on file then."""
    config_version: str
    config_label: str = ""
    """The configuration version as people know it, e.g. "Version 15 (published 13 Oct 2026)"."""
    run_id: str | None = None
    """The cross-check run the memo reports (XR-…)."""
    interim_template: bool
    """Sections from the assumed layout until RBL's template arrives (F-23.1)."""
    template_note: str | None = None
    """Said on the memo while the layout is assumed."""
    sections: list[CamSection]
    summary_number: int
    summary_title: str
    summary: list[CamSummaryItem]
    """Findings, deviations and open queries (F-23.3)."""
    recommendation_number: int
    recommendation_title: str
    recommendation: str = ""
    """Left empty for credit to complete (F-23.4)."""
    recommendation_prompts: list[str] = Field(default_factory=list)
    """The headings credit completes under the recommendation, each left blank."""
    sign_off: list[CamSignOff] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    """The wording printed inside the downloads (headings and field labels), from configuration."""
    sources: list[OutputSource] = Field(default_factory=list)
