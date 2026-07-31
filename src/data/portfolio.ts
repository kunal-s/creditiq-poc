import { useSyncExternalStore } from "react";
import { APPRAISALS } from "./seed";

/* ------------------------------------------------------- library records */

export type MemoStatus =
  | "In committee review"
  | "Completed"
  | "In preparation"
  | "Drafting"
  | "Refresh due";

export type MemoVersion = {
  version: string;
  reference: string;
  issued: string;
  rating: string;
  status: string;
  author: string;
  facilities: string;
  summary: string;
  current?: boolean;
};

export type BorrowerRecord = {
  slug: string;
  name: string;
  appraisalId: string;
  sector: string;
  pan: string;
  gstin: string;
  branch: string;
  rm: string;
  analyst: string;
  exposure: string;
  facilities: string;
  rating: string;
  ratingLabel: string;
  status: MemoStatus;
  lastUpdated: string;
  lastUpdatedSort: number;
  nextReview: string;
  nextReviewSort: number;
  memos: number;
  versions: MemoVersion[];
  refreshable: boolean;
};

export const BORROWERS: BorrowerRecord[] = [
  {
    slug: "northwind-manufacturing",
    name: "Northwind Manufacturing Ltd",
    appraisalId: "CAM-2026-0418",
    sector: "Engineering goods manufacturing",
    pan: "AABCN••••Q",
    gstin: "27AABCN4521Q1ZP",
    branch: "Pune Corporate Branch",
    rm: "Marcus Chen",
    analyst: "Elena Rossi",
    exposure: "INR 25.25 cr",
    facilities: "CC INR 18.50 cr + LC/BG INR 6.75 cr",
    rating: "CCB-4",
    ratingLabel: "Watch",
    status: "In committee review",
    lastUpdated: "31 July 2026",
    lastUpdatedSort: 20260731,
    nextReview: "31 August 2026",
    nextReviewSort: 20260831,
    memos: 4,
    refreshable: true,
    versions: [
      {
        version: "v4",
        reference: "CAM-2026-0418",
        issued: "31 July 2026",
        rating: "CCB-4",
        status: "In committee review",
        author: "Elena Rossi",
        facilities: "CC INR 18.50 cr + LC/BG INR 6.75 cr",
        summary:
          "Cash Credit enhancement from INR 12.20 cr to INR 18.50 cr. Turnover contradiction of INR 22.48 cr against GST and an undisclosed Crestline obligation carried into the memo; recommended at a reduced limit of INR 15.80 cr.",
        current: true,
      },
      {
        version: "v3",
        reference: "CAM-2025-0377",
        issued: "18 August 2025",
        rating: "CCB-3",
        status: "Sanctioned",
        author: "Elena Rossi",
        facilities: "CC INR 12.20 cr + LC/BG INR 5.00 cr",
        summary:
          "Annual renewal on FY2025 provisional financials. Turnover INR 117.60 cr, current ratio 1.31x, DSCR 1.72x. No cross-verification findings above mild; buyer concentration noted at 33.1%.",
      },
      {
        version: "v2",
        reference: "CAM-2024-0311",
        issued: "22 August 2024",
        rating: "CCB-3",
        status: "Sanctioned",
        author: "Vikram Sethi",
        facilities: "CC INR 12.20 cr + LC/BG INR 5.00 cr",
        summary:
          "Enhancement from INR 9.60 cr on FY2024 audited financials. Turnover INR 96.42 cr, EBITDA margin 11.8%, TOL/TNW 2.11x. Second unit at Bhosari commissioned during the year.",
      },
      {
        version: "v1",
        reference: "CAM-2023-0248",
        issued: "9 September 2023",
        rating: "CCB-4",
        status: "Sanctioned",
        author: "Vikram Sethi",
        facilities: "CC INR 9.60 cr",
        summary:
          "First sanction after takeover from a private-sector lender. Turnover INR 78.20 cr, tight liquidity at a current ratio of 1.18x, promoter guarantees taken.",
      },
    ],
  },
  {
    slug: "aurora-foods",
    name: "Aurora Foods Ltd",
    appraisalId: "CAM-2026-0402",
    sector: "Packaged foods and edible oils",
    pan: "AACCA••••P",
    gstin: "27AACCA••••P1ZR",
    branch: "Mumbai Fort Corporate Branch",
    rm: "Priya Nair",
    analyst: "Elena Rossi",
    exposure: "INR 9.40 cr",
    facilities: "CC INR 9.40 cr",
    rating: "CCB-2",
    ratingLabel: "Approved",
    status: "Completed",
    lastUpdated: "12 June 2026",
    lastUpdatedSort: 20260612,
    nextReview: "30 June 2027",
    nextReviewSort: 20270630,
    memos: 5,
    refreshable: true,
    versions: [
      {
        version: "v5",
        reference: "CAM-2026-0402",
        issued: "12 June 2026",
        rating: "CCB-2",
        status: "Sanctioned",
        author: "Elena Rossi",
        facilities: "CC INR 9.40 cr",
        summary:
          "Renewal at existing limits. Turnover INR 88.15 cr, current ratio 1.61x, DSCR 2.24x, no cross-verification findings. Approved by the credit manager without committee reference.",
        current: true,
      },
      {
        version: "v4",
        reference: "CAM-2025-0356",
        issued: "6 June 2025",
        rating: "CCB-2",
        status: "Sanctioned",
        author: "Elena Rossi",
        facilities: "CC INR 9.40 cr",
        summary: "Renewal on FY2025 audited financials. Turnover INR 79.44 cr, margins stable, one mild GST timing difference resolved with evidence.",
      },
      {
        version: "v3",
        reference: "CAM-2024-0298",
        issued: "14 June 2024",
        rating: "CCB-3",
        status: "Sanctioned",
        author: "Priya Nair",
        facilities: "CC INR 8.20 cr",
        summary: "Enhancement to INR 9.40 cr deferred; edible-oil price volatility held the rating at CCB-3 for one cycle.",
      },
    ],
  },
  {
    slug: "trident-industrial-packaging",
    name: "Trident Industrial Packaging Ltd",
    appraisalId: "CAM-2026-0421",
    sector: "Corrugated and industrial packaging",
    pan: "AABCT••••J",
    gstin: "24AABCT••••J1ZQ",
    branch: "Vadodara Commercial Branch",
    rm: "Kabir Shah",
    analyst: "Elena Rossi",
    exposure: "INR 18.90 cr",
    facilities: "TL INR 14.30 cr + CC INR 4.60 cr",
    rating: "CCB-3",
    ratingLabel: "First cut",
    status: "Drafting",
    lastUpdated: "29 July 2026",
    lastUpdatedSort: 20260729,
    nextReview: "30 September 2026",
    nextReviewSort: 20260930,
    memos: 3,
    refreshable: false,
    versions: [
      {
        version: "v3",
        reference: "CAM-2026-0421",
        issued: "In draft, started 3 July 2026",
        rating: "CCB-3",
        status: "Drafting",
        author: "Elena Rossi",
        facilities: "TL INR 14.30 cr + CC INR 4.60 cr",
        summary: "Term Loan of INR 14.30 cr for a third corrugation line at Halol. Five of eight sections drafted; project cost and DSCR sensitivity pending.",
        current: true,
      },
      {
        version: "v2",
        reference: "CAM-2025-0362",
        issued: "27 June 2025",
        rating: "CCB-3",
        status: "Sanctioned",
        author: "Elena Rossi",
        facilities: "CC INR 4.60 cr",
        summary: "Working capital renewal. Turnover INR 61.30 cr with a stable order book from two FMCG converters.",
      },
    ],
  },
  {
    slug: "sahyadri-pharma-distributors",
    name: "Sahyadri Pharma Distributors Pvt Ltd",
    appraisalId: "CAM-2026-0426",
    sector: "Pharmaceutical distribution",
    pan: "AAGCS••••M",
    gstin: "27AAGCS••••M1Z4",
    branch: "Nashik Commercial Branch",
    rm: "Devika Sundaram",
    analyst: "Elena Rossi",
    exposure: "INR 7.85 cr",
    facilities: "CC INR 6.10 cr + LC INR 1.75 cr",
    rating: "CCB-5",
    ratingLabel: "Indicative",
    status: "In preparation",
    lastUpdated: "30 July 2026",
    lastUpdatedSort: 20260730,
    nextReview: "First sanction, no review set",
    nextReviewSort: 99999999,
    memos: 1,
    refreshable: false,
    versions: [
      {
        version: "v1",
        reference: "CAM-2026-0426",
        issued: "In preparation, started 8 July 2026",
        rating: "CCB-5",
        status: "Gathering data",
        author: "Elena Rossi",
        facilities: "CC INR 6.10 cr + LC INR 1.75 cr",
        summary:
          "Fresh working capital sanction of INR 7.85 cr for a first-time borrower. GST and registry pulled; bank statements awaiting consent from the borrower.",
        current: true,
      },
    ],
  },
];

export const getBorrower = (slug: string) => BORROWERS.find((b) => b.slug === slug);
export const borrowerForAppraisal = (id: string) => BORROWERS.find((b) => b.appraisalId === id);

/** Every seeded appraisal is represented in the library. */
export const LIBRARY_COVERAGE = APPRAISALS.length === BORROWERS.length;

/* ------------------------------------------------------ refresh contents */

export type ChangeDirection = "worse" | "better" | "new" | "flat";

export type RefreshChange = {
  id: string;
  metric: string;
  area: "Financial" | "Obligations" | "Conduct" | "Compliance";
  prior: string;
  now: string;
  delta: string;
  direction: ChangeDirection;
  severity: "breach" | "watch" | "note";
  narrative: string;
  evidence: { source: string; detail: string; pulled: string };
  to: { kind: "spread" | "cross-verification" | "data"; anchor?: string };
  needsBankData?: boolean;
};

export const REFRESH_ASOF = "Quarter ended 30 June 2026, pulled 31 July 2026";
export const PRIOR_MEMO = "CAM-2026-0418 v4, drafted 31 July 2026 on FY2025 audited financials";

export const CHANGES: RefreshChange[] = [
  {
    id: "CHG-01",
    metric: "Current ratio",
    area: "Financial",
    prior: "1.28x",
    now: "1.19x",
    delta: "−0.09x, below the 1.20x policy minimum",
    direction: "worse",
    severity: "breach",
    narrative:
      "Current assets of INR 62.84 cr against current liabilities of INR 52.81 cr on the June 2026 provisional balance sheet. The slip comes from creditors stretching to INR 31.60 cr while receivables stayed flat, and it takes the ratio below CCB's 1.20x minimum for the first time since the 2023 sanction.",
    evidence: {
      source: "Provisional balance sheet, quarter ended 30 June 2026",
      detail:
        "Uploaded by the branch on 29 July 2026, unaudited, signed by the Managing Director. Current assets INR 62.84 cr (inventory INR 27.15 cr, receivables INR 29.42 cr, cash and bank INR 6.27 cr); current liabilities INR 52.81 cr (creditors INR 31.60 cr, short-term borrowings INR 18.94 cr, other INR 2.27 cr).",
      pulled: "29 July 2026",
    },
    to: { kind: "spread", anchor: "#ratio-current-ratio" },
  },
  {
    id: "CHG-02",
    metric: "Turnover trend",
    area: "Financial",
    prior: "INR 35.58 cr per quarter, FY2025 average",
    now: "INR 31.14 cr, quarter ended 30 June 2026",
    delta: "−12.5% against the FY2025 quarterly run rate",
    direction: "worse",
    severity: "watch",
    narrative:
      "GSTR-3B outward supplies for April to June 2026 total INR 31.14 cr against an FY2025 quarterly average of INR 35.58 cr. June alone was INR 9.02 cr, the weakest month in eighteen. The borrower's RM attributes it to a tier-1 customer moving to a quarterly call-off schedule; that explanation is not yet evidenced.",
    evidence: {
      source: "GSTR-3B, April, May and June 2026",
      detail:
        "Direct from GSTN under the borrower's registration 27AABCN4521Q1ZP. April INR 11.38 cr, May INR 10.74 cr, June INR 9.02 cr. All three returns filed on time; no amendments.",
      pulled: "31 July 2026",
    },
    to: { kind: "data", anchor: "#source-gst" },
  },
  {
    id: "CHG-03",
    metric: "Crestline Financial Services obligation",
    area: "Obligations",
    prior: "INR 4,37,500 per month, INR 52.50 lakh a year",
    now: "INR 6,12,000 per month, INR 73.44 lakh a year",
    delta: "+INR 1,74,500 per month since April 2026",
    direction: "worse",
    severity: "watch",
    narrative:
      "The undisclosed obligation raised as flag XV-0418-02 has grown. The monthly debit stepped up from INR 4,37,500 to INR 6,12,000 with the April 2026 instalment, consistent with a second drawdown from the same non-bank lender. Still no charge registered on the CERSAI or MCA index.",
    evidence: {
      source: "Meridian Bank account 4471, April to June 2026",
      detail:
        "Three debits of INR 6,12,000 on 5 April, 5 May and 5 June 2026, narration CRESTLINE FIN EMI. Statement lines carried through the Account Aggregator bundle; the consent under which this was pulled has since expired.",
      pulled: "1 July 2026, under the expired consent",
    },
    to: { kind: "cross-verification", anchor: "#flag-XV-0418-02" },
    needsBankData: true,
  },
  {
    id: "CHG-04",
    metric: "DSCR",
    area: "Financial",
    prior: "1.61x",
    now: "1.54x",
    delta: "−0.07x, still above the 1.25x floor",
    direction: "worse",
    severity: "note",
    narrative:
      "Eased on the softer quarter and the higher Crestline instalment, and remains inside policy. Restated for the full Crestline obligation of INR 73.44 lakh a year, DSCR would be 1.38x rather than the 1.44x shown in the memo as drafted.",
    evidence: {
      source: "Spread ratio grid, restated on June 2026 provisionals",
      detail:
        "EBITDA annualised at INR 14.92 cr against interest of INR 4.31 cr and term repayments of INR 5.38 cr, plus the restated non-bank obligation. Every input is traceable in the spread.",
      pulled: "31 July 2026",
    },
    to: { kind: "spread", anchor: "#ratio-dscr" },
  },
  {
    id: "CHG-05",
    metric: "Bureau rank and filing discipline",
    area: "Conduct",
    prior: "CMR-4, all returns filed",
    now: "CMR-4, all returns filed",
    delta: "No change",
    direction: "flat",
    severity: "note",
    narrative:
      "TransUnion CIBIL Commercial still ranks the borrower CMR-4 with no overdues across seven reported facilities, and all GST returns for the quarter were filed on time. Conduct is the one dimension that has not moved.",
    evidence: {
      source: "TransUnion CIBIL Commercial, pulled 31 July 2026",
      detail: "CMR-4 unchanged. No new enquiries since the June 2026 pull; no DPD reported in the last 27 months.",
      pulled: "31 July 2026",
    },
    to: { kind: "data", anchor: "#source-bureau" },
  },
];

export const CONSENT = {
  reference: "CONS-2026-0418-A",
  scope: "Meridian Bank current account 4471 and OD account 8802, twelve months of statements",
  grantedOn: "24 June 2026",
  expiredOn: "24 July 2026",
  window: "30 days, per the borrower's Account Aggregator authorisation",
  signatory: "Rajesh Malhotra, Managing Director",
  effect:
    "Bank figures in this refresh are as at 1 July 2026 and cannot be advanced until the borrower grants consent again. GST, bureau, registry and the branch-supplied provisionals are current.",
};

/* ------------------------------------------------------------ refresh UI */

export type RefreshState = {
  status: "idle" | "running" | "done";
  consent: "expired" | "requested" | "granted";
  bankRefreshedAt: string | null;
  accepted: null | { at: string; by: string };
  reviewStarted: boolean;
};

const NOW = "31 July 2026, 08:12";

let state: RefreshState = {
  status: "idle",
  consent: "expired",
  bankRefreshedAt: null,
  accepted: null,
  reviewStarted: false,
};

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const set = (patch: Partial<RefreshState>) => {
  state = { ...state, ...patch };
  emit();
};

export const startRefresh = () => set({ status: "running" });
export const completeRefresh = () => set({ status: "done" });
export const requestConsent = () => set({ consent: "requested" });
export const grantConsent = () => set({ consent: "granted", bankRefreshedAt: NOW });
export const acceptNoChange = (by: string) => set({ accepted: { at: NOW, by } });
export const markReviewStarted = () => set({ reviewStarted: true });

export function useRefreshState(): RefreshState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}
