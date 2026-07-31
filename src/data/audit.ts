import { useSyncExternalStore } from "react";
import { FLAGS, OUTCOME_LABEL, type Outcome, type XVState } from "./crossverify";
import type { MemoState } from "./memo";

/* ------------------------------------------------------------- event model */

export type EventKind =
  | "source"
  | "extraction"
  | "draft"
  | "edit"
  | "override"
  | "adjudication"
  | "routing"
  | "decision";

export const KIND_LABEL: Record<EventKind, string> = {
  source: "Source returned",
  extraction: "System extraction",
  draft: "Machine draft",
  edit: "Human edit",
  override: "Human override",
  adjudication: "Adjudication",
  routing: "Routing",
  decision: "Decision",
};

export const KIND_TONE: Record<EventKind, string> = {
  source: "border-border bg-surface-muted text-muted-foreground",
  extraction: "border-info/25 bg-info-soft text-info",
  draft: "border-info/25 bg-info-soft text-info",
  edit: "border-flag/35 bg-flag-soft text-flag-foreground",
  override: "border-critical/30 bg-critical-soft text-critical",
  adjudication: "border-flag/35 bg-flag-soft text-flag-foreground",
  routing: "border-border bg-surface-muted text-muted-foreground",
  decision: "border-positive/30 bg-positive-soft text-positive",
};

export const HUMAN_KINDS: EventKind[] = ["edit", "override", "adjudication", "decision"];

export type EventLink = { label: string; kind: "appraisal" | "borrower" | "person"; target: string; slug?: string; anchor?: string };

export type AuditEvent = {
  id: string;
  kind: EventKind;
  at: string;
  atSort: number;
  actor: string;
  actorRole: string;
  human: boolean;
  title: string;
  detail: string;
  meta?: { label: string; value: string }[];
  reason?: string;
  original?: string;
  replacement?: string;
  links?: EventLink[];
  hash: string;
};

export type AuditMemo = {
  id: string;
  reference: string;
  borrower: string;
  slug: string;
  appraisalId: string;
  sector: string;
  issued: string;
  status: string;
  rating: string;
  ratingLabel: string;
  facilities: string;
  analyst: string;
  approver: string;
  branch: string;
  seriousFlags: number;
  sealedAt: string;
  digest: string;
  retention: string;
  events: AuditEvent[];
};

/* ---------------------------------------------------------------- traces */

export type TraceStep = {
  stage: "Source" | "Extraction" | "Check" | "Human" | "Memo";
  title: string;
  detail: string;
  at: string;
  actor: string;
  link?: EventLink;
};

export type FigureTrace = {
  id: string;
  memoId: string;
  label: string;
  value: string;
  section: string;
  steps: TraceStep[];
};

const nw = (id: string, anchor?: string): EventLink => ({
  label:
    id === "spread"
      ? "Financial Spread"
      : id === "cross-verification"
        ? "Cross-Verification board"
        : id === "data"
          ? "Data Acquisition console"
          : id === "identity"
            ? "Entity Resolution"
            : id === "draft"
              ? "CAM Draft and Review"
              : id === "rating"
                ? "Rating and Recommendation"
                : "Submission and Routing",
  kind: "appraisal",
  target: id,
  anchor,
});

const person = (label: string, slug: string): EventLink => ({ label, kind: "person", target: "person", slug });

/* ------------------------------------------------- Northwind: the record */

const NW_EVENTS: AuditEvent[] = [
  {
    id: "NW-01",
    kind: "source",
    at: "31 July 2026, 07:02",
    atSort: 702,
    actor: "MCA company master",
    actorRole: "Registry connector",
    human: false,
    title: "Registry returned the company master record",
    detail:
      "CIN U27310MH2009PLC198435, Northwind Manufacturing Ltd, active, incorporated 14 August 2009, registered office Chakan, Pune district. Three directors on the DIN master, no disqualifications. Charge index returned four registered charges totalling INR 21.30 cr.",
    meta: [
      { label: "Response", value: "200 · 1.9 s · 14 fields" },
      { label: "Identifier", value: "PAN AABCN••••Q entered by Elena Rossi" },
    ],
    links: [nw("identity")],
    hash: "a41c9e",
  },
  {
    id: "NW-02",
    kind: "source",
    at: "31 July 2026, 07:04",
    atSort: 704,
    actor: "GSTN",
    actorRole: "Tax connector",
    human: false,
    title: "GSTN returned 24 of 24 filed returns",
    detail:
      "GSTIN 27AABCN4521Q1ZP, active. GSTR-3B outward taxable supplies aggregate INR 119.83 cr for FY2024-25 and INR 98.11 cr for FY2023-24. Every return filed inside the due date; no cancellations, no suspension history.",
    meta: [
      { label: "Response", value: "200 · 4.4 s · 24 return periods" },
      { label: "Retained", value: "Return ledger held as filed, unmodified" },
    ],
    links: [nw("data", "#gst-turnover")],
    hash: "7fd230",
  },
  {
    id: "NW-03",
    kind: "source",
    at: "31 July 2026, 07:09",
    atSort: 709,
    actor: "Rajesh Malhotra",
    actorRole: "Managing Director, borrower",
    human: true,
    title: "Borrower granted Account Aggregator consent CONS-2026-0418-A",
    detail:
      "Consent granted for Meridian Bank current account 4471 and Horizon Bank 2205, twelve months of statements, purpose 'credit appraisal', window 30 days from 24 June 2026. Signed on the registered mobile against the borrower's AA handle.",
    meta: [
      { label: "Scope", value: "Two accounts · 12 months · statements only" },
      { label: "Expiry", value: "24 July 2026 (later expired, refresh pending)" },
    ],
    links: [nw("consent")],
    hash: "b02e51",
  },
  {
    id: "NW-04",
    kind: "source",
    at: "31 July 2026, 07:14",
    atSort: 714,
    actor: "Marcus Chen",
    actorRole: "Relationship Manager, Pune Corporate Branch",
    human: true,
    title: "Audited financials and ITR uploaded as fallback",
    detail:
      "Northwind_Manufacturing_Audited_FS_FY2025.pdf (48 pages, signed by Kanade & Bhide, Chartered Accountants) and ITR-6 acknowledgement 274918365120725 for AY2025-26. Uploaded because the audited statements are not available from any connector.",
    meta: [
      { label: "Checksum", value: "SHA-256 4b8f…c209, unchanged since upload" },
      { label: "Classification", value: "Fallback source · not independent" },
    ],
    links: [nw("upload")],
    hash: "cc1a84",
  },
  {
    id: "NW-05",
    kind: "extraction",
    at: "31 July 2026, 07:21",
    atSort: 721,
    actor: "CreditIQ extraction engine",
    actorRole: "Automated",
    human: false,
    title: "Three years normalised into the CCB spread",
    detail:
      "62 line items lifted across FY2023 to FY2025 and mapped to the bank's own schedule. Turnover INR 96.42 cr, 118.74 cr and 142.31 cr; EBITDA INR 11.18 cr, 13.92 cr and 15.58 cr. Nine policy ratios computed on top, each carrying the document, page and line it came from.",
    meta: [
      { label: "Confidence", value: "58 items high, 4 medium, 0 low" },
      { label: "Unmapped", value: "None. Two items merged into 'Other income'" },
    ],
    links: [nw("spread", "#pl-turnover")],
    hash: "1de6f7",
  },
  {
    id: "NW-06",
    kind: "extraction",
    at: "31 July 2026, 07:36",
    atSort: 736,
    actor: "CreditIQ cross-verification, run XV-2026-0418",
    actorRole: "Automated",
    human: false,
    title: "Three contradictions raised, one serious",
    detail:
      "Rule XV-04 compared declared revenue against GST outward supplies and bank credits and returned a 15.8% shortfall against GST and 14.7% against credits, above the 5% tolerance. Rule XV-11 found a recurring debit of INR 4,37,500 to Crestline Financial Services absent from declared obligations. Rule XV-19 found buyer concentration of 38.4% against the 35% soft cap.",
    meta: [
      { label: "Rules run", value: "22 rules · 3 raised · 19 clean" },
      { label: "Blocking", value: "XV-0418-01 set to block submission" },
    ],
    links: [nw("cross-verification")],
    hash: "9a37bb",
  },
  {
    id: "NW-07",
    kind: "adjudication",
    at: "31 July 2026, 07:41",
    atSort: 741,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "XV-0418-01 adjudicated — accepted as a genuine risk",
    detail:
      "Declared turnover exceeds independent evidence: INR 142.31 cr against GST INR 119.83 cr and bank credits INR 121.44 cr.",
    reason:
      "Both independent sources agree within INR 1.61 cr and the shortfall is present in all twelve months, so this is a level difference and not a timing effect. Accepted as a revenue-quality risk rather than resolved: the assessment is run on evidenced turnover of INR 121.44 cr and drawing power sized at INR 15.80 cr pending the borrower's reconciliation.",
    meta: [
      { label: "Flag", value: "XV-0418-01 · serious · blocking" },
      { label: "Effect", value: "Submission unblocked; finding carried into the memo" },
    ],
    links: [nw("cross-verification"), person("Elena Rossi", "elena-rossi")],
    hash: "2f5c10",
  },
  {
    id: "NW-08",
    kind: "adjudication",
    at: "31 July 2026, 07:44",
    atSort: 744,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "XV-0418-02 adjudicated — accepted as a genuine risk",
    detail:
      "Undisclosed lender obligation: a monthly debit of INR 4,37,500 to Crestline Financial Services, INR 52.50 lakh a year, unreported and unregistered on the charge index.",
    reason:
      "Twelve consecutive debits on the same date with a fixed amount read as an instalment, not a trade payment. Restated debt service brings DSCR from 1.61x to 1.44x, still above the 1.25x floor, so accepted and carried into leverage and debt service.",
    meta: [{ label: "Flag", value: "XV-0418-02 · moderate" }],
    links: [nw("cross-verification"), person("Elena Rossi", "elena-rossi")],
    hash: "6b8d92",
  },
  {
    id: "NW-09",
    kind: "adjudication",
    at: "31 July 2026, 07:46",
    atSort: 746,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "XV-0418-03 adjudicated — accepted as a genuine risk",
    detail: "Buyer concentration: Meridian Auto Systems at 38.4% of sales against CCB's 35% soft cap.",
    reason:
      "Breach acknowledged, mitigated by a three-year OEM supply contract to March 2028 and an unbroken payment record. Recorded as a soft-cap breach with the contract as mitigant.",
    meta: [{ label: "Flag", value: "XV-0418-03 · mild" }],
    links: [nw("cross-verification"), person("Elena Rossi", "elena-rossi")],
    hash: "e4470a",
  },
  {
    id: "NW-10",
    kind: "draft",
    at: "31 July 2026, 07:52",
    atSort: 752,
    actor: "CreditIQ drafting engine",
    actorRole: "Automated",
    human: false,
    title: "Eight-section CAM drafted in CCB template v4.2",
    detail:
      "Borrower and Group Profile through Recommendation drafted from the resolved entity, the spread and the three adjudicated findings. 41 quantitative claims, each bound to a citation. First-cut rating CCB-4 (watch) from the rating model with the evidence-quality overlay applied.",
    meta: [
      { label: "Citations", value: "41 of 41 quantitative claims cited" },
      { label: "Template", value: "CCB CAM template v4.2" },
    ],
    links: [nw("draft")],
    hash: "58c3ad",
  },
  {
    id: "NW-11",
    kind: "edit",
    at: "31 July 2026, 07:58",
    atSort: 758,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "Risk Assessment section rewritten in the analyst's own words",
    detail:
      "The machine draft described the turnover contradiction as 'unreconciled'. Rewritten to state plainly that the assessment is run on evidenced turnover and that the limit is cut accordingly, so the committee reads the consequence and not only the finding.",
    original: "Machine draft, paragraph 2: \"FY2025 turnover remains unreconciled against independent sources.\"",
    replacement:
      "Analyst text: \"Drawing power is sized off a turnover figure two independent sources contradict by around INR 21 cr. The recommendation is therefore run on evidenced turnover of INR 121.44 cr and the limit reduced to INR 15.80 cr.\"",
    meta: [{ label: "Section", value: "Risk Assessment and Rating" }],
    links: [nw("draft"), person("Elena Rossi", "elena-rossi")],
    hash: "77b1e6",
  },
  {
    id: "NW-12",
    kind: "override",
    at: "31 July 2026, 08:01",
    atSort: 801,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "Recommended facility overridden — INR 18.50 cr reduced to INR 15.80 cr",
    detail: "The requested Cash Credit enhancement was cut before the memo left the analyst's desk.",
    original: "INR 18.50 cr Cash Credit as requested",
    replacement: "INR 15.80 cr Cash Credit, LC/BG unchanged at INR 6.75 cr",
    reason:
      "Drawing power computed on evidenced turnover of INR 121.44 cr at 20% of gross sales supports INR 15.80 cr. Sanctioning the full request would lend against turnover the bank cannot evidence.",
    meta: [{ label: "Field", value: "Facility Requested and Purpose · recommended limit" }],
    links: [nw("draft"), person("Elena Rossi", "elena-rossi")],
    hash: "0c92f4",
  },
  {
    id: "NW-13",
    kind: "override",
    at: "31 July 2026, 08:03",
    atSort: 803,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "Internal risk rating held at CCB-4 against a CCB-3 model score",
    detail:
      "The quantitative model scored CCB-3 on leverage, coverage and conduct. The analyst applied the evidence-quality overlay and held the grade at CCB-4 (watch).",
    original: "CCB-3 (model score, quantitative only)",
    replacement: "CCB-4 (watch)",
    reason:
      "A serious cross-verification finding stands unresolved on revenue quality, and an undisclosed obligation restates DSCR to 1.44x. Policy 6.3 requires a one-notch downgrade wherever a serious finding is accepted rather than resolved.",
    meta: [
      { label: "Field", value: "Risk Assessment and Rating · internal rating" },
      { label: "Policy", value: "CCB rating model, qualitative overlay 6.3" },
    ],
    links: [nw("rating"), person("Elena Rossi", "elena-rossi")],
    hash: "3ae8d5",
  },
  {
    id: "NW-14",
    kind: "decision",
    at: "31 July 2026, 08:04",
    atSort: 804,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "Rating and recommendation confirmed by the analyst",
    detail:
      "Recommended for sanction at a reduced Cash Credit limit of INR 15.80 cr with LC/BG of INR 6.75 cr, rated CCB-4 (watch), subject to the borrower's turnover reconciliation and registration of the Crestline obligation before first disbursement.",
    meta: [
      { label: "Attribution", value: "Recommendation is the analyst's, not the model's" },
      { label: "Conditions", value: "Two conditions precedent recorded" },
    ],
    links: [nw("rating"), person("Elena Rossi", "elena-rossi")],
    hash: "d13f7c",
  },
  {
    id: "NW-15",
    kind: "routing",
    at: "31 July 2026, 08:05",
    atSort: 805,
    actor: "CreditIQ routing",
    actorRole: "Automated",
    human: false,
    title: "Submitted and routed to Sofia Almeida, Credit Manager",
    detail:
      "Submission SUB-2026-0418-01 routed to Sofia Almeida for review by 08 July 2026 and then to the West Region Credit Committee chaired by Anand Iyer, Deputy General Manager. Pre-submission checklist passed with all three findings adjudicated and the rating set.",
    meta: [
      { label: "Reference", value: "SUB-2026-0418-01" },
      { label: "Committee", value: "West Region Credit Committee, sitting 14 July 2026" },
    ],
    links: [nw("submission"), person("Sofia Almeida", "sofia-almeida")],
    hash: "8e2b61",
  },
];

const AU_EVENTS: AuditEvent[] = [
  {
    id: "AU-01",
    kind: "source",
    at: "9 June 2026, 09:12",
    atSort: 912,
    actor: "MCA company master and GSTN",
    actorRole: "Registry and tax connectors",
    human: false,
    title: "Identity resolved on the first pass, no disambiguation needed",
    detail:
      "CIN U15490MH2011PLC221876, Aurora Foods Ltd, active, registered office Mumbai Fort. GSTIN 27AAACA8842L1Z4 with 24 of 24 returns filed. One group link to Aurora Cold Chain Pvt Ltd confirmed by the analyst; two directors on the DIN master.",
    meta: [
      { label: "Candidates", value: "One exact match on PAN, confidence high" },
      { label: "Analyst action", value: "Confirmed without amendment" },
    ],
    hash: "51a08c",
  },
  {
    id: "AU-02",
    kind: "source",
    at: "9 June 2026, 09:31",
    atSort: 931,
    actor: "Devika Sundaram",
    actorRole: "Relationship Manager, Mumbai Fort Corporate Branch",
    human: true,
    title: "Consent granted and audited financials received the same day",
    detail:
      "Account Aggregator consent CONS-2026-0402-A signed by Priya Nair, Director, covering Aurora's Meridian 7719 account for twelve months. Audited statements for FY2023 to FY2025 supplied by the borrower's auditors directly.",
    meta: [
      { label: "Sources", value: "5 of 5 returned complete · no fallback required" },
      { label: "Consent", value: "Granted 9 June 2026, valid through 9 July 2026" },
    ],
    hash: "aa7b23",
  },
  {
    id: "AU-03",
    kind: "extraction",
    at: "9 June 2026, 10:04",
    atSort: 1004,
    actor: "CreditIQ extraction engine",
    actorRole: "Automated",
    human: false,
    title: "Spread built and cross-verification run clean",
    detail:
      "Turnover INR 71.30 cr, 79.95 cr and 88.15 cr across FY2023 to FY2025. Declared turnover agreed with GST outward supplies to within 1.2% and with bank credits to within 1.9%, inside the 5% tolerance. 22 rules run, none raised above informational.",
    meta: [
      { label: "Findings", value: "0 serious · 0 moderate · 1 informational (seasonality)" },
      { label: "Ratios", value: "Current ratio 1.61x · DSCR 2.24x · TOL/TNW 1.42x, all inside policy" },
    ],
    hash: "34ce97",
  },
  {
    id: "AU-04",
    kind: "draft",
    at: "10 June 2026, 08:47",
    atSort: 847,
    actor: "CreditIQ drafting engine",
    actorRole: "Automated",
    human: false,
    title: "CAM drafted with 33 cited claims, first-cut rating CCB-2",
    detail:
      "Eight sections drafted in CCB template v4.2. No cross-verification narrative required beyond the clean-run statement. Rating model returned CCB-2 with no qualitative overlay applied, since no finding stood against the borrower.",
    meta: [{ label: "Citations", value: "33 of 33 quantitative claims cited" }],
    hash: "c7710e",
  },
  {
    id: "AU-05",
    kind: "edit",
    at: "10 June 2026, 11:19",
    atSort: 1119,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "Banking Conduct section expanded on seasonality",
    detail:
      "The only human change in this memo. The analyst added two sentences describing the September to November festive peak so the committee would not read the Q3 utilisation spike as stress.",
    original: "Machine draft: \"Average CC utilisation 68.2% with no continuous overdrawing.\"",
    replacement:
      "Analyst text: \"Average CC utilisation is 68.2%, rising to 91% between September and November against the festive packing season and falling back by January. There is no continuous overdrawing in the twelve months reviewed.\"",
    meta: [{ label: "Section", value: "Banking Conduct" }],
    links: [person("Elena Rossi", "elena-rossi")],
    hash: "9012fd",
  },
  {
    id: "AU-06",
    kind: "decision",
    at: "10 June 2026, 11:34",
    atSort: 1134,
    actor: "Elena Rossi",
    actorRole: "Credit Analyst",
    human: true,
    title: "Rating confirmed at CCB-2, no override applied",
    detail:
      "The analyst accepted the model's CCB-2 first cut unchanged and recommended sanction of the Cash Credit renewal at INR 9.40 cr with an LC sub-limit of INR 2.50 cr.",
    meta: [{ label: "Overrides", value: "None recorded on this memo" }],
    links: [person("Elena Rossi", "elena-rossi")],
    hash: "40b6aa",
  },
  {
    id: "AU-07",
    kind: "routing",
    at: "10 June 2026, 11:36",
    atSort: 1136,
    actor: "CreditIQ routing",
    actorRole: "Automated",
    human: false,
    title: "Routed to Sofia Almeida, then to committee",
    detail:
      "Submission SUB-2026-0402-01 reviewed by Sofia Almeida on 11 June 2026 with no queries raised, and placed before the West Region Credit Committee the following day.",
    meta: [{ label: "Reference", value: "SUB-2026-0402-01" }],
    links: [person("Sofia Almeida", "sofia-almeida")],
    hash: "2ba594",
  },
  {
    id: "AU-08",
    kind: "decision",
    at: "12 June 2026, 15:20",
    atSort: 1520,
    actor: "Anand Iyer",
    actorRole: "Deputy General Manager, committee chair",
    human: true,
    title: "Sanctioned by the West Region Credit Committee",
    detail:
      "Sanctioned as recommended at CCB-2: Cash Credit INR 9.40 cr with an LC sub-limit of INR 2.50 cr, renewal for twelve months, next review 30 June 2027. Recorded without conditions beyond the standard covenant set.",
    meta: [
      { label: "Vote", value: "Approved, three members present" },
      { label: "Memo sealed", value: "12 June 2026, 15:41 — read-only from this point" },
    ],
    hash: "f5d802",
  },
];

export const AUDIT_MEMOS: AuditMemo[] = [
  {
    id: "aurora",
    reference: "CAM-2026-0402",
    borrower: "Aurora Foods Ltd",
    slug: "aurora-foods",
    appraisalId: "CAM-2026-0402",
    sector: "Packaged foods and edible oils",
    issued: "12 June 2026",
    status: "Completed · sanctioned",
    rating: "CCB-2",
    ratingLabel: "Approved",
    facilities: "CC INR 9.40 cr + LC INR 2.50 cr",
    analyst: "Elena Rossi",
    approver: "Anand Iyer, Deputy General Manager",
    branch: "Mumbai Fort Corporate Branch",
    seriousFlags: 0,
    sealedAt: "12 June 2026, 15:41",
    digest: "sha256:9f31c0d4e7ab2158",
    retention: "10 years from sanction · disposal 12 June 2036",
    events: AU_EVENTS,
  },
  {
    id: "northwind",
    reference: "CAM-2026-0418",
    borrower: "Northwind Manufacturing Ltd",
    slug: "northwind-manufacturing",
    appraisalId: "CAM-2026-0418",
    sector: "Engineering goods manufacturing",
    issued: "31 July 2026",
    status: "In committee review",
    rating: "CCB-4",
    ratingLabel: "Watch",
    facilities: "CC INR 15.80 cr recommended + LC/BG INR 6.75 cr",
    analyst: "Elena Rossi",
    approver: "Sofia Almeida, Credit Manager (pending committee)",
    branch: "Pune Corporate Branch",
    seriousFlags: 1,
    sealedAt: "Open — record still accruing",
    digest: "sha256:1c84be27fa905d63",
    retention: "10 years from sanction · disposal date set on approval",
    events: NW_EVENTS,
  },
];

export const getAuditMemo = (id: string) => AUDIT_MEMOS.find((m) => m.id === id) ?? AUDIT_MEMOS[0]!;

/* ------------------------------------------------------------ figure traces */

export const FIGURE_TRACES: FigureTrace[] = [
  {
    id: "nw-turnover",
    memoId: "northwind",
    label: "FY2025 turnover carried into the memo",
    value: "INR 121.44 cr evidenced (INR 142.31 cr declared)",
    section: "Financial Analysis and Ratios · Risk Assessment",
    steps: [
      {
        stage: "Source",
        title: "Audited Statement of Profit and Loss FY2025, page 14, line I",
        detail: "Revenue from operations 1,42,31,08,442. Uploaded by Marcus Chen on 31 July 2026, checksum unchanged. Classified as a fallback source, not independent.",
        at: "31 July 2026, 07:14",
        actor: "Marcus Chen",
        link: nw("spread", "#pl-turnover"),
      },
      {
        stage: "Source",
        title: "GSTN return ledger, 27AABCN4521Q1ZP, FY2024-25",
        detail: "Twelve GSTR-3B returns, outward taxable supplies aggregate 1,19,83,44,617. Pulled direct from GSTN, no human handling.",
        at: "31 July 2026, 07:04",
        actor: "GSTN connector",
        link: nw("data", "#gst-turnover"),
      },
      {
        stage: "Source",
        title: "Account Aggregator bundle under consent CONS-2026-0418-A",
        detail: "Customer credits into Meridian 4471 and Horizon 2205 total INR 121.44 cr for the same twelve months, net of inter-account transfers and loan drawdowns.",
        at: "31 July 2026, 07:09",
        actor: "Meridian Bank via AA",
        link: nw("data", "#bank-credits"),
      },
      {
        stage: "Extraction",
        title: "Normalised into the CCB spread as declared turnover",
        detail: "INR 142.31 cr mapped to P&L line 'Revenue from operations' at high confidence, with page and line retained against the cell.",
        at: "31 July 2026, 07:21",
        actor: "CreditIQ extraction engine",
        link: nw("spread", "#pl-turnover"),
      },
      {
        stage: "Check",
        title: "Rule XV-04 raised a serious contradiction",
        detail: "Shortfall of INR 22.48 cr against GST (15.8%) and INR 20.87 cr against credits (14.7%), both beyond the 5% tolerance, present in all twelve months.",
        at: "31 July 2026, 07:36",
        actor: "Cross-verification run XV-2026-0418",
        link: nw("cross-verification"),
      },
      {
        stage: "Human",
        title: "Elena Rossi accepted the finding as a genuine risk",
        detail: "Recorded reasoning: the two independent sources agree within INR 1.61 cr, so the assessment is run on evidenced turnover of INR 121.44 cr and drawing power sized at INR 15.80 cr.",
        at: "31 July 2026, 07:41",
        actor: "Elena Rossi, Credit Analyst",
        link: person("Elena Rossi", "elena-rossi"),
      },
      {
        stage: "Memo",
        title: "Stated in Financial Analysis and driving the recommendation",
        detail: "The memo shows both figures side by side, cites all three sources, and sizes the recommended limit on the evidenced figure rather than the declared one.",
        at: "31 July 2026, 07:58",
        actor: "Elena Rossi (edited from machine draft)",
        link: nw("draft"),
      },
    ],
  },
  {
    id: "nw-rating",
    memoId: "northwind",
    label: "Internal risk rating",
    value: "CCB-4 (watch)",
    section: "Risk Assessment and Rating",
    steps: [
      {
        stage: "Extraction",
        title: "Quantitative model scored CCB-3",
        detail: "Leverage 1.12x, TOL/TNW 2.34x, DSCR 1.61x and CMR-4 conduct produced a CCB-3 score on the quantitative model alone.",
        at: "31 July 2026, 07:52",
        actor: "CCB rating model v3.1",
        link: nw("rating"),
      },
      {
        stage: "Check",
        title: "Evidence-quality overlay triggered",
        detail: "Policy 6.3 requires a one-notch downgrade wherever a serious cross-verification finding is accepted rather than resolved. XV-0418-01 was accepted.",
        at: "31 July 2026, 07:52",
        actor: "CCB rating model, qualitative overlay",
        link: nw("cross-verification"),
      },
      {
        stage: "Human",
        title: "Elena Rossi held the grade at CCB-4 and recorded the reason",
        detail: "Both the CCB-3 original and the CCB-4 override are retained with author and timestamp. The reason cites the unresolved revenue-quality finding and the restated DSCR of 1.44x.",
        at: "31 July 2026, 08:03",
        actor: "Elena Rossi, Credit Analyst",
        link: person("Elena Rossi", "elena-rossi"),
      },
      {
        stage: "Memo",
        title: "Rating stated as CCB-4 (watch) with the override visible",
        detail: "The memo shows the grade, the model score it departs from, and the analyst's reasoning, so the committee reads the judgement and not only the outcome.",
        at: "31 July 2026, 08:04",
        actor: "Elena Rossi",
        link: nw("draft"),
      },
    ],
  },
  {
    id: "nw-crestline",
    memoId: "northwind",
    label: "Undisclosed Crestline obligation",
    value: "INR 4,37,500 per month · INR 52.50 lakh a year",
    section: "Cross-Verification Results · Financial Analysis",
    steps: [
      {
        stage: "Source",
        title: "Meridian Bank 4471 statement, twelve monthly debits",
        detail: "Debits of INR 4,37,500 on the 5th of each month, narration 'ACH DR CRESTLINE FIN SERV', unbroken from April 2024 to March 2025.",
        at: "31 July 2026, 07:09",
        actor: "Meridian Bank via AA",
        link: nw("data", "#bank-credits"),
      },
      {
        stage: "Source",
        title: "Declared obligations and MCA charge index",
        detail: "The borrower's declared obligation schedule lists four facilities, none with Crestline. The charge index shows no registered charge in Crestline's favour.",
        at: "31 July 2026, 07:02",
        actor: "MCA registry connector",
        link: nw("identity"),
      },
      {
        stage: "Check",
        title: "Rule XV-11 raised a moderate finding",
        detail: "Recurring fixed debit with no matching declared obligation and no registered charge. Implied residual principal of about INR 1.85 cr at prevailing NBFC rates.",
        at: "31 July 2026, 07:36",
        actor: "Cross-verification run XV-2026-0418",
        link: nw("cross-verification"),
      },
      {
        stage: "Human",
        title: "Elena Rossi accepted it and restated debt service",
        detail: "DSCR restated from 1.61x to 1.44x, still above the 1.25x floor. Registration of the charge made a condition precedent to first disbursement.",
        at: "31 July 2026, 07:44",
        actor: "Elena Rossi, Credit Analyst",
        link: person("Elena Rossi", "elena-rossi"),
      },
      {
        stage: "Memo",
        title: "Narrated in Cross-Verification Results with the restated DSCR",
        detail: "Carried into leverage and debt service and into the conditions precedent, cited to the bank statement and the charge index.",
        at: "31 July 2026, 07:52",
        actor: "CreditIQ drafting engine",
        link: nw("draft"),
      },
    ],
  },
  {
    id: "au-turnover",
    memoId: "aurora",
    label: "FY2025 turnover",
    value: "INR 88.15 cr",
    section: "Financial Analysis and Ratios",
    steps: [
      {
        stage: "Source",
        title: "Audited Statement of Profit and Loss FY2025, page 11",
        detail: "Revenue from operations 88,15,42,006, supplied directly by the borrower's auditors on 9 June 2026.",
        at: "9 June 2026, 09:31",
        actor: "Devika Sundaram",
      },
      {
        stage: "Source",
        title: "GSTN return ledger, FY2024-25",
        detail: "Outward taxable supplies aggregate INR 87.09 cr, a 1.2% difference against the audited figure and inside the 5% tolerance.",
        at: "9 June 2026, 09:12",
        actor: "GSTN connector",
      },
      {
        stage: "Check",
        title: "Rule XV-04 passed",
        detail: "Declared, GST and bank-credit turnover agreed within 1.9%. No finding raised; the clean-run statement was written into the memo instead.",
        at: "9 June 2026, 10:04",
        actor: "Cross-verification run XV-2026-0402",
      },
      {
        stage: "Memo",
        title: "Stated as INR 88.15 cr with three sources cited",
        detail: "No human change was made to this figure or to the paragraph containing it.",
        at: "10 June 2026, 08:47",
        actor: "CreditIQ drafting engine",
      },
    ],
  },
  {
    id: "au-rating",
    memoId: "aurora",
    label: "Internal risk rating",
    value: "CCB-2 (approved)",
    section: "Risk Assessment and Rating",
    steps: [
      {
        stage: "Extraction",
        title: "Model scored CCB-2, no overlay applied",
        detail: "Current ratio 1.61x, DSCR 2.24x, TOL/TNW 1.42x, CMR-2 conduct. No serious finding stood, so the evidence-quality overlay did not trigger.",
        at: "10 June 2026, 08:47",
        actor: "CCB rating model v3.1",
      },
      {
        stage: "Human",
        title: "Elena Rossi accepted the first cut unchanged",
        detail: "No override recorded on this memo. The confirmation itself is attributed and timestamped.",
        at: "10 June 2026, 11:34",
        actor: "Elena Rossi, Credit Analyst",
        link: person("Elena Rossi", "elena-rossi"),
      },
      {
        stage: "Memo",
        title: "Sanctioned at CCB-2 by the committee",
        detail: "Approved on 12 June 2026 as recommended, chaired by Anand Iyer. The memo was sealed read-only nineteen minutes later.",
        at: "12 June 2026, 15:20",
        actor: "West Region Credit Committee",
      },
    ],
  },
];

export const tracesFor = (memoId: string) => FIGURE_TRACES.filter((t) => t.memoId === memoId);

/* ------------------------------------------- live session events overlay */

/** Events recorded in this session, merged on top of the sealed record. */
export function sessionEvents(memo: AuditMemo, xv: XVState, m: MemoState): AuditEvent[] {
  if (memo.id !== "northwind") return [];
  const out: AuditEvent[] = [];
  for (const f of FLAGS) {
    const a = xv.adjudications[f.id];
    if (!a) continue;
    out.push({
      id: `LIVE-${f.id}`,
      kind: "adjudication",
      at: a.at,
      atSort: 900 + f.rank,
      actor: a.by,
      actorRole: "Credit Analyst",
      human: true,
      title: `${f.id} re-adjudicated — ${OUTCOME_LABEL[a.outcome as Outcome].toLowerCase()}`,
      detail: f.title,
      reason: a.rationale,
      meta: [{ label: "Recorded", value: "This session, appended to the record" }],
      links: [nw("cross-verification")],
      hash: "live",
    });
  }
  for (const o of m.overrides) {
    out.push({
      id: `LIVE-${o.id}`,
      kind: "override",
      at: o.at,
      atSort: 920,
      actor: o.by,
      actorRole: "Credit Analyst",
      human: true,
      title: `${o.field} overridden — ${o.original} to ${o.override}`,
      detail: o.scope,
      original: o.original,
      replacement: o.override,
      reason: o.reason,
      meta: [{ label: "Recorded", value: "This session, appended to the record" }],
      links: [nw("draft")],
      hash: "live",
    });
  }
  if (m.submitted) {
    out.push({
      id: "LIVE-SUB",
      kind: "routing",
      at: m.submitted.at,
      atSort: 940,
      actor: m.submitted.by,
      actorRole: "Credit Analyst",
      human: true,
      title: `Re-submitted and routed to ${m.submitted.to}`,
      detail: `Submission ${m.submitted.reference} raised from this session.`,
      meta: [{ label: "Recorded", value: "This session, appended to the record" }],
      links: [nw("submission")],
      hash: "live",
    });
  }
  return out;
}

/* --------------------------------------------------------- export state */

export type ExportRecord = { at: string; reference: string; digest: string; pages: number; memoId: string };

let exports: ExportRecord[] = [];
const listeners = new Set<() => void>();

export function recordExport(memo: AuditMemo, events: number): ExportRecord {
  const seq = (exports.length + 1).toString().padStart(2, "0");
  const rec: ExportRecord = {
    at: "31 July 2026, 08:19",
    reference: `EXM-2026-${memo.reference.slice(-4)}-${seq}`,
    digest: `${memo.digest}-${seq}`,
    pages: 12 + events,
    memoId: memo.id,
  };
  exports = [rec, ...exports];
  listeners.forEach((l) => l());
  return rec;
}

export function useExports(): ExportRecord[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => exports,
    () => exports,
  );
}
