import { useSyncExternalStore } from "react";

export type Severity = "serious" | "moderate" | "mild";

export const SEVERITY_LABEL: Record<Severity, string> = {
  serious: "Serious",
  moderate: "Moderate",
  mild: "Mild",
};

export const SEVERITY_TONE: Record<Severity, string> = {
  serious: "border-critical/30 bg-critical-soft text-critical",
  moderate: "border-flag/35 bg-flag-soft text-flag-foreground",
  mild: "border-info/25 bg-info-soft text-info",
};

export const SEVERITY_BAR: Record<Severity, string> = {
  serious: "bg-critical",
  moderate: "bg-flag",
  mild: "bg-info",
};

/** One side of a contradiction: a figure with the source it came from. */
export type EvidenceFigure = {
  key: string;
  label: string;
  value: string;
  basis: string;
  provenance: string;
  independent: boolean;
  to: "spread" | "data";
  anchor?: string;
  excerpt: string[];
  excerptTitle: string;
};

export type Flag = {
  id: string;
  rank: number;
  severity: Severity;
  title: string;
  summary: string;
  reading: string;
  detected: string;
  rule: string;
  policy: string;
  blocking: boolean;
  memoSection: string;
  owner: string;
  figures: EvidenceFigure[];
  gaps: { label: string; value: string }[];
  months?: { month: string; gst: number; credits: number }[];
  ledger?: { date: string; narration: string; amount: string }[];
  concentration?: { name: string; share: number; value: string }[];
};

export const FLAGS: Flag[] = [
  {
    id: "XV-0418-01",
    rank: 1,
    severity: "serious",
    title: "Declared turnover exceeds independent evidence",
    summary:
      "FY2025 turnover of INR 142.31 cr in the audited financials and the ITR is not supported by either independent source. GST filings for the same twelve months total INR 119.83 cr and credits into the two consented bank accounts total INR 121.44 cr.",
    reading:
      "Either turnover is overstated in the audited statement, or a material part of collections is settled outside the banking and GST system. Both readings change the assessment: drawing power on an INR 18.50 cr Cash Credit is sized off the very turnover that is in question.",
    detected: "31 July 2026, 07:36 · run XV-2026-0418",
    rule: "Rule XV-04 — declared revenue against GST outward supplies and bank credits, tolerance 5%",
    policy: "CCB CAM template v4.2, cross-verification rule 4.1",
    blocking: true,
    memoSection: "Risk narrative — revenue quality",
    owner: "Elena Rossi",
    figures: [
      {
        key: "afs",
        label: "Audited financials and ITR",
        value: "INR 142.31 cr",
        basis: "Revenue from operations, year ended 31 March 2025",
        provenance: "Fallback · uploaded by Marcus Chen",
        independent: false,
        to: "spread",
        anchor: "#pl-turnover",
        excerptTitle: "Northwind_Manufacturing_Audited_FS_FY2025.pdf — page 14, line I",
        excerpt: [
          "I.   Revenue from operations              1,42,31,08,442",
          "II.  Other income                            1,04,71,900",
          "III. Total income (I + II)                 1,43,35,80,342",
          "",
          "ITR-6 AY2025-26, acknowledgement 274918365120725",
          "Part A-P&L, item 1(a) gross receipts     1,42,31,08,442",
        ],
      },
      {
        key: "gst",
        label: "GST filings (GSTR-3B)",
        value: "INR 119.83 cr",
        basis: "Outward taxable supplies, April 2024 to March 2025, 12 of 12 returns filed",
        provenance: "Direct from GSTN",
        independent: true,
        to: "data",
        anchor: "#gst-turnover",
        excerptTitle: "GSTN return ledger — 27AABCN4521Q1ZP, FY2024-25",
        excerpt: [
          "Period      Filed        3.1(a) outward taxable supplies",
          "Apr 2024    18 May 2024              9,42,18,110",
          "May 2024    17 Jun 2024              9,88,04,325",
          "…",
          "Feb 2025    18 Mar 2025             10,64,77,208",
          "Mar 2025    16 Apr 2025             11,02,41,880",
          "Aggregate FY2024-25                1,19,83,44,617",
        ],
      },
      {
        key: "bank",
        label: "Bank credits (Account Aggregator)",
        value: "INR 121.44 cr",
        basis: "Customer credits into Meridian 4471 and Horizon 2205, same twelve months",
        provenance: "Consent CONS-2026-0418-A",
        independent: true,
        to: "data",
        anchor: "#bank-credits",
        excerptTitle: "Account Aggregator bundle — credit summary, both accounts",
        excerpt: [
          "Meridian Bank 4471   1,412 customer credits     94,18,62,040",
          "Horizon Bank 2205      430 customer credits     27,25,71,300",
          "Total customer credits                        1,21,44,33,340",
          "",
          "Excluded: 38 inter-account transfers, CC drawdowns and one",
          "insurance settlement of 1,18,40,000 (not trade receipts).",
        ],
      },
    ],
    gaps: [
      { label: "Gap against GST outward supplies", value: "INR 22.48 cr · 15.8% of declared" },
      { label: "Gap against bank credits", value: "INR 20.87 cr · 14.7% of declared" },
      { label: "CCB tolerance", value: "5% — breached on both legs" },
    ],
    months: [
      { month: "Apr 2024", gst: 9.42, credits: 9.61 },
      { month: "May 2024", gst: 9.88, credits: 10.04 },
      { month: "Jun 2024", gst: 9.71, credits: 9.55 },
      { month: "Jul 2024", gst: 10.12, credits: 10.28 },
      { month: "Aug 2024", gst: 9.34, credits: 9.12 },
      { month: "Sep 2024", gst: 10.41, credits: 10.66 },
      { month: "Oct 2024", gst: 9.86, credits: 9.94 },
      { month: "Nov 2024", gst: 9.18, credits: 9.02 },
      { month: "Dec 2024", gst: 10.24, credits: 10.31 },
      { month: "Jan 2025", gst: 9.40, credits: 9.68 },
      { month: "Feb 2025", gst: 10.65, credits: 11.05 },
      { month: "Mar 2025", gst: 11.62, credits: 12.18 },
    ],
  },
  {
    id: "XV-0418-02",
    rank: 2,
    severity: "moderate",
    title: "Undisclosed lender obligation",
    summary:
      "A recurring monthly debit of INR 4,37,500 to Crestline Financial Services Ltd runs through the Meridian Bank 4471 statement in all twelve months — about INR 52.50 lakh a year. No Crestline facility appears in the borrower's declared obligations or in the spread's debt schedule.",
    reading:
      "Leverage and debt service are both understated. Adding the obligation lifts total debt by the residual principal and pulls DSCR down; the borrower should also explain why an NBFC facility was left out of the declaration.",
    detected: "31 July 2026, 07:36 · run XV-2026-0418",
    rule: "Rule XV-11 — recurring debits matched against declared obligations and charge registries",
    policy: "CCB CAM template v4.2, obligations completeness rule 4.4",
    blocking: false,
    memoSection: "Risk narrative — leverage and debt service",
    owner: "Elena Rossi",
    figures: [
      {
        key: "declared",
        label: "Declared obligations",
        value: "INR 16.70 cr",
        basis: "CCB Cash Credit 12.20 cr and Meridian equipment loan 4.50 cr",
        provenance: "Borrower declaration at intake",
        independent: false,
        to: "spread",
        anchor: "#bs-debt",
        excerptTitle: "Declaration of borrowings, signed 22 June 2026",
        excerpt: [
          "1. Continental Commercial Bank — Cash Credit    12,20,00,000",
          "2. Meridian Bank — equipment term loan            4,50,00,000",
          "3. Any other borrowing                                    NIL",
        ],
      },
      {
        key: "observed",
        label: "Observed in bank statement",
        value: "INR 4,37,500 / month",
        basis: "12 of 12 months, standing instruction to Crestline Financial Services Ltd",
        provenance: "Consent CONS-2026-0418-A",
        independent: true,
        to: "data",
        anchor: "#bank-credits",
        excerptTitle: "Meridian_Bank_4471_Apr2024-Mar2025 — narration filter 'CRESTLINE'",
        excerpt: [
          "07 Apr 2024  ACH DR CRESTLINE FIN SERV LN60148       4,37,500.00",
          "07 May 2024  ACH DR CRESTLINE FIN SERV LN60148       4,37,500.00",
          "07 Jun 2024  ACH DR CRESTLINE FIN SERV LN60148       4,37,500.00",
          "…  nine further debits, same amount and narration  …",
          "07 Mar 2025  ACH DR CRESTLINE FIN SERV LN60148       4,37,500.00",
          "Total debited FY2024-25                            52,50,000.00",
        ],
      },
      {
        key: "registry",
        label: "Charge registry",
        value: "No Crestline charge",
        basis: "MCA index of charges and CERSAI show only the CCB 12.20 cr charge subsisting",
        provenance: "MCA / CERSAI",
        independent: true,
        to: "data",
        anchor: "#registry-charges",
        excerptTitle: "CERSAI charge register — CIN U27310MH2009PLC198435",
        excerpt: [
          "100482913  Continental Commercial Bank  12,20,00,000  subsisting",
          "100311874  Horizon Bank                  4,50,00,000  satisfied 18 Jan 2024",
          "",
          "No charge in favour of Crestline Financial Services Ltd —",
          "consistent with an unsecured NBFC facility.",
        ],
      },
    ],
    gaps: [
      { label: "Annual outflow", value: "INR 52.50 lakh" },
      { label: "Implied facility", value: "approx. INR 1.85 cr residual, 48-month amortisation" },
      { label: "Effect on DSCR", value: "1.61 falls to 1.44 if included" },
    ],
    ledger: [
      { date: "07 Apr 2024", narration: "ACH DR CRESTLINE FIN SERV LN60148", amount: "4,37,500.00" },
      { date: "07 Aug 2024", narration: "ACH DR CRESTLINE FIN SERV LN60148", amount: "4,37,500.00" },
      { date: "07 Dec 2024", narration: "ACH DR CRESTLINE FIN SERV LN60148", amount: "4,37,500.00" },
      { date: "07 Mar 2025", narration: "ACH DR CRESTLINE FIN SERV LN60148", amount: "4,37,500.00" },
    ],
  },
  {
    id: "XV-0418-03",
    rank: 3,
    severity: "mild",
    title: "Buyer concentration above policy soft cap",
    summary:
      "Meridian Auto Systems Ltd accounts for 38.4% of FY2025 sales — INR 54.65 cr of INR 142.31 cr — against CCB's 35% soft cap for a single buyer. The top three buyers together are 61.2%.",
    reading:
      "Not a contradiction between sources, but a structural exposure: a pause in one OEM programme removes more than a third of revenue and the receivable cycle with it. A soft-cap breach is reported and mitigated in the memo rather than declined.",
    detected: "31 July 2026, 07:36 · run XV-2026-0418",
    rule: "Rule XV-19 — single-buyer share of sales against the concentration soft cap",
    policy: "CCB credit policy, concentration soft cap 35% of sales",
    blocking: false,
    memoSection: "Risk narrative — business and concentration",
    owner: "Elena Rossi",
    figures: [
      {
        key: "top-buyer",
        label: "Top buyer share",
        value: "38.4%",
        basis: "Meridian Auto Systems Ltd, INR 54.65 cr of FY2025 sales",
        provenance: "GSTR-1 counterparty analysis",
        independent: true,
        to: "data",
        anchor: "#gst-turnover",
        excerptTitle: "GSTR-1 B2B counterparty summary, FY2024-25",
        excerpt: [
          "27AAACM2201F1Z8  Meridian Auto Systems Ltd     54,65,10,400   38.4%",
          "27AABCV8812K1ZM  Vantage Drivetrain Pvt Ltd    21,04,88,120   14.8%",
          "24AAECS5510L1ZD  Sarvodaya Castings Ltd        11,38,44,900    8.0%",
          "Remaining 61 counterparties                    55,22,64,580   38.8%",
        ],
      },
      {
        key: "cap",
        label: "CCB soft cap",
        value: "35.0%",
        basis: "Single-buyer concentration; a breach is reportable, not a decline",
        provenance: "CCB credit policy",
        independent: false,
        to: "spread",
        anchor: "#ratio-wc",
        excerptTitle: "CCB credit policy — concentration limits",
        excerpt: [
          "Single buyer       soft cap 35% of sales    report and mitigate",
          "Top three buyers   soft cap 60% of sales    report and mitigate",
          "Single buyer       hard cap 50% of sales    committee approval",
        ],
      },
    ],
    gaps: [
      { label: "Headroom used", value: "38.4% against a 35% cap · 3.4 points over" },
      { label: "Top three buyers", value: "61.2% against a 60% cap" },
      { label: "Mitigant on file", value: "OEM contract to March 2028, 45-day terms honoured" },
    ],
    concentration: [
      { name: "Meridian Auto Systems Ltd", share: 38.4, value: "INR 54.65 cr" },
      { name: "Vantage Drivetrain Pvt Ltd", share: 14.8, value: "INR 21.05 cr" },
      { name: "Sarvodaya Castings Ltd", share: 8.0, value: "INR 11.38 cr" },
      { name: "61 other counterparties", share: 38.8, value: "INR 55.23 cr" },
    ],
  },
];

export function getFlag(id: string) {
  return FLAGS.find((f) => f.id === id);
}

/* ---------------------------------------------------------------- state */

export type Outcome = "resolved" | "accepted" | "info-requested";

export const OUTCOME_LABEL: Record<Outcome, string> = {
  resolved: "Resolved with evidence",
  accepted: "Accepted as a genuine risk",
  "info-requested": "More information requested",
};

export const OUTCOME_TONE: Record<Outcome, string> = {
  resolved: "border-positive/30 bg-positive-soft text-positive",
  accepted: "border-flag/35 bg-flag-soft text-flag-foreground",
  "info-requested": "border-info/25 bg-info-soft text-info",
};

export type Adjudication = { outcome: Outcome; rationale: string; by: string; at: string };
export type Note = { id: string; flagId: string; text: string; by: string; at: string };

export type XVState = {
  adjudications: Record<string, Adjudication>;
  owners: Record<string, string>;
  notes: Note[];
};

let state: XVState = { adjudications: {}, owners: {}, notes: [] };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const REVIEWERS = [
  "Elena Rossi · Credit Analyst",
  "Marcus Chen · Relationship Manager",
  "Devika Sundaram · Relationship Manager",
  "Anand Iyer · Credit Manager",
];

export function adjudicate(flagId: string, outcome: Outcome, rationale: string, by: string) {
  state = {
    ...state,
    adjudications: {
      ...state.adjudications,
      [flagId]: { outcome, rationale, by, at: "31 July 2026, 07:41" },
    },
  };
  emit();
}

export function reopenFlag(flagId: string) {
  const next = { ...state.adjudications };
  delete next[flagId];
  state = { ...state, adjudications: next };
  emit();
}

export function reassignFlag(flagId: string, owner: string) {
  state = { ...state, owners: { ...state.owners, [flagId]: owner } };
  emit();
}

export function addNote(flagId: string, text: string, by: string) {
  state = {
    ...state,
    notes: [
      ...state.notes,
      { id: `n-${Math.random().toString(36).slice(2, 7)}`, flagId, text, by, at: "31 July 2026, 07:41" },
    ],
  };
  emit();
}

export function useXVState(): XVState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}

export function ownerOf(s: XVState, f: Pick<Flag, "id" | "owner">) {
  return s.owners[f.id] ?? `${f.owner} · Credit Analyst`;
}

export function isBlocked(s: XVState) {
  return FLAGS.some((f) => f.blocking && !s.adjudications[f.id]);
}

/* ------------------------------------------------- exception queue rows */

export type Exception = {
  flagId: string;
  appraisalId: string;
  borrower: string;
  severity: Severity;
  title: string;
  detail: string;
  ageDays: number;
  raised: string;
  owner: string;
  blocking: boolean;
  stage: string;
};

/** Open exceptions on other borrowers in the West Region book. */
export const OTHER_EXCEPTIONS: Exception[] = [
  {
    flagId: "XV-0426-01",
    appraisalId: "CAM-2026-0426",
    borrower: "Sahyadri Pharma Distributors Pvt Ltd",
    severity: "moderate",
    title: "Two GST returns not filed for the assessed window",
    detail:
      "GSTR-3B for January and February 2026 are not on the GSTN ledger, so two months of the twelve-month turnover test cannot be evidenced independently.",
    ageDays: 11,
    raised: "20 July 2026",
    owner: "Devika Sundaram · Relationship Manager",
    blocking: true,
    stage: "Data",
  },
  {
    flagId: "XV-0421-01",
    appraisalId: "CAM-2026-0421",
    borrower: "Trident Industrial Packaging Ltd",
    severity: "moderate",
    title: "Bureau shows an overdue absent from the declaration",
    detail:
      "CIBIL Commercial reports a 31-day overdue on a Horizon Bank equipment loan in November 2025; the borrower declared a clean conduct record.",
    ageDays: 6,
    raised: "25 July 2026",
    owner: "Elena Rossi · Credit Analyst",
    blocking: false,
    stage: "Draft",
  },
  {
    flagId: "XV-0421-02",
    appraisalId: "CAM-2026-0421",
    borrower: "Trident Industrial Packaging Ltd",
    severity: "mild",
    title: "Registered office differs from GST principal place",
    detail:
      "MCA registered office is Vapi, Gujarat; the GST principal place of business is Silvassa. Both are the borrower's own premises per the site visit note.",
    ageDays: 6,
    raised: "25 July 2026",
    owner: "Marcus Chen · Relationship Manager",
    blocking: false,
    stage: "Draft",
  },
];

export function northwindExceptions(s: XVState): Exception[] {
  return FLAGS.map((f) => ({
    flagId: f.id,
    appraisalId: "CAM-2026-0418",
    borrower: "Northwind Manufacturing Ltd",
    severity: f.severity,
    title: f.title,
    detail: f.summary,
    ageDays: 0,
    raised: "31 July 2026",
    owner: ownerOf(s, f),
    blocking: f.blocking,
    stage: "Cross-Verification",
  }));
}
