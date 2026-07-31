import { useSyncExternalStore } from "react";
import type { Confidence } from "@/data/identity";

export type SourceStatus = "received" | "partial" | "awaiting" | "not-attempted";

export type AcqSource = {
  key: string;
  name: string;
  category: string;
  connector: string;
  provenance: string;
  coverage: string;
  freshness: string;
  status: SourceStatus;
  confidence: Confidence;
  findings: string[];
  downstream: { label: string; anchor: string };
  raw: { title: string; lines: string[] };
  note?: string;
};

export const CONSENT_WINDOW = "01 April 2025 to 31 March 2026";

export const CONSENT_ACCOUNTS = [
  {
    id: "meridian-4471",
    bank: "Meridian Bank",
    branch: "Chakan MIDC, Pune",
    type: "Current account",
    masked: "XXXX XXXX 4471",
    ifsc: "MERI0000318",
    note: "Primary collection account for OEM receipts",
  },
  {
    id: "horizon-2205",
    bank: "Horizon Bank",
    branch: "Bhosari, Pune",
    type: "Cash credit account",
    masked: "XXXX XXXX 2205",
    ifsc: "HRZN0000114",
    note: "Working capital account with a second lender",
  },
];

export const ACCEPTED_UPLOADS = [
  "Bank statements — PDF or password-free bank-issued statement, per account, full window",
  "Audited financial statements with schedules and auditor's report — FY2023 to FY2025",
  "Income tax returns with computation and acknowledgement — AY2023-24 to AY2025-26",
  "GST returns — GSTR-1 and GSTR-3B, monthly, FY2025",
  "Sanction letters and charge documents from other lenders",
];

export const INGESTED_UPLOADS = [
  {
    id: "upl-2201",
    name: "Northwind_Manufacturing_Audited_FS_FY2025.pdf",
    kind: "Audited financial statements · FY2025",
    size: "4.2 MB · 61 pages",
    uploadedBy: "Marcus Chen, Pune Corporate Branch",
    uploadedAt: "28 July 2026, 16:42",
    provenance: "Upload",
    detail: "Signed by M/s Kulkarni & Associates, FRN 104512W, dated 12 June 2025.",
  },
  {
    id: "upl-2202",
    name: "Northwind_ITR_AY2025-26_Acknowledgement.pdf",
    kind: "Income tax return · AY2025-26",
    size: "0.8 MB · 9 pages",
    uploadedBy: "Marcus Chen, Pune Corporate Branch",
    uploadedAt: "28 July 2026, 16:44",
    provenance: "Upload",
    detail: "ITR-6, acknowledgement number 428913470280725.",
  },
];

export const SOURCES: AcqSource[] = [
  {
    key: "gst",
    name: "GST returns",
    category: "Statutory filing",
    connector: "GSTN filing history · consent-bound API",
    provenance: "Direct from GSTN",
    coverage: "GSTR-1 and GSTR-3B, April 2024 to March 2025 (FY2025)",
    freshness: "Pulled 30 July 2026, 07:12",
    status: "received",
    confidence: "high",
    findings: [
      "24 of 24 returns filed; on time except two late GSTR-3B filings (November 2024 filed 27 December 2024, January 2025 filed 24 February 2025).",
      "Declared outward supplies FY2025 INR 84.60 cr against audited revenue of INR 78.90 cr.",
    ],
    downstream: { label: "Revenue and GST turnover reconciliation", anchor: "gst-turnover" },
    raw: {
      title: "GSTN filing history — 27AABCN4521Q1ZP",
      lines: [
        "GSTR-1 2024-04 | filed 2024-05-09 | taxable value 6,42,10,400",
        "GSTR-3B 2024-11 | filed 2024-12-27 | due 2024-12-20 | LATE 7 days | tax paid 41,08,220",
        "GSTR-3B 2025-01 | filed 2025-02-24 | due 2025-02-20 | LATE 4 days | tax paid 38,71,905",
        "GSTR-1 2025-03 | filed 2025-04-10 | taxable value 8,11,95,700",
        "FY2025 aggregate outward supplies 84,60,32,118",
      ],
    },
  },
  {
    key: "bureau",
    name: "Commercial credit bureau",
    category: "Conduct",
    connector: "CIBIL Commercial · member enquiry",
    provenance: "TransUnion CIBIL",
    coverage: "Company report, PAN AABCN4521Q, 36-month conduct history",
    freshness: "Pulled 30 July 2026, 07:14",
    status: "received",
    confidence: "high",
    findings: [
      "CMR-4. One 31–60 day delinquency on a term loan about 14 months ago (May 2025); current across all facilities since.",
      "Three commercial enquiries in the last six months, including one by a non-bank lender in March 2026.",
    ],
    downstream: { label: "Conduct and rating inputs", anchor: "bureau-conduct" },
    raw: {
      title: "CIBIL Commercial report — CCR/2026/4471902",
      lines: [
        "CMR band: CMR-4 (as at 30 June 2026)",
        "Facility 1 | Cash Credit | CCB | limit 12,20,00,000 | DPD 000 x 36",
        "Facility 2 | Term Loan | Horizon Bank | limit 4,50,00,000 | DPD 031 in 2025-05",
        "Enquiry | 2026-03-11 | NBFC | working capital | 5,00,00,000",
      ],
    },
  },
  {
    key: "registry",
    name: "Company registry and charges",
    category: "Registry",
    connector: "MCA21 and CERSAI · registry lookup",
    provenance: "MCA and CERSAI",
    coverage: "CIN U27310MH2009PLC198435 · charge register, full history",
    freshness: "Pulled 30 July 2026, 07:10",
    status: "received",
    confidence: "high",
    findings: [
      "Existing charge in favour of Continental Commercial Bank, INR 12.20 cr, created 30 August 2025, on stock and book debts.",
      "One older charge in favour of Horizon Bank satisfied on 18 January 2024; no other subsisting charges.",
    ],
    downstream: { label: "Security and charge position", anchor: "charges" },
    raw: {
      title: "CERSAI charge register — CIN U27310MH2009PLC198435",
      lines: [
        "Charge ID 100482913 | holder Continental Commercial Bank | amount 12,20,00,000 | created 2025-08-30 | status SUBSISTING",
        "Charge ID 100311874 | holder Horizon Bank | amount 4,50,00,000 | created 2021-11-02 | satisfied 2024-01-18",
        "MCA index of charges last updated 2026-07-24",
      ],
    },
  },
  {
    key: "lei",
    name: "LEI lookup",
    category: "Registry",
    connector: "LEIL India · GLEIF mirror",
    provenance: "LEIL registry",
    coverage: "894500XYZ7NORTHWIND12",
    freshness: "Pulled 30 July 2026, 07:10",
    status: "received",
    confidence: "high",
    findings: [
      "Issued and valid to 31 March 2027 — renewal falls inside the proposed facility tenor.",
      "Related party Northwind Logistics Ltd has no LEI on record; carried as an open item from identity.",
    ],
    downstream: { label: "Identity block in the memo", anchor: "identity-block" },
    raw: {
      title: "LEIL record — 894500XYZ7NORTHWIND12",
      lines: [
        "Legal name: Northwind Manufacturing Limited",
        "Registration status: ISSUED | next renewal 2027-03-31",
        "Legal address: Plot D-42, Chakan Industrial Area Phase II, Pune 410501",
        "Managing LOU: Legal Entity Identifier India Ltd",
      ],
    },
  },
  {
    key: "media",
    name: "Adverse media",
    category: "Screening",
    connector: "Media and sanctions screening · three feeds",
    provenance: "Screening service",
    coverage: "Borrower, group and three directors, 60-month lookback",
    freshness: "Attempted 30 July 2026, 07:16",
    status: "partial",
    confidence: "medium",
    findings: [
      "No material hits across the two feeds that returned. Two routine trade-press mentions of a new OEM order win.",
      "One source timed out (regional-language press aggregator) — the screen is incomplete until it is retried.",
    ],
    note: "Partial — one source timed out, retry available",
    downstream: { label: "Reputational screen in the memo", anchor: "screening" },
    raw: {
      title: "Screening run SCR-2026-118842",
      lines: [
        "Feed 1 national press | 412 documents scanned | 0 material hits",
        "Feed 2 sanctions and watchlists | 0 hits on entity, group or DINs",
        "Feed 3 regional-language aggregator | STATUS TIMEOUT after 30,000 ms | 0 documents scanned",
      ],
    },
  },
  {
    key: "bank",
    name: "Bank-account data via Account Aggregator",
    category: "Transactions",
    connector: "Account Aggregator · consent-bound",
    provenance: "Awaiting borrower consent",
    coverage: `Meridian Bank current account 4471 and Horizon Bank cash credit account 2205 · ${CONSENT_WINDOW}`,
    freshness: "Consent request not yet sent",
    status: "awaiting",
    confidence: "low",
    findings: [
      "No transaction data can be fetched until the borrower approves the consent request on their own device.",
      "Without it the bank-credit line of the cross-verification cannot be run.",
    ],
    downstream: { label: "Bank credits versus declared turnover", anchor: "bank-credits" },
    raw: {
      title: "Consent artefact (draft) — CONS-2026-0418-A",
      lines: [
        "Requester: Continental Commercial Bank | FIU ID CCB-FIU-0021",
        "Accounts: MERI XXXX4471 (SAVINGS/CURRENT), HRZN XXXX2205 (CREDIT)",
        `Data window: ${CONSENT_WINDOW}`,
        "Purpose: 103 — Explicit consent for credit appraisal | frequency ONE-TIME | revocable",
      ],
    },
  },
  {
    key: "financials",
    name: "Audited financials and ITR",
    category: "Documents",
    connector: "Document ingestion · relationship manager upload",
    provenance: "Upload",
    coverage: "FY2023, FY2024 and FY2025 audited statements with ITR acknowledgements",
    freshness: "Ingested 28 July 2026, 16:44",
    status: "received",
    confidence: "high",
    findings: [
      "Three years of audited statements with schedules and auditor's report; unmodified opinion in all three years.",
      "ITR-6 acknowledgements match the audited profit before tax in each year.",
    ],
    downstream: { label: "Three-year spread", anchor: "spread-base" },
    raw: {
      title: "Ingested documents — CAM-2026-0418",
      lines: [
        "Northwind_Manufacturing_Audited_FS_FY2025.pdf | 61 pages | OCR complete | 412 figures extracted",
        "Northwind_Manufacturing_Audited_FS_FY2024.pdf | 58 pages | OCR complete | 396 figures extracted",
        "Northwind_ITR_AY2025-26_Acknowledgement.pdf | 9 pages | ack 428913470280725",
      ],
    },
  },
];

export const STATUS_LABEL: Record<SourceStatus, string> = {
  received: "Received",
  partial: "Partial",
  awaiting: "Awaiting consent",
  "not-attempted": "Not attempted",
};

export const STATUS_TONE: Record<SourceStatus, string> = {
  received: "border-positive/30 bg-positive-soft text-positive",
  partial: "border-flag/35 bg-flag-soft text-flag-foreground",
  awaiting: "border-flag/35 bg-flag-soft text-flag-foreground",
  "not-attempted": "border-border bg-surface-muted text-muted-foreground",
};

/* ------------------------------------------------------------------ */
/* Session state: consent, retries and fallback uploads                */
/* ------------------------------------------------------------------ */

export type BankState = "awaiting" | "requested" | "consented" | "declined" | "fallback";

export type AcqState = {
  bank: BankState;
  consentRef: string;
  mediaRetried: boolean;
  fallbackUploads: { id: string; name: string; kind: string; uploadedAt: string }[];
};

let state: AcqState = {
  bank: "awaiting",
  consentRef: "CONS-2026-0418-A",
  mediaRetried: false,
  fallbackUploads: [],
};

const listeners = new Set<() => void>();
function emit() {
  for (const l of listeners) l();
}

export function setAcqState(patch: Partial<AcqState>) {
  state = { ...state, ...patch };
  emit();
}

export function addFallbackUpload(name: string, kind: string) {
  state = {
    ...state,
    bank: "fallback",
    fallbackUploads: [
      ...state.fallbackUploads,
      { id: `upl-${Math.random().toString(36).slice(2, 7)}`, name, kind, uploadedAt: "31 July 2026, 07:33" },
    ],
  };
  emit();
}

export function useAcqState(): AcqState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}

export function bankRowFor(s: AcqState): Pick<AcqSource, "status" | "provenance" | "freshness" | "findings" | "confidence" | "note"> {
  switch (s.bank) {
    case "requested":
      return {
        status: "awaiting",
        provenance: "Consent request sent",
        freshness: `Sent 31 July 2026, 07:33 · ${s.consentRef}`,
        confidence: "low",
        note: "Awaiting borrower approval — link valid 24 hours",
        findings: [
          "Consent request delivered to the authorised signatory for both named accounts.",
          "Nothing is fetched until the borrower approves on their own device.",
        ],
      };
    case "consented":
      return {
        status: "received",
        provenance: "Consent",
        freshness: `Fetched 31 July 2026, 07:34 · ${s.consentRef}`,
        confidence: "high",
        findings: [
          "12 months of transactions for both accounts; 1,842 credits totalling INR 79.14 cr.",
          "Bank credits sit INR 5.46 cr below declared GST turnover of INR 84.60 cr — carried into cross-verification.",
        ],
      };
    case "declined":
      return {
        status: "awaiting",
        provenance: "Consent declined by borrower",
        freshness: "Declined 31 July 2026, 07:33",
        confidence: "low",
        note: "Declined — supply statements through the manual fallback",
        findings: [
          "The borrower declined the Account Aggregator request; no transaction data was fetched.",
          "Bank statements must now be supplied to the fallback and will be marked provenance 'fallback'.",
        ],
      };
    case "fallback":
      return {
        status: "received",
        provenance: "Fallback upload",
        freshness: "Ingested 31 July 2026, 07:33",
        confidence: "medium",
        note: "Received by fallback — not consent-bound, lower assurance",
        findings: [
          "Statements supplied by the relationship manager rather than fetched under consent.",
          "Cross-verification will flag the provenance difference in the audit trail.",
        ],
      };
    default:
      return {
        status: "awaiting",
        provenance: "Awaiting borrower consent",
        freshness: "Consent request not yet sent",
        confidence: "low",
        findings: SOURCES.find((x) => x.key === "bank")!.findings,
      };
  }
}
