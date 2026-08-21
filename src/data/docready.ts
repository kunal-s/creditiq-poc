import { useSyncExternalStore } from "react";
import { APPRAISALS, type Appraisal } from "@/data/seed";

/* ------------------------------------------------------------------ types */

export type DocStatus =
  | "not-requested"
  | "requested"
  | "received"
  | "rejected"
  | "accepted"
  | "waived";

export type Insufficiency = "stale" | "incomplete" | "inconsistent";

export type CheckOutcome = "pass" | "warn" | "fail";

export type ValidationCheck = {
  key: string;
  label: string;
  outcome: CheckOutcome;
  detail: string;
};

export type Section = "Constitution and KYC" | "Financials" | "Banking and operations" | "Collateral and security";

export const SECTION_WEIGHT: Record<Section, number> = {
  "Constitution and KYC": 20,
  Financials: 30,
  "Banking and operations": 30,
  "Collateral and security": 20,
};

export const SECTIONS: Section[] = [
  "Constitution and KYC",
  "Financials",
  "Banking and operations",
  "Collateral and security",
];

export type ChecklistItem = {
  id: string;
  name: string;
  category: Section;
  why: string;
  basis: string;
  blocking: boolean;
  status: DocStatus;
  weight: number;
  insufficiency?: Insufficiency | undefined;
  confidence?: number | undefined;
  ageDays?: number | undefined;
  remindersSent?: number | undefined;
  escalate?: boolean | undefined;
  fileName?: string | undefined;
  receivedAt?: string | undefined;
  receivedFrom?: string | undefined;
  pages?: string | undefined;
  checks?: ValidationCheck[] | undefined;
  rejection?: string | undefined;
  waiverReason?: string | undefined;
};

export type ChaseEvent = {
  id: string;
  at: string;
  actor: string;
  kind: "request" | "reminder" | "upload" | "rejection" | "acceptance" | "call" | "waiver" | "handoff" | "escalation";
  title: string;
  detail: string;
  items?: string[] | undefined;
};

export type DocReadyCase = {
  id: string;
  borrower: string;
  slug: string;
  constitution: string;
  sector: string;
  segment: "Micro" | "Small" | "Medium";
  employees?: number | undefined;
  cin?: string | undefined;
  pan: string;
  gstin: string;
  udyam: string;
  product: string;
  facilities: string;
  requested: string;
  purpose?: string | undefined;
  branch: string;
  rm: string;
  owner: string;
  opened: string;
  lastContact: string;
  daysInCollection: number;
  targetSanction: string;
  existingRelationship?: string | undefined;
  contact: { name: string; role: string; phone: string; email: string };
  link?:
    | { sentAt: string; channels: string; opens: number; lastOpened: string; uploadsThroughLink: number }
    | undefined;
  clearedBy?: string | undefined;
  clearedAt?: string | undefined;
  scoreOverride?: number | undefined;
  nextActions?: string[] | undefined;
  items: ChecklistItem[];
  chase: ChaseEvent[];
  handedOffTo?: string | undefined;
};

export const TODAY = "21 August 2026";

export const STAGE_GATES = [
  { label: "Ready for credit review", threshold: 85 },
  { label: "Ready for disbursement", threshold: 100 },
];

export const REMINDER_CADENCE = {
  first: 3,
  second: 7,
  escalation: 12,
  channels: "Email and WhatsApp",
};

/* ------------------------------------------------ Southgate Textiles items */

const SOUTHGATE_ITEMS: ChecklistItem[] = [
  /* --------------------------------------- A: Constitution and KYC (20%) */
  {
    id: "coi",
    name: "Certificate of incorporation",
    category: "Constitution and KYC",
    why: "Establishes legal existence and the date from which the borrowing entity has existed.",
    basis: "Private limited constitution · CCB MSME checklist A.1",
    blocking: false,
    status: "accepted",
    weight: 4,
    confidence: 97,
    fileName: "Southgate_Certificate_of_Incorporation.pdf",
    receivedAt: "06 August 2026, 10:42",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "2 pages · 420 KB",
    checks: [
      { key: "legible", label: "Legibility", outcome: "pass", detail: "Text layer present on both pages." },
      { key: "identifier", label: "Identifier match", outcome: "pass", detail: "CIN U17291TZ2016PTC027431 matches the MCA record." },
    ],
  },
  {
    id: "moa-aoa",
    name: "Memorandum and articles of association",
    category: "Constitution and KYC",
    why: "Confirms the objects clause permits the activity financed and that borrowing powers exist.",
    basis: "Private limited constitution · CCB MSME checklist A.2",
    blocking: false,
    status: "accepted",
    weight: 4,
    confidence: 94,
    fileName: "Southgate_MOA_AOA.pdf",
    receivedAt: "06 August 2026, 10:44",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "31 pages · 3.4 MB",
    checks: [
      { key: "legible", label: "Legibility", outcome: "pass", detail: "Readable at 300 dpi; two pages scanned at an angle but fully extractable." },
      { key: "objects", label: "Objects clause", outcome: "pass", detail: "Manufacture and export of textiles covered under clause III(A)(1)." },
    ],
  },
  {
    id: "board-resolution",
    name: "Board resolution for borrowing",
    category: "Constitution and KYC",
    why: "Without a signed resolution the company has not authorised anyone to borrow or execute security.",
    basis: "Companies Act s.179(3)(d) · CCB MSME checklist A.3",
    blocking: false,
    status: "rejected",
    insufficiency: "incomplete",
    weight: 2,
    confidence: 71,
    ageDays: 13,
    fileName: "Southgate_Board_Resolution_draft.pdf",
    receivedAt: "08 August 2026, 16:20",
    receivedFrom: "Emailed to Priya Raghavan",
    pages: "1 page · 96 KB",
    rejection:
      "Unsigned and not on company letterhead. A signed copy on letterhead, certified by a director, is required before documentation.",
    checks: [
      { key: "signature", label: "Attestation", outcome: "fail", detail: "No director signature and no company seal." },
      { key: "letterhead", label: "Format", outcome: "fail", detail: "Plain paper; company letterhead required." },
      { key: "content", label: "Content", outcome: "pass", detail: "Borrowing amount and authorised signatories correctly stated." },
    ],
  },
  {
    id: "kyc-directors",
    name: "KYC of directors — Lakshmi Iyer and Venkat Iyer",
    category: "Constitution and KYC",
    why: "Both directors must be identified and verified before the borrower can be onboarded.",
    basis: "RBI Master Direction on KYC · CCB MSME checklist A.4",
    blocking: false,
    status: "accepted",
    weight: 4,
    confidence: 96,
    fileName: "Southgate_Director_KYC_Iyer_x2.pdf",
    receivedAt: "06 August 2026, 10:51",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "8 pages · 1.2 MB",
    checks: [
      { key: "completeness", label: "Completeness", outcome: "pass", detail: "Two directors on the MCA record, two KYC sets received." },
      { key: "recency", label: "Recency", outcome: "pass", detail: "Address proofs dated 19 July 2026, inside the two-month window." },
    ],
  },
  {
    id: "pan-entity",
    name: "PAN of the entity",
    category: "Constitution and KYC",
    why: "The entity PAN keys every statutory cross-check that follows — GST, ITR and bureau.",
    basis: "CCB MSME checklist A.5",
    blocking: false,
    status: "accepted",
    weight: 4,
    confidence: 99,
    fileName: "Southgate_Entity_PAN.pdf",
    receivedAt: "06 August 2026, 10:45",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "1 page · 88 KB",
    checks: [
      { key: "identifier", label: "Identifier match", outcome: "pass", detail: "AAHCS6612M matches the PAN embedded in GSTIN 33AAHCS6612M1ZQ." },
    ],
  },
  {
    id: "udyam",
    name: "Udyam registration certificate",
    category: "Constitution and KYC",
    why: "Confirms MSME classification, which drives pricing, collateral relief and priority-sector tagging.",
    basis: "MSMED Act classification · CCB MSME checklist A.6",
    blocking: false,
    status: "not-requested",
    weight: 2,
    ageDays: 17,
    checks: [],
  },

  /* ----------------------------------------------------- B: Financials (30%) */
  {
    id: "fs-fy2024",
    name: "Audited financial statements FY2024",
    category: "Financials",
    why: "First of the two audited years the spread is built on.",
    basis: "CCB ratio policy v6.2 · two audited years for MSME secured limits",
    blocking: false,
    status: "accepted",
    weight: 7,
    confidence: 96,
    fileName: "Southgate_Audited_FS_FY2024.pdf",
    receivedAt: "07 August 2026, 12:06",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "26 pages · 2.9 MB",
    checks: [
      { key: "signature", label: "Auditor sign-off", outcome: "pass", detail: "Signed, UDIN 24051233AKQPTL4419 present." },
      { key: "schedules", label: "Schedules attached", outcome: "pass", detail: "Notes and fixed asset schedule complete." },
    ],
  },
  {
    id: "fs-fy2025",
    name: "Audited financial statements FY2025",
    category: "Financials",
    why: "Second audited year; provides the comparative for growth, margin and leverage trends.",
    basis: "CCB ratio policy v6.2",
    blocking: false,
    status: "accepted",
    weight: 8,
    confidence: 95,
    fileName: "Southgate_Audited_FS_FY2025.pdf",
    receivedAt: "07 August 2026, 12:08",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "28 pages · 3.2 MB",
    checks: [
      { key: "signature", label: "Auditor sign-off", outcome: "pass", detail: "Signed, UDIN 25051233AKQRWP8802 present." },
      { key: "comparatives", label: "Comparatives", outcome: "pass", detail: "FY2024 comparatives agree with the FY2024 statement to the rupee." },
    ],
  },
  {
    id: "fs-fy2026-prov",
    name: "Provisional financials FY2026, part year",
    category: "Financials",
    why: "Bridges the audited FY2025 position to the date of the application; without it the assessment is fifteen months stale.",
    basis: "CCB MSME checklist B.3",
    blocking: false,
    status: "rejected",
    insufficiency: "incomplete",
    weight: 5,
    confidence: 62,
    ageDays: 10,
    fileName: "Southgate_Provisional_FY2026.pdf",
    receivedAt: "11 August 2026, 09:15",
    receivedFrom: "Emailed to Priya Raghavan",
    pages: "6 pages · 740 KB",
    rejection:
      "Profit and loss present but balance sheet pages 3 to 5 are absent, so current assets and current liabilities cannot be read. Complete set required.",
    checks: [
      { key: "completeness", label: "Completeness", outcome: "fail", detail: "Pages 3 to 5 missing; balance sheet absent." },
      { key: "pl", label: "Profit and loss", outcome: "pass", detail: "Nine months to 31 December 2025 extracted cleanly." },
    ],
  },
  {
    id: "itr",
    name: "ITR with computation, FY2024 and FY2025",
    category: "Financials",
    why: "Independent check on declared turnover and profit against the audited statements.",
    basis: "CCB cross-verification rule XV-04",
    blocking: false,
    status: "accepted",
    weight: 6,
    confidence: 93,
    fileName: "Southgate_ITR_FY2024_FY2025.pdf",
    receivedAt: "07 August 2026, 12:11",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "18 pages · 1.9 MB",
    checks: [
      { key: "ack", label: "Acknowledgement", outcome: "pass", detail: "Both ITR-V acknowledgements present." },
      { key: "agreement", label: "Agreement with FS", outcome: "pass", detail: "Turnover agrees with the audited statements within INR 0.02 cr." },
    ],
  },
  {
    id: "gst",
    name: "GST returns — GSTR-3B, last 12 months",
    category: "Financials",
    why: "Monthly outward supplies are the independent turnover check and drive the drawing-power view.",
    basis: "CCB cross-verification rule XV-04 · GSTIN 33AAHCS6612M1ZQ",
    blocking: false,
    status: "rejected",
    insufficiency: "incomplete",
    weight: 4,
    confidence: 68,
    ageDays: 12,
    fileName: "Southgate_GSTR3B_Dec2025_Jul2026.pdf",
    receivedAt: "09 August 2026, 17:33",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "8 monthly filings",
    rejection:
      "Covers 8 of the 12 required months, December 2025 to July 2026. August to November 2025 are absent, so the full-year turnover check cannot be run.",
    checks: [
      { key: "coverage", label: "Period coverage", outcome: "fail", detail: "8 of 12 months. Missing: Aug, Sep, Oct and Nov 2025." },
      { key: "legible", label: "Legibility", outcome: "pass", detail: "Portal-generated PDFs, machine readable." },
    ],
  },

  /* -------------------------------------- C: Banking and operations (30%) */
  {
    id: "bank-stmt",
    name: "Bank statements, last 12 months, all accounts",
    category: "Banking and operations",
    why: "Conduct, cheque returns and collection routing cannot be assessed on one account when two exist.",
    basis: "CCB MSME checklist C.1 · Account Aggregator preferred",
    blocking: true,
    status: "rejected",
    insufficiency: "incomplete",
    weight: 8,
    confidence: 74,
    ageDays: 13,
    fileName: "Southgate_CCB_CA_Statements_12m.pdf",
    receivedAt: "08 August 2026, 11:02",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "64 pages · 4.1 MB",
    rejection:
      "CCB current account only. The client has declared a second account with Meridian Bank ending 8830, for which no statement has been provided. Twelve months required for that account.",
    checks: [
      { key: "coverage", label: "Account coverage", outcome: "fail", detail: "1 of 2 declared accounts. Meridian Bank 8830 missing." },
      { key: "period", label: "Period coverage", outcome: "pass", detail: "August 2025 to July 2026 complete for the CCB account." },
    ],
  },
  {
    id: "stock-statement",
    name: "Stock and book-debt statement, latest",
    category: "Banking and operations",
    why: "Drawing power on the cash credit is computed off this statement; a stale one cannot be used.",
    basis: "CCB working capital assessment note 3.3 · maximum age 30 days",
    blocking: true,
    status: "rejected",
    insufficiency: "stale",
    weight: 7,
    confidence: 88,
    ageDays: 16,
    fileName: "Southgate_Stock_BookDebt_30Jun2026.pdf",
    receivedAt: "05 August 2026, 14:48",
    receivedFrom: "Emailed to Priya Raghavan",
    pages: "3 pages · 210 KB",
    rejection:
      "Statement is as at 30 June 2026, making it 52 days old against a maximum of 30. Drawing power cannot be computed on it. Statement as at 31 July 2026 required.",
    checks: [
      { key: "recency", label: "Recency", outcome: "fail", detail: "Dated 30 June 2026 — 52 days old against a 30-day limit." },
      { key: "extract", label: "Extraction", outcome: "pass", detail: "Stock INR 2.14 cr and book debts INR 1.66 cr read cleanly." },
    ],
  },
  {
    id: "ageing",
    name: "Debtors and creditors ageing",
    category: "Banking and operations",
    why: "Needed to strip debts over 90 days out of drawing power and to see creditor stretch.",
    basis: "CCB working capital assessment note 3.4",
    blocking: false,
    status: "requested",
    weight: 5,
    ageDays: 13,
    remindersSent: 2,
    escalate: true,
    checks: [],
  },
  {
    id: "sanction-others",
    name: "Sanction letters of existing facilities with other lenders",
    category: "Banking and operations",
    why: "Total obligations cannot be stated without them; a nil declaration is only as good as the evidence behind it.",
    basis: "CCB MSME checklist C.4",
    blocking: false,
    status: "accepted",
    weight: 10,
    confidence: 90,
    fileName: "Southgate_Nil_Facilities_Declaration.pdf",
    receivedAt: "06 August 2026, 10:58",
    receivedFrom: "Collection link — Lakshmi Iyer",
    pages: "1 page · 74 KB",
    checks: [
      { key: "declaration", label: "Declaration on file", outcome: "pass", detail: "Client declared nil existing facilities on 06 August 2026." },
      {
        key: "consistency",
        label: "Consistency with other documents",
        outcome: "fail",
        detail:
          "Contradicted by the title deed, which shows a Meridian Bank mortgage dated March 2024, and by the undisclosed Meridian Bank account 8830.",
      },
    ],
  },

  /* ------------------------------------ D: Collateral and security (20%) */
  {
    id: "property-docs",
    name: "Property documents for collateral — industrial unit, Coimbatore",
    category: "Collateral and security",
    why: "A charge cannot be created without a clear title chain, and an existing mortgage changes the security position entirely.",
    basis: "CCB security documentation manual 7.1",
    blocking: true,
    status: "rejected",
    insufficiency: "inconsistent",
    weight: 8,
    confidence: 91,
    ageDays: 11,
    fileName: "Southgate_Title_Deed_Coimbatore_Unit.pdf",
    receivedAt: "10 August 2026, 15:27",
    receivedFrom: "Emailed to Priya Raghavan",
    pages: "22 pages · 5.6 MB",
    rejection:
      "The title deed carries an existing mortgage in favour of Meridian Bank dated March 2024. That contradicts the client's declaration of nil existing facilities and is consistent with the undisclosed Meridian Bank account 8830. Clarification and a charge search are required before the security can be relied on.",
    checks: [
      { key: "legible", label: "Legibility", outcome: "pass", detail: "Registered deed, clean scan; encumbrance page readable." },
      {
        key: "consistency",
        label: "Consistency with other documents",
        outcome: "fail",
        detail:
          "Mortgage in favour of Meridian Bank, March 2024, against a nil-facilities declaration dated 06 August 2026 and bank statements showing only the CCB account.",
      },
      { key: "chain", label: "Title chain", outcome: "warn", detail: "Chain complete back to 2016; encumbrance certificate not yet obtained." },
    ],
  },
  {
    id: "valuation",
    name: "Latest valuation report",
    category: "Collateral and security",
    why: "Sets the security cover ratio on the term loan; the panel valuer's report is the only accepted basis.",
    basis: "CCB security documentation manual 7.4 · panel valuers only",
    blocking: false,
    status: "requested",
    weight: 7,
    ageDays: 11,
    remindersSent: 1,
    checks: [],
  },
  {
    id: "insurance",
    name: "Insurance policy on collateral",
    category: "Collateral and security",
    why: "Sum insured must at least match the assessed value, so this cannot be asked for until the valuation lands.",
    basis: "CCB security documentation manual 7.6",
    blocking: false,
    status: "not-requested",
    weight: 5,
    checks: [],
  },
];

const SOUTHGATE_CHASE: ChaseEvent[] = [
  {
    id: "ev-1",
    at: "04 August 2026, 09:40",
    actor: "Priya Raghavan, Relationship Manager",
    kind: "request",
    title: "Application received and checklist derived",
    detail:
      "Eighteen requirements derived from the MSME Secured Working Capital plus Term Loan product, private limited constitution, collateral present, no co-applicant and export exposure. Cash credit INR 2.85 cr against stock and book debts, term loan INR 1.40 cr for machinery.",
  },
  {
    id: "ev-2",
    at: "06 August 2026, 09:05",
    actor: "CreditIQ collection engine",
    kind: "request",
    title: "Collection link sent to Lakshmi Iyer",
    detail:
      "Sent by email and WhatsApp to the Managing Director. Reminder cadence for this product: first at 3 days, second at 7 days, escalation to Credit Operations at 12 days.",
  },
  {
    id: "ev-3",
    at: "06 August 2026, 10:58",
    actor: "Lakshmi Iyer, Southgate Textiles",
    kind: "upload",
    title: "First batch through the link — six documents",
    detail:
      "Incorporation certificate, MOA and AOA, entity PAN, KYC for both directors and the nil-facilities declaration uploaded in one session.",
    items: [
      "Certificate of incorporation",
      "Memorandum and articles of association",
      "PAN of the entity",
      "KYC of directors — Lakshmi Iyer and Venkat Iyer",
      "Sanction letters of existing facilities with other lenders",
    ],
  },
  {
    id: "ev-4",
    at: "07 August 2026, 12:11",
    actor: "Lakshmi Iyer, Southgate Textiles",
    kind: "upload",
    title: "Audited financials and returns received",
    detail: "FY2024 and FY2025 audited statements with UDINs, plus ITR and computation for both years. All accepted on first pass.",
    items: ["Audited financial statements FY2024", "Audited financial statements FY2025", "ITR with computation, FY2024 and FY2025"],
  },
  {
    id: "ev-5",
    at: "08 August 2026, 11:04",
    actor: "CreditIQ validation",
    kind: "rejection",
    title: "Bank statements insufficient — one account of two",
    detail:
      "Twelve months received for the CCB current account. The client's own application declares a second account with Meridian Bank ending 8830, for which nothing has been provided.",
    items: ["Bank statements, last 12 months, all accounts"],
  },
  {
    id: "ev-6",
    at: "08 August 2026, 16:22",
    actor: "CreditIQ validation",
    kind: "rejection",
    title: "Board resolution insufficient — unsigned",
    detail: "Content is correct but the document is unsigned and on plain paper. Precise re-ask issued: signed copy on company letterhead.",
    items: ["Board resolution for borrowing"],
  },
  {
    id: "ev-7",
    at: "08 August 2026, 16:30",
    actor: "Priya Raghavan, Relationship Manager",
    kind: "request",
    title: "Debtors and creditors ageing requested",
    detail: "Requested directly from Lakshmi Iyer by email and WhatsApp with a five-day window.",
    items: ["Debtors and creditors ageing"],
  },
  {
    id: "ev-8",
    at: "09 August 2026, 17:35",
    actor: "CreditIQ validation",
    kind: "rejection",
    title: "GST returns insufficient — 8 of 12 months",
    detail:
      "December 2025 to July 2026 received. August to November 2025 absent, so the twelve-month turnover comparison against the audited statements cannot be completed.",
    items: ["GST returns — GSTR-3B, last 12 months"],
  },
  {
    id: "ev-9",
    at: "10 August 2026, 15:30",
    actor: "CreditIQ validation",
    kind: "rejection",
    title: "Title deed inconsistent with two other documents on file",
    detail:
      "The deed shows a Meridian Bank mortgage dated March 2024. Read against the nil-facilities declaration of 06 August and the bank statements covering only the CCB account, this is a contradiction across three separate documents, surfaced at collection rather than at appraisal.",
    items: [
      "Property documents for collateral — industrial unit, Coimbatore",
      "Sanction letters of existing facilities with other lenders",
      "Bank statements, last 12 months, all accounts",
    ],
  },
  {
    id: "ev-10",
    at: "10 August 2026, 15:44",
    actor: "Priya Raghavan, Relationship Manager",
    kind: "request",
    title: "Valuation report requested from the panel valuer",
    detail: "Requested through the client; insurance on the collateral is held back until the valuation lands.",
    items: ["Latest valuation report"],
  },
  {
    id: "ev-11",
    at: "11 August 2026, 09:17",
    actor: "CreditIQ validation",
    kind: "rejection",
    title: "Provisional FY2026 financials insufficient — balance sheet missing",
    detail: "Profit and loss for the nine months to December 2025 is present; pages 3 to 5 carrying the balance sheet are absent.",
    items: ["Provisional financials FY2026, part year"],
  },
  {
    id: "ev-12",
    at: "13 August 2026, 09:00",
    actor: "CreditIQ collection engine",
    kind: "reminder",
    title: "First reminder — debtors and creditors ageing",
    detail: "Sent on the three-day cadence by email and WhatsApp. No response recorded.",
    items: ["Debtors and creditors ageing"],
  },
  {
    id: "ev-13",
    at: "18 August 2026, 09:00",
    actor: "CreditIQ collection engine",
    kind: "reminder",
    title: "Second reminder — debtors and creditors ageing",
    detail: "Seven-day cadence reached. Still no response; the item is now 13 days old and past the 12-day escalation threshold.",
    items: ["Debtors and creditors ageing"],
  },
  {
    id: "ev-14",
    at: "21 August 2026, 08:30",
    actor: "CreditIQ collection engine",
    kind: "escalation",
    title: "Due for escalation to Credit Operations",
    detail:
      "Debtors and creditors ageing has passed the 12-day escalation threshold with two reminders sent. Escalation routes to Thomas Weber, Credit Operations Officer.",
    items: ["Debtors and creditors ageing"],
  },
];

const SOUTHGATE: DocReadyCase = {
  id: "SGT-2026-0147",
  borrower: "Southgate Textiles Pvt Ltd",
  slug: "southgate-textiles",
  constitution: "Private limited company",
  sector: "Home textiles and furnishing fabrics",
  segment: "Small",
  employees: 46,
  cin: "U17291TZ2016PTC027431",
  pan: "AAHCS••••M",
  gstin: "33AAHCS6612M1ZQ",
  udyam: "Not yet provided",
  product: "MSME Secured Working Capital plus Term Loan",
  facilities: "CC INR 2.85 cr + TL INR 1.40 cr",
  requested: "INR 4.25 cr",
  purpose: "Capacity expansion for an export order",
  branch: "Coimbatore SME Branch",
  rm: "Priya Raghavan",
  owner: "Thomas Weber",
  opened: "04 August 2026",
  lastContact: "18 August 2026",
  daysInCollection: 17,
  targetSanction: "11 September 2026",
  existingRelationship: "Current account with CCB since 2021; no existing credit facility",
  contact: {
    name: "Lakshmi Iyer",
    role: "Managing Director",
    phone: "+91 98•••• 3316",
    email: "lakshmi.iyer@southgatetextiles.in",
  },
  link: {
    sentAt: "06 August 2026",
    channels: "Email and WhatsApp",
    opens: 4,
    lastOpened: "12 August 2026",
    uploadsThroughLink: 7,
  },
  items: SOUTHGATE_ITEMS,
  chase: SOUTHGATE_CHASE,
};

/* ------------------------------------------------- Fairwind Components (ready) */

const FAIRWIND_NAMES: { id: string; name: string; category: Section; weight: number; blocking: boolean }[] = [
  { id: "coi", name: "Certificate of incorporation", category: "Constitution and KYC", weight: 4, blocking: false },
  { id: "moa-aoa", name: "Memorandum and articles of association", category: "Constitution and KYC", weight: 3, blocking: false },
  { id: "board-resolution", name: "Board resolution for borrowing", category: "Constitution and KYC", weight: 4, blocking: false },
  { id: "kyc-directors", name: "KYC of directors", category: "Constitution and KYC", weight: 4, blocking: false },
  { id: "pan-entity", name: "PAN of the entity", category: "Constitution and KYC", weight: 3, blocking: false },
  { id: "udyam", name: "Udyam registration certificate", category: "Constitution and KYC", weight: 2, blocking: false },
  { id: "fs-fy2024", name: "Audited financial statements FY2024", category: "Financials", weight: 8, blocking: false },
  { id: "fs-fy2025", name: "Audited financial statements FY2025", category: "Financials", weight: 8, blocking: false },
  { id: "fs-fy2026-prov", name: "Provisional financials FY2026, part year", category: "Financials", weight: 5, blocking: false },
  { id: "itr", name: "ITR with computation, FY2024 and FY2025", category: "Financials", weight: 4, blocking: false },
  { id: "gst", name: "GST returns — GSTR-3B, last 12 months", category: "Financials", weight: 5, blocking: false },
  { id: "bank-stmt", name: "Bank statements, last 12 months, all accounts", category: "Banking and operations", weight: 10, blocking: true },
  { id: "stock-statement", name: "Stock and book-debt statement, latest", category: "Banking and operations", weight: 8, blocking: true },
  { id: "ageing", name: "Debtors and creditors ageing", category: "Banking and operations", weight: 6, blocking: false },
  { id: "sanction-others", name: "Sanction letters of existing facilities with other lenders", category: "Banking and operations", weight: 6, blocking: false },
  { id: "collateral-security", name: "Hypothecation of stock and book debts — security documents", category: "Collateral and security", weight: 20, blocking: true },
];

const FAIRWIND: DocReadyCase = {
  id: "FWC-2026-0132",
  borrower: "Fairwind Components Pvt Ltd",
  slug: "fairwind-components",
  constitution: "Private limited company",
  sector: "Precision engineering components",
  segment: "Small",
  pan: "AAECF••••K",
  gstin: "27AAECF3390K1ZR",
  udyam: "UDYAM-MH-26-0041188",
  product: "MSME Secured Working Capital",
  facilities: "CC INR 1.95 cr",
  requested: "INR 1.95 cr",
  purpose: "Working capital for an expanded order book",
  branch: "Pune SME Branch",
  rm: "Priya Raghavan",
  owner: "Thomas Weber",
  opened: "21 July 2026",
  lastContact: "14 August 2026",
  daysInCollection: 24,
  targetSanction: "31 August 2026",
  existingRelationship: "Current account and prior CGTMSE-backed term loan, closed 2024",
  clearedBy: "Thomas Weber, Credit Operations Officer",
  clearedAt: "14 August 2026",
  contact: {
    name: "Anand Deshmukh",
    role: "Director",
    phone: "+91 90•••• 7742",
    email: "anand@fairwindcomponents.in",
  },
  link: {
    sentAt: "22 July 2026",
    channels: "Email",
    opens: 6,
    lastOpened: "12 August 2026",
    uploadsThroughLink: 14,
  },
  items: FAIRWIND_NAMES.map((f) => ({
    id: f.id,
    name: f.name,
    category: f.category,
    why: "Required for the MSME Secured Working Capital product against a private limited borrower.",
    basis: "CCB MSME checklist · derived 21 July 2026",
    blocking: f.blocking,
    status: "accepted" as DocStatus,
    weight: f.weight,
    confidence: 95,
    fileName: `Fairwind_${f.id.replace(/-/g, "_")}.pdf`,
    receivedAt: "Received between 23 July and 12 August 2026",
    receivedFrom: "Collection link — Anand Deshmukh",
    pages: "Complete",
    checks: [
      { key: "legible", label: "Legibility", outcome: "pass" as CheckOutcome, detail: "Machine readable throughout." },
      { key: "completeness", label: "Completeness", outcome: "pass" as CheckOutcome, detail: "Full period and all pages present." },
      { key: "consistency", label: "Consistency", outcome: "pass" as CheckOutcome, detail: "Agrees with every other document on file." },
    ],
  })),
  chase: [
    {
      id: "fw-1",
      at: "21 July 2026, 10:15",
      actor: "Priya Raghavan, Relationship Manager",
      kind: "request",
      title: "Application received and checklist derived",
      detail: "Sixteen requirements applicable: no term loan, so no valuation or insurance; security is hypothecation of stock and book debts.",
    },
    {
      id: "fw-2",
      at: "22 July 2026, 09:00",
      actor: "CreditIQ collection engine",
      kind: "request",
      title: "Collection link sent to Anand Deshmukh",
      detail: "Sent by email. Opened six times; fourteen of the sixteen documents arrived through the link.",
    },
    {
      id: "fw-3",
      at: "12 August 2026, 16:40",
      actor: "Anand Deshmukh, Fairwind Components",
      kind: "upload",
      title: "Final document received",
      detail: "Stock and book-debt statement as at 31 July 2026, inside the 30-day window.",
      items: ["Stock and book-debt statement, latest"],
    },
    {
      id: "fw-4",
      at: "14 August 2026, 11:20",
      actor: "Thomas Weber, Credit Operations Officer",
      kind: "acceptance",
      title: "Case cleared for credit review",
      detail:
        "All sixteen applicable requirements satisfied, no insufficiency and no contradiction across documents. Readiness 100% at 24 days from application.",
    },
  ],
};

/* --------------------------------------------- Brightline Foods (just started) */

const BRIGHTLINE: DocReadyCase = {
  id: "BLF-2026-0158",
  borrower: "Brightline Foods Pvt Ltd",
  slug: "brightline-foods",
  constitution: "Private limited company",
  sector: "Food processing",
  segment: "Micro",
  pan: "AAGCB••••N",
  gstin: "27AAGCB4417N1ZD",
  udyam: "UDYAM-MH-19-0066204",
  product: "MSME Secured Working Capital",
  facilities: "CC INR 1.20 cr",
  requested: "INR 1.20 cr",
  purpose: "Working capital for a new processing line",
  branch: "Nashik SME Branch",
  rm: "Priya Raghavan",
  owner: "Thomas Weber",
  opened: "19 August 2026",
  lastContact: "19 August 2026",
  daysInCollection: 2,
  targetSanction: "18 September 2026",
  existingRelationship: "New to bank",
  scoreOverride: 12,
  contact: {
    name: "Nikhil Bhatia",
    role: "Director",
    phone: "+91 99•••• 5108",
    email: "nikhil@brightlinefoods.in",
  },
  link: {
    sentAt: "19 August 2026",
    channels: "Email and WhatsApp",
    opens: 1,
    lastOpened: "19 August 2026",
    uploadsThroughLink: 0,
  },
  items: [
    { id: "coi", name: "Certificate of incorporation", category: "Constitution and KYC" as Section, weight: 5, blocking: false },
    { id: "moa-aoa", name: "Memorandum and articles of association", category: "Constitution and KYC" as Section, weight: 4, blocking: false },
    { id: "board-resolution", name: "Board resolution for borrowing", category: "Constitution and KYC" as Section, weight: 4, blocking: false },
    { id: "kyc-directors", name: "KYC of directors", category: "Constitution and KYC" as Section, weight: 4, blocking: false },
    { id: "pan-entity", name: "PAN of the entity", category: "Constitution and KYC" as Section, weight: 3, blocking: false },
    { id: "fs-fy2024", name: "Audited financial statements FY2024", category: "Financials" as Section, weight: 9, blocking: false },
    { id: "fs-fy2025", name: "Audited financial statements FY2025", category: "Financials" as Section, weight: 9, blocking: false },
    { id: "itr", name: "ITR with computation, FY2024 and FY2025", category: "Financials" as Section, weight: 6, blocking: false },
    { id: "gst", name: "GST returns — GSTR-3B, last 12 months", category: "Financials" as Section, weight: 6, blocking: false },
    { id: "bank-stmt", name: "Bank statements, last 12 months, all accounts", category: "Banking and operations" as Section, weight: 12, blocking: true },
    { id: "stock-statement", name: "Stock and book-debt statement, latest", category: "Banking and operations" as Section, weight: 10, blocking: true },
    { id: "ageing", name: "Debtors and creditors ageing", category: "Banking and operations" as Section, weight: 8, blocking: false },
    { id: "collateral-security", name: "Hypothecation of stock and book debts — security documents", category: "Collateral and security" as Section, weight: 20, blocking: true },
  ].map((f) => ({
    ...f,
    why: "Part of the derived set for MSME Secured Working Capital against a private limited borrower.",
    basis: "CCB MSME checklist · derived 19 August 2026",
    status: "requested" as DocStatus,
    ageDays: 2,
    checks: [],
  })),
  chase: [
    {
      id: "bl-1",
      at: "19 August 2026, 11:05",
      actor: "Priya Raghavan, Relationship Manager",
      kind: "request",
      title: "Application received and checklist generated",
      detail: "Thirteen requirements derived for a micro private limited borrower seeking a cash credit of INR 1.20 cr against stock and book debts.",
    },
    {
      id: "bl-2",
      at: "19 August 2026, 11:22",
      actor: "CreditIQ collection engine",
      kind: "request",
      title: "Collection link sent to Nikhil Bhatia",
      detail: "Sent by email and WhatsApp. Opened once on 19 August; nothing uploaded yet. First reminder falls due on 22 August.",
    },
  ],
};

/* --------------------------------------------------------------- readiness */

export const STATUS_LABEL: Record<DocStatus, string> = {
  "not-requested": "Not requested",
  requested: "Missing",
  received: "In review",
  rejected: "Insufficient",
  accepted: "Satisfied",
  waived: "Waived",
};

export const INSUFFICIENCY_LABEL: Record<Insufficiency, string> = {
  stale: "Stale",
  incomplete: "Incomplete",
  inconsistent: "Inconsistent",
};

export function readiness(c: DocReadyCase) {
  const settled = (s: DocStatus) => s === "accepted" || s === "waived";
  const weightTotal = c.items.reduce((n, i) => n + i.weight, 0);
  const weightDone = c.items.reduce(
    (n, i) => n + (settled(i.status) ? i.weight : i.status === "rejected" ? i.weight * 0.5 : 0),
    0,
  );
  const computed = weightTotal ? Math.round((weightDone / weightTotal) * 100) : 0;
  return {
    score: c.scoreOverride ?? computed,
    total: c.items.length,
    accepted: c.items.filter((i) => settled(i.status)).length,
    insufficient: c.items.filter((i) => i.status === "rejected").length,
    missing: c.items.filter((i) => i.status === "requested" || i.status === "not-requested").length,
    outstanding: c.items.filter((i) => !settled(i.status)).length,
    blockingOpen: c.items.filter((i) => i.blocking && !settled(i.status)).length,
    inReview: c.items.filter((i) => i.status === "received").length,
    reviewGate: (c.scoreOverride ?? computed) >= 85,
  };
}

/* ------------------------------------------------------------------- store */

type State = { cases: DocReadyCase[] };

let state: State = { cases: [SOUTHGATE, FAIRWIND, BRIGHTLINE] };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const setCase = (id: string, fn: (c: DocReadyCase) => DocReadyCase) => {
  state = { cases: state.cases.map((c) => (c.id === id ? fn(c) : c)) };
  emit();
};
const log = (c: DocReadyCase, ev: Omit<ChaseEvent, "id">): DocReadyCase => ({
  ...c,
  chase: [...c.chase, { ...ev, id: `ev-${c.chase.length + 1}-${Date.now()}` }],
});

const NOW = `${TODAY}, 12:53`;
const ANALYST = "Priya Raghavan, Relationship Manager";

export const docReadyActions = {
  request(caseId: string, itemId: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) => (i.id === itemId ? { ...i, status: "requested" as DocStatus } : i)),
      };
      return log(next, {
        at: NOW,
        actor: ANALYST,
        kind: "request",
        title: `Requested: ${item?.name ?? itemId}`,
        detail: `Added to the open ask on the collection link for ${c.contact.name}, sent by ${REMINDER_CADENCE.channels.toLowerCase()}.`,
        items: item ? [item.name] : undefined,
      });
    });
  },
  accept(caseId: string, itemId: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) =>
          i.id === itemId
            ? { ...i, status: "accepted" as DocStatus, rejection: undefined, insufficiency: undefined }
            : i,
        ),
      };
      return log(next, {
        at: NOW,
        actor: "Thomas Weber, Credit Operations Officer",
        kind: "acceptance",
        title: `Satisfied: ${item?.name ?? itemId}`,
        detail: "Credit Operations cleared the document into the evidence set.",
        items: item ? [item.name] : undefined,
      });
    });
  },
  reject(caseId: string, itemId: string, reason: string, insufficiency: Insufficiency = "incomplete") {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) =>
          i.id === itemId ? { ...i, status: "rejected" as DocStatus, rejection: reason, insufficiency } : i,
        ),
      };
      return log(next, {
        at: NOW,
        actor: "Thomas Weber, Credit Operations Officer",
        kind: "rejection",
        title: `Marked ${INSUFFICIENCY_LABEL[insufficiency].toLowerCase()}: ${item?.name ?? itemId}`,
        detail: reason,
        items: item ? [item.name] : undefined,
      });
    });
  },
  waive(caseId: string, itemId: string, reason: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) => (i.id === itemId ? { ...i, status: "waived" as DocStatus, waiverReason: reason } : i)),
      };
      return log(next, {
        at: NOW,
        actor: "Sofia Almeida, Credit Manager",
        kind: "waiver",
        title: `Waived: ${item?.name ?? itemId}`,
        detail: reason,
        items: item ? [item.name] : undefined,
      });
    });
  },
  simulateUpload(caseId: string, itemId: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) =>
          i.id === itemId
            ? {
                ...i,
                status: "received" as DocStatus,
                rejection: undefined,
                insufficiency: undefined,
                confidence: 92,
                fileName: `${c.slug.replace(/-/g, "_")}_${i.id}.pdf`,
                receivedAt: NOW,
                receivedFrom: `Collection link — ${c.contact.name}`,
                pages: "machine checks queued",
                checks: [
                  { key: "legible", label: "Legibility", outcome: "pass" as CheckOutcome, detail: "Text layer detected on every page." },
                  { key: "identifier", label: "Identifier match", outcome: "pass" as CheckOutcome, detail: `PAN and GSTIN match ${c.borrower}.` },
                  { key: "period", label: "Period coverage", outcome: "warn" as CheckOutcome, detail: "Coverage to be confirmed by Credit Operations." },
                ],
              }
            : i,
        ),
      };
      return log(next, {
        at: NOW,
        actor: `${c.contact.name}, ${c.borrower}`,
        kind: "upload",
        title: `Upload received: ${item?.name ?? itemId}`,
        detail: "Uploaded through the collection link; automated checks run on receipt and cross-read against the documents already on file.",
        items: item ? [item.name] : undefined,
      });
    });
  },
  sendReminder(caseId: string) {
    setCase(caseId, (c) => {
      const open = c.items.filter((i) => i.status === "requested" || i.status === "rejected");
      return log(c, {
        at: NOW,
        actor: ANALYST,
        kind: "reminder",
        title: `Reminder sent — ${open.length} item${open.length === 1 ? "" : "s"} outstanding`,
        detail: `One consolidated message to ${c.contact.name} by ${REMINDER_CADENCE.channels.toLowerCase()}, listing only what is missing or insufficient.`,
        items: open.map((i) => i.name),
      });
    });
  },
  escalate(caseId: string, itemId: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      return log(c, {
        at: NOW,
        actor: ANALYST,
        kind: "escalation",
        title: `Escalated to Credit Operations: ${item?.name ?? itemId}`,
        detail: `Past the ${REMINDER_CADENCE.escalation}-day threshold with ${item?.remindersSent ?? 2} reminders sent. Routed to Thomas Weber, Credit Operations Officer.`,
        items: item ? [item.name] : undefined,
      });
    });
  },
  handoff(caseId: string): string | null {
    const c = state.cases.find((x) => x.id === caseId);
    if (!c) return null;
    if (c.handedOffTo) return c.handedOffTo;
    const r = readiness(c);
    if (r.blockingOpen > 0 || !r.reviewGate) return null;

    const seq = 500 + state.cases.findIndex((x) => x.id === caseId) + 1;
    const camId = `CAM-2026-0${seq}`;
    const appraisal: Appraisal = {
      id: camId,
      borrower: c.borrower,
      sector: c.sector,
      pan: c.pan,
      gstin: c.gstin,
      proposal: `${c.product} — ${c.requested}`,
      facilities: c.facilities,
      exposure: c.requested,
      stage: "Identity",
      analyst: "Elena Rossi",
      rm: c.rm,
      started: TODAY,
      rating: "Not rated",
      ratingLabel: "Awaiting first cut",
      discrepancies: 0,
      branch: c.branch,
    };
    if (!APPRAISALS.some((a) => a.id === camId)) APPRAISALS.push(appraisal);

    setCase(caseId, (nc) =>
      log({ ...nc, handedOffTo: camId }, {
        at: NOW,
        actor: ANALYST,
        kind: "handoff",
        title: `Handed off to credit appraisal ${camId}`,
        detail: `Stage gate met with no blocking gap. Identifiers, constitution, facility ask, branch and relationship manager carried across; ${
          nc.items.filter((i) => i.status === "accepted").length
        } satisfied documents registered as present so the client is not asked for them again.`,
      }),
    );
    return camId;
  },
};

export function useDocReady() {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}

export function useDocReadyCase(id: string) {
  return useDocReady().cases.find((c) => c.id === id);
}
