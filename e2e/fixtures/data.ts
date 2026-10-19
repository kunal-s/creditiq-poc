/// <reference types="node" />
// Fixture data for the screen tests, typed against the generated API
// contract (src/api/types.ts). Every name here is fictional and was checked
// against the excluded-terms list.
import type {
  ApprovalMatrixConfig,
  ApprovingAuthority,
  Cam,
  CamBlock,
  CamSection,
  CamSummaryItem,
  CamTable,
  CamText,
  CaseComparison,
  CaseDetail,
  CaseFacts,
  CrossVerificationView,
  EditableSettings,
  Evidence,
  EvidenceRow,
  FactValue,
  Finding,
  FindingArea,
  FindingSide,
  OutputSource,
  PdNote,
  PdQuestion,
  NormInput,
  NormResult,
  PolicyAssessment,
  PolicyCounts,
  PolicyGroup,
  PolicyConfig,
  CaseProposal,
  CaseSummary,
  ChecklistItemState,
  ChecklistTaxonomy,
  DocumentTypes,
  FieldValue,
  FileRecord,
  LogicalDocument,
  Meta,
  Party,
  PersonEntry,
  QueryItem,
  Readiness,
  ReviewItem,
  SessionUser,
  SourceColumn,
  Spread,
  Span,
  XvArea,
  XvCounts,
  XvDecision,
  XvFact,
  XvHighlight,
  XvItem,
  XvRun,
} from "../../src/api/types";

export const API = "http://localhost:8201";

export const ANALYST: SessionUser = {
  id: "ananya-krishnan",
  name: "Ananya Krishnan",
  email: "ananya.krishnan@rblbank.com",
  initials: "AK",
  role: "analyst",
  roleLabel: "Credit Analyst",
  branch: "Mumbai hub",
  navGroups: ["workbench", "governance", "administration", "help"],
  permissions: [
    "audit.read",
    "config.read",
    "case.create",
    "case.read",
    "case.read.all",
    "case.delete",
    "document.upload",
    "checklist.read",
    "query.read",
    "data.read",
    "review.read",
    "review.decide",
    "finding.read",
    "output.read",
    "manual.make",
  ],
};

export const RM: SessionUser = {
  id: "arjun-deshpande",
  name: "Arjun Deshpande",
  email: "arjun.deshpande@rblbank.com",
  initials: "AD",
  role: "rm",
  roleLabel: "Relationship Manager",
  branch: "Mumbai hub",
  navGroups: ["workbench", "help"],
  permissions: [
    "case.create",
    "case.read",
    "case.delete",
    "document.upload",
    "checklist.read",
    "query.read",
  ],
};

/** The RBL reviewer: the Credit Manager, who alone adjudicates the comparison and decides an
 * escalated cross-check discrepancy (roles.yaml). */
export const MANAGER: SessionUser = {
  id: "meenal-kulkarni",
  name: "Meenal Kulkarni",
  email: "meenal.kulkarni@rblbank.com",
  initials: "MK",
  role: "credit-manager",
  roleLabel: "Credit Manager",
  branch: "Mumbai hub",
  navGroups: ["workbench", "governance", "administration", "help"],
  permissions: [
    "case.read",
    "case.read.all",
    "case.delete",
    "checklist.read",
    "query.read",
    "data.read",
    "review.read",
    "review.decide",
    "finding.read",
    "output.read",
    "manual.check",
    "comparison.adjudicate",
    "finding.escalation",
    "scorecard.read",
    "audit.read",
    "config.read",
  ],
};

/** The Administrator: administration only, and the one role that publishes settings (roles.yaml). */
export const ADMIN: SessionUser = {
  id: "nikhil-sawant",
  name: "Nikhil Sawant",
  email: "nikhil.sawant@rblbank.com",
  initials: "NS",
  role: "administrator",
  roleLabel: "Administrator",
  branch: "Head office",
  navGroups: ["administration", "help"],
  permissions: ["config.read", "config.publish", "audit.read"],
};

export const META: Meta = {
  channels: [
    { id: "email", label: "Email" },
    { id: "whatsapp", label: "WhatsApp" },
    { id: "phone_note", label: "Phone note" },
  ],
  constitutions: [
    { id: "private_limited", label: "Private limited" },
    { id: "partnership", label: "Partnership" },
    { id: "proprietorship", label: "Proprietorship" },
    { id: "unknown", label: "Not yet confirmed" },
  ],
  facilities: [
    { id: "cash_credit", label: "Cash credit" },
    { id: "term_loan", label: "Term loan" },
    { id: "bank_guarantee", label: "Bank guarantee" },
  ],
  case_create_minimum: ["borrower", "facilities", "amount_inr"],
};

// --- Cases ---

export const KESTREL = "BBG-2026-000021";
export const SAFFRON = "BBG-2026-000022";
export const ORIEL = "BBG-2026-000023";
export const EXISTING = "BBG-2026-000014";

function summary(
  id: string,
  borrower: string,
  stage: CaseSummary["stage"],
  open: number,
  extra: Partial<CaseSummary> = {},
): CaseSummary {
  return {
    id,
    borrower,
    constitution: "private_limited",
    facilities: ["cash_credit", "term_loan"],
    amount_inr: 5_000_000,
    stage,
    rm: "Arjun Deshpande",
    created_at: "2026-09-20T10:00:00Z",
    open_review_items: open,
    ...extra,
  };
}

export const CASES: CaseSummary[] = [
  summary(KESTREL, "Kestrel Polymers Pvt Ltd", "Completeness", 3),
  summary(SAFFRON, "Saffron Loom Textiles Pvt Ltd", "CrossVerification", 0, {
    facilities: ["cash_credit"],
    amount_inr: 25_000_000,
  }),
  summary(ORIEL, "Oriel Castings", "Intake", 0, { constitution: "unknown" }),
];

export function detail(s: CaseSummary, extra: Partial<CaseDetail> = {}): CaseDetail {
  return {
    ...s,
    pan: "AAACK1234K",
    gstin: "27AAACK1234K1Z5",
    cin: null,
    udyam: null,
    collateral_present: true,
    channel: "email",
    as_of: "2026-09-20",
    created_by: "arjun-deshpande",
    config_version: "v3",
    header: {
      borrower: { value: s.borrower, proposed: s.borrower, source: "message:52-76" },
      pan: { value: "AAACK1234K", proposed: "AAACK1234K", source: "message:120-130" },
      gstin: { value: "27AAACK1234K1Z5", proposed: null, source: "document:doc-gst:p1" },
    },
    ...extra,
  };
}

// --- Checklist (F-12, F-13) ---

export const TAXONOMY: ChecklistTaxonomy = {
  sections: [
    "Constitution and KYC",
    "Financials",
    "Banking and operations",
    "Collateral and security",
  ],
  section_weight: {
    "Constitution and KYC": 20,
    Financials: 30,
    "Banking and operations": 30,
    "Collateral and security": 20,
  },
  review_gate_threshold: 85,
  disbursement_gate_threshold: 100,
  items: [
    {
      id: "gst_returns",
      name: "GST returns (12 months)",
      category: "Banking and operations",
      constitutions: ["private_limited", "partnership", "proprietorship"],
      why: "GST returns (12 months) is required for this constitution and facility.",
      basis: "Published credit policy.",
      source: "published_policy",
      blocking: false,
      weight: 4,
      coverage: { kind: "monthly_periods", months: 12, count: 0, offset: 0 },
      request: "GSTR-3B returns for the last 12 months.",
    },
  ],
};

function item(
  item_id: string,
  name: string,
  section: string,
  status: ChecklistItemState["status"],
  extra: Partial<ChecklistItemState> = {},
): ChecklistItemState {
  return {
    item_id,
    name,
    section,
    status,
    blocking: false,
    weight: 4,
    why: `${name} is required for this constitution and facility.`,
    basis: "Published credit policy.",
    document_ids: [],
    deficiency: null,
    ...extra,
  };
}

export const KESTREL_CHECKLIST: Readiness = {
  score_pct: 58,
  gate_pct: 85,
  gate_met: false,
  blocking_open: 2,
  provisional: false,
  ready_for_credit: false,
  items: [
    // Deliberately out of section order: the screen orders by the taxonomy.
    item("valuation", "Valuation report", "Collateral and security", "missing", {
      deficiency: "Missing: valuation report for the property offered as collateral.",
    }),
    item("coi", "Certificate of incorporation", "Constitution and KYC", "satisfied", {
      blocking: true,
      document_ids: ["doc-coi"],
    }),
    item("board_resolution", "Board resolution", "Constitution and KYC", "insufficient", {
      blocking: true,
      deficiency: "Unsigned: the copy provided is not signed.",
      document_ids: ["doc-br"],
    }),
    item("kyc_directors", "KYC of directors", "Constitution and KYC", "missing", {
      blocking: true,
      deficiency: "Missing: 1 of 2 directors (Leela Varghese): PAN and address proof.",
    }),
    item("audited_fs", "Audited financial statements FY24, FY25", "Financials", "satisfied", {
      document_ids: ["doc-bs"],
    }),
    item("provisional_fs", "Provisional financial statements FY26", "Financials", "insufficient", {
      deficiency: "Incomplete: balance sheet pages absent.",
    }),
    item("gst_returns", "GST returns (12 months)", "Banking and operations", "insufficient", {
      deficiency: "Period gap: April to July 2025 absent.",
      document_ids: ["doc-gst"],
    }),
    item("stock_statement", "Stock statement", "Banking and operations", "insufficient", {
      deficiency: "Outdated: dated 31 Jan 2026; permitted age 60 days from 20 Sep 2026.",
    }),
    item("bank_statements", "Bank statements (12 months)", "Banking and operations", "in_review", {
      document_ids: ["doc-bank"],
    }),
  ],
};

export const SAFFRON_CHECKLIST: Readiness = {
  score_pct: 100,
  gate_pct: 85,
  gate_met: true,
  blocking_open: 0,
  provisional: false,
  ready_for_credit: true,
  items: KESTREL_CHECKLIST.items.map((i) => ({ ...i, status: "satisfied", deficiency: null })),
};

export const ORIEL_CHECKLIST: Readiness = {
  score_pct: 0,
  gate_pct: 85,
  gate_met: false,
  blocking_open: 1,
  provisional: true,
  ready_for_credit: false,
  items: [
    item("kyc_proprietor", "KYC of the proprietor", "Constitution and KYC", "missing", {
      blocking: true,
      deficiency: "Missing: PAN and address proof of the proprietor.",
    }),
  ],
};

// --- Pre-login query list (F-14) ---

function query(
  id: string,
  group: QueryItem["group"],
  text: string,
  extra: Partial<QueryItem> = {},
): QueryItem {
  return {
    id,
    case_id: KESTREL,
    group,
    text,
    source_kind: "checklist",
    source_ref: id,
    resolved: false,
    evidence: [],
    ...extra,
  };
}

export const KESTREL_QUERIES: QueryItem[] = [
  query("q1", "documents_needed", "KYC of Leela Varghese: PAN and address proof."),
  query("q2", "documents_needed", "Valuation report for the property offered as collateral."),
  query("q3", "documents_needed", "GST returns (GSTR-3B) for April to July 2025."),
  query("q4", "documents_to_redo", "Board resolution: the copy provided is not signed."),
  query(
    "q5",
    "documents_to_redo",
    "Stock statement dated within the last 60 days (latest is 31 Jan 2026).",
  ),
  query(
    "q6",
    "documents_to_redo",
    "ITR acknowledgement FY25: the photo is blurred; please re-scan.",
    {
      source_kind: "quality",
      resolved: true,
    },
  ),
  query(
    "q7",
    "clarifications",
    "Bank statements show a monthly EMI of INR 1,45,000 to a lender not in the declaration of existing facilities. Please explain.",
    {
      source_kind: "finding",
      evidence: [{ document_id: "doc-bank", page: 7, bbox: [0.1, 0.4, 0.6, 0.45] }],
    },
  ),
];

// --- Files and documents (F-05, F-07 to F-10) ---

function file(
  id: string,
  original_name: string,
  status: FileRecord["status"],
  extra: Partial<FileRecord> = {},
): FileRecord {
  return {
    id,
    case_id: KESTREL,
    sha256: `${id}-sha`,
    original_name,
    archive_path: null,
    content_type: "application/pdf",
    size_bytes: 245_000,
    channel: "upload",
    uploaded_by: "arjun-deshpande",
    uploaded_at: "2026-09-21T09:00:00Z",
    status,
    reason: null,
    duplicate_of: null,
    label_hint: null,
    ...extra,
  };
}

export const ZIP_FILES: FileRecord[] = [
  file("f-pan", "director1_pan.jpg", "registered", {
    archive_path: "case-file.zip/KYC/director1_pan.jpg",
    content_type: "image/jpeg",
  }),
  file("f-bs", "bank stmt apr-mar.pdf", "registered", {
    archive_path: "case-file.zip/bank stmt apr-mar.pdf",
    label_hint: "bank statement",
  }),
  file("f-merged", "merged_docs.pdf", "registered", {
    archive_path: "case-file.zip/merged_docs.pdf",
  }),
  file("f-thumbs", "Thumbs.db", "ignored", {
    archive_path: "case-file.zip/Thumbs.db",
    reason: "System file",
    content_type: "application/octet-stream",
  }),
];

export const LOOSE_FILES: FileRecord[] = [
  file("f-dup", "bank stmt apr-mar.pdf", "duplicate", { duplicate_of: "f-bs" }),
  file("f-numbers", "statement.numbers", "rejected", {
    reason: "Unsupported format",
    content_type: "application/octet-stream",
  }),
];

function doc(
  id: string,
  file_id: string,
  from: number,
  to: number,
  types: string[],
  status: LogicalDocument["status"],
  extra: Partial<LogicalDocument> = {},
): LogicalDocument {
  const pages = Array.from({ length: to - from + 1 }, (_, i) => ({
    n: from + i,
    route: "text" as const,
    grade: extra.grade ?? ("A" as const),
    reasons: [],
    ocr_confidence: null,
  }));
  return {
    id,
    case_id: KESTREL,
    file_id,
    page_from: from,
    page_to: to,
    pages,
    grade: "A",
    classification: types.length
      ? {
          types,
          confidence: 0.96,
          exit_tier: "signals",
          signals: ["header phrase", "identifier pattern"],
          candidates: [],
        }
      : null,
    status,
    instance_key: null,
    party_id: null,
    version_of: null,
    duplicate_of: null,
    label_mismatch: false,
    config_version: "v3",
    ...extra,
  };
}

export const DOCUMENTS: LogicalDocument[] = [
  doc("doc-pan", "f-pan", 1, 1, ["pan_individual"], "accepted", { party_id: "p-kabir" }),
  doc("doc-bs", "f-bs", 1, 6, ["balance_sheet"], "extracted", { label_mismatch: true }),
  doc("doc-gst", "f-merged", 1, 2, ["gst_registration"], "classified"),
  doc("doc-bank", "f-merged", 3, 9, ["bank_statement"], "in_review", {
    instance_key: "account ·1234",
    grade: "B",
  }),
  doc("doc-unc", "f-merged", 10, 10, [], "unclassified", {
    classification: {
      types: [],
      confidence: 0.41,
      exit_tier: "none",
      signals: [],
      candidates: [
        { type_id: "utility_bill", confidence: 0.41 },
        { type_id: "itr_ack", confidence: 0.22 },
        { type_id: "bank_statement", confidence: 0.1 },
      ],
    },
  }),
];

type DocumentType = DocumentTypes["types"][number];

function docType(id: string, name: string, group: DocumentType["group"]): DocumentType {
  return {
    id,
    name,
    group,
    description: `${name}.`,
    instance_key: "none",
    partner_output: false,
    personal: group === "kyc",
    satisfies: [],
  };
}

export const DOCUMENT_TYPES: DocumentTypes = {
  types: [
    docType("pan_individual", "PAN (individual)", "kyc"),
    docType("gst_registration", "GST registration", "registration"),
    docType("bank_statement", "Bank statement", "banking"),
    docType("balance_sheet", "Balance sheet", "financials"),
    docType("board_resolution", "Board resolution", "constitution"),
    docType("itr_ack", "ITR acknowledgement", "tax"),
    docType("utility_bill", "Utility bill", "other_known"),
  ],
};

/** The documents the cross-verification board's evidence points to beyond the case's own
 * fixture documents, each with its configured type (config/document_types.yaml). The board's
 * screen tests add them, so that every source and every row opens its own document. */
export const XV_DOCUMENTS: LogicalDocument[] = [
  doc("doc-cpan", "f-cpan", 1, 1, ["company_pan"], "accepted"),
  doc("doc-gstr3b", "f-gstr3b", 1, 2, ["gstr_3b"], "accepted"),
  doc("doc-itr", "f-itr", 1, 3, ["income_tax_return"], "accepted"),
  doc("doc-decl", "f-decl", 1, 1, ["existing_facilities_declaration"], "accepted"),
  doc("doc-sanction", "f-sanction", 1, 2, ["sanction_letter"], "accepted"),
  doc("doc-bureau", "f-bureau", 1, 4, ["commercial_bureau_report"], "accepted"),
  doc("doc-coi", "f-coi", 1, 1, ["certificate_of_incorporation"], "accepted"),
  doc("doc-moa", "f-moa", 1, 12, ["memorandum_articles_of_association"], "accepted"),
];

/** The published document types, with those of the board's documents. */
export const XV_DOCUMENT_TYPES: DocumentTypes = {
  types: [
    ...DOCUMENT_TYPES.types,
    docType("company_pan", "Company PAN", "registration"),
    docType("gstr_3b", "GSTR-3B", "tax"),
    docType("income_tax_return", "Income tax return", "tax"),
    docType("existing_facilities_declaration", "Declaration of existing facilities", "banking"),
    docType("sanction_letter", "Sanction letter", "banking"),
    docType("commercial_bureau_report", "Commercial bureau report", "bureau"),
    docType("certificate_of_incorporation", "Certificate of incorporation", "constitution"),
    docType(
      "memorandum_articles_of_association",
      "Memorandum and articles of association",
      "constitution",
    ),
  ],
};

// --- Extracted fields (F-15 to F-17) ---

function fv(
  id: string,
  document_id: string,
  field: string,
  value: FieldValue["value"],
  page: number,
  extra: Partial<FieldValue> = {},
): FieldValue {
  return {
    id,
    case_id: KESTREL,
    document_id,
    field,
    value,
    raw: typeof value === "number" ? value.toLocaleString("en-IN") : String(value),
    evidence: { document_id, page, bbox: [0.12, 0.3, 0.48, 0.34] },
    method: "deterministic",
    confidence: 0.97,
    confidence_components: { classification: 0.96, page_grade: 1, ocr_trust: 0.98, validation: 1 },
    status: "accepted",
    missing_reason: null,
    corrected_value: null,
    ...extra,
  };
}

export const FIELDS: FieldValue[] = [
  fv("fv-name", "doc-pan", "name", "Kabir Rao", 1),
  fv("fv-pan", "doc-pan", "pan", "ABCPR1234F", 1),
  fv("fv-credits-jun", "doc-bank", "monthly[2].credits", 4_102_300, 7, {
    confidence: 0.62,
    status: "in_review",
    method: "model",
  }),
  fv("fv-credits-may", "doc-bank", "monthly[1].credits", 3_895_000, 6, {
    status: "corrected",
    corrected_value: 3_985_000,
  }),
  fv("fv-networth", "doc-bs", "net_worth", 42_500_000, 4),
  fv("fv-pat", "doc-bs", "pat", null, 3, {
    status: "missing",
    missing_reason: "Not printed on the statement",
    evidence: null,
    confidence: null,
  }),
];

export const PARTIES: Party[] = [
  {
    id: "p-borrower",
    case_id: KESTREL,
    name: "Kestrel Polymers Pvt Ltd",
    role: "borrower",
    pan: "AAACK1234K",
    source: "message",
    kyc_document_ids: [],
  },
  {
    id: "p-kabir",
    case_id: KESTREL,
    name: "Kabir Rao",
    role: "director",
    pan: "ABCPR1234F",
    din: "01234567",
    source: "document:doc-pan:p1",
    kyc_document_ids: ["doc-pan"],
  },
  {
    id: "p-leela",
    case_id: KESTREL,
    name: "Leela Varghese",
    role: "director",
    source: "message",
    kyc_document_ids: [],
  },
];

// --- Review queue (F-17) ---

export const REVIEW: ReviewItem[] = [
  {
    id: "r-type",
    case_id: KESTREL,
    kind: "type",
    ref: "document:doc-unc",
    summary: "merged_docs.pdf p10: no type fits (utility bill 0.41)",
    status: "open",
    escalated: false,
    created_at: "2026-09-21T09:05:00Z",
  },
  {
    id: "r-field",
    case_id: KESTREL,
    kind: "field",
    ref: "field:fv-credits-jun",
    summary: "Bank statement ·1234 Jun 25: credits (0.62)",
    status: "open",
    escalated: false,
    created_at: "2026-09-21T09:06:00Z",
  },
  {
    id: "r-corrected",
    case_id: KESTREL,
    kind: "field",
    ref: "field:fv-credits-may",
    summary: "Bank statement ·1234 May 25: credits (0.58)",
    status: "decided",
    decision: "correct",
    reason: "Misread 8 as 9",
    decided_by: "Ananya Krishnan",
    decided_at: "2026-09-21T10:00:00Z",
    escalated: false,
    created_at: "2026-09-21T09:06:00Z",
  },
];

// --- Case proposal (F-04) ---

export const MESSAGE = [
  "From: RM desk, Mumbai hub",
  "Subject: CC renewal",
  "",
  "Client Kestrel Polymers Pvt Ltd wants CC of 50L and a TL, PAN AAACK1234K.",
  "Constitution is Pvt Ltd or maybe LLP, to confirm.",
  "Turnover approx 3 cr. Directors Kabir Rao and Leela Varghese.",
].join("\n");

/** The span of the n-th occurrence of `needle` in the message. */
export function spanOf(needle: string, nth = 0): Span {
  let at = -1;
  for (let i = 0; i <= nth; i++) at = MESSAGE.indexOf(needle, at + 1);
  if (at < 0) throw new Error(`fixture: "${needle}" not in message`);
  return { start: at, end: at + needle.length };
}

export function proposal(duplicates: CaseSummary[] = []): CaseProposal {
  return {
    text_sha256: "c0ffee",
    duplicates,
    stripped: [{ kind: "header", span: { start: 0, end: MESSAGE.indexOf("\n\n") } }],
    missing_minimum: [],
    fields: {
      borrower: {
        value: "Kestrel Polymers Pvt Ltd",
        status: "found",
        span: spanOf("Kestrel Polymers Pvt Ltd"),
      },
      constitution: {
        value: null,
        status: "unclear",
        note: "Two constitutions are mentioned.",
        candidates: [
          { value: "Private limited", span: spanOf("Pvt Ltd", 1) },
          { value: "Partnership", span: spanOf("LLP") },
        ],
      },
      facilities: {
        value: "Cash credit, Term loan",
        status: "found",
        span: spanOf("CC of 50L and a TL"),
      },
      amount_inr: { value: "5000000", status: "found", span: spanOf("50L") },
      pan: { value: "AAACK1234K", status: "found", span: spanOf("AAACK1234K") },
      gstin: { value: null, status: "not_found" },
      declared_turnover_inr: {
        value: null,
        status: "unclear",
        note: "3 cr or 30 cr?",
        candidates: [
          { value: "30000000", span: spanOf("3 cr") },
          { value: "300000000", span: spanOf("3 cr") },
        ],
      },
      promoters: {
        value: "Kabir Rao, Leela Varghese",
        status: "found",
        span: spanOf("Kabir Rao and Leela Varghese"),
      },
    },
  };
}

/** A 1x1 PNG, served as every rendered page. */
export const PAGE_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
  "base64",
);

// --- Cross-checks and aligned facts (F-18, F-19) ---
//
// Kestrel's cross-verification board as GET /api/cases/{id}/cross-verification returns it: the
// findings of the 18 enabled rules by area (identity, turnover, bank accounts, existing
// obligations); in each area its discrepancies ranked by credit impact (severity, then the size
// of the gap in rupees, findings without an amount after those with one, then the rules' order),
// then the checks that could not run, those that passed and those that did not apply. Seven
// discrepancies across the four areas: two blocking identity discrepancies, one escalated to the
// Credit Manager, one dismissed. The rules switched off in configuration (BR-01 to BR-04, TX-01,
// TX-02, FS-01, FS-02) give no finding. xvView assembles a board as engine/xv.py does; GET
// /findings answers the same findings (FINDINGS).

/** When the latest run was made, and when the mock records a decision. */
export const XV_RUN_AT = "2026-10-09T08:30:00+00:00";
export const XV_DECIDED_AT = "2026-10-09T09:45:00+00:00";

export const XV_RUN: XvRun = { id: "XR-000021-003", at: XV_RUN_AT, rules: 18, sources: 9 };

/** The enabled rules in their configured order, each with its area (config/crosschecks.yaml).
 * The board's areas follow the order in which they first appear here. */
export const XV_RULES: [string, FindingArea][] = [
  ["ID-01", "identity"],
  ["ID-02", "identity"],
  ["ID-03", "identity"],
  ["ID-04", "identity"],
  ["ID-05", "identity"],
  ["ID-06", "identity"],
  ["ID-07", "identity"],
  ["ID-08", "identity"],
  ["TO-01", "turnover"],
  ["TO-02", "turnover"],
  ["TO-03", "turnover"],
  ["TO-04", "turnover"],
  ["TO-05", "turnover"],
  ["BA-01", "accounts"],
  ["BA-02", "accounts"],
  ["OB-01", "obligations"],
  ["OB-02", "obligations"],
  ["OB-03", "obligations"],
];

const at = (document_id: string, page: number): Evidence[] => [{ document_id, page }];

/** One source a finding compared, as a column of its card. */
export function xvColumn(
  key: string,
  label: string,
  value: string | number | null,
  extra: Partial<SourceColumn> = {},
): SourceColumn {
  return {
    key,
    label,
    value,
    sources: [],
    provenance: ["borrower_supplied"],
    unit: "text",
    coverage: null,
    differs: false,
    relies_on_manual: false,
    awaiting_review: false,
    field_ids: [],
    evidence: [],
    row_columns: [],
    rows: [],
    ...extra,
  };
}

/** One row behind a column's value, with the page it was read from. */
export function xvRow(
  cells: EvidenceRow["cells"],
  evidence: Evidence[] = [],
  kind: EvidenceRow["kind"] = "row",
): EvidenceRow {
  return { cells, evidence, kind };
}

/** One side of a comparison, as the rule recorded it (F-19.3). */
export function xvSide(
  label: string,
  value: FindingSide["value"],
  evidence: Evidence[],
  extra: Partial<FindingSide> = {},
): FindingSide {
  return {
    label,
    value,
    evidence,
    sources: [],
    differs: false,
    relies_on_manual: false,
    awaiting_review: false,
    field_ids: [],
    ...extra,
  };
}

/** A key figure for an area's overview card, as a card builder writes it (engine/xv_cards):
 * what is compared, the figures side by side, a short note. xvFinding gives it the finding's id,
 * rule and outcome. */
export function xvLine(
  label: string,
  facts: XvFact[] = [],
  note: string | null = null,
): XvHighlight {
  return { finding_id: "", rule_id: "", outcome: "pass", label, facts, note };
}

/** One figure of a key figure: its source, its value and unit, and whether it differs. */
export function xvFact(
  label: string,
  value: string | number | null,
  unit: XvFact["unit"] = "text",
  differs = false,
): XvFact {
  return { label, value, unit, differs };
}

/** A finding of the latest run with the card fields the board shows. */
export function xvFinding(
  f: Pick<
    Finding,
    "id" | "rule_id" | "title" | "area" | "outcome" | "severity" | "blocking" | "explanation"
  > &
    Partial<Finding>,
): Finding {
  return {
    case_id: KESTREL,
    sides: [],
    detail: null,
    missing: [],
    scope: null,
    tolerance: null,
    config_version: "v3",
    run_id: XV_RUN.id,
    query: null,
    ref: null,
    finding_title: null,
    compares: f.title,
    policy_ref: null,
    columns: [],
    gaps: [],
    gap_tolerance: null,
    mismatch: null,
    reference: null,
    amount: null,
    request: null,
    ...f,
    highlights: (f.highlights ?? []).map((line) => ({
      ...line,
      finding_id: f.id,
      rule_id: f.rule_id,
      outcome: f.outcome,
    })),
  };
}

/** A finding with its review state, as the board lists it. */
export function xvItem(finding: Finding, extra: Partial<XvItem> = {}): XvItem {
  return {
    finding,
    rank: null,
    review_item_id: null,
    decision: null,
    escalation: null,
    adjudicated: false,
    in_query_list: false,
    ...extra,
  };
}

/** A person's decision on a discrepancy, with its comment. */
export function xvDecision(
  decision: XvDecision["decision"],
  comment: string,
  when: string,
  by: SessionUser = ANALYST,
): XvDecision {
  return { decision, comment, by: by.id, by_name: by.name, at: when };
}

/** The open discrepancies by severity and how many are decided, as engine/xv.py counts them. */
export function xvCounts(items: XvItem[]): XvCounts {
  const discrepancies = items.filter((i) => i.finding.outcome === "fail");
  const open = discrepancies.filter((i) => !i.adjudicated);
  const of = (severity: Finding["severity"]) =>
    open.filter((i) => i.finding.severity === severity).length;
  return {
    serious: of("serious"),
    moderate: of("moderate"),
    mild: of("mild"),
    adjudicated: discrepancies.length - open.length,
    total: discrepancies.length,
    blocking_open: open.filter((i) => i.finding.blocking).length,
  };
}

const SEVERITY_ORDER: Record<Finding["severity"], number> = { serious: 0, moderate: 1, mild: 2 };
const OUTCOME_ORDER: Record<Finding["outcome"], number> = {
  fail: 0,
  incomplete: 1,
  pass: 2,
  not_applicable: 3,
};

/** The key figures on an area's card. */
const XV_HIGHLIGHTS = 3;

/** One area's overview card, counted from its discrepancies (ranked) and its other findings, as
 * engine/xv.py `_area` counts it; its key figures picked as `_area` picks them: the open
 * discrepancies' lines by rank, then the decided ones', then those of the checks that could not
 * run and of the passed ones (`rest` is in that order), the first three. */
function xvArea(area: FindingArea, rules: number, ranked: XvItem[], rest: XvItem[]): XvArea {
  const open = ranked.filter((i) => !i.adjudicated);
  const outcomes = rest.map((i) => i.finding.outcome);
  const sources = [
    ...open,
    ...ranked.filter((i) => i.adjudicated),
    ...rest.filter((i) => i.finding.outcome !== "not_applicable"),
  ];
  const count = (outcome: Finding["outcome"]) => outcomes.filter((o) => o === outcome).length;
  const of = (severity: Finding["severity"]) =>
    open.filter((i) => i.finding.severity === severity).length;
  return {
    area,
    rules,
    discrepancies: ranked.length,
    open: open.length,
    serious: of("serious"),
    moderate: of("moderate"),
    mild: of("mild"),
    blocking_open: open.filter((i) => i.finding.blocking).length,
    adjudicated: ranked.length - open.length,
    incomplete: count("incomplete"),
    passed: count("pass"),
    not_applicable: count("not_applicable"),
    top_finding_id: (open[0] ?? ranked[0])?.finding.id ?? null,
    highlights: sources.flatMap((i) => i.finding.highlights ?? []).slice(0, XV_HIGHLIGHTS),
    status:
      open.length > 0
        ? "open"
        : ranked.length > 0
          ? "decided"
          : outcomes.includes("incomplete")
            ? "incomplete"
            : "clear",
  };
}

/**
 * The board of these items, assembled as engine/xv.py `view` does: only the enabled rules'
 * findings (`rules`, in configured order), by area in the order the areas first appear; within
 * an area its discrepancies by credit impact, each given its rank within the area, then the
 * checks that could not run, those that passed and those that did not apply. The counts, the
 * areas, the first open blocking discrepancy and the top one are derived from the items, so a
 * decision recorded on an item shows on the next read. Each item's `rank` is set in place.
 */
export function xvView(
  caseId: string,
  items: XvItem[],
  run: XvRun | null = XV_RUN,
  rules: [string, FindingArea][] = XV_RULES,
): CrossVerificationView {
  const order = new Map(rules.map(([id], i) => [id, i]));
  const areaOf = new Map(rules);
  const shown = items.filter((i) => order.has(i.finding.rule_id));
  const ruleOrder = (i: XvItem) => order.get(i.finding.rule_id) ?? 999;
  const scope = (a: XvItem, b: XvItem) =>
    (a.finding.scope ?? "").localeCompare(b.finding.scope ?? "");
  // Credit impact: severity, then the gap in rupees (none after any), then the rules' order.
  const failed = shown
    .filter((i) => i.finding.outcome === "fail")
    .sort((a, b) => {
      const x = a.finding;
      const y = b.finding;
      return (
        SEVERITY_ORDER[x.severity] - SEVERITY_ORDER[y.severity] ||
        Number(x.amount == null) - Number(y.amount == null) ||
        (y.amount ?? 0) - (x.amount ?? 0) ||
        ruleOrder(a) - ruleOrder(b) ||
        scope(a, b)
      );
    });
  const others = shown
    .filter((i) => i.finding.outcome !== "fail")
    .sort(
      (a, b) =>
        OUTCOME_ORDER[a.finding.outcome] - OUTCOME_ORDER[b.finding.outcome] ||
        ruleOrder(a) - ruleOrder(b) ||
        scope(a, b),
    );
  const ordered: XvItem[] = [];
  const areas: XvArea[] = [];
  for (const area of new Set(rules.map(([, a]) => a))) {
    const inArea = (i: XvItem) => areaOf.get(i.finding.rule_id) === area;
    const ranked = failed.filter(inArea);
    ranked.forEach((item, n) => {
      item.rank = n + 1;
    });
    const rest = others.filter(inArea);
    ordered.push(...ranked, ...rest);
    areas.push(xvArea(area, rules.filter(([, a]) => a === area).length, ranked, rest));
  }
  const open = failed.filter((i) => !i.adjudicated);
  const counts = xvCounts(failed);
  return {
    case_id: caseId,
    run,
    areas,
    items: ordered,
    counts,
    blocked: counts.blocking_open > 0,
    first_blocking: open.find((i) => i.finding.blocking)?.finding.id ?? null,
    // The first card on the board: the top of the first area with an open discrepancy, else with any.
    top_finding_id:
      areas.find((a) => a.open > 0)?.top_finding_id ??
      areas.find((a) => a.top_finding_id)?.top_finding_id ??
      null,
  };
}

const ACCOUNT = "Lotuscrest Bank ·1234";
const CIN = "U28999MH2015PTC123456";
const CIN_MOA = "U28999MH2015PTC123465";

// GST returns against the bank credits over the months both cover, Aug 2025 to Mar 2026 (the
// April to July 2025 returns are not on file): GST is INR 2.39 cr short of the cleansed credits.
// Each month: its return's filing date, outward supplies and page; the account's credits, the
// credits excluded and the statement page.
const WINDOW = (
  [
    ["Aug 2025", "20 Sep 2025", 17_800_000, 1, 21_200_000, 0, 5],
    ["Sep 2025", "20 Oct 2025", 19_200_000, 1, 23_100_000, 2_000_000, 5],
    ["Oct 2025", "20 Nov 2025", 18_100_000, 1, 22_000_000, 0, 6],
    ["Nov 2025", "19 Dec 2025", 18_600_000, 1, 21_700_000, 0, 7],
    ["Dec 2025", "24 Jan 2026", 19_000_000, 2, 22_600_000, 0, 7],
    ["Jan 2026", "20 Feb 2026", 17_900_000, 2, 21_400_000, 1_500_000, 8],
    ["Feb 2026", "20 Mar 2026", 18_800_000, 2, 22_300_000, 0, 8],
    ["Mar 2026", "20 Apr 2026", 18_600_000, 2, 21_100_000, 0, 9],
  ] as const
).map(([label, filed, gst, gstPage, credits, excluded, bankPage]) => ({
  label,
  filed,
  gst,
  gstPage,
  credits,
  excluded,
  bankPage,
}));

const OB2 = xvFinding({
  id: "fnd-ob2",
  rule_id: "OB-02",
  title: "Instalments in bank statements go to declared lenders",
  finding_title: "Instalments to a lender that was not declared",
  area: "obligations",
  outcome: "fail",
  severity: "serious",
  blocking: false,
  ref: "XV-000021-01",
  explanation:
    "Regular debits to lender(s) not declared: ASHWOOD FINSERV (₹1,45,000 a month in 6 months, Lotuscrest Bank ·1234).",
  sides: [
    xvSide("Instalments in bank statements", "ASHWOOD FINSERV (₹1,45,000 × 6)", at("doc-bank", 7), {
      sources: ["bank_statement"],
      differs: true,
    }),
    xvSide("Declaration of existing facilities", "Tidewater Finance", at("doc-decl", 1), {
      sources: ["existing_facilities_declaration"],
    }),
  ],
  columns: [
    xvColumn(
      "instalments",
      "Instalments in bank statements",
      "ASHWOOD FINSERV, Tidewater Finance",
      {
        sources: ["bank_statement"],
        differs: true,
        coverage: `Apr 2025 to Mar 2026 · ${ACCOUNT}`,
        evidence: at("doc-bank", 7),
        row_columns: ["Lender", "Account", "Monthly instalment", "Months"],
        rows: [
          xvRow(["ASHWOOD FINSERV", ACCOUNT, 145_000, "Apr 2025 to Sep 2025"], at("doc-bank", 7)),
          xvRow(["Tidewater Finance", ACCOUNT, 92_000, "Apr 2025 to Mar 2026"], at("doc-bank", 4)),
        ],
      },
    ),
    xvColumn("declaration", "Declaration of existing facilities", "Tidewater Finance", {
      sources: ["existing_facilities_declaration"],
      provenance: ["declared"],
      coverage: "Page 1",
      evidence: at("doc-decl", 1),
      row_columns: ["Lender", "Facility", "EMI"],
      rows: [xvRow(["Tidewater Finance", "Term loan", 92_000], at("doc-decl", 1))],
    }),
  ],
  gaps: [
    {
      label: "Annual outflow to ASHWOOD FINSERV (INR 1.45 lakh a month), not declared",
      amount: 1_740_000,
      pct: null,
      base: null,
      legs: "ASHWOOD FINSERV",
      breached: true,
    },
  ],
  amount: 1_740_000,
  mismatch:
    "Instalments to ASHWOOD FINSERV appear in the bank statements but no declaration names them.",
  highlights: [
    xvLine("ASHWOOD FINSERV", [], "INR 1.45 lakh a month in the bank statements, not declared"),
  ],
  detail: {
    columns: ["Account", "Monthly instalment", "Months", "Declared"],
    rows: [
      {
        label: "ASHWOOD FINSERV",
        cells: [ACCOUNT, 145_000, 6, "—"],
        flagged: true,
        flagged_cells: [],
      },
      {
        label: "Tidewater Finance",
        cells: [ACCOUNT, 92_000, 12, "✓"],
        flagged: false,
        flagged_cells: [],
      },
    ],
  },
  query:
    "Please give details of the facility with ASHWOOD FINSERV: the amount, the outstanding and the instalment.",
});

const TIDEWATER = (sanctioned: number, ...more: number[]) => [
  "Tidewater Finance",
  "Term loan",
  sanctioned,
  ...more,
];

const OB1 = xvFinding({
  id: "fnd-ob1",
  rule_id: "OB-01",
  title: "Declared facilities reconcile with sanction letters and the bureau",
  finding_title: "Existing facilities do not reconcile",
  area: "obligations",
  outcome: "fail",
  severity: "serious",
  blocking: false,
  ref: "XV-000021-02",
  tolerance: "5%",
  explanation:
    "The existing facilities do not reconcile: Tidewater Finance: sanctioned amounts differ: declared INR 40.00 lakh, sanction letter INR 55.00 lakh, bureau INR 55.00 lakh; Lotuscrest Bank: not declared.",
  sides: [
    xvSide(
      "Declaration of existing facilities",
      "Tidewater Finance INR 40.00 lakh",
      at("doc-decl", 1),
      {
        sources: ["existing_facilities_declaration"],
        differs: true,
      },
    ),
    xvSide("Sanction letters", "Tidewater Finance INR 55.00 lakh", at("doc-sanction", 1), {
      sources: ["sanction_letter"],
    }),
    xvSide(
      "Commercial bureau report",
      "Tidewater Finance INR 55.00 lakh; Lotuscrest Bank INR 12.00 lakh",
      at("doc-bureau", 2),
      { sources: ["commercial_bureau_report"] },
    ),
  ],
  columns: [
    xvColumn(
      "declaration",
      "Declaration of existing facilities",
      "Tidewater Finance INR 40.00 lakh",
      {
        sources: ["existing_facilities_declaration"],
        provenance: ["declared"],
        differs: true,
        coverage: "Page 1",
        evidence: at("doc-decl", 1),
        row_columns: ["Lender", "Facility", "Sanctioned", "EMI"],
        rows: [xvRow(TIDEWATER(4_000_000, 92_000), at("doc-decl", 1))],
      },
    ),
    xvColumn("sanction", "Sanction letters", "Tidewater Finance INR 55.00 lakh", {
      sources: ["sanction_letter"],
      coverage: "1 letter · Page 1",
      evidence: at("doc-sanction", 1),
      row_columns: ["Lender", "Facility", "Sanctioned", "EMI"],
      rows: [xvRow(TIDEWATER(5_500_000, 92_000), at("doc-sanction", 1))],
    }),
    xvColumn(
      "bureau",
      "Commercial bureau report",
      "Tidewater Finance INR 55.00 lakh; Lotuscrest Bank INR 12.00 lakh",
      {
        sources: ["commercial_bureau_report"],
        provenance: ["independent"],
        coverage: "Pages 2 to 3",
        evidence: at("doc-bureau", 2),
        row_columns: ["Lender", "Facility", "Sanctioned", "Outstanding", "Overdue"],
        rows: [
          xvRow(TIDEWATER(5_500_000, 3_850_000, 0), at("doc-bureau", 2)),
          xvRow(["Lotuscrest Bank", "Overdraft", 1_200_000, 800_000, 0], at("doc-bureau", 3)),
        ],
      },
    ),
  ],
  gaps: [
    {
      label: "Tidewater Finance: declared against sanction letter",
      amount: 1_500_000,
      pct: 27.3,
      base: "sanction letter",
      legs: "Tidewater Finance declared against sanction letter",
      breached: true,
    },
    {
      label: "Tidewater Finance: declared against bureau",
      amount: 1_500_000,
      pct: 27.3,
      base: "bureau",
      legs: "Tidewater Finance declared against bureau",
      breached: true,
    },
    {
      label: "Lotuscrest Bank: not declared",
      amount: 1_200_000,
      pct: null,
      base: null,
      legs: "Lotuscrest Bank",
      breached: true,
    },
  ],
  gap_tolerance: "5%",
  amount: 1_500_000,
  detail: {
    columns: ["Declared", "Sanction letter", "Bureau", "Outstanding (bureau)"],
    rows: [
      {
        label: "Tidewater Finance",
        cells: [4_000_000, 5_500_000, 5_500_000, 3_850_000],
        flagged: true,
        flagged_cells: [],
      },
      {
        label: "Lotuscrest Bank",
        cells: ["—", "—", 1_200_000, 800_000],
        flagged: true,
        flagged_cells: [],
      },
    ],
  },
  query:
    "Please reconcile the existing facilities (Tidewater Finance and Lotuscrest Bank): give each facility's lender, sanctioned amount and outstanding, with its sanction letter.",
  highlights: [
    xvLine(
      "Tidewater Finance",
      [
        xvFact("Declared", 4_000_000, "inr", true),
        xvFact("Sanction letter", 5_500_000, "inr"),
        xvFact("Bureau", 5_500_000, "inr"),
      ],
      "27.3% apart · tolerance 5%",
    ),
    xvLine("Lotuscrest Bank", [], "not declared · INR 12.00 lakh in the bureau report"),
  ],
});

// More than four documents state the PAN: one column per group of documents agreeing, each
// document a row of its own.
const PAN = "AAACK1234K";
const PAN_BUREAU = "AAACK1243K";
const PAN_GROUP =
  "Company PAN, GSTR-3B (PAN within the GSTIN), Income tax return, Declaration of existing facilities, Sourcing message";

const ID1 = xvFinding({
  id: "fnd-id1",
  rule_id: "ID-01",
  title: "Entity PAN consistent across documents",
  finding_title: "Entity PAN differs between documents",
  area: "identity",
  outcome: "fail",
  severity: "serious",
  blocking: true,
  ref: "XV-000021-03",
  policy_ref: "Credit policy 3.2: identity of the borrower",
  explanation: `The entity PAN differs between documents: ${PAN} (${PAN_GROUP}) · ${PAN_BUREAU} (Commercial bureau report).`,
  sides: [
    xvSide(PAN_GROUP, PAN, at("doc-cpan", 1), {
      sources: [
        "company_pan",
        "gstr_3b",
        "income_tax_return",
        "existing_facilities_declaration",
        "application_message",
      ],
    }),
    xvSide("Commercial bureau report", PAN_BUREAU, at("doc-bureau", 1), {
      sources: ["commercial_bureau_report"],
      differs: true,
    }),
  ],
  columns: [
    xvColumn("group-0", PAN_GROUP, PAN, {
      sources: [
        "company_pan",
        "gstr_3b",
        "income_tax_return",
        "existing_facilities_declaration",
        "application_message",
      ],
      provenance: ["borrower_supplied", "declared"],
      coverage: "4 documents and the sourcing message",
      evidence: [
        ...at("doc-cpan", 1),
        ...at("doc-gstr3b", 1),
        ...at("doc-itr", 1),
        ...at("doc-decl", 1),
      ],
      row_columns: ["Document", "PAN"],
      rows: [
        xvRow(["Company PAN", PAN], at("doc-cpan", 1)),
        xvRow(["GSTR-3B (PAN within the GSTIN)", PAN], at("doc-gstr3b", 1)),
        xvRow(["Income tax return", PAN], at("doc-itr", 1)),
        xvRow(["Declaration of existing facilities", PAN], at("doc-decl", 1)),
        xvRow(["Sourcing message", PAN]),
      ],
    }),
    xvColumn("group-1", "Commercial bureau report", PAN_BUREAU, {
      sources: ["commercial_bureau_report"],
      provenance: ["independent"],
      differs: true,
      coverage: "Page 1",
      evidence: at("doc-bureau", 1),
      row_columns: ["Document", "PAN"],
      rows: [xvRow(["Commercial bureau report", PAN_BUREAU], at("doc-bureau", 1))],
    }),
  ],
  reference: PAN,
  mismatch: `Commercial bureau report gives ${PAN_BUREAU}; the other 5 sources give ${PAN}.`,
  highlights: [
    xvLine("PAN", [
      xvFact("4 documents and the sourcing message", PAN),
      xvFact("Commercial bureau report", PAN_BUREAU, "text", true),
    ]),
  ],
  query: `Please confirm the company's PAN; the documents show ${PAN} (${PAN_GROUP}) · ${PAN_BUREAU} (Commercial bureau report).`,
});

const ID5 = xvFinding({
  id: "fnd-id5",
  rule_id: "ID-05",
  title: "CIN consistent across documents",
  finding_title: "CIN differs between documents",
  area: "identity",
  outcome: "fail",
  severity: "serious",
  blocking: true,
  ref: "XV-000021-04",
  explanation: `The CIN differs between documents: ${CIN} (Certificate of incorporation, Commercial bureau report, Declaration of existing facilities) · ${CIN_MOA} (Memorandum and articles of association).`,
  sides: [
    xvSide(
      "Certificate of incorporation, Commercial bureau report, Declaration of existing facilities",
      CIN,
      at("doc-coi", 1),
      {
        sources: [
          "certificate_of_incorporation",
          "commercial_bureau_report",
          "existing_facilities_declaration",
        ],
      },
    ),
    xvSide("Memorandum and articles of association", CIN_MOA, at("doc-moa", 2), {
      sources: ["memorandum_articles_of_association"],
      differs: true,
    }),
  ],
  columns: [
    xvColumn("statement-0", "Certificate of incorporation", CIN, {
      sources: ["certificate_of_incorporation"],
      coverage: "Page 1",
      evidence: at("doc-coi", 1),
      row_columns: ["Field", "Value"],
      rows: [xvRow(["CIN", CIN], at("doc-coi", 1))],
    }),
    xvColumn("statement-1", "Memorandum and articles of association", CIN_MOA, {
      sources: ["memorandum_articles_of_association"],
      differs: true,
      coverage: "Page 2",
      evidence: at("doc-moa", 2),
      row_columns: ["Field", "Value"],
      rows: [xvRow(["CIN", CIN_MOA], at("doc-moa", 2))],
    }),
    xvColumn("statement-2", "Commercial bureau report", CIN, {
      sources: ["commercial_bureau_report"],
      provenance: ["independent"],
      coverage: "Page 1",
      evidence: at("doc-bureau", 1),
      row_columns: ["Field", "Value"],
      rows: [xvRow(["CIN", CIN], at("doc-bureau", 1))],
    }),
    xvColumn("statement-3", "Declaration of existing facilities", CIN, {
      sources: ["existing_facilities_declaration"],
      provenance: ["declared"],
      coverage: "Page 1",
      evidence: at("doc-decl", 1),
      row_columns: ["Field", "Value"],
      rows: [xvRow(["CIN", CIN], at("doc-decl", 1))],
    }),
  ],
  reference: CIN,
  mismatch: `Memorandum and articles of association gives ${CIN_MOA}; the other 3 sources give ${CIN}.`,
  highlights: [
    xvLine("CIN", [
      xvFact("3 documents", CIN),
      xvFact("Memorandum and articles of association", CIN_MOA, "text", true),
    ]),
  ],
  query: `Please confirm the company's CIN; the documents show ${CIN} (Certificate of incorporation, Commercial bureau report, Declaration of existing facilities) · ${CIN_MOA} (Memorandum and articles of association).`,
});

const TO5 = xvFinding({
  id: "fnd-to5",
  rule_id: "TO-05",
  title: "GST outward supplies against bank credits, months both cover · Aug 2025 to Mar 2026",
  compares: "GST outward supplies against bank credits, months both cover",
  finding_title: "GST and bank credits diverge over the months both cover",
  area: "turnover",
  outcome: "fail",
  severity: "moderate",
  blocking: false,
  scope: "Aug 2025 to Mar 2026",
  ref: "XV-000021-05",
  tolerance: "10%",
  explanation:
    "Aug 2025 to Mar 2026: GST outward supplies INR 14.80 cr against business credits INR 17.19 cr, a variance of 13.9% (tolerance 10%).",
  sides: [
    xvSide("GST outward supplies (8 returns)", 148_000_000, at("doc-gstr3b", 1), {
      sources: ["gstr_3b"],
      differs: true,
    }),
    xvSide("Business credits in bank statements", 171_900_000, at("doc-bank", 5), {
      sources: ["bank_statement"],
      differs: true,
    }),
  ],
  columns: [
    xvColumn("gst", "GST outward supplies (GSTR-3B)", 148_000_000, {
      sources: ["gstr_3b"],
      unit: "inr",
      differs: true,
      coverage: "Aug 2025 to Mar 2026 · 8 returns",
      evidence: [...at("doc-gstr3b", 1), ...at("doc-gstr3b", 2)],
      row_columns: ["Period", "Filed", "3.1(a)+(b)+(c) outward supplies"],
      rows: [
        ...WINDOW.map((m) => xvRow([m.label, m.filed, m.gst], at("doc-gstr3b", m.gstPage))),
        xvRow(["Aggregate Aug 2025 to Mar 2026", "", 148_000_000], [], "total"),
      ],
    }),
    xvColumn("bank", "Business credits in bank statements", 171_900_000, {
      sources: ["bank_statement"],
      unit: "inr",
      differs: true,
      coverage: `Aug 2025 to Mar 2026 · 1 account: ${ACCOUNT}`,
      evidence: at("doc-bank", 5),
      row_columns: ["Month", "Account", "Credits", "Excluded credits"],
      rows: [
        ...WINDOW.map((m) =>
          xvRow([m.label, ACCOUNT, m.credits, m.excluded], at("doc-bank", m.bankPage)),
        ),
        xvRow(["Total Aug 2025 to Mar 2026", "", 175_400_000, 3_500_000], [], "total"),
        xvRow(
          [
            "12 Sep 2025",
            ACCOUNT,
            "Transfer between the borrower's own accounts: NEFT CR OWN ACCOUNT TRANSFER",
            2_000_000,
          ],
          at("doc-bank", 5),
          "excluded",
        ),
        xvRow(
          ["18 Jan 2026", ACCOUNT, "Reversal or refund: NEFT CR REFUND OF ADVANCE", 1_500_000],
          at("doc-bank", 8),
          "excluded",
        ),
      ],
    }),
  ],
  gaps: [
    {
      label: "Gap against GST outward supplies",
      amount: 23_900_000,
      pct: 13.9,
      base: "bank credits",
      legs: "GST outward supplies against bank credits",
      breached: true,
    },
  ],
  gap_tolerance: "10%",
  amount: 23_900_000,
  highlights: [
    xvLine(
      "GST against bank credits · Aug 2025 to Mar 2026",
      [
        xvFact("GST outward supplies", 148_000_000, "inr", true),
        xvFact("Bank credits", 171_900_000, "inr"),
      ],
      "13.9% apart · tolerance 10%",
    ),
  ],
  detail: {
    columns: ["GST outward supplies", "Business credits", "Difference"],
    rows: WINDOW.map((m) => {
      const net = m.credits - m.excluded;
      const pct = (Math.abs(net - m.gst) / Math.max(net, m.gst)) * 100;
      return {
        label: m.label,
        cells: [m.gst, net, `${pct.toFixed(1)}%`],
        flagged: pct > 10,
        flagged_cells: [],
      };
    }),
  },
});

const BA1 = xvFinding({
  id: "fnd-ba1",
  rule_id: "BA-01",
  title: "Declared accounts have statements",
  finding_title: "Declared account without a statement",
  area: "accounts",
  outcome: "fail",
  severity: "moderate",
  blocking: false,
  ref: "XV-000021-06",
  explanation: "Declared account(s) without a statement: Lotuscrest Bank ·5678.",
  sides: [
    xvSide("Declared in the sourcing message", `${ACCOUNT}, Lotuscrest Bank ·5678`, [], {
      sources: ["application_message"],
      differs: true,
    }),
    xvSide("Statements on file", ACCOUNT, at("doc-bank", 3), { sources: ["bank_statement"] }),
  ],
  columns: [
    xvColumn("declared", "Declared in the sourcing message", `${ACCOUNT}, Lotuscrest Bank ·5678`, {
      sources: ["application_message"],
      provenance: ["declared"],
      differs: true,
      coverage: "In the sourcing message",
      row_columns: ["Account", "Where it appears"],
      rows: [
        xvRow([ACCOUNT, "Sourcing message"]),
        xvRow(["Lotuscrest Bank ·5678", "Sourcing message"]),
      ],
    }),
    xvColumn("statements", "Statements on file", ACCOUNT, {
      sources: ["bank_statement"],
      coverage: "1 statement · Apr 2025 to Mar 2026",
      evidence: at("doc-bank", 3),
      row_columns: ["Account", "Where it appears"],
      rows: [xvRow([ACCOUNT, "Bank statement, pages 3 to 9"], at("doc-bank", 3))],
    }),
  ],
  mismatch: "Lotuscrest Bank ·5678 was declared but has no statement.",
  highlights: [xvLine("Lotuscrest Bank ·5678", [], "declared, no statement")],
  detail: {
    columns: ["Statement on file"],
    rows: [
      { label: ACCOUNT, cells: ["✓"], flagged: false, flagged_cells: [] },
      { label: "Lotuscrest Bank ·5678", cells: ["—"], flagged: true, flagged_cells: [] },
    ],
  },
  query: "Please provide the statements of Lotuscrest Bank ·5678 for the last 12 months.",
});

const TO4 = xvFinding({
  id: "fnd-to4",
  rule_id: "TO-04",
  title: "RM-declared turnover against evidenced turnover · FY 2025-26",
  compares: "RM-declared turnover against evidenced turnover",
  finding_title: "Declared turnover differs from the evidence",
  area: "turnover",
  outcome: "fail",
  severity: "mild",
  blocking: false,
  scope: "FY 2025-26",
  ref: "XV-000021-07",
  tolerance: "20%",
  explanation:
    "FY 2025-26: declared turnover INR 3.00 cr against audited turnover INR 30.00 cr, a variance of 90.0% (tolerance 20%).",
  sides: [
    xvSide("Declared turnover", 30_000_000, [], {
      sources: ["application_message"],
      differs: true,
    }),
    xvSide("Audited turnover", 300_000_000, at("doc-bs", 4), {
      sources: ["audited_financial_statements"],
    }),
  ],
  columns: [
    xvColumn("declared", "Turnover declared in the sourcing message", 30_000_000, {
      sources: ["application_message"],
      provenance: ["declared"],
      unit: "inr",
      differs: true,
      coverage: "Declared for FY 2025-26",
      row_columns: ["Line", "Year", "Amount"],
      rows: [xvRow(["Declared turnover", "FY 2025-26", 30_000_000])],
    }),
    xvColumn("audited", "Audited financial statements", 300_000_000, {
      sources: ["audited_financial_statements"],
      unit: "inr",
      coverage: "Year ended 31 Mar 2026 · audited",
      evidence: at("doc-bs", 4),
      row_columns: ["Line", "Year", "Amount"],
      rows: [xvRow(["Revenue from operations", "FY 2025-26", 300_000_000], at("doc-bs", 4))],
    }),
  ],
  gaps: [
    {
      label: "Gap against declared",
      amount: 270_000_000,
      pct: 90,
      base: "audited",
      legs: "declared against audited",
      breached: true,
    },
  ],
  gap_tolerance: "20%",
  amount: 270_000_000,
  highlights: [
    xvLine(
      "Declared against audited · FY 2025-26",
      [xvFact("Declared", 30_000_000, "inr", true), xvFact("Audited", 300_000_000, "inr")],
      "90.0% apart · tolerance 20%",
    ),
  ],
});

const GST_MONTHS_MISSING = {
  explanation: "GST outward supplies covers 8 of 12 months (Apr 2025, May 2025, Jun 2025… absent).",
  request: "GSTR-3B returns for Apr 2025 to Jul 2025",
  tolerance: "10%",
  scope: "FY 2025-26",
};

const COULD_NOT_CHECK = [
  xvFinding({
    id: "fnd-id4",
    rule_id: "ID-04",
    title: "Promoters match the KYC received",
    finding_title: "Promoter missing from a source",
    area: "identity",
    outcome: "incomplete",
    severity: "serious",
    blocking: true,
    explanation: "Director KYC not on file.",
    missing: ["Director KYC"],
    request: "the director KYC",
  }),
  xvFinding({
    id: "fnd-to1",
    rule_id: "TO-01",
    title: "Audited turnover against GST outward supplies · FY 2025-26",
    compares: "Audited turnover against GST outward supplies",
    finding_title: "Audited turnover differs from GST returns",
    area: "turnover",
    outcome: "incomplete",
    severity: "moderate",
    blocking: false,
    ...GST_MONTHS_MISSING,
    highlights: [
      xvLine(
        "Audited against GST · FY 2025-26",
        [],
        "GSTR-3B returns for Apr 2025 to Jul 2025 needed",
      ),
    ],
  }),
  xvFinding({
    id: "fnd-to2",
    rule_id: "TO-02",
    title: "GST outward supplies against cleansed bank credits · FY 2025-26",
    compares: "GST outward supplies against cleansed bank credits",
    finding_title: "GST turnover not supported by bank credits",
    area: "turnover",
    outcome: "incomplete",
    severity: "moderate",
    blocking: false,
    ...GST_MONTHS_MISSING,
    highlights: [
      xvLine(
        "GST against bank credits · FY 2025-26",
        [],
        "GSTR-3B returns for Apr 2025 to Jul 2025 needed",
      ),
    ],
  }),
  xvFinding({
    id: "fnd-to3",
    rule_id: "TO-03",
    title: "Audited turnover against cleansed bank credits · FY 2025-26",
    compares: "Audited turnover against cleansed bank credits",
    finding_title: "Audited turnover not supported by bank credits",
    area: "turnover",
    outcome: "incomplete",
    severity: "moderate",
    blocking: false,
    scope: "FY 2025-26",
    tolerance: "10%",
    explanation:
      "Waiting for review of the bank statement credits for Jun 2025; confirm or correct the value to complete this check.",
    sides: [
      xvSide("Business credits in bank statements", null, at("doc-bank", 7), {
        sources: ["bank_statement"],
        awaiting_review: true,
        field_ids: ["fv-credits-jun"],
      }),
    ],
    columns: [
      xvColumn("bank", "Business credits in bank statements", null, {
        sources: ["bank_statement"],
        unit: "inr",
        coverage: `Apr 2025 to Mar 2026 · 1 account: ${ACCOUNT}`,
        awaiting_review: true,
        field_ids: ["fv-credits-jun"],
        evidence: at("doc-bank", 7),
      }),
    ],
  }),
];

const PASSED = [
  xvFinding({
    id: "fnd-id2",
    rule_id: "ID-02",
    title: "GSTIN consistent across documents",
    finding_title: "GSTIN differs between documents",
    area: "identity",
    outcome: "pass",
    severity: "serious",
    blocking: true,
    explanation: "Consistent across 3 sources.",
    highlights: [
      xvLine("GSTIN", [xvFact("3 sources", "27AAACK1234K1Z5")], "same across 3 sources"),
    ],
  }),
  xvFinding({
    id: "fnd-id3",
    rule_id: "ID-03",
    title: "Legal name consistent across documents",
    finding_title: "Company name differs between documents",
    area: "identity",
    outcome: "pass",
    severity: "moderate",
    blocking: false,
    explanation: "Consistent across 6 sources.",
    highlights: [
      xvLine(
        "Company name",
        [xvFact("6 sources", "Kestrel Polymers Pvt Ltd")],
        "same across 6 sources",
      ),
    ],
  }),
  xvFinding({
    id: "fnd-id6",
    rule_id: "ID-06",
    title: "Director identifiers agree",
    finding_title: "Director identifiers disagree",
    area: "identity",
    outcome: "pass",
    severity: "moderate",
    blocking: false,
    explanation: "Identifiers agree for 2 director(s).",
  }),
  xvFinding({
    id: "fnd-id7",
    rule_id: "ID-07",
    title: "CIN agrees with the incorporation particulars",
    finding_title: "CIN does not match the incorporation details",
    area: "identity",
    outcome: "pass",
    severity: "mild",
    blocking: false,
    explanation: "The CIN agrees with 3 particular(s) on file.",
  }),
  xvFinding({
    id: "fnd-ba2",
    rule_id: "BA-02",
    title: "Accounts on file are declared",
    finding_title: "Account on file that was not declared",
    area: "accounts",
    outcome: "pass",
    severity: "moderate",
    blocking: false,
    explanation: "Every account on file is declared.",
    highlights: [xvLine("Accounts on file", [], "1 account · each declared and with a statement")],
  }),
  xvFinding({
    id: "fnd-ob3",
    rule_id: "OB-03",
    title: "Borrowings in the books are serviced in the bank · FY 2025-26",
    compares: "Borrowings in the books are serviced in the bank",
    finding_title: "Borrowings and instalments do not match",
    area: "obligations",
    outcome: "pass",
    severity: "moderate",
    blocking: false,
    scope: "FY 2025-26",
    explanation: "The borrowings in the books are serviced in the bank statements.",
    highlights: [
      xvLine("Long-term borrowings · FY 2025-26", [], "serviced in the bank statements"),
    ],
  }),
];

const NOT_APPLICABLE = [
  xvFinding({
    id: "fnd-id8",
    rule_id: "ID-08",
    title: "Directors in the memorandum are accounted for",
    finding_title: "Director in the memorandum not accounted for",
    area: "identity",
    outcome: "not_applicable",
    severity: "mild",
    blocking: false,
    explanation: "No director is named in the memorandum.",
  }),
];

/** Kestrel's board, a fresh copy each call: decisions in a test change only that test's copy. */
export function kestrelBoard(): CrossVerificationView {
  const discrepancies = [
    xvItem(OB2, { review_item_id: "r-finding" }),
    xvItem(OB1, {
      review_item_id: "r-ob1",
      escalation: xvDecision(
        "escalate",
        "The sanction letter and the bureau agree against the declaration; the Credit Manager should decide.",
        "2026-10-08T11:20:00+00:00",
      ),
    }),
    xvItem(ID1, { review_item_id: "r-id1" }),
    xvItem(ID5, { review_item_id: "r-id5" }),
    xvItem(TO5, { review_item_id: "r-to5" }),
    xvItem(BA1, { review_item_id: "r-ba1" }),
    xvItem(TO4, {
      review_item_id: "r-to4",
      adjudicated: true,
      decision: xvDecision(
        "dismiss",
        "The sourcing message meant INR 30 cr; the RM confirmed the typing slip.",
        "2026-10-08T10:05:00+00:00",
      ),
    }),
  ];
  const rest = [...COULD_NOT_CHECK, ...PASSED, ...NOT_APPLICABLE].map((f) =>
    xvItem(f, { in_query_list: f.id === "fnd-to2" }),
  );
  return xvView(KESTREL, structuredClone([...discrepancies, ...rest]));
}

/** The same findings, as GET /findings answers them. */
export const FINDINGS: Finding[] = kestrelBoard().items.map((i) => i.finding);

export const FINDING_ITEM: ReviewItem = {
  id: "r-finding",
  case_id: KESTREL,
  kind: "finding",
  ref: "finding:fnd-ob2",
  summary: "OB-02 Instalments in bank statements go to declared lenders",
  status: "open",
  escalated: false,
  created_at: "2026-09-21T09:07:00Z",
};

/** The escalated discrepancy's review item: open, and decided by the Credit Manager only. */
export const ESCALATED_ITEM: ReviewItem = {
  id: "r-ob1",
  case_id: KESTREL,
  kind: "finding",
  ref: "finding:fnd-ob1",
  summary: "OB-01 Declared facilities reconcile with sanction letters and the bureau",
  status: "open",
  escalated: true,
  created_at: "2026-09-21T09:08:00Z",
};

/** A value a document states, as the aligned facts carry it. */
function stated(label: string, source: string, value: string, evidence: Evidence[]): FactValue {
  return { label, source, value, evidence, awaiting_review: false, relies_on_manual: false };
}

/** A person as a source names them. */
function person(
  name: string,
  din: string | null,
  pan: string | null,
  evidence: Evidence[] = [],
): PersonEntry {
  return { name, din, pan, evidence, awaiting_review: false, relies_on_manual: false };
}

export const FACTS: CaseFacts = {
  case_id: KESTREL,
  identities: {
    entity_pan: [
      stated("Company PAN", "company_pan", PAN, at("doc-cpan", 1)),
      stated("GSTR-3B (PAN within the GSTIN)", "gstr_3b", PAN, at("doc-gstr3b", 1)),
      stated(
        "Commercial bureau report",
        "commercial_bureau_report",
        PAN_BUREAU,
        at("doc-bureau", 1),
      ),
    ],
    gstin: [stated("GSTR-3B", "gstr_3b", "27AAACK1234K1Z5", at("doc-gstr3b", 1))],
    legal_name: [],
  },
  persons: [
    {
      label: "KYC received",
      source: "director_kyc",
      names: ["Kabir Rao"],
      entries: [person("Kabir Rao", "08812345", "ABCPR1234F", at("doc-pan", 1))],
      relies_on_manual: false,
    },
    {
      label: "Sourcing message",
      source: "application_message",
      names: ["Kabir Rao", "Leela Varghese"],
      entries: [person("Kabir Rao", null, null), person("Leela Varghese", null, null)],
      relies_on_manual: false,
    },
  ],
  turnover: [
    {
      fy: "FY 2025-26",
      fy_end: "2026-03-31",
      figures: [
        {
          source: "gst",
          label: "GST outward supplies",
          value: 80_000_000,
          months_covered: 8,
          months_missing: ["Apr 2025", "May 2025", "Jun 2025", "Jul 2025"],
          evidence: [{ document_id: "doc-gstr3b", page: 1 }],
          field_ids: [],
          relies_on_manual: false,
          awaiting_review: false,
        },
      ],
    },
  ],
  credits: [
    {
      account: "Lotuscrest Bank ·1234",
      gross: 3_276_500,
      excluded: 2_876_500,
      net: 400_000,
      months: ["Apr 2025"],
      exclusions: [
        {
          rule: "loan_disbursal",
          label: "Loan disbursal",
          account: "Lotuscrest Bank ·1234",
          date: "2025-04-06",
          narration: "LOAN DISBURSAL TL 7781",
          amount: 2_500_000,
          evidence: [{ document_id: "doc-bank", page: 7 }],
        },
      ],
    },
  ],
  obligations: [
    {
      lender: "ASHWOOD FINSERV",
      variants: ["ASHWOOD FINSERV"],
      account: "Lotuscrest Bank ·1234",
      months: ["Apr 2025", "May 2025", "Jun 2025"],
      typical_amount: 145_000,
      debits: 3,
      evidence: [{ document_id: "doc-bank", page: 7 }],
    },
  ],
  accounts: [
    {
      bank: "Lotuscrest Bank",
      last4: "1234",
      label: "Lotuscrest Bank ·1234",
      sources: ["Bank statement"],
      declared: true,
      has_statement: true,
      evidence: [{ document_id: "doc-bank", page: 7 }],
    },
  ],
  facilities: [
    {
      label: "Declaration of existing facilities",
      source: "existing_facilities_declaration",
      lender: "Tidewater Finance",
      facility: "Term loan",
      amount: 4_000_000,
      emi: 92_000,
      evidence: at("doc-decl", 1),
      awaiting_review: false,
      relies_on_manual: false,
    },
  ],
  declaration_received: true,
};

// --- Policy norms (F-20) ---

const bs = (page: number) => [{ document_id: "doc-bs", page }];

export function norm(
  n: Partial<NormResult> & Pick<NormResult, "id" | "family" | "label" | "outcome">,
): NormResult {
  return {
    formula: "",
    required: "",
    comparator: "min",
    threshold_text: "",
    actual: null,
    unit: null,
    category: "financial",
    category_label: "Financial norms",
    inputs: [],
    missing: [],
    reason: null,
    reason_inputs: [],
    actual_text: null,
    definition: null,
    source: "provisional",
    note: null,
    provisional: true,
    ...n,
  };
}

function input(
  name: string,
  label: string,
  value: number | null,
  page: number | null,
  extra: Partial<NormInput> = {},
): NormInput {
  return {
    name,
    label,
    value,
    evidence: page === null ? [] : bs(page),
    relies_on_manual: false,
    awaiting_review: false,
    basis: "document",
    refs: [],
    ...extra,
  };
}

const ELIGIBILITY = { category: "eligibility", category_label: "Eligibility" } as const;
const DOCUMENTATION = { category: "documentation", category_label: "Documentation" } as const;

/** Norms by outcome, as the engine counts them. */
function policyCounts(
  deviations: number,
  cannot_evaluate: number,
  passed: number,
  not_applicable = 0,
): PolicyCounts {
  return { deviations, cannot_evaluate, passed, not_applicable };
}

/** A family's overview card, as engine/policy.py (_group) sends it. */
function policyGroup(
  family: PolicyGroup["family"],
  norms: number,
  counts: PolicyCounts,
  status: PolicyGroup["status"],
  highlights: string[] = [],
): PolicyGroup {
  return { family, norms, counts, status, highlights };
}

/** Kestrel: a loss-making year, a debt / equity deviation, open blocking items, figures still under review. */
export const POLICY = {
  case_id: KESTREL,
  period: "FY 2025-26",
  config_version: "v3",
  norms: [
    norm({
      id: "FR-05",
      family: "ratios",
      label: "Debt / equity",
      formula: "Total borrowings / Net worth",
      definition: "Total debt ÷ Tangible net worth",
      note: "Interim threshold proposed by the delivery team.",
      required: "at most 2.00x",
      comparator: "max",
      threshold_text: "2.00x",
      actual: 3,
      actual_text: "3.00x",
      unit: "x",
      outcome: "deviation",
      inputs: [
        input("total_borrowings", "Total borrowings", 120_000_000, 4),
        input("net_worth", "Net worth", 40_000_000, 4),
      ],
    }),
    norm({
      id: "EL-02",
      family: "eligibility",
      label: "Commercial bureau rank",
      formula: "Commercial bureau rank",
      required: "at most rank 6",
      comparator: "max",
      threshold_text: "rank 6",
      unit: "rank",
      outcome: "cannot_evaluate",
      ...ELIGIBILITY,
      missing: ["Commercial bureau rank"],
    }),
    norm({
      id: "EL-04",
      family: "eligibility",
      label: "Profit in the latest year",
      formula: "Profit after tax",
      required: "at least INR 0",
      comparator: "min",
      threshold_text: "INR 0",
      actual: -4_000_000,
      actual_text: "INR -40.00 lakh",
      unit: "inr",
      outcome: "deviation",
      ...ELIGIBILITY,
      inputs: [input("profit_after_tax", "Profit after tax", -4_000_000, 5)],
    }),
    norm({
      id: "FR-01",
      family: "ratios",
      label: "Current ratio",
      formula: "Current assets / Current liabilities",
      required: "at least 1.20x",
      comparator: "min",
      threshold_text: "1.20x",
      actual: 1.5,
      actual_text: "1.50x",
      unit: "x",
      outcome: "pass",
      inputs: [
        input("current_assets", "Current assets", 90_000_000, 4),
        input("current_liabilities", "Current liabilities", 60_000_000, 4),
      ],
    }),
    norm({
      id: "FR-04",
      family: "ratios",
      label: "Interest coverage",
      formula: "(Profit before tax + Finance costs) / Finance costs",
      required: "at least 2.50x",
      comparator: "min",
      threshold_text: "2.50x",
      unit: "x",
      outcome: "cannot_evaluate",
      reason: "zero_denominator",
      reason_inputs: ["Finance costs"],
      inputs: [
        input("profit_before_tax", "Profit before tax", -3_000_000, 5),
        input("finance_costs", "Finance costs", 0, 5),
      ],
    }),
    norm({
      id: "FR-06",
      family: "ratios",
      label: "Working-capital cycle",
      formula: "(Inventories + Trade receivables - Trade payables) / Revenue from operations * 365",
      required: "at most 75 days",
      comparator: "max",
      threshold_text: "75 days",
      unit: "days",
      outcome: "cannot_evaluate",
      reason: "awaiting_review",
      reason_inputs: ["Trade receivables"],
      inputs: [
        input("inventories", "Inventories", 25_000_000, 4),
        input("trade_receivables", "Trade receivables", 24_000_000, 4, { awaiting_review: true }),
        input("trade_payables", "Trade payables", 20_000_000, 4),
        input("revenue_from_operations", "Revenue from operations", 300_000_000, 5),
      ],
    }),
    norm({
      id: "DOC-01",
      family: "documentation",
      label: "Blocking checklist items open",
      formula: "Blocking checklist items open",
      required: "at most 0",
      comparator: "max",
      threshold_text: "0",
      actual: 2,
      actual_text: "2",
      unit: "count",
      outcome: "deviation",
      ...DOCUMENTATION,
      inputs: [
        input("blocking_items_open", "Blocking checklist items open", 2, null, {
          basis: "checklist",
          refs: ["kyc_directors", "valuation_report"],
        }),
      ],
    }),
  ],
  counts: policyCounts(3, 3, 1),
  // In the page's order; each card's norms: deviations, then those that cannot be evaluated,
  // then passed ones, three at most.
  groups: [
    policyGroup("eligibility", 2, policyCounts(1, 1, 0), "deviation", ["EL-04", "EL-02"]),
    policyGroup("ratios", 4, policyCounts(1, 2, 1), "deviation", ["FR-05", "FR-04", "FR-06"]),
    policyGroup("documentation", 1, policyCounts(1, 0, 0), "deviation", ["DOC-01"]),
    policyGroup("security_cover", 0, policyCounts(0, 0, 0), "no_norms"),
  ],
} satisfies PolicyAssessment;

/** Saffron: negative net worth, so the leverage norms have no meaningful value. */
export const SAFFRON_POLICY = {
  case_id: SAFFRON,
  period: "FY 2025-26",
  config_version: "v3",
  norms: [
    norm({
      id: "EL-03",
      family: "eligibility",
      label: "Positive net worth",
      formula: "Net worth",
      required: "at least INR 1",
      comparator: "min",
      threshold_text: "INR 1",
      actual: -40_000_000,
      actual_text: "INR -4.00 cr",
      unit: "inr",
      outcome: "deviation",
      ...ELIGIBILITY,
      inputs: [input("net_worth", "Net worth", -40_000_000, 4)],
    }),
    norm({
      id: "FR-02",
      family: "ratios",
      label: "TOL / TNW",
      formula: "(Long-term borrowings + Current liabilities) / Net worth",
      required: "at most 3.00x",
      comparator: "max",
      threshold_text: "3.00x",
      unit: "x",
      outcome: "deviation",
      reason: "denominator_not_positive",
      reason_inputs: ["Net worth"],
      actual_text: "unbounded (Net worth zero or negative)",
      inputs: [
        input("long_term_borrowings", "Long-term borrowings", 80_000_000, 4),
        input("current_liabilities", "Current liabilities", 60_000_000, 4),
        input("net_worth", "Net worth", -40_000_000, 4),
      ],
    }),
  ],
  counts: policyCounts(2, 0, 0),
  groups: [
    policyGroup("eligibility", 1, policyCounts(1, 0, 0), "deviation", ["EL-03"]),
    policyGroup("ratios", 1, policyCounts(1, 0, 0), "deviation", ["FR-02"]),
    policyGroup("documentation", 0, policyCounts(0, 0, 0), "no_norms"),
    policyGroup("security_cover", 0, policyCounts(0, 0, 0), "no_norms"),
  ],
} satisfies PolicyAssessment;

const authority = (key: string, label: string, level: number) => ({ key, label, level });
const REGIONAL = authority("regional_credit_head", "Regional Credit Head", 2);
const CREDIT_OFFICER = authority("credit_officer", "Credit Officer", 1);

/** Kestrel, INR 50 lakh of cash credit and term loan: both bands need the Credit Officer; each
 * deviation category asks one level more, and eligibility (first in policy order) decides. */
export const APPROVAL = {
  case_id: KESTREL,
  outcome: "determined",
  required: REGIONAL,
  reason: null,
  unmapped_facilities: [],
  amount_inr: 5_000_000,
  amount_basis: "amount_requested",
  products: ["working_capital", "term"],
  product_labels: ["Working capital", "Term loan"],
  steps: [
    {
      kind: "amount",
      rule: "bands.working_capital[0]",
      product: "working_capital",
      product_label: "Working capital",
      band_from_inr: null,
      band_to_inr: 20_000_000,
      capped: false,
      authority: CREDIT_OFFICER,
      governs: false,
    },
    {
      kind: "amount",
      rule: "bands.term[0]",
      product: "term",
      product_label: "Term loan",
      band_from_inr: null,
      band_to_inr: 10_000_000,
      capped: false,
      authority: CREDIT_OFFICER,
      governs: false,
    },
    {
      kind: "deviation",
      rule: "deviations.eligibility",
      category: "eligibility",
      category_label: "Eligibility",
      norms: ["EL-04"],
      norm_labels: ["Profit in the latest year"],
      levels_above: 1,
      at_least: REGIONAL,
      capped: false,
      authority: REGIONAL,
      governs: true,
    },
    {
      kind: "deviation",
      rule: "deviations.financial",
      category: "financial",
      category_label: "Financial norms",
      norms: ["FR-05"],
      norm_labels: ["Debt / equity"],
      levels_above: 1,
      at_least: null,
      capped: false,
      authority: REGIONAL,
      governs: false,
    },
    {
      kind: "deviation",
      rule: "deviations.documentation",
      category: "documentation",
      category_label: "Documentation",
      norms: ["DOC-01"],
      norm_labels: ["Blocking checklist items open"],
      levels_above: 1,
      at_least: null,
      capped: false,
      authority: REGIONAL,
      governs: false,
    },
  ],
  lower_bound: true,
  unevaluated: ["EL-02", "FR-04", "FR-06"],
  unevaluated_labels: ["Commercial bureau rank", "Interest coverage", "Working-capital cycle"],
  could_rise_to: REGIONAL,
  provisional: true,
  source: "provisional",
  config_version: "v3",
} satisfies ApprovingAuthority;

export const APPROVAL_MATRIX = {
  source: "provisional",
  status: "provisional",
  note: "Interim matrix proposed by the delivery team, awaiting RBL's approval and delegation matrix.",
  amount_basis: "amount_requested",
  authorities: [
    { ...CREDIT_OFFICER, status: "provisional" },
    { ...REGIONAL, status: "provisional" },
  ],
  products: [{ key: "working_capital", label: "Working capital", facilities: ["cash_credit"] }],
  bands: {
    working_capital: [
      { up_to_inr: 20_000_000, authority: "credit_officer", status: "provisional" },
      { up_to_inr: null, authority: "regional_credit_head", status: "provisional" },
    ],
  },
  deviations: [{ category: "financial", levels_above: 1, at_least: null, status: "provisional" }],
} satisfies ApprovalMatrixConfig;

// --- Comparison with RBL's record (F-25) ---

const byId = (id: string) => POLICY.norms.find((n) => n.id === id)!;

function record(confirmed: boolean, importedBy = "ananya-krishnan") {
  return {
    case_id: KESTREL,
    workbook_name: "kestrel-record.xlsx",
    workbook_sha256: "4f1c0de5",
    record_date: "2026-09-25",
    deviations_recorded: true,
    imported_by: importedBy,
    imported_at: "2026-10-01T09:00:00Z",
    confirmed_by: confirmed ? "meenal-kulkarni" : null,
    confirmed_by_name: confirmed ? "Meenal Kulkarni" : null,
    confirmed_at: confirmed ? "2026-10-02T09:00:00Z" : null,
    config_version: "v3",
    deviations: [],
    approval: null,
    areas_not_compared: ["classification", "key_fields", "discrepancies", "queries", "decision"],
  };
}

const deviationRow = (
  row: number,
  norm_id: string | null,
  description: string,
  value: string,
  category: string | null,
) => ({
  row,
  norm_id,
  description,
  category,
  recorded_value: value,
  approved_by_text: "Zonal Credit Committee",
  source_ref: `CAM p.14, deviation table row ${row - 1}`,
  notes: null,
});

/** Kestrel compared with its confirmed record: one agreement, one difference, one new
 * deviation, three missed, and an authority recorded one level above the matrix. */
export function comparison(confirmed = true, importedBy = "ananya-krishnan"): CaseComparison {
  const items: CaseComparison["items"] = [
    {
      area: "deviations",
      key: "FR-05",
      label: "Debt / equity",
      status: "agree",
      creditiq_text: "3.00x",
      record_text: "3.00x",
      norm: byId("FR-05"),
      record_deviation: deviationRow(2, "FR-05", "Debt equity above norm", "3.00x", "financial"),
      notes: [],
      adjudicable: false,
      adjudication: null,
      scored: true,
    },
    {
      area: "deviations",
      key: "EL-04",
      label: "Profit in the latest year",
      status: "new",
      creditiq_text: "INR -40.00 lakh",
      record_text: null,
      norm: byId("EL-04"),
      record_deviation: null,
      notes: [],
      adjudicable: confirmed,
      adjudication: null,
      scored: true,
    },
    {
      area: "deviations",
      key: "DOC-01",
      label: "Blocking checklist items open",
      status: "differ",
      creditiq_text: "2",
      record_text: "3 items",
      norm: byId("DOC-01"),
      record_deviation: deviationRow(
        3,
        "DOC-01",
        "Documents pending at sanction",
        "3 items",
        "documentation",
      ),
      notes: ["value_differs"],
      adjudicable: confirmed,
      adjudication: null,
      scored: true,
    },
    {
      area: "deviations",
      key: "EL-02",
      label: "Commercial bureau rank",
      status: "missed",
      creditiq_text: null,
      record_text: "rank 7",
      norm: byId("EL-02"),
      record_deviation: deviationRow(
        4,
        "EL-02",
        "Bureau rank weaker than norm",
        "rank 7",
        "eligibility",
      ),
      notes: ["cannot_evaluate"],
      adjudicable: false,
      adjudication: null,
      scored: true,
    },
    {
      area: "deviations",
      key: "FR-01",
      label: "Current ratio",
      status: "missed",
      creditiq_text: "1.50x",
      record_text: "1.10x",
      norm: byId("FR-01"),
      record_deviation: deviationRow(5, "FR-01", "Current ratio below norm", "1.10x", "financial"),
      notes: ["pass"],
      adjudicable: false,
      adjudication: null,
      scored: true,
    },
    {
      area: "deviations",
      key: "REC-6",
      label: "Pricing below card rate",
      status: "missed",
      creditiq_text: null,
      record_text: "25 bps below card",
      norm: null,
      record_deviation: deviationRow(6, null, "Pricing below card rate", "25 bps below card", null),
      notes: ["no_norm"],
      adjudicable: false,
      adjudication: null,
      scored: true,
    },
    {
      area: "approving_authority",
      key: "approval",
      label: "Approving authority",
      status: "differ",
      creditiq_text: "Regional Credit Head",
      record_text: "Zonal Credit Committee",
      required: APPROVAL,
      record_approval: {
        authority_text: "Zonal Credit Committee",
        authority_key: "zonal_credit_committee",
        decision: "approved",
        decided_on: "2026-09-26",
        source_ref: "Sanction note p.1",
        notes: null,
      },
      authority_on_record_deviations: REGIONAL,
      notes: ["higher"],
      adjudicable: confirmed,
      adjudication: null,
      scored: false,
    },
  ];
  return {
    case_id: KESTREL,
    config_version: "v3",
    record: record(confirmed, importedBy),
    provisional_norms: true,
    provisional_matrix: true,
    counts: {
      agree: 1,
      differ: 1,
      new: 1,
      missed: 3,
      to_adjudicate: confirmed ? 3 : 0,
      no_deviation_either_side: 4,
    },
    items,
    scores: [
      {
        area: "deviations",
        scored: true,
        found_in_record: 2,
        recorded_total: 5,
        valid: 1,
        flagged_total: 3,
        pending: 2,
      },
    ],
  };
}

/** No record imported yet. */
export const NO_COMPARISON: CaseComparison = {
  case_id: KESTREL,
  config_version: "v3",
  record: null,
  provisional_norms: true,
  provisional_matrix: true,
  counts: { agree: 0, differ: 0, new: 0, missed: 0, to_adjudicate: 0, no_deviation_either_side: 0 },
  items: [],
  scores: [],
};

/** A decision whose item has changed since: shown stale, not counted. */
export function staleComparison(): CaseComparison {
  const c = comparison();
  const doc = c.items.find((i) => i.key === "DOC-01")!;
  doc.adjudication = {
    verdict: "valid",
    reason: "Record counted the CA certificate twice",
    decided_by: "meenal-kulkarni",
    decided_by_name: "Meenal Kulkarni",
    decided_at: "2026-10-03T09:00:00Z",
    stale: true,
  };
  return c;
}

// --- Outputs (F-22 to F-24) ---

const cite = (page: number) => [{ document_id: "doc-bs", page }];

export const SPREAD: Spread = {
  case_id: KESTREL,
  interim: true,
  columns: [{ key: "audited-2026", fy: "FY 2025-26", period_end: "2026-03-31", basis: "audited" }],
  rows: [
    {
      key: "revenue_from_operations",
      label: "Revenue from operations",
      section: "profit_and_loss",
      kind: "line",
      unit: "inr",
      formula: null,
      cells: [{ value: 300_000_000, evidence: cite(4), relies_on_manual: false }],
    },
    {
      key: "current-ratio",
      label: "Current ratio",
      section: "ratios",
      kind: "ratio",
      unit: "x",
      formula: "Current assets ÷ Current liabilities",
      cells: [{ value: 1.5, evidence: cite(4), relies_on_manual: false }],
    },
  ],
  working_capital: {
    method: "turnover",
    reason: "The request is within INR 5.00 cr, so the turnover method applies.",
    column: "FY 2025-26 (audited)",
    steps: [
      {
        label: "Turnover",
        value: 300_000_000,
        unit: "inr",
        basis: "Revenue from operations",
        evidence: cite(4),
      },
      {
        label: "Eligible bank finance",
        value: 60_000_000,
        unit: "inr",
        basis: "Requirement less the margin",
        evidence: [],
      },
    ],
    eligible: 60_000_000,
    requested: 50_000_000,
    missing: [],
  },
};

// The draft CAM in the assumed layout (config/cam.yaml), as engine/cam.py drafts it for Kestrel:
// twelve numbered sections of blocks, the summary, the empty recommendation and the documents
// cited, numbered in the order they are first cited.

const said = (text: string, ...citations: Evidence[]): CamText => ({ text, citations });
const paragraph = (text: string, ...citations: Evidence[]): CamBlock => ({
  kind: "paragraph",
  paragraph: said(text, ...citations),
});
const facts = (...rows: [string, string | CamText][]): CamBlock => ({
  kind: "facts",
  facts: rows.map(([label, value]) => ({
    label,
    value: typeof value === "string" ? said(value) : value,
  })),
});
const table = (
  columns: string[],
  rows: (string | CamText)[][],
  extra: Partial<CamTable> = {},
): CamBlock => ({
  kind: "table",
  table: {
    title: null,
    numeric: [],
    note: null,
    ...extra,
    columns,
    rows: rows.map((row) => row.map((value) => (typeof value === "string" ? said(value) : value))),
  },
});
const subheading = (text: string): CamBlock => ({ kind: "subheading", text });
const note = (text: string): CamBlock => ({ kind: "note", text });
const memoSection = (
  number: number,
  id: string,
  title: string,
  blocks: CamBlock[],
): CamSection => ({
  id,
  number,
  title,
  blocks,
  empty: null,
  parts: [],
  review: { state: "machine", paragraphs: [], overrides: [], requests: [] },
});

/** The memo's eight sections as config/cam.yaml composes them: six drafted from the parts (each a
 * part keeping its id, under its subheading where there are several), then the risk assessment
 * and the recommendation. */
const CAM_LAYOUT: [string, string, string, string[]][] = [
  [
    "profile",
    "Borrower and Group Profile",
    "Legal identity, constitution, promoters and management, as the documents show them.",
    ["borrower", "promoters"],
  ],
  [
    "facility",
    "Facility Requested and Purpose",
    "What is being asked for, why, and the working-capital assessment behind it.",
    ["snapshot", "proposal", "working_capital"],
  ],
  [
    "conduct",
    "Banking Conduct",
    "Account behaviour across the statements on file, and the facilities already running.",
    ["banking", "obligations"],
  ],
  [
    "analysis",
    "Financial Analysis and Ratios",
    "The audited years' performance and the ratios tested against the policy norms.",
    ["financials", "policy"],
  ],
  [
    "gst",
    "GST and Bureau Findings",
    "Turnover across GST returns, income tax returns and banking, as filed.",
    ["turnover"],
  ],
  [
    "verification",
    "Cross-Verification Results",
    "Contradictions between sources, the evidence, and how each was decided; the documents' status.",
    ["verification", "documentation"],
  ],
];
function eightSections(parts: CamSection[]): CamSection[] {
  return CAM_LAYOUT.map(([id, title, purpose, ids], i) => {
    const own = ids.map((p) => parts.find((s) => s.id === p)!);
    const blocks =
      own.length === 1
        ? (own[0]!.blocks ?? [])
        : own.flatMap((p) =>
            (p.blocks ?? []).length ? [subheading(p.title), ...(p.blocks ?? [])] : [],
          );
    return {
      ...memoSection(i + 1, id, title, blocks),
      purpose,
      parts: own.map((p) => ({ id: p.id, kind: p.id, title: p.title, blocks: p.blocks ?? [] })),
      empty: blocks.length ? null : "Nothing on file yet.",
    };
  });
}
const summaryItem = (
  kind: CamSummaryItem["kind"],
  ref: string,
  text: string,
  extra: Partial<CamSummaryItem> = {},
): CamSummaryItem => ({
  kind,
  ref,
  text,
  severity: null,
  rule: null,
  title: null,
  status: null,
  blocking: false,
  citations: [],
  ...extra,
});
const source = (
  number: number,
  document_id: string,
  label: string,
  file_name: string,
  pages: number[],
): OutputSource => ({ number, document_id, label, file_name, pages });

/** The configuration the memo and the note are drafted under: the full version, and the label
 * Administration counts it by. */
export const OUTPUT_CONFIG_VERSION =
  "7f3c9a1e5b2d48c6a0e4f1b7d9c3a5e2f8b6d4c0a1e3f5b7c9d2e4f6a8b0c1d3";
export const OUTPUT_CONFIG_LABEL = "Version 3 (published 18 Sep 2026)";

/** The monthly GSTR-3B returns on file, Aug 2025 to Mar 2026, one document each: a year's GST
 * figure rests on every one of them, at page 1. */
const GST_RETURNS: [document_id: string, month: string, file_name: string][] = [
  ["doc-gstr3b", "Aug 2025", "gstr3b_aug25.pdf"],
  ["doc-gstr3b-sep", "Sep 2025", "gstr3b_sep25.pdf"],
  ["doc-gstr3b-oct", "Oct 2025", "gstr3b_oct25.pdf"],
  ["doc-gstr3b-nov", "Nov 2025", "gstr3b_nov25.pdf"],
  ["doc-gstr3b-dec", "Dec 2025", "gstr3b_dec25.pdf"],
  ["doc-gstr3b-jan", "Jan 2026", "gstr3b_jan26.pdf"],
  ["doc-gstr3b-feb", "Feb 2026", "gstr3b_feb26.pdf"],
  ["doc-gstr3b-mar", "Mar 2026", "gstr3b_mar26.pdf"],
];
const gstReturns = (): Evidence[] => GST_RETURNS.flatMap(([id]) => at(id, 1));

const PAN_TEXT = `The entity PAN differs between documents: ${PAN} (${PAN_GROUP}) · ${PAN_BUREAU} (Commercial bureau report).`;
const CIN_TEXT = `The CIN differs between documents: ${CIN} (Certificate of incorporation, Commercial bureau report, Declaration of existing facilities) · ${CIN_MOA} (Memorandum and articles of association).`;
const GST_TEXT =
  "Aug 2025 to Mar 2026: GST outward supplies INR 14.80 cr against business credits INR 17.19 cr, a variance of 13.9% (tolerance 10%).";
const DECLARED_TEXT =
  "FY 2025-26: declared turnover INR 3.00 cr against audited turnover INR 30.00 cr, a variance of 90.0% (tolerance 20%).";
const ACCOUNT_TEXT = "Declared account(s) without a statement: Lotuscrest Bank ·5678.";
const LENDER_TEXT = `Regular debits to lender(s) not declared: ASHWOOD FINSERV (INR 1,45,000 a month in 6 months, ${ACCOUNT}).`;
const FACILITIES_TEXT =
  "The existing facilities do not reconcile: Tidewater Finance: sanctioned amounts differ: declared INR 40.00 lakh, sanction letter INR 55.00 lakh, bureau INR 55.00 lakh; Lotuscrest Bank: not declared.";

/** An observation: a fact the memo states (section 8) that the note asks the promoter about. */
export const DISBURSAL_TEXT =
  "The loan disbursal of INR 25.00 lakh on 06 Apr 2025 (TL 7781) matches no facility on file.";

export const CAM: Cam = {
  case_id: KESTREL,
  title: "Credit Approval Memo",
  borrower: "Kestrel Polymers Pvt Ltd",
  as_of: "2026-09-20",
  config_version: OUTPUT_CONFIG_VERSION,
  config_label: OUTPUT_CONFIG_LABEL,
  run_id: XV_RUN.id,
  interim_template: true,
  template_note: "Draft — layout assumed until RBL's CAM template is received.",
  copilot: false,
  sections: eightSections([
    memoSection(1, "snapshot", "Proposal at a glance", [
      facts(
        ["Borrower", said("Kestrel Polymers Pvt Ltd", ...at("doc-coi", 1))],
        ["Constitution", "Private limited company"],
        ["PAN", said(PAN, ...at("doc-cpan", 1))],
        ["GSTIN", said("27AAACK1234K1Z5", ...at("doc-gstr3b", 1))],
        ["CIN", said(CIN, ...at("doc-coi", 1))],
        ["Incorporated", said("12 Jun 2015 (11 years 3 months)", ...at("doc-coi", 1))],
        ["Facilities proposed", "Cash credit, Term loan"],
        ["Amount requested", "INR 50.00 lakh"],
        ["Collateral offered", "Offered (case record; details not on file)"],
        ["Turnover declared in the sourcing message", "INR 3.00 cr"],
        ["Relationship manager and branch", "Arjun Deshpande · Mumbai hub"],
        ["Approving authority", "At least Regional Credit Head (provisional matrix)"],
        [
          "Cross-checks",
          "18 run; 7 discrepancies: 5 open (2 blocking submission), 1 accepted as valid, 1 not valid; 4 could not be completed",
        ],
        ["Policy norms", "3 deviations · 3 not assessed"],
        ["Documentation", "Readiness 58% against the 85% gate · 2 blocking items open"],
        ["Case ID", KESTREL],
      ),
    ]),
    memoSection(2, "borrower", "Borrower profile", [
      paragraph(
        "Kestrel Polymers Pvt Ltd is a private limited company (limited by shares) incorporated on 12 Jun 2015, 11 years 3 months in business.",
        ...at("doc-coi", 1),
      ),
      facts(
        [
          "Legal name (certificate of incorporation)",
          said("Kestrel Polymers Private Limited", ...at("doc-coi", 1)),
        ],
        ["CIN", said(CIN, ...at("doc-coi", 1))],
        ["Date of incorporation", said("12 Jun 2015", ...at("doc-coi", 1))],
        ["Company type", said("Company limited by shares", ...at("doc-coi", 1))],
        ["PAN", said(PAN, ...at("doc-cpan", 1))],
        ["GSTIN", said("27AAACK1234K1Z5 (Maharashtra)", ...at("doc-gstr3b", 1))],
        [
          "Registered office",
          said("Unit 7, Sector 3 industrial estate, Navi Mumbai 410208", ...at("doc-coi", 1)),
        ],
      ),
      note(
        "The entity PAN and the CIN differ between documents: see XV-000021-03 and XV-000021-04 in section 10.",
      ),
    ]),
    memoSection(3, "promoters", "Promoters and management", [
      table(
        ["Name", "Role", "DIN", "PAN", "KYC on file", "Named in"],
        [
          [
            "Kabir Rao",
            "Director",
            "08812345",
            said("ABCPR1234F", ...at("doc-pan", 1)),
            "Yes",
            "KYC received, Sourcing message",
          ],
          ["Leela Varghese", "Director", "—", "—", "No", "Sourcing message"],
        ],
      ),
      paragraph("No KYC has been received for Leela Varghese."),
    ]),
    memoSection(4, "proposal", "Proposal and facilities", [
      table(
        ["Facility", "Product"],
        [
          ["Cash credit", "Working capital"],
          ["Term loan", "Term loan"],
        ],
      ),
      paragraph(
        "The total amount requested is INR 50.00 lakh, with collateral offered. The sourcing message states annual turnover of INR 3.00 cr and does not state the purpose of the facilities.",
      ),
      note("The split of the amount between the facilities is not on file."),
    ]),
    memoSection(5, "financials", "Financial performance", [
      table(
        ["", "FY 2024-25 (audited)", "FY 2025-26 (audited)"],
        [
          [
            "Revenue from operations",
            said("INR 26.40 cr", ...bs(3)),
            said("INR 30.00 cr", ...bs(4)),
          ],
          ["Growth in revenue (%)", "—", "13.6%"],
          ["EBITDA", said("INR 1.85 cr", ...bs(3)), said("INR 0.90 cr", ...bs(4))],
          ["EBITDA margin (%)", "7.0%", "3.0%"],
          ["Profit after tax", said("INR 42.00 lakh", ...bs(3)), said("INR -40.00 lakh", ...bs(5))],
          ["PAT margin (%)", "1.6%", "-1.3%"],
          ["Net worth", said("INR 4.40 cr", ...bs(3)), said("INR 4.00 cr", ...bs(4))],
          ["Total borrowings", said("INR 9.80 cr", ...bs(3)), said("INR 12.00 cr", ...bs(4))],
          ["Current ratio", said("1.42x", ...bs(3)), said("1.50x", ...bs(4))],
          ["TOL / TNW", said("3.10x", ...bs(3)), said("3.75x", ...bs(4))],
          ["Debt / equity", said("2.23x", ...bs(3)), said("3.00x", ...bs(4))],
        ],
        { title: "Key financials", numeric: [1, 2] },
      ),
      paragraph(
        "Revenue from operations grew 13.6%, from INR 26.40 cr in FY 2024-25 to INR 30.00 cr in FY 2025-26.",
        ...bs(3),
        ...bs(4),
      ),
      paragraph(
        "The company made a loss after tax of INR 40.00 lakh in FY 2025-26, against a profit of INR 42.00 lakh the year before: a deviation from the norm of a profit in the latest year, see section 11.",
        ...bs(5),
        ...bs(3),
      ),
      paragraph(
        "Debt / equity rose to 3.00x against the norm of at most 2.00x, a deviation, see section 11. The current ratio of 1.50x is within the norm of at least 1.20x.",
        ...bs(4),
      ),
      note("Figures as on the spread (interim layout)."),
    ]),
    memoSection(6, "working_capital", "Assessment of working-capital requirement", [
      paragraph("The request is within INR 5.00 cr, so the turnover method applies."),
      table(
        ["Step", "Amount", "Basis"],
        [
          [
            "Turnover",
            said("INR 30.00 cr", ...bs(4)),
            "Revenue from operations, FY 2025-26 (audited)",
          ],
          ["Working-capital requirement", "INR 7.50 cr", "25% of turnover"],
          ["Margin", "INR 1.50 cr", "5% of turnover"],
          ["Eligible bank finance", "INR 6.00 cr", "Requirement less the margin"],
        ],
        { numeric: [1] },
      ),
      paragraph(
        "On the figures for FY 2025-26 (audited), eligible bank finance is INR 6.00 cr; the request of INR 50.00 lakh is within it.",
        ...bs(4),
      ),
      paragraph(
        "The proposed instalment of the term loan is not on file, so the DSCR on the proposal cannot be computed.",
      ),
    ]),
    memoSection(7, "turnover", "Turnover across sources (GST, income tax and banking)", [
      table(
        [
          "Financial year",
          "Audited",
          "GST outward supplies (GSTR-3B)",
          "Income tax return",
          "Business credits (bank)",
          "Declared",
        ],
        [
          [
            "FY 2025-26",
            said("INR 30.00 cr", ...bs(4)),
            said("INR 14.80 cr (8 of 12 months)", ...gstReturns()),
            "—",
            said("INR 25.62 cr", ...at("doc-bank", 3)),
            "INR 3.00 cr",
          ],
          [
            "FY 2024-25",
            said("INR 26.40 cr", ...bs(3)),
            "—",
            said("INR 26.10 cr", ...at("doc-itr", 2)),
            "—",
            "—",
          ],
        ],
        {
          numeric: [1, 2, 3, 4, 5],
          note: "Business credits exclude transfers between the borrower's own accounts, loan disbursals and reversals.",
        },
      ),
      paragraph(`XV-000021-05: ${GST_TEXT}`, ...at("doc-gstr3b", 1), ...at("doc-bank", 5)),
      paragraph(`XV-000021-07, found not valid: ${DECLARED_TEXT}`, ...bs(4)),
      paragraph(
        "GST returns (GSTR-3B) are on file for 8 months, Aug 2025 to Mar 2026; income tax returns for AY 2025-26. Every audited year that is due has its return on file (TX-01).",
        ...gstReturns(),
        ...at("doc-itr", 1),
      ),
    ]),
    memoSection(8, "banking", "Banking and account conduct", [
      table(
        ["Account", "Months", "Gross credits", "Excluded", "Business credits", "Average a month"],
        [
          [
            ACCOUNT,
            "12",
            said("INR 27.95 cr", ...at("doc-bank", 3)),
            said("INR 2.33 cr", ...at("doc-bank", 7)),
            "INR 25.62 cr",
            "INR 2.14 cr",
          ],
        ],
        { numeric: [1, 2, 3, 4, 5] },
      ),
      paragraph(
        "Excluded from the credits: a loan disbursal of INR 25.00 lakh (TL 7781) on 06 Apr 2025, transfers between the borrower's own accounts of INR 1.73 cr and reversals of INR 35.00 lakh.",
        ...at("doc-bank", 7),
      ),
      paragraph(
        "No statements have been received for Lotuscrest Bank ·5678, declared in the sourcing message: see XV-000021-06.",
      ),
      paragraph(
        `${DISBURSAL_TEXT} No instalment of that loan is seen in the statements.`,
        ...at("doc-bank", 7),
      ),
    ]),
    memoSection(9, "obligations", "Existing facilities and obligations", [
      table(
        [
          "Lender",
          "Facility",
          "Declared",
          "Sanction letter",
          "Bureau",
          "Instalment",
          "Seen in the bank (a month)",
        ],
        [
          [
            "Tidewater Finance",
            "Term loan",
            said("INR 40.00 lakh", ...at("doc-decl", 1)),
            said("INR 55.00 lakh", ...at("doc-sanction", 1)),
            said("INR 55.00 lakh; outstanding INR 38.00 lakh", ...at("doc-bureau", 2)),
            said("INR 92,000", ...at("doc-decl", 1)),
            said("INR 92,000 (12 months)", ...at("doc-bank", 7)),
          ],
          [
            "ASHWOOD FINSERV",
            "—",
            "Not declared",
            "—",
            "—",
            "—",
            said("INR 1,45,000 (6 months)", ...at("doc-bank", 7)),
          ],
          [
            "Lotuscrest Bank",
            "Cash credit",
            "Not declared",
            "—",
            said("INR 1.20 cr; outstanding INR 95.00 lakh", ...at("doc-bureau", 3)),
            "—",
            "—",
          ],
        ],
        { numeric: [2, 3, 4, 5, 6] },
      ),
      paragraph("The commercial bureau rank is not on file."),
      paragraph(
        "Existing sanctioned exposure is INR 1.75 cr as the bureau reports it; the bureau shows no overdues.",
        ...at("doc-bureau", 2),
        ...at("doc-bureau", 3),
      ),
      paragraph(
        "Regular debits of about INR 1,45,000 a month go to ASHWOOD FINSERV, a lender that has not been declared: see XV-000021-01.",
        ...at("doc-bank", 7),
      ),
    ]),
    memoSection(10, "verification", "Cross-verification of sources", [
      table(
        ["Area", "Checks", "Discrepancies", "Accepted", "Open", "Could not be completed"],
        [
          ["Identity consistency", "8", "2", "0", "2", "1"],
          ["Turnover", "5", "2", "0", "1", "3"],
          ["Bank accounts", "2", "1", "1", "0", "0"],
          ["Existing obligations", "3", "2", "0", "2", "0"],
        ],
        { title: "By area", numeric: [1, 2, 3, 4, 5] },
      ),
      table(
        ["Check", "Why", "What would complete it"],
        [
          [
            "ID-04 Promoters match the KYC received",
            "Director KYC not on file.",
            "The director KYC",
          ],
          [
            "TO-01 Audited turnover against GST outward supplies · FY 2025-26",
            said(
              "GST outward supplies covers 8 of 12 months (Apr 2025 to Jul 2025 absent).",
              ...at("doc-gstr3b", 1),
            ),
            "GSTR-3B returns for Apr 2025 to Jul 2025",
          ],
        ],
        { title: "Checks not completed" },
      ),
      table(
        ["Ref", "Severity", "Finding", "Detail", "Status"],
        [
          [
            "XV-000021-03",
            "Serious",
            "Entity PAN differs between documents",
            said(PAN_TEXT, ...at("doc-cpan", 1), ...at("doc-bureau", 1)),
            "Open · blocks submission",
          ],
          [
            "XV-000021-04",
            "Serious",
            "CIN differs between documents",
            said(CIN_TEXT, ...at("doc-coi", 1), ...at("doc-moa", 2)),
            "Open · blocks submission",
          ],
          [
            "XV-000021-05",
            "Moderate",
            "GST and bank credits diverge over the months both cover",
            said(GST_TEXT, ...at("doc-gstr3b", 1), ...at("doc-bank", 5)),
            "Open",
          ],
          [
            "XV-000021-07",
            "Mild",
            "Declared turnover differs from the evidence",
            said(DECLARED_TEXT, ...bs(4)),
            "Not valid",
          ],
          [
            "XV-000021-06",
            "Moderate",
            "Declared account without a statement",
            said(ACCOUNT_TEXT, ...at("doc-bank", 3)),
            "Accepted as valid",
          ],
          [
            "XV-000021-01",
            "Serious",
            "Instalments to a lender that was not declared",
            said(LENDER_TEXT, ...at("doc-bank", 7)),
            "Open",
          ],
          [
            "XV-000021-02",
            "Serious",
            "Existing facilities do not reconcile",
            said(
              FACILITIES_TEXT,
              ...at("doc-decl", 1),
              ...at("doc-sanction", 1),
              ...at("doc-bureau", 2),
            ),
            "Escalated",
          ],
        ],
        { title: "Discrepancies" },
      ),
    ]),
    memoSection(11, "policy", "Compliance with policy norms", [
      table(
        ["Norm", "Required", "Actual", "Result", "Category"],
        [
          [
            "EL-04 Profit in the latest year",
            "no loss",
            said("INR -40.00 lakh", ...bs(5)),
            "Deviation",
            "Eligibility",
          ],
          ["EL-02 Commercial bureau rank", "at most rank 6", "—", "Not assessed", "Eligibility"],
          [
            "FR-01 Current ratio",
            "at least 1.20x",
            said("1.50x", ...bs(4)),
            "Met",
            "Financial norms",
          ],
          ["FR-04 Interest coverage", "at least 2.50x", "—", "Not assessed", "Financial norms"],
          [
            "FR-05 Debt / equity",
            "at most 2.00x",
            said("3.00x", ...bs(4)),
            "Deviation",
            "Financial norms",
          ],
          [
            "FR-06 Working-capital cycle",
            "at most 75 days",
            "—",
            "Not assessed",
            "Financial norms",
          ],
          ["DOC-01 Blocking checklist items open", "none", "2", "Deviation", "Documentation"],
        ],
        { numeric: [2] },
      ),
      paragraph(
        "Profit in the latest year is INR -40.00 lakh against a norm of no loss (Eligibility).",
        ...bs(5),
      ),
      paragraph(
        "Debt / equity is 3.00x against a norm of at most 2.00x (Financial norms).",
        ...bs(4),
      ),
      paragraph("Blocking checklist items open: 2 against a norm of none (Documentation)."),
      paragraph(
        "Commercial bureau rank could not be assessed: Commercial bureau rank not on file.",
      ),
      paragraph("Interest coverage could not be computed: Finance costs is zero.", ...bs(5)),
      paragraph(
        "Working-capital cycle could not be assessed: Trade receivables awaits review.",
        ...bs(4),
      ),
      subheading("Approving authority"),
      facts(
        [
          "Amount",
          "Credit Officer: working capital up to INR 2.00 cr, term loan up to INR 1.00 cr",
        ],
        ["Eligibility deviation (EL-04)", "One level above, at least Regional Credit Head"],
        ["Financial norms deviation (FR-05)", "One level above: Regional Credit Head"],
        ["Documentation deviation (DOC-01)", "One level above: Regional Credit Head"],
        ["Authority required", "At least Regional Credit Head"],
        ["Could rise to", "Regional Credit Head, once EL-02, FR-04 and FR-06 are assessed"],
        ["Matrix", "Provisional matrix"],
      ),
    ]),
    memoSection(12, "documentation", "Documentation status", [
      facts(["Readiness", "58% against the 85% gate"], ["Blocking items open", "2"]),
      table(
        ["Item", "Status", "What is missing"],
        [
          [
            "Valuation report",
            "Missing",
            "Valuation report for the property offered as collateral.",
          ],
          ["Board resolution", "Insufficient", "Unsigned: the copy provided is not signed."],
          [
            "KYC of directors",
            "Missing",
            "1 of 2 directors (Leela Varghese): PAN and address proof.",
          ],
          [
            "Provisional financial statements FY26",
            "Insufficient",
            "Incomplete: balance sheet pages absent.",
          ],
          ["GST returns (12 months)", "Insufficient", "Period gap: April to July 2025 absent."],
          [
            "Stock statement",
            "Insufficient",
            "Outdated: dated 31 Jan 2026; permitted age 60 days from 20 Sep 2026.",
          ],
        ],
      ),
      paragraph("Outdated documents: the stock statement dated 31 Jan 2026."),
    ]),
  ]),
  summary_number: 7,
  summary_title: "Risk Assessment and Rating",
  summary_purpose: "The findings, deviations and open queries the risk rests on, and the rating.",
  rating_note: "Not rated: RBL's rating model is not configured.",
  // The findings as a register (their explanations are in section 10), the checks that could not
  // be completed with what would complete them, the deviations, the norms not assessed and the
  // open queries by group.
  summary: [
    summaryItem("finding", "XV-000021-03", "", {
      severity: "serious",
      rule: "ID-01",
      title: "Entity PAN differs between documents",
      status: "Open",
      blocking: true,
      citations: [...at("doc-cpan", 1), ...at("doc-bureau", 1)],
    }),
    summaryItem("finding", "XV-000021-04", "", {
      severity: "serious",
      rule: "ID-05",
      title: "CIN differs between documents",
      status: "Open",
      blocking: true,
      citations: [...at("doc-coi", 1), ...at("doc-moa", 2)],
    }),
    summaryItem("finding", "XV-000021-05", "", {
      severity: "moderate",
      rule: "TO-05",
      title: "GST and bank credits diverge over the months both cover",
      status: "Open",
      citations: [...gstReturns(), ...at("doc-bank", 5)],
    }),
    summaryItem("finding", "XV-000021-06", "", {
      severity: "moderate",
      rule: "BA-01",
      title: "Declared account without a statement",
      status: "Accepted as valid",
      citations: at("doc-bank", 3),
    }),
    summaryItem("finding", "XV-000021-01", "", {
      severity: "serious",
      rule: "OB-02",
      title: "Instalments to a lender that was not declared",
      status: "Open",
      citations: at("doc-bank", 7),
    }),
    summaryItem("finding", "XV-000021-02", "", {
      severity: "serious",
      rule: "OB-01",
      title: "Existing facilities do not reconcile",
      status: "Escalated",
      citations: [...at("doc-decl", 1), ...at("doc-sanction", 1), ...at("doc-bureau", 2)],
    }),
    summaryItem("incomplete", "ID-04", "Director KYC not on file.", {
      severity: "serious",
      rule: "ID-04",
      title: "Promoters match the KYC received",
      request: "the director KYC",
    }),
    summaryItem(
      "incomplete",
      "TO-01",
      "GST outward supplies covers 8 of 12 months (Apr 2025 to Jul 2025 absent).",
      {
        severity: "moderate",
        rule: "TO-01",
        title: "Audited turnover against GST outward supplies · FY 2025-26",
        request: "GSTR-3B returns for Apr 2025 to Jul 2025",
        citations: at("doc-gstr3b", 1),
      },
    ),
    summaryItem(
      "deviation",
      "EL-04",
      "Eligibility: Profit in the latest year INR -40.00 lakh against no loss.",
      { rule: "EL-04", title: "Profit in the latest year", citations: bs(5) },
    ),
    summaryItem(
      "deviation",
      "FR-05",
      "Financial norms: Debt / equity 3.00x against at most 2.00x.",
      {
        rule: "FR-05",
        title: "Debt / equity",
        citations: bs(4),
      },
    ),
    summaryItem(
      "deviation",
      "DOC-01",
      "Documentation: Blocking checklist items open 2 against none.",
      { rule: "DOC-01", title: "Blocking checklist items open" },
    ),
    summaryItem(
      "unassessed",
      "EL-02",
      "The commercial bureau report is not on file, so the bureau rank could not be assessed.",
      { rule: "EL-02", title: "Commercial bureau rank" },
    ),
    summaryItem(
      "unassessed",
      "FR-04",
      "Interest coverage could not be computed: Finance costs is zero.",
      {
        rule: "FR-04",
        title: "Interest coverage",
        citations: bs(5),
      },
    ),
    summaryItem(
      "unassessed",
      "FR-06",
      "Working-capital cycle could not be assessed: Trade receivables awaits review.",
      { rule: "FR-06", title: "Working-capital cycle", citations: bs(4) },
    ),
    summaryItem("query", "q1", "KYC of Leela Varghese: PAN and address proof.", {
      group: "documents_needed",
    }),
    summaryItem("query", "q2", "Valuation report for the property offered as collateral.", {
      group: "documents_needed",
    }),
    summaryItem("query", "q3", "GST returns (GSTR-3B) for April to July 2025.", {
      group: "documents_needed",
    }),
    summaryItem("query", "q4", "Board resolution: the copy provided is not signed.", {
      group: "documents_to_redo",
    }),
    summaryItem(
      "query",
      "q5",
      "Stock statement dated within the last 60 days (latest is 31 Jan 2026).",
      { group: "documents_to_redo" },
    ),
    summaryItem(
      "query",
      "q7",
      "Bank statements show a monthly EMI of INR 1,45,000 to a lender not in the declaration of existing facilities. Please explain.",
      { group: "clarifications", citations: at("doc-bank", 7) },
    ),
  ],
  recommendation_number: 8,
  recommendation_title: "Recommendation",
  recommendation_purpose: "The analyst's recommendation to the approving authority.",
  recommendation: "",
  recommendation_prompts: [
    "Recommendation",
    "Terms and conditions",
    "Deviations recommended for approval",
    "Decision of the approving authority",
  ],
  sign_off: [{ role: "Prepared by" }, { role: "Recommended by" }, { role: "Approved by" }],
  sources: [
    source(1, "doc-coi", "Certificate of incorporation", "coi.pdf", [1]),
    source(2, "doc-cpan", "Company PAN", "company_pan.pdf", [1]),
    source(3, "doc-gstr3b", "GSTR-3B · Aug 2025", "gstr3b_aug25.pdf", [1]),
    source(4, "doc-pan", "PAN (individual) · Kabir Rao", "director1_pan.jpg", [1]),
    source(
      5,
      "doc-bs",
      "Audited financial statements · FY 2025-26",
      "bank stmt apr-mar.pdf",
      [3, 4, 5],
    ),
    ...GST_RETURNS.slice(1).map(([id, month, file], i) =>
      source(6 + i, id, `GSTR-3B · ${month}`, file, [1]),
    ),
    source(13, "doc-bank", "Bank statement · Lotuscrest Bank ·1234", "merged_docs.pdf", [3, 5, 7]),
    source(14, "doc-itr", "Income tax return · AY 2025-26", "itr_ay2025-26.pdf", [1, 2]),
    source(
      15,
      "doc-decl",
      "Declaration of existing facilities",
      "existing_facilities_declaration.pdf",
      [1],
    ),
    source(
      16,
      "doc-sanction",
      "Sanction letter · Tidewater Finance",
      "sanction_tidewater.pdf",
      [1],
    ),
    source(17, "doc-bureau", "Commercial bureau report", "bureau_report.pdf", [1, 2, 3]),
    source(18, "doc-moa", "Memorandum and articles of association", "moa_aoa.pdf", [2]),
  ],
};

// The PD question note for Kestrel, as engine/pd_note.py composes it: the questions by topic,
// most serious first within each, numbered across the note; each with the finding, deviation,
// gap or memo observation it comes from and its pages.

const pdQuestion = (
  q: Pick<
    PdQuestion,
    | "id"
    | "number"
    | "question"
    | "context"
    | "severity"
    | "source"
    | "ref"
    | "rule"
    | "title"
    | "area"
  > &
    Partial<PdQuestion>,
): PdQuestion => ({
  xv_ref: null,
  status: null,
  evidence: [],
  target:
    q.source === "deviation" ? "policy" : q.source === "observation" ? "cam" : "cross_verification",
  text: `${q.context} ${q.question}`,
  ...q,
});

export const PD_NOTE: PdNote = {
  case_id: KESTREL,
  title: "Personal discussion — question note",
  borrower: "Kestrel Polymers Pvt Ltd",
  as_of: "2026-09-20",
  config_version: OUTPUT_CONFIG_VERSION,
  config_label: OUTPUT_CONFIG_LABEL,
  header: [
    { label: "Borrower", value: said("Kestrel Polymers Pvt Ltd") },
    { label: "Case ID", value: said(KESTREL) },
    { label: "Constitution", value: said("Private limited company") },
    { label: "Proposal", value: said("Cash credit and term loan, INR 50.00 lakh") },
    { label: "Data as of", value: said("20 Sep 2026") },
    { label: "Configuration", value: said(OUTPUT_CONFIG_LABEL) },
  ],
  people: [
    {
      name: "Kabir Rao",
      role: "Director",
      din: "08812345",
      sources: ["KYC received", "Memorandum and articles of association", "Sourcing message"],
      evidence: [...at("doc-moa", 2), ...at("doc-br", 1)],
    },
    {
      name: "Leela Varghese",
      role: "Director",
      din: null,
      sources: ["Memorandum and articles of association", "Sourcing message"],
      evidence: at("doc-moa", 2),
    },
  ],
  questions: [
    pdQuestion({
      id: "pdq-id1",
      number: 1,
      area: "identity",
      severity: "serious",
      source: "finding",
      ref: "fnd-id1",
      xv_ref: "XV-000021-03",
      rule: "ID-01",
      title: "Entity PAN differs between documents",
      status: "Open",
      question: "Which PAN is the company's, and has the bureau been asked to correct its record?",
      context: PAN_TEXT,
      evidence: [...at("doc-cpan", 1), ...at("doc-bureau", 1)],
    }),
    pdQuestion({
      id: "pdq-id5",
      number: 2,
      area: "identity",
      severity: "serious",
      source: "finding",
      ref: "fnd-id5",
      xv_ref: "XV-000021-04",
      rule: "ID-05",
      title: "CIN differs between documents",
      status: "Open",
      question:
        "Which CIN is correct, and can a corrected memorandum and articles of association be provided?",
      context: CIN_TEXT,
      evidence: [...at("doc-coi", 1), ...at("doc-moa", 2)],
    }),
    pdQuestion({
      id: "pdq-id4",
      number: 3,
      area: "identity",
      severity: "mild",
      source: "gap",
      ref: "fnd-id4",
      rule: "ID-04",
      title: "Promoter missing from a source",
      question: "When will the KYC of Leela Varghese, director, be provided?",
      context: "Director KYC not on file: no KYC has been received for Leela Varghese.",
    }),
    pdQuestion({
      id: "pdq-to5",
      number: 4,
      area: "turnover",
      severity: "moderate",
      source: "finding",
      ref: "fnd-to5",
      xv_ref: "XV-000021-05",
      rule: "TO-05",
      title: "GST and bank credits diverge over the months both cover",
      status: "Open",
      question:
        "What explains business credits of INR 17.19 cr against GST outward supplies of INR 14.80 cr over the same months?",
      context: GST_TEXT,
      evidence: [...at("doc-gstr3b", 1), ...at("doc-bank", 5)],
    }),
    pdQuestion({
      id: "pdq-to1",
      number: 5,
      area: "turnover",
      severity: "mild",
      source: "gap",
      ref: "fnd-to1",
      rule: "TO-01",
      title: "Audited turnover differs from GST returns",
      question:
        "Can the following be provided before sanction: GSTR-3B returns for Apr 2025 to Jul 2025?",
      context:
        "Could not be checked: audited turnover against GST outward supplies; GST outward supplies against cleansed bank credits.",
      evidence: at("doc-gstr3b", 1),
      also: [
        {
          ref: "fnd-to2",
          xv_ref: null,
          rule: "TO-02",
          title: "GST turnover not supported by bank credits",
          status: null,
          evidence: [],
        },
      ],
    }),
    pdQuestion({
      id: "pdq-ba1",
      number: 6,
      area: "accounts",
      severity: "moderate",
      source: "finding",
      ref: "fnd-ba1",
      xv_ref: "XV-000021-06",
      rule: "BA-01",
      title: "Declared account without a statement",
      status: "Accepted as valid",
      question:
        "What is the Lotuscrest Bank account ending 5678 used for, and can its statements for the last 12 months be provided?",
      context: ACCOUNT_TEXT,
      evidence: at("doc-bank", 3),
    }),
    pdQuestion({
      id: "pdq-ob2",
      number: 7,
      area: "obligations",
      severity: "serious",
      source: "finding",
      ref: "fnd-ob2",
      xv_ref: "XV-000021-01",
      rule: "OB-02",
      title: "Instalments to a lender that was not declared",
      status: "Open",
      question:
        "What are the monthly payments of INR 1,45,000 to ASHWOOD FINSERV for, and why is that facility not in the declaration?",
      context: LENDER_TEXT,
      evidence: at("doc-bank", 7),
    }),
    pdQuestion({
      id: "pdq-ob1",
      number: 8,
      area: "obligations",
      severity: "serious",
      source: "finding",
      ref: "fnd-ob1",
      xv_ref: "XV-000021-02",
      rule: "OB-01",
      title: "Existing facilities do not reconcile",
      status: "Escalated",
      question:
        "What is the sanctioned amount of the Tidewater Finance term loan, and why does the declaration show INR 40.00 lakh?",
      context: FACILITIES_TEXT,
      evidence: [...at("doc-decl", 1), ...at("doc-sanction", 1), ...at("doc-bureau", 2)],
    }),
    pdQuestion({
      id: "pdq-obs1",
      number: 9,
      area: "obligations",
      severity: "moderate",
      source: "observation",
      ref: "banking:loan-disbursal",
      rule: "OBS",
      title: "Loan disbursal no facility explains",
      // The memo section that states it, as the engine names it.
      status: "section 8",
      question:
        "Which lender disbursed the INR 25.00 lakh on 06 Apr 2025, on what terms, and why is no instalment seen?",
      context: DISBURSAL_TEXT,
      evidence: at("doc-bank", 7),
    }),
    pdQuestion({
      id: "pdq-el04",
      number: 10,
      area: "policy",
      severity: "serious",
      source: "deviation",
      ref: "EL-04",
      rule: "EL-04",
      title: "Profit in the latest year",
      question:
        "What caused the loss in FY 2025-26, and what are the results for the current year so far?",
      context:
        "Profit in the latest year is INR -40.00 lakh against a norm of at least INR 0 (Eligibility).",
      evidence: bs(5),
    }),
    pdQuestion({
      id: "pdq-fr05",
      number: 11,
      area: "policy",
      severity: "moderate",
      source: "deviation",
      ref: "FR-05",
      rule: "FR-05",
      title: "Debt / equity",
      question: "How will borrowings be brought within the norm of debt / equity at most 2.00x?",
      context: "Debt / equity is 3.00x against a norm of at most 2.00x (Financial norms).",
      evidence: bs(4),
    }),
  ],
  topics: [
    {
      area: "identity",
      title: "Identity and KYC",
      question_ids: ["pdq-id1", "pdq-id5", "pdq-id4"],
    },
    { area: "turnover", title: "Turnover, tax and sales", question_ids: ["pdq-to5", "pdq-to1"] },
    { area: "accounts", title: "Bank accounts", question_ids: ["pdq-ba1"] },
    {
      area: "obligations",
      title: "Existing borrowings",
      question_ids: ["pdq-ob2", "pdq-ob1", "pdq-obs1"],
    },
    { area: "policy", title: "Policy norms", question_ids: ["pdq-el04", "pdq-fr05"] },
  ],
  documents_to_collect: [
    said("KYC of Leela Varghese: PAN and address proof."),
    said("Valuation report for the property offered as collateral."),
    said("GST returns (GSTR-3B) for April to July 2025."),
    said("Board resolution: the copy provided is not signed.", ...at("doc-br", 1)),
    said("Stock statement dated within the last 60 days (latest is 31 Jan 2026)."),
  ],
  record_fields: [
    "Date of discussion",
    "Place",
    "Bank officials present",
    "Promoters or representatives present",
  ],
  sign_off: [{ role: "Discussion held by" }],
  sources: [
    source(1, "doc-cpan", "Company PAN", "company_pan.pdf", [1]),
    source(2, "doc-bureau", "Commercial bureau report", "bureau_report.pdf", [1, 2]),
    source(3, "doc-coi", "Certificate of incorporation", "coi.pdf", [1]),
    source(4, "doc-moa", "Memorandum and articles of association", "moa_aoa.pdf", [2]),
    source(5, "doc-gstr3b", "GSTR-3B · Aug 2025", "gstr3b_aug25.pdf", [1]),
    source(6, "doc-bank", "Bank statement · Lotuscrest Bank ·1234", "merged_docs.pdf", [3, 5, 7]),
    source(
      7,
      "doc-decl",
      "Declaration of existing facilities",
      "existing_facilities_declaration.pdf",
      [1],
    ),
    source(8, "doc-sanction", "Sanction letter · Tidewater Finance", "sanction_tidewater.pdf", [1]),
    source(
      9,
      "doc-bs",
      "Audited financial statements · FY 2025-26",
      "bank stmt apr-mar.pdf",
      [4, 5],
    ),
    source(10, "doc-br", "Board resolution", "board_resolution.pdf", [1]),
  ],
};

/** What the download endpoints answer: a few bytes of each kind of file. */
export const DOWNLOAD_BYTES = {
  docx: Buffer.from("PK\u0003\u0004 CreditIQ draft", "latin1"),
  pdf: Buffer.from("%PDF-1.4\n% CreditIQ draft\n%%EOF\n", "latin1"),
};

export const CONFIG_VERSIONS = [
  {
    version: "v2hash",
    author: "Config Admin",
    note: "Tighten the review gate",
    published_at: "2026-10-01T09:30:00+00:00",
    prior_version: "v1hash",
    sections_changed: ["policy", "ingestion.fields"],
    current: true,
  },
  {
    version: "v1hash",
    author: "Config Admin",
    note: "",
    published_at: "2026-09-20T09:30:00+00:00",
    prior_version: null,
    sections_changed: ["policy", "checklist_taxonomy"],
    current: false,
  },
];

/** The settings an Administrator edits, as the version in force has them (GET /api/admin/settings). */
export const SETTINGS: EditableSettings = {
  version: "v2hash",
  published_at: "2026-10-01T09:30:00+00:00",
  author: "Config Admin",
  origin: "cli",
  tolerances: [
    {
      key: "turnover_variance",
      label: "Turnover variance between sources",
      value: 1,
      unit: "%",
      source: "provisional",
      rules: ["TO-02"],
    },
    {
      key: "declared_turnover_variance",
      label: "RM-declared against evidenced turnover",
      value: 2,
      unit: "%",
      source: "provisional",
      rules: ["TO-04"],
    },
    {
      key: "name_match",
      label: "Minimum name similarity to treat two names as one",
      value: 0.9,
      unit: "ratio",
      source: "provisional",
      rules: ["ID-01"],
    },
    {
      key: "itr_due_days",
      label: "Days after a financial year ends before its income tax return is expected",
      value: 214,
      unit: "days",
      source: "provisional",
      rules: [],
    },
  ],
  ratios: [
    {
      key: "current-ratio",
      label: "Current ratio",
      unit: "x",
      kind: "min",
      acceptable: 1.2,
      marginal: 1.1,
      norms: ["FR-01"],
    },
    {
      key: "tol-tnw",
      label: "TOL / TNW",
      unit: "x",
      kind: "max",
      acceptable: 3,
      marginal: 3.75,
      norms: ["FR-02"],
    },
  ],
  norms: [
    {
      id: "EL-01",
      family: "eligibility",
      label: "Business vintage",
      unit: "years",
      kind: "min",
      threshold: 3,
    },
    {
      id: "EL-05",
      family: "eligibility",
      label: "Total request against turnover",
      unit: "%",
      kind: "max",
      threshold: 20,
    },
    {
      id: "DOC-01",
      family: "documentation",
      label: "Blocking checklist items open",
      unit: "count",
      kind: "max",
      threshold: 0,
    },
  ],
  rules: [
    {
      id: "ID-01",
      title: "Entity PAN consistent across documents",
      area: "identity",
      severity: "serious",
      blocking: true,
      enabled: true,
    },
    {
      id: "BR-01",
      title: "Board resolution covers the amount requested",
      area: "authority",
      severity: "serious",
      blocking: true,
      enabled: false,
    },
    {
      id: "TO-02",
      title: "GST outward supplies against cleansed bank credits",
      area: "turnover",
      severity: "moderate",
      blocking: false,
      enabled: true,
    },
    {
      id: "TO-04",
      title: "RM-declared turnover against evidenced turnover",
      area: "turnover",
      severity: "mild",
      blocking: false,
      enabled: true,
    },
  ],
  matrix: {
    status: "provisional",
    authorities: [
      { key: "credit_officer", level: 1, label: "Credit Officer" },
      { key: "regional_credit_head", level: 2, label: "Regional Credit Head" },
      { key: "zonal_credit_committee", level: 3, label: "Zonal Credit Committee" },
    ],
    products: [
      {
        key: "working_capital",
        label: "Working capital",
        bands: [
          { up_to_inr: 20_000_000, authority: "credit_officer" },
          { up_to_inr: 50_000_000, authority: "regional_credit_head" },
          { up_to_inr: null, authority: "zonal_credit_committee" },
        ],
      },
      {
        key: "term",
        label: "Term loan",
        bands: [
          { up_to_inr: 10_000_000, authority: "credit_officer" },
          { up_to_inr: null, authority: "regional_credit_head" },
        ],
      },
    ],
    deviations: [
      {
        category: "eligibility",
        label: "Eligibility",
        levels_above: 1,
        at_least: "regional_credit_head",
      },
      { category: "financial", label: "Financial norms", levels_above: 1, at_least: null },
    ],
  },
};

export const USERS = [ANALYST, RM].map((u) => ({
  id: u.id,
  name: u.name,
  role: u.role,
  roleLabel: u.roleLabel,
  email: u.email,
  branch: u.branch,
  permissions: u.permissions,
}));

export const AUDIT = {
  entries: [
    {
      seq: 2,
      at: "2026-10-02T10:00:00+00:00",
      actor: "ananya-krishnan",
      actor_name: "Ananya Krishnan",
      case_id: "BBG-2026-000021",
      action: "review.decided",
      detail: { decision: "confirm", item_id: "x" },
    },
    {
      seq: 1,
      at: "2026-10-02T09:00:00+00:00",
      actor: "ananya-krishnan",
      actor_name: "Ananya Krishnan",
      case_id: null,
      action: "session.signed_in",
      detail: {},
    },
  ],
  next_before: null,
  actors: ["ananya-krishnan"],
  actions: ["review.decided", "session.signed_in"],
};

export const POLICY_CONFIG = {
  working_capital: {
    mpbf_above_limit_inr: 50_000_000,
    source: "provisional",
    status: "provisional",
    turnover_requirement_pct: 25,
    turnover_margin_pct: 5,
    mpbf_margin_pct: 25,
  },
  ratios: [
    {
      key: "dscr",
      label: "Debt service coverage",
      unit: "x",
      kind: "min",
      acceptable: 1.25,
      marginal: 1.1,
      formula: "(PAT + depreciation) / instalments",
      applies: "term debt",
      source: "provisional",
      status: "provisional",
      note: "Interim threshold.",
      hard_floor: null,
    },
  ],
  deviation_categories: [{ key: "financial", label: "Financial norms" }],
  norms: [
    {
      id: "FR-01",
      family: "ratios",
      expression: "x",
      ratio: "dscr",
      category: "financial",
      applies_when: "always",
      non_positive_denominator: "cannot_evaluate",
      pd_gap: "ask",
    },
    {
      id: "EL-01",
      family: "eligibility",
      expression: "x",
      label: "Business vintage",
      unit: "years",
      kind: "min",
      threshold: 3,
      category: "financial",
      applies_when: "always",
      non_positive_denominator: "cannot_evaluate",
      pd_gap: "ask",
      status: "active",
    },
  ],
} satisfies PolicyConfig;
