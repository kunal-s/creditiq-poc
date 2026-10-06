/// <reference types="node" />
// Fixture data for the screen tests, typed against the generated API
// contract (src/api/types.ts). Every name here is fictional and was checked
// against the excluded-terms list.
import type {
  Cam,
  CaseDetail,
  CaseFacts,
  Finding,
  PdNote,
  PolicyAssessment,
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
  QueryItem,
  Readiness,
  ReviewItem,
  SessionUser,
  Spread,
  Span,
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
  navGroups: ["workbench", "governance"],
  permissions: [
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
  navGroups: ["workbench"],
  permissions: [
    "case.create",
    "case.read",
    "case.delete",
    "document.upload",
    "checklist.read",
    "query.read",
  ],
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

export const DOCUMENT_TYPES: DocumentTypes = {
  types: [
    ["pan_individual", "PAN (individual)", "kyc"],
    ["gst_registration", "GST registration", "registration"],
    ["bank_statement", "Bank statement", "banking"],
    ["balance_sheet", "Balance sheet", "financials"],
    ["board_resolution", "Board resolution", "constitution"],
    ["itr_ack", "ITR acknowledgement", "tax"],
    ["utility_bill", "Utility bill", "other_known"],
  ].map(([id, name, group]) => ({
    id: id!,
    name: name!,
    group: group as DocumentTypes["types"][number]["group"],
    description: `${name}.`,
    instance_key: "none" as const,
    partner_output: false,
    personal: group === "kyc",
    satisfies: [],
  })),
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
    created_at: "2026-09-21T09:05:00Z",
  },
  {
    id: "r-field",
    case_id: KESTREL,
    kind: "field",
    ref: "field:fv-credits-jun",
    summary: "Bank statement ·1234 Jun 25: credits (0.62)",
    status: "open",
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

export const FINDINGS: Finding[] = [
  {
    id: "fnd-ob2",
    case_id: KESTREL,
    rule_id: "OB-02",
    title: "Instalments in bank statements go to declared lenders",
    outcome: "fail",
    severity: "serious",
    blocking: true,
    explanation:
      "Regular debits to lender(s) not declared: ASHWOOD FINSERV (₹1,45,000 a month in 6 months, Lotuscrest Bank ·1234).",
    sides: [
      {
        label: "Instalments in bank statements",
        value: "ASHWOOD FINSERV (₹1,45,000 × 6)",
        evidence: [{ document_id: "doc-bank", page: 7 }],
        relies_on_manual: false,
      },
      {
        label: "Declared facilities",
        value: "none",
        evidence: [{ document_id: "doc-bs", page: 4 }],
        relies_on_manual: false,
      },
    ],
    tolerance: "5%",
    config_version: "v1",
    run_id: null,
    query: "Please explain the regular debits to ASHWOOD FINSERV.",
  },
  {
    id: "fnd-to1",
    case_id: KESTREL,
    rule_id: "TO-01",
    title: "Audited turnover against GST outward supplies · FY 2025-26",
    outcome: "incomplete",
    severity: "moderate",
    blocking: false,
    explanation:
      "GST outward supplies covers 8 of 12 months (Apr 2025, May 2025, Jun 2025… absent).",
    sides: [],
    tolerance: "10%",
    config_version: "v1",
    run_id: null,
    query: null,
  },
  {
    id: "fnd-id1",
    case_id: KESTREL,
    rule_id: "ID-01",
    title: "Entity PAN consistent across documents",
    outcome: "pass",
    severity: "serious",
    blocking: true,
    explanation: "Consistent across 4 sources.",
    sides: [],
    tolerance: null,
    config_version: "v1",
    run_id: null,
    query: null,
  },
];

export const FINDING_ITEM: ReviewItem = {
  id: "r-finding",
  case_id: KESTREL,
  kind: "finding",
  ref: "finding:fnd-ob2",
  summary: "OB-02 Instalments in bank statements go to declared lenders",
  status: "open",
  created_at: "2026-09-21T09:07:00Z",
};

export const FACTS: CaseFacts = {
  case_id: KESTREL,
  identities: { entity_pan: [], gstin: [], legal_name: [] },
  persons: [],
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
          evidence: [{ document_id: "doc-gst", page: 1 }],
          field_ids: [],
          relies_on_manual: false,
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
  facilities: [],
  declaration_received: true,
};

// --- Policy norms (F-20) ---

export const POLICY: PolicyAssessment = {
  case_id: KESTREL,
  period: "FY 2025-26",
  norms: [
    {
      id: "FR-05",
      family: "ratios",
      label: "Debt / equity",
      formula: "Total debt ÷ Tangible net worth",
      required: "at most 2.00x",
      actual: 3,
      unit: "x",
      outcome: "deviation",
      category: "financial",
      category_label: "Financial norms",
      inputs: [
        {
          name: "total_borrowings",
          label: "Total borrowings",
          value: 120_000_000,
          evidence: [{ document_id: "doc-bs", page: 4 }],
          relies_on_manual: false,
        },
        {
          name: "net_worth",
          label: "Net worth",
          value: 40_000_000,
          evidence: [{ document_id: "doc-bs", page: 4 }],
          relies_on_manual: false,
        },
      ],
      missing: [],
      note: null,
      provisional: true,
    },
    {
      id: "EL-02",
      family: "eligibility",
      label: "Commercial bureau rank",
      formula: "Commercial bureau rank",
      required: "at most rank 6",
      actual: null,
      unit: "rank",
      outcome: "cannot_evaluate",
      category: "eligibility",
      category_label: "Eligibility",
      inputs: [],
      missing: ["Commercial bureau rank"],
      note: null,
      provisional: true,
    },
    {
      id: "FR-01",
      family: "ratios",
      label: "Current ratio",
      formula: "Current assets ÷ Current liabilities",
      required: "at least 1.20x",
      actual: 1.5,
      unit: "x",
      outcome: "pass",
      category: "financial",
      category_label: "Financial norms",
      inputs: [],
      missing: [],
      note: null,
      provisional: true,
    },
  ],
};

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

export const CAM: Cam = {
  case_id: KESTREL,
  interim_template: true,
  sections: [
    {
      id: "financials",
      title: "Financial performance",
      paragraphs: [
        { text: "Revenue from operations was INR 30.00 cr in FY 2025-26.", citations: cite(4) },
      ],
      table: null,
      empty: null,
    },
    {
      id: "banking",
      title: "Banking and account conduct",
      paragraphs: [],
      table: null,
      empty: "Nothing on file yet.",
    },
  ],
  summary_title: "Summary of findings, deviations and open queries",
  summary: [
    {
      kind: "finding",
      severity: "serious",
      ref: "fnd-ob2",
      text: "Regular debits to lender(s) not declared: ASHWOOD FINSERV.",
      citations: [{ document_id: "doc-bank", page: 7 }],
    },
    { kind: "query", severity: null, ref: "q1", text: "KYC of Leela Varghese.", citations: [] },
  ],
  recommendation_title: "Recommendation",
  recommendation: "",
};

export const PD_NOTE: PdNote = {
  case_id: KESTREL,
  questions: [
    {
      id: "pdq-1",
      text: "Regular debits to lender(s) not declared: ASHWOOD FINSERV. What are these payments for?",
      severity: "serious",
      source: "finding",
      ref: "fnd-ob2",
      rule: "OB-02",
      title: "Instalments in bank statements go to declared lenders",
      evidence: [{ document_id: "doc-bank", page: 7 }],
    },
    {
      id: "pdq-2",
      text: "Debt / equity is 3.00x against a norm of at most 2.00x. What explains it?",
      severity: "moderate",
      source: "deviation",
      ref: "FR-05",
      rule: "FR-05",
      title: "Debt / equity",
      evidence: cite(4),
    },
  ],
};
