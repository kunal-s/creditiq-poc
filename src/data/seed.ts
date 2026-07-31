export type Stage =
  | "Identity"
  | "Data"
  | "Spread"
  | "Cross-Verification"
  | "Draft"
  | "Submission"
  | "Completed";

export const STAGE_ROUTE: Record<Stage, string> = {
  Identity: "identity",
  Data: "data",
  Spread: "spread",
  "Cross-Verification": "cross-verification",
  Draft: "draft",
  Submission: "submission",
  Completed: "submission",
};

export const TENANT = {
  bank: "Continental Commercial Bank",
  unit: "Corporate and Commercial Credit",
  region: "West Region",
};

export const CURRENT_USER = {
  name: "Elena Rossi",
  role: "Credit Analyst",
  initials: "ER",
  email: "elena.rossi@contcombank.in",
};

export type Appraisal = {
  id: string;
  borrower: string;
  sector: string;
  pan: string;
  gstin: string;
  proposal: string;
  facilities: string;
  exposure: string;
  stage: Stage;
  analyst: string;
  rm: string;
  started: string;
  completed?: string;
  rating: string;
  ratingLabel: string;
  discrepancies: number;
  reviewDue?: string;
  branch: string;
};

export const APPRAISALS: Appraisal[] = [
  {
    id: "CAM-2026-0418",
    borrower: "Northwind Manufacturing Ltd",
    sector: "Engineering goods manufacturing",
    pan: "AABCN••••Q",
    gstin: "27AABCN4521Q1ZP",
    proposal: "Cash Credit enhancement INR 12.20 cr to INR 18.50 cr",
    facilities: "CC INR 18.50 cr + LC/BG INR 6.75 cr",
    exposure: "INR 25.25 cr",
    stage: "Cross-Verification",
    analyst: "Elena Rossi",
    rm: "Marcus Chen",
    started: "22 June 2026",
    rating: "CCB-4",
    ratingLabel: "First cut",
    discrepancies: 2,
    reviewDue: "31 August 2026",
    branch: "Pune Corporate Branch",
  },
  {
    id: "CAM-2026-0402",
    borrower: "Aurora Foods Ltd",
    sector: "Packaged foods and edible oils",
    pan: "AACCA••••P",
    gstin: "27AACCA••••P1ZR",
    proposal: "Cash Credit renewal INR 9.40 cr",
    facilities: "CC INR 9.40 cr",
    exposure: "INR 9.40 cr",
    stage: "Completed",
    analyst: "Elena Rossi",
    rm: "Priya Nair",
    started: "2 June 2026",
    completed: "12 June 2026",
    rating: "CCB-2",
    ratingLabel: "Approved",
    discrepancies: 0,
    branch: "Mumbai Fort Corporate Branch",
  },
  {
    id: "CAM-2026-0426",
    borrower: "Sahyadri Pharma Distributors Pvt Ltd",
    sector: "Pharmaceutical distribution",
    pan: "AAGCS••••M",
    gstin: "27AAGCS••••M1Z4",
    proposal: "Working capital sanction INR 7.85 cr (fresh)",
    facilities: "CC INR 6.10 cr + LC INR 1.75 cr",
    exposure: "INR 7.85 cr",
    stage: "Data",
    analyst: "Elena Rossi",
    rm: "Devika Sundaram",
    started: "8 July 2026",
    rating: "CCB-5",
    ratingLabel: "Indicative",
    discrepancies: 0,
    branch: "Nashik Commercial Branch",
  },
  {
    id: "CAM-2026-0421",
    borrower: "Trident Industrial Packaging Ltd",
    sector: "Corrugated and industrial packaging",
    pan: "AABCT••••J",
    gstin: "24AABCT••••J1ZQ",
    proposal: "Term Loan INR 14.30 cr for line expansion",
    facilities: "TL INR 14.30 cr + CC INR 4.60 cr",
    exposure: "INR 18.90 cr",
    stage: "Draft",
    analyst: "Elena Rossi",
    rm: "Marcus Chen",
    started: "29 June 2026",
    rating: "CCB-3",
    ratingLabel: "First cut",
    discrepancies: 1,
    branch: "Vadodara Corporate Branch",
  },
];

export const getAppraisal = (id: string) => APPRAISALS.find((a) => a.id === id);

export type AttentionItem = {
  id: string;
  kind: "discrepancy" | "review";
  severity: "high" | "medium" | "low";
  appraisalId: string;
  borrower: string;
  title: string;
  detail: string;
  step: string;
};

export const ATTENTION: AttentionItem[] = [
  {
    id: "DSC-1147",
    kind: "discrepancy",
    severity: "high",
    appraisalId: "CAM-2026-0418",
    borrower: "Northwind Manufacturing Ltd",
    title: "Declared turnover exceeds GST filings and bank credits",
    detail:
      "FY25 declared INR 84.60 cr against GSTR-3B INR 71.35 cr and bank credit summations of INR 68.92 cr — a gap of INR 15.68 cr.",
    step: "cross-verification",
  },
  {
    id: "DSC-1148",
    kind: "discrepancy",
    severity: "high",
    appraisalId: "CAM-2026-0418",
    borrower: "Northwind Manufacturing Ltd",
    title: "Undisclosed recurring lender payment",
    detail:
      "Monthly debit of INR 18.40 lakh to Sundaram Finance Ltd across 11 statement months, absent from the declared obligations.",
    step: "cross-verification",
  },
  {
    id: "RVW-0318",
    kind: "review",
    severity: "medium",
    appraisalId: "CAM-2026-0418",
    borrower: "Northwind Manufacturing Ltd",
    title: "Annual review due 31 August 2026",
    detail: "Sanction dated 30 August 2025 lapses in 34 days; renewal memo must reach committee by 18 August 2026.",
    step: "submission",
  },
];

export const PORTFOLIO = {
  memosThisMonth: 23,
  memosLastMonth: 19,
  turnaroundBefore: "6.4 days",
  turnaroundAfter: "1.3 days",
  medianReviewSession: "48 min",
  ratingDistribution: [
    { grade: "CCB-1", count: 2 },
    { grade: "CCB-2", count: 5 },
    { grade: "CCB-3", count: 9 },
    { grade: "CCB-4", count: 14 },
    { grade: "CCB-5", count: 8 },
    { grade: "CCB-6", count: 4 },
    { grade: "CCB-7", count: 2 },
    { grade: "CCB-8", count: 1 },
  ],
};

export const COUNTERS = {
  inProgress: 4,
  awaitingReview: 2,
  dueThisWeek: 3,
};