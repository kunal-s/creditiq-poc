import type { Confidence } from "@/data/identity";

export type FY = "FY2023" | "FY2024" | "FY2025";
export const PERIODS: FY[] = ["FY2023", "FY2024", "FY2025"];

export const PERIOD_META: Record<FY, { label: string; ended: string; auditor: string; status: string }> = {
  FY2023: {
    label: "FY2023",
    ended: "Year ended 31 March 2023",
    auditor: "Kelkar & Bhide, Chartered Accountants",
    status: "Audited, unqualified",
  },
  FY2024: {
    label: "FY2024",
    ended: "Year ended 31 March 2024",
    auditor: "Kelkar & Bhide, Chartered Accountants",
    status: "Audited, unqualified",
  },
  FY2025: {
    label: "FY2025",
    ended: "Year ended 31 March 2025",
    auditor: "Kelkar & Bhide, Chartered Accountants",
    status: "Audited, emphasis of matter on related-party balances",
  },
};

/** A document a figure can be traced back to. */
export type SpreadSource = {
  id: string;
  doc: string;
  locator: string;
  provenance: string;
  acqKey: string;
  ingested: string;
  excerpt: string[];
};

export const SOURCE_DOCS: Record<string, SpreadSource> = {
  "afs-fy2025": {
    id: "afs-fy2025",
    doc: "Northwind_Manufacturing_Audited_FS_FY2025.pdf",
    locator: "Page 14 — Statement of Profit and Loss, year ended 31 March 2025",
    provenance: "Uploaded by Marcus Chen · fallback",
    acqKey: "financials",
    ingested: "28 July 2026, 16:42 · 4.2 MB · 61 pages",
    excerpt: [
      "I.   Revenue from operations              1,42,31,08,442",
      "II.  Other income                            1,04,71,900",
      "III. Total income (I + II)                 1,43,35,80,342",
      "IV.  Expenses",
      "       Cost of materials consumed         1,04,86,22,110",
      "       Changes in inventories                (2,41,08,730)",
      "       Employee benefits expense             9,88,41,205",
      "       Finance costs                         4,55,12,880",
      "       Depreciation and amortisation         4,28,06,415",
      "       Other expenses                       12,40,77,516",
    ],
  },
  "afs-fy2025-bs": {
    id: "afs-fy2025-bs",
    doc: "Northwind_Manufacturing_Audited_FS_FY2025.pdf",
    locator: "Page 12 — Balance Sheet as at 31 March 2025",
    provenance: "Uploaded by Marcus Chen · fallback",
    acqKey: "financials",
    ingested: "28 July 2026, 16:42 · 4.2 MB · 61 pages",
    excerpt: [
      "EQUITY AND LIABILITIES",
      "  Equity share capital                        6,00,00,000",
      "  Other equity                               27,08,41,662",
      "  Total equity (net worth)                   33,08,41,662",
      "  Borrowings — non-current                   14,62,90,000",
      "  Borrowings — current                       22,42,10,400",
      "  Trade payables                             13,21,64,880",
      "  Other current liabilities                   6,32,88,510",
    ],
  },
  "afs-fy2024": {
    id: "afs-fy2024",
    doc: "Northwind_Manufacturing_Audited_FS_FY2024.pdf",
    locator: "Pages 11 to 13 — Balance Sheet and Statement of Profit and Loss, FY2024 with FY2023 comparatives",
    provenance: "Uploaded by Marcus Chen · fallback",
    acqKey: "financials",
    ingested: "28 July 2026, 16:44 · 3.6 MB · 54 pages",
    excerpt: [
      "I.   Revenue from operations              1,18,74,26,118",
      "     (previous year)                        96,42,18,905",
      "  Total equity (net worth)                 27,34,20,118",
      "     (previous year)                       22,61,44,780",
      "  Total borrowings                         29,60,11,240",
      "     (previous year)                       24,90,63,300",
    ],
  },
  "itr-ay2526": {
    id: "itr-ay2526",
    doc: "ITR-6 acknowledgement, AY2025-26 with computation",
    locator: "Acknowledgement 418277340290925 — Part B-TI, line 13",
    provenance: "Income Tax e-filing portal",
    acqKey: "financials",
    ingested: "28 July 2026, 16:47 · filed 29 September 2025",
    excerpt: [
      "Part B-TI  Computation of total income",
      "  Profits and gains of business or profession       9,41,80,120",
      "  Total income                                      9,41,80,120",
      "  Tax payable on total income                       2,47,86,000",
      "  Profit after tax as per books                     6,94,02,415",
    ],
  },
  "gstr3b-fy2025": {
    id: "gstr3b-fy2025",
    doc: "GSTR-3B summary, GSTIN 27AABCN4521Q1ZP, FY2025",
    locator: "Twelve monthly returns, table 3.1(a) aggregated",
    provenance: "Direct from GSTN",
    acqKey: "gst",
    ingested: "30 July 2026, 06:12 · API pull",
    excerpt: [
      "Aggregate outward taxable supplies FY2025      1,47,77,41,060",
      "  of which zero-rated (export) supplies           8,12,44,900",
      "Two returns filed late: Nov 2024 (11 days),",
      "Feb 2025 (6 days). Interest paid, no notice issued.",
    ],
  },
  "aa-bank": {
    id: "aa-bank",
    doc: "Account Aggregator statement bundle, FY2025-26 window",
    locator: "Meridian Bank current account XXXX 4471 and Horizon Bank cash credit XXXX 2205",
    provenance: "Consent CONS-2026-0418-A",
    acqKey: "bank",
    ingested: "31 July 2026, 07:20 · consent artefact retained",
    excerpt: [
      "Total credits, both accounts, 12 months      1,36,85,22,410",
      "  Customer collections (OEM and tier-1)      1,29,44,10,880",
      "  Inter-account transfers (excluded)            4,90,00,000",
      "Peak CC utilisation Horizon 2205                    96.4%",
    ],
  },
  "cibil-comm": {
    id: "cibil-comm",
    doc: "CIBIL Commercial report, CMR-4",
    locator: "Section 4 — credit facilities and repayment history",
    provenance: "TransUnion CIBIL",
    acqKey: "bureau",
    ingested: "30 July 2026, 06:18 · report 2026073000418",
    excerpt: [
      "Term loan, Horizon Bank — original 9,00,00,000",
      "  Scheduled principal repayment FY2025        5,24,00,000",
      "  One DPD bucket 31-60 days, May 2025",
      "Cash credit, Continental Commercial Bank    12,20,00,000",
    ],
  },
};

export type Cell = {
  fy: FY;
  value: number;
  sourceId: string;
  confidence: Confidence;
  note?: string;
};

export type LineItem = {
  key: string;
  label: string;
  unit: "cr" | "days" | "x" | "%";
  emphasis?: boolean;
  definition: string;
  cells: Record<FY, Cell>;
};

const c = (fy: FY, value: number, sourceId: string, confidence: Confidence = "high", note?: string): Cell =>
  note === undefined ? { fy, value, sourceId, confidence } : { fy, value, sourceId, confidence, note };

const row = (
  key: string,
  label: string,
  definition: string,
  v: [number, number, number],
  sources: [string, string, string],
  opts?: { emphasis?: boolean; confidence?: Partial<Record<FY, Confidence>>; notes?: Partial<Record<FY, string>> },
): LineItem => ({
  key,
  label,
  unit: "cr",
  definition,
  ...(opts?.emphasis ? { emphasis: true } : {}),
  cells: {
    FY2023: c("FY2023", v[0], sources[0], opts?.confidence?.FY2023 ?? "high", opts?.notes?.FY2023),
    FY2024: c("FY2024", v[1], sources[1], opts?.confidence?.FY2024 ?? "high", opts?.notes?.FY2024),
    FY2025: c("FY2025", v[2], sources[2], opts?.confidence?.FY2025 ?? "high", opts?.notes?.FY2025),
  },
});

const AFS_ALL: [string, string, string] = ["afs-fy2024", "afs-fy2024", "afs-fy2025"];
const BS_ALL: [string, string, string] = ["afs-fy2024", "afs-fy2024", "afs-fy2025-bs"];

export const PL_ITEMS: LineItem[] = [
  row("turnover", "Turnover (revenue from operations)", "Net of GST, as reported in the audited Statement of Profit and Loss.", [96.42, 118.74, 142.31], AFS_ALL, { emphasis: true }),
  row("other-income", "Other income", "Interest, scrap sales and forex gain; excluded from operating margins.", [0.72, 0.88, 1.05], AFS_ALL),
  row("gross-profit", "Gross profit", "Turnover less cost of materials consumed and change in inventories.", [18.71, 22.44, 25.90], AFS_ALL),
  row("ebitda", "EBITDA", "Operating profit before finance costs, depreciation, amortisation and tax.", [11.18, 13.92, 15.58], AFS_ALL, { emphasis: true }),
  row("depreciation", "Depreciation and amortisation", "Straight-line on plant and machinery at Chakan and Bhosari units.", [3.11, 3.68, 4.28], AFS_ALL),
  row("interest", "Finance costs", "Interest on working capital and term borrowings, plus bank charges.", [2.82, 3.75, 4.55], AFS_ALL),
  row("pbt", "Profit before tax", "EBITDA less depreciation and finance costs, plus other income.", [6.53, 8.19, 9.42], AFS_ALL),
  row("pat", "Profit after tax", "Profit after current and deferred tax as certified by the auditor.", [4.83, 6.07, 6.94], ["afs-fy2024", "afs-fy2024", "itr-ay2526"], { emphasis: true }),
];

export const BS_ITEMS: LineItem[] = [
  row("networth", "Tangible net worth", "Share capital plus other equity, less intangibles and related-party receivables.", [22.61, 27.34, 33.08], BS_ALL, { emphasis: true }),
  row("debt", "Total debt", "Non-current and current borrowings across all lenders, including CC utilisation.", [24.90, 29.60, 37.05], BS_ALL, { emphasis: true }),
  row("tol", "Total outside liabilities", "All liabilities other than net worth, including trade payables and provisions.", [44.77, 59.05, 77.41], BS_ALL),
  row("ca", "Current assets", "Inventory, trade receivables, cash and bank balances, and other current assets.", [29.84, 35.12, 41.86], BS_ALL),
  row("cl", "Current liabilities", "Trade payables, current borrowings, statutory dues and other current liabilities.", [21.16, 26.21, 32.70], BS_ALL, {
    confidence: { FY2025: "low" },
    notes: {
      FY2025:
        "Extracted with low confidence, please confirm — page 12 of the FY2025 audited statement splits other current liabilities across two schedules and the OCR total (6.32 cr) could not be tied to schedule 11 (6.33 cr).",
    },
  }),
  row("inventory", "Inventory", "Raw material, work in progress and finished goods at the two units.", [16.42, 19.88, 24.16], BS_ALL),
  row("receivables", "Trade receivables", "Net of provision for doubtful debts; OEM receivables at 60 to 90 day terms.", [18.90, 22.71, 27.68], BS_ALL),
  row("payables", "Trade payables", "Supplier dues, of which 71% are to the top ten vendors.", [9.02, 11.10, 13.22], BS_ALL),
];

export type RatioStatus = "pass" | "marginal" | "breach";

export type Ratio = {
  key: string;
  label: string;
  unit: "x" | "%" | "days";
  values: Record<FY, number>;
  policy?: { text: string; kind: "min" | "max"; value: number };
  status: Record<FY, RatioStatus>;
  formula: string;
  derivation: { fy: FY; lines: { label: string; value: string; itemKey?: string; sourceId: string }[]; math: string }[];
  comment: string;
};

const st = (a: RatioStatus, b: RatioStatus, d: RatioStatus): Record<FY, RatioStatus> => ({ FY2023: a, FY2024: b, FY2025: d });
const vals = (a: number, b: number, d: number): Record<FY, number> => ({ FY2023: a, FY2024: b, FY2025: d });

export const RATIOS: Ratio[] = [
  {
    key: "current-ratio",
    label: "Current ratio",
    unit: "x",
    values: vals(1.41, 1.34, 1.28),
    policy: { text: "CCB policy minimum 1.20", kind: "min", value: 1.2 },
    status: st("pass", "pass", "marginal"),
    formula: "Current assets ÷ Current liabilities",
    comment: "Still above the covenant floor but has slipped in each of the three years as inventory has built.",
    derivation: [
      {
        fy: "FY2025",
        lines: [
          { label: "Current assets", value: "41.86 cr", itemKey: "ca", sourceId: "afs-fy2025-bs" },
          { label: "Current liabilities", value: "32.70 cr", itemKey: "cl", sourceId: "afs-fy2025-bs" },
        ],
        math: "41.86 ÷ 32.70 = 1.28",
      },
    ],
  },
  {
    key: "tol-tnw",
    label: "TOL / TNW",
    unit: "x",
    values: vals(1.98, 2.16, 2.34),
    policy: { text: "CCB policy maximum 3.00", kind: "max", value: 3.0 },
    status: st("pass", "pass", "pass"),
    formula: "Total outside liabilities ÷ Tangible net worth",
    comment: "Headroom of 0.66x against the ceiling; the proposed enhancement takes it to an estimated 2.61x.",
    derivation: [
      {
        fy: "FY2025",
        lines: [
          { label: "Total outside liabilities", value: "77.41 cr", itemKey: "tol", sourceId: "afs-fy2025-bs" },
          { label: "Tangible net worth", value: "33.08 cr", itemKey: "networth", sourceId: "afs-fy2025-bs" },
        ],
        math: "77.41 ÷ 33.08 = 2.34",
      },
    ],
  },
  {
    key: "debt-equity",
    label: "Debt / equity",
    unit: "x",
    values: vals(1.1, 1.08, 1.12),
    policy: { text: "CCB indicative maximum 2.00", kind: "max", value: 2.0 },
    status: st("pass", "pass", "pass"),
    formula: "Total debt ÷ Tangible net worth",
    comment: "Stable through the growth phase; retained earnings have largely funded the incremental working capital.",
    derivation: [
      {
        fy: "FY2025",
        lines: [
          { label: "Total debt", value: "37.05 cr", itemKey: "debt", sourceId: "afs-fy2025-bs" },
          { label: "Tangible net worth", value: "33.08 cr", itemKey: "networth", sourceId: "afs-fy2025-bs" },
        ],
        math: "37.05 ÷ 33.08 = 1.12",
      },
    ],
  },
  {
    key: "dscr",
    label: "DSCR",
    unit: "x",
    values: vals(1.78, 1.72, 1.61),
    policy: { text: "CCB policy minimum 1.50", kind: "min", value: 1.5 },
    status: st("pass", "pass", "marginal"),
    formula: "(PAT + depreciation + finance costs) ÷ (finance costs + scheduled principal repayments)",
    comment: "Within policy, but 0.11x of erosion in one year with the enhancement not yet loaded into the denominator.",
    derivation: [
      {
        fy: "FY2025",
        lines: [
          { label: "Profit after tax", value: "6.94 cr", itemKey: "pat", sourceId: "itr-ay2526" },
          { label: "Depreciation and amortisation", value: "4.28 cr", itemKey: "depreciation", sourceId: "afs-fy2025" },
          { label: "Finance costs", value: "4.55 cr", itemKey: "interest", sourceId: "afs-fy2025" },
          { label: "Scheduled principal repayments", value: "5.24 cr", sourceId: "cibil-comm" },
        ],
        math: "(6.94 + 4.28 + 4.55) = 15.77 ÷ (4.55 + 5.24) = 9.79 → 1.61",
      },
    ],
  },
  {
    key: "interest-coverage",
    label: "Interest coverage",
    unit: "x",
    values: vals(3.96, 3.71, 3.42),
    policy: { text: "CCB policy minimum 2.50", kind: "min", value: 2.5 },
    status: st("pass", "pass", "pass"),
    formula: "EBITDA ÷ Finance costs",
    comment: "Comfortable, though a 100 bp rise on the enhanced limit would take it to an estimated 3.11x.",
    derivation: [
      {
        fy: "FY2025",
        lines: [
          { label: "EBITDA", value: "15.58 cr", itemKey: "ebitda", sourceId: "afs-fy2025" },
          { label: "Finance costs", value: "4.55 cr", itemKey: "interest", sourceId: "afs-fy2025" },
        ],
        math: "15.58 ÷ 4.55 = 3.42",
      },
    ],
  },
  {
    key: "wc-cycle",
    label: "Working-capital cycle",
    unit: "days",
    values: vals(71, 79, 87),
    policy: { text: "CCB sector benchmark 75 days for auto components", kind: "max", value: 75 },
    status: st("pass", "marginal", "breach"),
    formula: "Inventory days + receivable days − payable days",
    comment: "Sixteen days longer than FY2023 and now beyond the sector benchmark; this is the driver of the enhancement request.",
    derivation: [
      {
        fy: "FY2025",
        lines: [
          { label: "Inventory days (24.16 cr on materials consumed)", value: "62 days", itemKey: "inventory", sourceId: "afs-fy2025-bs" },
          { label: "Receivable days (27.68 cr on turnover)", value: "71 days", itemKey: "receivables", sourceId: "afs-fy2025-bs" },
          { label: "Payable days (13.22 cr on materials consumed)", value: "46 days", itemKey: "payables", sourceId: "afs-fy2025-bs" },
        ],
        math: "62 + 71 − 46 = 87 days",
      },
    ],
  },
  {
    key: "gross-margin",
    label: "Gross margin",
    unit: "%",
    values: vals(19.4, 18.9, 18.2),
    status: st("pass", "pass", "marginal"),
    formula: "Gross profit ÷ Turnover",
    comment: "A 120 bp contraction over three years as the OEM mix has shifted toward higher-volume, lower-margin parts.",
    derivation: [
      {
        fy: "FY2025",
        lines: [
          { label: "Gross profit", value: "25.90 cr", itemKey: "gross-profit", sourceId: "afs-fy2025" },
          { label: "Turnover", value: "142.31 cr", itemKey: "turnover", sourceId: "afs-fy2025" },
        ],
        math: "25.90 ÷ 142.31 = 18.2%",
      },
    ],
  },
  {
    key: "net-margin",
    label: "Net margin",
    unit: "%",
    values: vals(5.0, 5.1, 4.9),
    status: st("pass", "pass", "pass"),
    formula: "Profit after tax ÷ Turnover",
    comment: "Broadly flat; volume growth has offset the gross-margin slippage.",
    derivation: [
      {
        fy: "FY2025",
        lines: [
          { label: "Profit after tax", value: "6.94 cr", itemKey: "pat", sourceId: "itr-ay2526" },
          { label: "Turnover", value: "142.31 cr", itemKey: "turnover", sourceId: "afs-fy2025" },
        ],
        math: "6.94 ÷ 142.31 = 4.9%",
      },
    ],
  },
];

export const TREND_NOTES = [
  {
    tone: "positive" as const,
    title: "Turnover growth of 19.8% in FY2025",
    detail:
      "Three-year CAGR of 21.5%, from 96.42 cr to 142.31 cr, driven by the tier-1 OEM order book. EBITDA has grown with it in absolute terms, from 11.18 cr to 15.58 cr.",
  },
  {
    tone: "flag" as const,
    title: "Working-capital cycle lengthened by 16 days over the same period",
    detail:
      "Inventory days rose from 51 to 62 and receivable days from 66 to 71, while payable days stayed near 46. Growth is being funded on the cash conversion cycle, which is what the enhancement is being asked to cover.",
  },
];

export const DISCREPANCY_BANNER = {
  title: "GST-declared turnover and bank credits do not agree with the declared financials",
  detail:
    "FY2025 turnover in the audited statement is 142.31 cr. GSTR-3B outward supplies for the same period total 147.77 cr, a gap of 5.46 cr. Credits into the two consented accounts total 136.85 cr. Nothing is resolved here — the spread carries the audited figure and the reconciliation is raised at cross-verification.",
  refs: [
    { label: "GSTR-3B FY2025 — 147.77 cr", sourceId: "gstr3b-fy2025" },
    { label: "Bank credits FY2025-26 — 136.85 cr", sourceId: "aa-bank" },
  ],
};

export const fmt = (v: number, unit: LineItem["unit"] | Ratio["unit"]) => {
  if (unit === "days") return `${v}`;
  if (unit === "%") return v.toFixed(1);
  return v.toFixed(2);
};

export const RATIO_TONE: Record<RatioStatus, string> = {
  pass: "border-positive/30 bg-positive-soft text-positive",
  marginal: "border-flag/35 bg-flag-soft text-flag-foreground",
  breach: "border-destructive/30 bg-destructive/10 text-destructive",
};

export const RATIO_LABEL: Record<RatioStatus, string> = {
  pass: "Within policy",
  marginal: "Marginal",
  breach: "Outside benchmark",
};
