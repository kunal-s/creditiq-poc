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

export type CheckOutcome = "pass" | "warn" | "fail";

export type ValidationCheck = {
  key: string;
  label: string;
  outcome: CheckOutcome;
  detail: string;
};

export type ChecklistItem = {
  id: string;
  name: string;
  category: "Constitution and KYC" | "Financial" | "Statutory" | "Banking" | "Security" | "Business";
  why: string;
  basis: string;
  blocking: boolean;
  status: DocStatus;
  weight: number;
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
  kind: "request" | "reminder" | "upload" | "rejection" | "acceptance" | "call" | "waiver" | "handoff";
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
  pan: string;
  gstin: string;
  udyam: string;
  product: string;
  facilities: string;
  requested: string;
  branch: string;
  rm: string;
  owner: string;
  opened: string;
  lastContact: string;
  daysInCollection: number;
  targetSanction: string;
  contact: { name: string; role: string; phone: string; email: string };
  items: ChecklistItem[];
  chase: ChaseEvent[];
  handedOffTo?: string | undefined;
};

/* ------------------------------------------------------------------- seed */

const SOUTHGATE_ITEMS: ChecklistItem[] = [
  {
    id: "coi",
    name: "Certificate of incorporation and MOA/AOA",
    category: "Constitution and KYC",
    why: "Establishes legal existence and borrowing powers before any facility is documented.",
    basis: "Private limited company · CCB SME checklist 2.1",
    blocking: true,
    status: "accepted",
    weight: 6,
    fileName: "Southgate_Textiles_COI_MOA_AOA.pdf",
    receivedAt: "04 August 2026, 11:18",
    receivedFrom: "Client portal — Anita Kulkarni",
    pages: "28 pages · 3.1 MB",
    checks: [
      { key: "legible", label: "Legibility", outcome: "pass", detail: "Text layer present on all 28 pages." },
      { key: "identifier", label: "Identifier match", outcome: "pass", detail: "CIN U17120PN2011PTC141288 matches MCA registry." },
      { key: "signature", label: "Attestation", outcome: "pass", detail: "ROC seal and digital signature verified." },
    ],
  },
  {
    id: "udyam",
    name: "Udyam registration certificate",
    category: "Constitution and KYC",
    why: "Confirms MSME classification, which drives pricing, collateral relief and priority-sector tagging.",
    basis: "MSMED Act classification · CCB SME checklist 2.4",
    blocking: true,
    status: "accepted",
    weight: 4,
    fileName: "Southgate_Udyam_Certificate.pdf",
    receivedAt: "04 August 2026, 11:20",
    receivedFrom: "Client portal — Anita Kulkarni",
    pages: "1 page · 210 KB",
    checks: [
      { key: "identifier", label: "Identifier match", outcome: "pass", detail: "UDYAM-MH-19-0043712 matches PAN on file." },
      { key: "class", label: "Classification", outcome: "pass", detail: "Registered as Small enterprise, investment INR 3.62 cr." },
    ],
  },
  {
    id: "kyc-directors",
    name: "Director KYC — PAN, Aadhaar and address proof",
    category: "Constitution and KYC",
    why: "Required for all three directors before the borrower can be onboarded in core banking.",
    basis: "RBI Master Direction on KYC · CCB SME checklist 2.6",
    blocking: true,
    status: "rejected",
    weight: 5,
    fileName: "Southgate_Director_KYC_set.pdf",
    receivedAt: "06 August 2026, 15:04",
    receivedFrom: "Client portal — Anita Kulkarni",
    pages: "9 pages · 1.4 MB",
    rejection:
      "Only two of three directors covered. Address proof for Vikram Sethi is a mobile bill dated 12 January 2026, older than the two-month window.",
    checks: [
      { key: "completeness", label: "Completeness", outcome: "fail", detail: "3 directors on MCA record, 2 KYC sets received." },
      { key: "recency", label: "Recency", outcome: "fail", detail: "Address proof 7 months old against the 2-month rule." },
      { key: "legible", label: "Legibility", outcome: "pass", detail: "All pages readable at 300 dpi." },
    ],
  },
  {
    id: "fs-3y",
    name: "Audited financial statements FY2024 to FY2026",
    category: "Financial",
    why: "Three comparable years are the base of the spread; anything shorter cannot support the ratio grid.",
    basis: "CCB ratio policy v6.2 · minimum three audited years",
    blocking: true,
    status: "rejected",
    weight: 12,
    fileName: "Southgate_Financials_FY24_FY25_FY26.pdf",
    receivedAt: "07 August 2026, 09:37",
    receivedFrom: "Client portal — CA Prakash Bhide",
    pages: "44 pages · 5.8 MB",
    rejection:
      "FY2026 statement is provisional and unsigned. FY2024 and FY2025 are audited and accepted; the provisional year cannot carry the spread.",
    checks: [
      { key: "period", label: "Period coverage", outcome: "warn", detail: "FY2024 and FY2025 audited; FY2026 provisional." },
      { key: "signature", label: "Auditor sign-off", outcome: "fail", detail: "No auditor signature or UDIN on the FY2026 set." },
      { key: "schedules", label: "Schedules attached", outcome: "pass", detail: "Notes and fixed asset schedules present for all years." },
    ],
  },
  {
    id: "itr",
    name: "Income tax returns AY2024-25 to AY2026-27",
    category: "Statutory",
    why: "Cross-checks declared turnover and profit against the audited statements.",
    basis: "CCB cross-verification rule XV-04",
    blocking: false,
    status: "accepted",
    weight: 6,
    fileName: "Southgate_ITR_AY2425_AY2627.pdf",
    receivedAt: "05 August 2026, 18:12",
    receivedFrom: "Client portal — CA Prakash Bhide",
    pages: "22 pages · 2.6 MB",
    checks: [
      { key: "ack", label: "Acknowledgement", outcome: "pass", detail: "All three ITR-V acknowledgements present." },
      { key: "identifier", label: "Identifier match", outcome: "pass", detail: "PAN on returns matches PAN on file." },
    ],
  },
  {
    id: "gst",
    name: "GST returns — GSTR-1 and GSTR-3B, 24 months",
    category: "Statutory",
    why: "Monthly outward supplies are the independent turnover check and drive the drawing-power view.",
    basis: "CCB cross-verification rule XV-04 · connector: GST returns",
    blocking: false,
    status: "accepted",
    weight: 7,
    fileName: "Fetched from GSTN connector",
    receivedAt: "04 August 2026, 11:31",
    receivedFrom: "GST returns connector — consent DR-CONS-0142",
    pages: "24 monthly filings",
    checks: [
      { key: "coverage", label: "Period coverage", outcome: "pass", detail: "Aug 2024 to Jul 2026, no missing month." },
      { key: "status", label: "Filing discipline", outcome: "warn", detail: "Three filings late by 9 to 17 days in FY2026." },
    ],
  },
  {
    id: "bank-stmt",
    name: "Bank statements — 12 months, all operating accounts",
    category: "Banking",
    why: "Conduct, cheque returns and collection routing cannot be assessed without the full window.",
    basis: "CCB SME checklist 4.2 · Account Aggregator preferred",
    blocking: true,
    status: "requested",
    weight: 10,
    checks: [],
  },
  {
    id: "sanction-others",
    name: "Sanction letters from existing lenders",
    category: "Banking",
    why: "Needed to state total obligations and to size the takeover, if any.",
    basis: "CCB SME checklist 4.5",
    blocking: false,
    status: "received",
    weight: 5,
    fileName: "Southgate_Kolhapur_Coop_Sanction_2025.pdf",
    receivedAt: "08 August 2026, 12:55",
    receivedFrom: "Relationship manager — Rohan Deshpande",
    pages: "6 pages · 780 KB",
    checks: [
      { key: "legible", label: "Legibility", outcome: "pass", detail: "Scan clean at 240 dpi." },
      { key: "completeness", label: "Completeness", outcome: "warn", detail: "One lender covered; CIBIL shows two live term loans." },
    ],
  },
  {
    id: "stock-debtors",
    name: "Latest stock and debtors statement",
    category: "Business",
    why: "Drawing power on the cash credit is computed off this statement.",
    basis: "CCB working capital assessment note 3.3",
    blocking: true,
    status: "requested",
    weight: 8,
    checks: [],
  },
  {
    id: "collateral",
    name: "Title deeds and valuation for the Ichalkaranji unit",
    category: "Security",
    why: "Primary collateral for the term loan; charge cannot be created without a clear title chain.",
    basis: "CCB security documentation manual 7.1",
    blocking: false,
    status: "requested",
    weight: 7,
    checks: [],
  },
  {
    id: "orders",
    name: "Order book and buyer confirmations",
    category: "Business",
    why: "Supports the projected turnover behind the enhancement ask.",
    basis: "CCB SME checklist 6.2",
    blocking: false,
    status: "not-requested",
    weight: 4,
    checks: [],
  },
  {
    id: "provisional-fs",
    name: "Provisional financials for the current year to date",
    category: "Financial",
    why: "Bridges the audited FY2025 position to the appraisal date.",
    basis: "CCB SME checklist 3.6",
    blocking: false,
    status: "waived",
    weight: 3,
    waiverReason:
      "Waived by Elena Rossi on 08 August 2026 — the four-month gap is covered by GST filings and will be reconciled at spread stage.",
    checks: [],
  },
];

const SOUTHGATE_CHASE: ChaseEvent[] = [
  {
    id: "ev-1",
    at: "03 August 2026, 10:05",
    actor: "Rohan Deshpande, Ichalkaranji SME Branch",
    kind: "request",
    title: "Case opened and first request issued",
    detail:
      "Twelve-item checklist derived from constitution (private limited), segment (Small) and product (CC plus TL). Secure portal link sent to Anita Kulkarni with a seven-day window.",
    items: ["Certificate of incorporation and MOA/AOA", "Udyam registration certificate", "Audited financial statements FY2024 to FY2026"],
  },
  {
    id: "ev-2",
    at: "04 August 2026, 11:31",
    actor: "Anita Kulkarni, Southgate Textiles",
    kind: "upload",
    title: "First upload batch — three documents",
    detail:
      "Incorporation set, Udyam certificate and GST consent granted in the same session. GST returns for 24 months pulled automatically once consent was recorded.",
    items: ["Certificate of incorporation and MOA/AOA", "Udyam registration certificate", "GST returns — GSTR-1 and GSTR-3B, 24 months"],
  },
  {
    id: "ev-3",
    at: "05 August 2026, 18:12",
    actor: "CA Prakash Bhide, statutory auditor",
    kind: "upload",
    title: "Income tax returns received",
    detail: "Three assessment years with acknowledgements. Accepted on first pass.",
    items: ["Income tax returns AY2024-25 to AY2026-27"],
  },
  {
    id: "ev-4",
    at: "06 August 2026, 15:04",
    actor: "Anita Kulkarni, Southgate Textiles",
    kind: "upload",
    title: "Director KYC set uploaded",
    detail: "Nine pages covering two directors.",
    items: ["Director KYC — PAN, Aadhaar and address proof"],
  },
  {
    id: "ev-5",
    at: "06 August 2026, 15:06",
    actor: "CreditIQ validation",
    kind: "rejection",
    title: "Director KYC rejected — two automated checks failed",
    detail:
      "Third director missing against the MCA record, and the address proof for Vikram Sethi is dated 12 January 2026, outside the two-month window. Precise re-ask sent to the client, naming only what is wrong.",
    items: ["Director KYC — PAN, Aadhaar and address proof"],
  },
  {
    id: "ev-6",
    at: "07 August 2026, 09:39",
    actor: "CreditIQ validation",
    kind: "rejection",
    title: "FY2026 financials rejected as provisional",
    detail:
      "FY2024 and FY2025 audited statements accepted for the spread. FY2026 set carries no auditor signature or UDIN, so it cannot be used; the audited FY2026 statement is the outstanding ask.",
    items: ["Audited financial statements FY2024 to FY2026"],
  },
  {
    id: "ev-7",
    at: "07 August 2026, 16:20",
    actor: "Elena Rossi, Credit Analyst",
    kind: "call",
    title: "Call with the auditor",
    detail:
      "CA Bhide confirmed the FY2026 audit closes on 19 August 2026 and undertook to upload the signed statement the same day. Recorded against the case rather than left in an inbox.",
  },
  {
    id: "ev-8",
    at: "08 August 2026, 09:00",
    actor: "CreditIQ collection engine",
    kind: "reminder",
    title: "Reminder two sent — four items outstanding",
    detail:
      "Single consolidated reminder rather than four separate messages: bank statements, stock and debtors statement, title deeds and valuation, and the corrected director KYC.",
    items: [
      "Bank statements — 12 months, all operating accounts",
      "Latest stock and debtors statement",
      "Title deeds and valuation for the Ichalkaranji unit",
      "Director KYC — PAN, Aadhaar and address proof",
    ],
  },
  {
    id: "ev-9",
    at: "08 August 2026, 12:55",
    actor: "Rohan Deshpande, Ichalkaranji SME Branch",
    kind: "upload",
    title: "Existing lender sanction letter added by the branch",
    detail:
      "Kolhapur District Co-operative Bank sanction dated 22 May 2025. CIBIL shows a second live term loan, so one more sanction letter is expected.",
    items: ["Sanction letters from existing lenders"],
  },
  {
    id: "ev-10",
    at: "08 August 2026, 13:40",
    actor: "Elena Rossi, Credit Analyst",
    kind: "waiver",
    title: "Provisional financials waived",
    detail:
      "Four-month gap covered by GST filings; reconciliation deferred to spread stage. Waiver reason recorded for the examiner.",
    items: ["Provisional financials for the current year to date"],
  },
];

const OTHER_CASES: DocReadyCase[] = [
  {
    id: "DR-2026-0138",
    borrower: "Konkan Steel Traders Pvt Ltd",
    slug: "konkan-steel-traders",
    constitution: "Private limited company",
    sector: "Steel trading and fabrication",
    segment: "Small",
    pan: "AADCK••••R",
    gstin: "27AADCK••••R1ZT",
    udyam: "UDYAM-MH-18-0021904",
    product: "MSME working capital renewal",
    facilities: "CC INR 2.60 cr",
    requested: "INR 2.60 cr",
    branch: "Ratnagiri SME Branch",
    rm: "Sneha Pawar",
    owner: "Elena Rossi",
    opened: "28 July 2026",
    lastContact: "07 August 2026",
    daysInCollection: 11,
    targetSanction: "26 August 2026",
    contact: { name: "Mahesh Sawant", role: "Director", phone: "+91 98•••• 4417", email: "mahesh@konkansteel.in" },
    items: [],
    chase: [],
  },
  {
    id: "DR-2026-0145",
    borrower: "Deccan Auto Components Pvt Ltd",
    slug: "deccan-auto-components",
    constitution: "Private limited company",
    sector: "Auto component machining",
    segment: "Medium",
    pan: "AAECD••••L",
    gstin: "27AAECD••••L1ZK",
    udyam: "UDYAM-MH-26-0058120",
    product: "Term loan for CNC capacity",
    facilities: "TL INR 6.20 cr + CC INR 2.90 cr",
    requested: "INR 9.10 cr",
    branch: "Chakan MIDC Branch",
    rm: "Marcus Chen",
    owner: "Elena Rossi",
    opened: "05 August 2026",
    lastContact: "08 August 2026",
    daysInCollection: 3,
    targetSanction: "04 September 2026",
    contact: { name: "Ritu Bansal", role: "Chief Financial Officer", phone: "+91 90•••• 8802", email: "ritu.bansal@deccanauto.in" },
    items: [],
    chase: [],
  },
  {
    id: "DR-2026-0131",
    borrower: "Vashi Cold Storage LLP",
    slug: "vashi-cold-storage",
    constitution: "Limited liability partnership",
    sector: "Cold chain and warehousing",
    segment: "Small",
    pan: "AAQFV••••H",
    gstin: "27AAQFV••••H1ZB",
    udyam: "UDYAM-MH-19-0009873",
    product: "MSME working capital, fresh",
    facilities: "CC INR 1.85 cr",
    requested: "INR 1.85 cr",
    branch: "Navi Mumbai SME Branch",
    rm: "Priya Nair",
    owner: "Elena Rossi",
    opened: "18 July 2026",
    lastContact: "01 August 2026",
    daysInCollection: 21,
    targetSanction: "20 August 2026",
    contact: { name: "Farhan Qureshi", role: "Designated partner", phone: "+91 99•••• 1130", email: "farhan@vashicold.in" },
    items: [],
    chase: [],
  },
  {
    id: "DR-2026-0126",
    borrower: "Solapur Weaving Mills Pvt Ltd",
    slug: "solapur-weaving-mills",
    constitution: "Private limited company",
    sector: "Cotton weaving",
    segment: "Micro",
    pan: "AAJCS••••D",
    gstin: "27AAJCS••••D1ZF",
    udyam: "UDYAM-MH-19-0031255",
    product: "MSME term loan under CGTMSE",
    facilities: "TL INR 0.95 cr",
    requested: "INR 0.95 cr",
    branch: "Solapur Commercial Branch",
    rm: "Devika Sundaram",
    owner: "Elena Rossi",
    opened: "11 July 2026",
    lastContact: "08 August 2026",
    daysInCollection: 28,
    targetSanction: "15 August 2026",
    contact: { name: "Sunita Rathi", role: "Director", phone: "+91 87•••• 6604", email: "sunita@solapurweaving.in" },
    items: [],
    chase: [],
  },
];

/* placeholder progress for the non-lead cases, expressed as accepted/total weights */
export const CASE_SUMMARY: Record<string, { total: number; accepted: number; outstanding: number; blocking: number }> = {
  "DR-2026-0138": { total: 11, accepted: 9, outstanding: 2, blocking: 0 },
  "DR-2026-0145": { total: 14, accepted: 5, outstanding: 9, blocking: 4 },
  "DR-2026-0131": { total: 10, accepted: 4, outstanding: 6, blocking: 3 },
  "DR-2026-0126": { total: 9, accepted: 8, outstanding: 1, blocking: 1 },
};

const SOUTHGATE: DocReadyCase = {
  id: "DR-2026-0142",
  borrower: "Southgate Textiles Pvt Ltd",
  slug: "southgate-textiles",
  constitution: "Private limited company",
  sector: "Cotton yarn and processed fabric",
  segment: "Small",
  pan: "AAJCS••••T",
  gstin: "27AAJCS••••T1ZM",
  udyam: "UDYAM-MH-19-0043712",
  product: "MSME working capital with capex",
  facilities: "CC INR 3.40 cr + TL INR 1.15 cr",
  requested: "INR 4.55 cr",
  branch: "Ichalkaranji SME Branch",
  rm: "Rohan Deshpande",
  owner: "Elena Rossi",
  opened: "03 August 2026",
  lastContact: "08 August 2026",
  daysInCollection: 5,
  targetSanction: "29 August 2026",
  contact: {
    name: "Anita Kulkarni",
    role: "Finance Controller",
    phone: "+91 94•••• 2087",
    email: "anita.kulkarni@southgatetextiles.in",
  },
  items: SOUTHGATE_ITEMS,
  chase: SOUTHGATE_CHASE,
};

/* --------------------------------------------------------------- readiness */

export const STATUS_LABEL: Record<DocStatus, string> = {
  "not-requested": "Not requested",
  requested: "Requested",
  received: "Received",
  rejected: "Rejected",
  accepted: "Accepted",
  waived: "Waived",
};

export function readiness(c: DocReadyCase) {
  const summary = CASE_SUMMARY[c.id];
  if (!c.items.length && summary) {
    return {
      score: Math.round((summary.accepted / summary.total) * 100),
      total: summary.total,
      accepted: summary.accepted,
      outstanding: summary.outstanding,
      blockingOpen: summary.blocking,
      inReview: 0,
    };
  }
  const settled = (s: DocStatus) => s === "accepted" || s === "waived";
  const weightTotal = c.items.reduce((n, i) => n + i.weight, 0);
  const weightDone = c.items.filter((i) => settled(i.status)).reduce((n, i) => n + i.weight, 0);
  return {
    score: weightTotal ? Math.round((weightDone / weightTotal) * 100) : 0,
    total: c.items.length,
    accepted: c.items.filter((i) => settled(i.status)).length,
    outstanding: c.items.filter((i) => !settled(i.status)).length,
    blockingOpen: c.items.filter((i) => i.blocking && !settled(i.status)).length,
    inReview: c.items.filter((i) => i.status === "received").length,
  };
}

/* ------------------------------------------------------------------- store */

type State = { cases: DocReadyCase[] };

let state: State = { cases: [SOUTHGATE, ...OTHER_CASES] };
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

const NOW = "Today, 09:12";

export const docReadyActions = {
  request(caseId: string, itemId: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = { ...c, items: c.items.map((i) => (i.id === itemId ? { ...i, status: "requested" as DocStatus } : i)) };
      return log(next, {
        at: NOW,
        actor: "Elena Rossi, Credit Analyst",
        kind: "request",
        title: `Requested: ${item?.name ?? itemId}`,
        detail: `Added to the open ask on the client portal for ${c.contact.name}.`,
        items: item ? [item.name] : undefined,
      });
    });
  },
  accept(caseId: string, itemId: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        items: c.items.map((i) => (i.id === itemId ? { ...i, status: "accepted" as DocStatus, rejection: undefined } : i)),
      };
      return log(next, {
        at: NOW,
        actor: "Elena Rossi, Credit Analyst",
        kind: "acceptance",
        title: `Accepted: ${item?.name ?? itemId}`,
        detail: "Analyst accepted the document into the evidence set.",
        items: item ? [item.name] : undefined,
      });
    });
  },
  reject(caseId: string, itemId: string, reason: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        items: c.items.map((i) =>
          i.id === itemId ? { ...i, status: "rejected" as DocStatus, rejection: reason } : i,
        ),
      };
      return log(next, {
        at: NOW,
        actor: "Elena Rossi, Credit Analyst",
        kind: "rejection",
        title: `Rejected: ${item?.name ?? itemId}`,
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
        items: c.items.map((i) => (i.id === itemId ? { ...i, status: "waived" as DocStatus, waiverReason: reason } : i)),
      };
      return log(next, {
        at: NOW,
        actor: "Elena Rossi, Credit Analyst",
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
        items: c.items.map((i) =>
          i.id === itemId
            ? {
                ...i,
                status: "received" as DocStatus,
                fileName: `${c.slug.replace(/-/g, "_")}_${i.id}.pdf`,
                receivedAt: NOW,
                receivedFrom: `Client portal — ${c.contact.name}`,
                pages: "machine checks queued",
                checks: [
                  { key: "legible", label: "Legibility", outcome: "pass" as CheckOutcome, detail: "Text layer detected on every page." },
                  { key: "identifier", label: "Identifier match", outcome: "pass" as CheckOutcome, detail: `PAN and GSTIN match ${c.borrower}.` },
                  { key: "period", label: "Period coverage", outcome: "warn" as CheckOutcome, detail: "Coverage to be confirmed by the analyst." },
                ],
              }
            : i,
        ),
      };
      return log(next, {
        at: NOW,
        actor: `${c.contact.name}, ${c.borrower}`,
        kind: "upload",
        title: `Client upload received: ${item?.name ?? itemId}`,
        detail: "Uploaded through the secure portal; automated checks run on receipt.",
        items: item ? [item.name] : undefined,
      });
    });
  },
  sendReminder(caseId: string) {
    setCase(caseId, (c) => {
      const open = c.items.filter((i) => i.status === "requested" || i.status === "rejected");
      return log(c, {
        at: NOW,
        actor: "Elena Rossi, Credit Analyst",
        kind: "reminder",
        title: `Reminder sent — ${open.length} item${open.length === 1 ? "" : "s"} outstanding`,
        detail: `One consolidated message to ${c.contact.name} listing only what is still missing or was rejected.`,
        items: open.map((i) => i.name),
      });
    });
  },
  handoff(caseId: string): string | null {
    const c = state.cases.find((x) => x.id === caseId);
    if (!c) return null;
    if (c.handedOffTo) return c.handedOffTo;
    if (readiness(c).blockingOpen > 0) return null;

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
      analyst: c.owner,
      rm: c.rm,
      started: "Today",
      rating: "Not rated",
      ratingLabel: "Awaiting first cut",
      discrepancies: 0,
      branch: c.branch,
    };
    if (!APPRAISALS.some((a) => a.id === camId)) APPRAISALS.push(appraisal);

    setCase(caseId, (nc) =>
      log({ ...nc, handedOffTo: camId }, {
        at: NOW,
        actor: "Elena Rossi, Credit Analyst",
        kind: "handoff",
        title: `Handed off to credit appraisal ${camId}`,
        detail: `Readiness reached with no blocking gap. Identifiers, constitution, facility ask, branch and relationship manager carried across; ${
          nc.items.filter((i) => i.status === "accepted").length
        } accepted documents registered as present so the pipeline does not re-ask for them.`,
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
