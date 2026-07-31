import { useSyncExternalStore } from "react";

/* ------------------------------------------------------------- citations */

export type CiteTarget = "spread" | "cross-verification" | "data" | "identity" | "policy";

export type Citation = {
  id: string;
  claim: string;
  source: string;
  detail: string;
  to: CiteTarget;
  anchor?: string;
};

export const CITATIONS: Record<string, Citation> = {
  "cin": {
    id: "cin",
    claim: "CIN U27310MH2009PLC198435",
    source: "MCA company master",
    detail: "Registry record refreshed 29 July 2026. Incorporated 14 August 2009, active, registered office Chakan, Pune district.",
    to: "identity",
  },
  "gstin": {
    id: "gstin",
    claim: "GSTIN 27AABCN4521Q1ZP",
    source: "GSTN taxpayer search",
    detail: "Active registration, principal place of business Chakan MIDC Phase II, 24 of 24 returns filed for the assessed window.",
    to: "identity",
  },
  "group": {
    id: "group",
    claim: "Group link to Northwind Logistics Ltd",
    source: "MCA DIN master, DIN 01847362",
    detail: "Rajesh Malhotra is Managing Director of the borrower and Director of Northwind Logistics Ltd (CIN U63030MH2016PLC276104) since 3 February 2016. Link confirmed by the analyst at entity resolution.",
    to: "identity",
  },
  "directors": {
    id: "directors",
    claim: "Three directors on record",
    source: "MCA DIN master",
    detail: "Rajesh Malhotra (DIN 01847362), Anita Malhotra (DIN 01847388), Sameer Deshpande (DIN 02911574). No disqualifications on the registry.",
    to: "identity",
  },
  "facility": {
    id: "facility",
    claim: "CC INR 18.50 cr and LC/BG INR 6.75 cr",
    source: "Sanction request, Marcus Chen, Pune Corporate Branch",
    detail: "Cash Credit enhancement from INR 12.20 cr to INR 18.50 cr and non-fund LC/BG of INR 6.75 cr, total proposed exposure INR 25.25 cr.",
    to: "identity",
  },
  "conduct": {
    id: "conduct",
    claim: "CIBIL Commercial rank CMR-4",
    source: "TransUnion CIBIL Commercial, pulled 29 July 2026",
    detail: "CMR-4 on a 1 to 10 scale. No overdues in the last 24 months across seven reported facilities; two enquiries in the last six months.",
    to: "data",
    anchor: "#bureau-conduct",
  },
  "cc-util": {
    id: "cc-util",
    claim: "Average CC utilisation 91.4%",
    source: "Meridian Bank 4471 statement under consent CONS-2026-0418-A",
    detail: "Twelve-month average utilisation of the INR 12.20 cr limit is 91.4%, with 27 days above 95% and no continuous overdrawing beyond three days.",
    to: "data",
    anchor: "#bank-credits",
  },
  "turnover": {
    id: "turnover",
    claim: "Turnover INR 96.42 cr, 118.74 cr, 142.31 cr",
    source: "Audited Statement of Profit and Loss FY2024 and FY2025",
    detail: "FY2023 96.42 cr, FY2024 118.74 cr, FY2025 142.31 cr. Three-year CAGR 21.5%. FY2025 figure is contested at cross-verification.",
    to: "spread",
    anchor: "#pl-turnover",
  },
  "ebitda": {
    id: "ebitda",
    claim: "EBITDA INR 15.58 cr in FY2025",
    source: "Audited Statement of Profit and Loss FY2025, page 14",
    detail: "EBITDA of 11.18 cr, 13.92 cr and 15.58 cr across FY2023 to FY2025. Margin has compressed from 11.6% to 10.9%.",
    to: "spread",
    anchor: "#pl-ebitda",
  },
  "pat": {
    id: "pat",
    claim: "PAT INR 6.94 cr in FY2025",
    source: "ITR-6 AY2025-26, acknowledgement 274918365120725",
    detail: "PAT of 4.83 cr, 6.07 cr and 6.94 cr across the three years; net margin 4.9% in FY2025.",
    to: "spread",
    anchor: "#pl-pat",
  },
  "tnw": {
    id: "tnw",
    claim: "Tangible net worth INR 33.08 cr",
    source: "Audited Balance Sheet FY2025",
    detail: "TNW of 22.61 cr, 27.34 cr and 33.08 cr; growth is entirely from retained earnings, no fresh equity infused.",
    to: "spread",
    anchor: "#bs-networth",
  },
  "debt": {
    id: "debt",
    claim: "Total debt INR 37.05 cr",
    source: "Audited Balance Sheet FY2025",
    detail: "Borrowings across all lenders including CC utilisation: 24.90 cr, 29.60 cr and 37.05 cr.",
    to: "spread",
    anchor: "#bs-debt",
  },
  "current-ratio": {
    id: "current-ratio",
    claim: "Current ratio 1.28x",
    source: "Spread ratio grid, derived 41.86 ÷ 32.70",
    detail: "1.41x, 1.34x and 1.28x. Above the CCB floor of 1.20x but slipping in each year as inventory builds.",
    to: "spread",
    anchor: "#ratio-current-ratio",
  },
  "toltnw": {
    id: "toltnw",
    claim: "TOL/TNW 2.34x",
    source: "Spread ratio grid, derived 77.41 ÷ 33.08",
    detail: "1.98x, 2.16x and 2.34x against a CCB ceiling of 3.00x. Restating for the undisclosed Crestline obligation adds about 0.06x.",
    to: "spread",
    anchor: "#ratio-toltnw",
  },
  "dscr": {
    id: "dscr",
    claim: "DSCR 1.61x",
    source: "Spread ratio grid, (PAT + depreciation + interest) ÷ (interest + repayments)",
    detail: "1.61x in FY2025 against a CCB floor of 1.25x. Restated for the Crestline obligation of INR 52.50 lakh a year, DSCR falls to 1.44x.",
    to: "spread",
    anchor: "#ratio-dscr",
  },
  "wc": {
    id: "wc",
    claim: "Working capital cycle 87 days",
    source: "Spread ratio grid, inventory + receivable less payable days",
    detail: "Lengthened by 16 days over three years: inventory 51 to 62 days, receivables 66 to 71 days, payables steady near 46 days.",
    to: "spread",
    anchor: "#ratio-wc",
  },
  "gst-filed": {
    id: "gst-filed",
    claim: "24 of 24 GST returns filed",
    source: "GSTN return ledger, 27AABCN4521Q1ZP",
    detail: "All GSTR-1 and GSTR-3B filings for FY2024-25 and FY2025-26 to date are on the ledger, none filed beyond 20 days late.",
    to: "data",
    anchor: "#gst-turnover",
  },
  "gst-turnover": {
    id: "gst-turnover",
    claim: "GST outward supplies INR 119.83 cr",
    source: "GSTR-3B aggregate, April 2024 to March 2025",
    detail: "Direct from GSTN. Table 3.1(a) outward taxable supplies aggregate to 1,19,83,44,617 for the twelve months.",
    to: "data",
    anchor: "#gst-turnover",
  },
  "bank-credits": {
    id: "bank-credits",
    claim: "Bank credits INR 121.44 cr",
    source: "Account Aggregator bundle, consent CONS-2026-0418-A",
    detail: "Customer credits into Meridian 4471 (94.19 cr) and Horizon 2205 (27.26 cr), excluding inter-account transfers and CC drawdowns.",
    to: "data",
    anchor: "#bank-credits",
  },
  "flag1": {
    id: "flag1",
    claim: "Flag XV-0418-01, serious",
    source: "Cross-verification rule XV-04, tolerance 5%",
    detail: "Declared FY2025 turnover of 142.31 cr against GST of 119.83 cr (gap 22.48 cr, 15.8%) and bank credits of 121.44 cr (gap 20.87 cr, 14.7%).",
    to: "cross-verification",
    anchor: "#XV-0418-01",
  },
  "flag2": {
    id: "flag2",
    claim: "Flag XV-0418-02, moderate",
    source: "Meridian Bank 4471 statement, 12 recurring debits",
    detail: "Monthly debit of INR 4,37,500 to Crestline Financial Services, INR 52.50 lakh a year, absent from the declared obligations. Implied residual of about INR 1.85 cr.",
    to: "cross-verification",
    anchor: "#XV-0418-02",
  },
  "flag3": {
    id: "flag3",
    claim: "Flag XV-0418-03, mild",
    source: "GSTR-1 B2B counterparty summary FY2024-25",
    detail: "Meridian Auto Systems Ltd at INR 54.65 cr is 38.4% of sales against a CCB soft cap of 35%. OEM contract runs to March 2028.",
    to: "cross-verification",
    anchor: "#XV-0418-03",
  },
  "charges": {
    id: "charges",
    claim: "Two charges on the CERSAI and MCA registers",
    source: "MCA charge index and CERSAI search, 29 July 2026",
    detail: "CCB charge of INR 16.30 cr subsisting over current assets; Horizon Bank charge of INR 3.10 cr satisfied 18 February 2025.",
    to: "data",
    anchor: "#registry",
  },
  "policy-rating": {
    id: "policy-rating",
    claim: "CCB internal rating model v3.1",
    source: "CCB credit policy, rating model and qualitative overlay",
    detail: "Financial score maps to CCB-3; the evidence-quality overlay applies a one-notch downgrade where a serious cross-verification finding is open or accepted.",
    to: "policy",
  },
};

export const citationsFor = (ids: string[]) => ids.map((i) => CITATIONS[i]).filter(Boolean) as Citation[];

/* -------------------------------------------------------------- sections */

export type MemoSection = {
  id: string;
  number: string;
  title: string;
  summary: string;
  /** Paragraphs. Inline citations are written as [[citationId]]. */
  body: string[];
  facts?: { label: string; value: string; cite?: string }[];
  drafted: string;
};

export const SECTIONS: MemoSection[] = [
  {
    id: "profile",
    number: "1",
    title: "Borrower and Group Profile",
    summary: "Legal identity, group perimeter and management, as resolved from the registries.",
    drafted: "31 July 2026, 07:48",
    body: [
      "Northwind Manufacturing Ltd is a public limited company incorporated on 14 August 2009 under [[cin]], with its registered office and principal manufacturing unit at Chakan MIDC Phase II, Pune district, and a second unit at Bhosari. The company is registered for GST under [[gstin]] and holds LEI 894500XYZ7NORTHWIND12, valid to 31 March 2027. It manufactures precision machined components and sub-assemblies for tier-1 automotive and off-highway equipment makers.",
      "The board comprises three directors [[directors]]: Rajesh Malhotra (Managing Director, DIN 01847362), Anita Malhotra (Whole-time Director, DIN 01847388) and Sameer Deshpande (Independent Director, DIN 02911574). The promoter family holds 71.4% of the paid-up capital directly and through Malhotra Family Holdings Pvt Ltd, which carries no bank facilities.",
      "The group perimeter for this appraisal includes Northwind Logistics Ltd [[group]], a related party that provides inbound and outbound transport to the borrower and invoices it under GSTIN 27AABCL8890R1Z4. Related-party transactions of INR 6.42 cr in FY2025 are disclosed in note 34 of the audited financials and have been eliminated from the group view. No other entity sharing these directors meets the perimeter test in the CAM template.",
    ],
    facts: [
      { label: "Constitution", value: "Public limited, incorporated 14 August 2009", cite: "cin" },
      { label: "Industry", value: "Precision machined components, tier-1 automotive supply" },
      { label: "Group", value: "Northwind Logistics Ltd (transport, related party)", cite: "group" },
      { label: "Banking since", value: "March 2017, Pune Corporate Branch" },
    ],
  },
  {
    id: "facility",
    number: "2",
    title: "Facility Requested and Purpose",
    summary: "What is being asked for, why, and how it is secured.",
    drafted: "31 July 2026, 07:48",
    body: [
      "The borrower has requested an enhancement of the existing Cash Credit limit from INR 12.20 cr to INR 18.50 cr, together with a non-fund LC/BG line of INR 6.75 cr, taking total proposed exposure to INR 25.25 cr [[facility]]. The existing limit was last sanctioned on 30 August 2025 and is due for annual review on 31 August 2026.",
      "The stated purpose is to fund the working capital gap created by a lengthening cash conversion cycle [[wc]] as the tier-1 order book has grown, and to replace supplier credit currently taken at 46 days with a formal LC line. Assessed working capital requirement on the Nayak method at 25% of projected FY2027 turnover supports a limit of INR 18.50 cr against the audited turnover, and INR 15.80 cr against the independently evidenced turnover [[bank-credits]] — a difference the committee should note.",
      "Security is a first pari passu charge on the entire current assets of the company, an existing charge of INR 16.30 cr being enhanced [[charges]], collateral of the Chakan factory land and building valued at INR 11.40 cr by the panel valuer on 12 June 2026, and the personal guarantees of Rajesh Malhotra and Anita Malhotra.",
    ],
    facts: [
      { label: "Existing", value: "CC INR 12.20 cr, sanctioned 30 August 2025" },
      { label: "Proposed", value: "CC INR 18.50 cr + LC/BG INR 6.75 cr", cite: "facility" },
      { label: "Total exposure", value: "INR 25.25 cr" },
      { label: "Security", value: "First pari passu on current assets, collateral INR 11.40 cr", cite: "charges" },
    ],
  },
  {
    id: "conduct",
    number: "3",
    title: "Banking Conduct",
    summary: "Account behaviour and bureau record across the assessed window.",
    drafted: "31 July 2026, 07:48",
    body: [
      "Conduct of the Cash Credit account with this bank has been satisfactory. Average utilisation of the INR 12.20 cr limit over the last twelve months is 91.4% [[cc-util]], with 27 days above 95% and no continuous overdrawing beyond three days. Interest and charges have been serviced on the due date in every month, and no cheque return has been recorded in the assessed window.",
      "The commercial bureau ranks the borrower at CMR-4 [[conduct]], with no overdues reported across seven live facilities in the last 24 months. Two credit enquiries appear in the last six months, both attributable to this proposal and the Horizon Bank closure.",
      "Sustained utilisation above 90% is consistent with the borrower's case that the existing limit is binding. It is also consistent with collections being tighter than the declared turnover implies, which is the subject of section 6.",
    ],
    facts: [
      { label: "Average CC utilisation", value: "91.4% over twelve months", cite: "cc-util" },
      { label: "Bureau rank", value: "CIBIL CMR-4, no overdues in 24 months", cite: "conduct" },
      { label: "Cheque returns", value: "Nil in the assessed window" },
      { label: "Other lenders", value: "Horizon Bank charge satisfied 18 February 2025", cite: "charges" },
    ],
  },
  {
    id: "financials",
    number: "4",
    title: "Financial Analysis and Ratios",
    summary: "FY2023 to FY2025 performance and the ratios the bank underwrites on.",
    drafted: "31 July 2026, 07:48",
    body: [
      "Turnover has grown from INR 96.42 cr in FY2023 to INR 118.74 cr in FY2024 and INR 142.31 cr in FY2025 [[turnover]], a three-year CAGR of 21.5%. EBITDA has grown in absolute terms to INR 15.58 cr [[ebitda]] but the margin has compressed from 11.6% to 10.9% as material costs and freight have risen faster than realisations. Profit after tax is INR 6.94 cr [[pat]], a net margin of 4.9%.",
      "Tangible net worth stands at INR 33.08 cr [[tnw]], built entirely from retained earnings with no fresh equity infused in the three years. Total debt is INR 37.05 cr [[debt]], of which CC utilisation is INR 11.15 cr at the year end. Gearing on this basis is 1.12x.",
      "Liquidity and leverage remain inside policy. The current ratio is 1.28x [[current-ratio]] against a floor of 1.20x, TOL/TNW is 2.34x [[toltnw]] against a ceiling of 3.00x, and DSCR is 1.61x [[dscr]] against a floor of 1.25x. Two of these are moving in the wrong direction: the current ratio has fallen in each of the three years, and the working capital cycle has lengthened by 16 days to 87 days [[wc]]. Growth is being funded on the cash conversion cycle, which is precisely what the enhancement is asked to cover.",
      "One balance sheet figure required analyst attention. FY2025 current liabilities were extracted with low confidence because page 12 of the audited statement splits other current liabilities across two schedules; the figure of INR 32.70 cr has been confirmed against schedule 11 and the spread carries the confirmed value.",
    ],
    facts: [
      { label: "Turnover FY2025", value: "INR 142.31 cr, up 19.8%", cite: "turnover" },
      { label: "EBITDA FY2025", value: "INR 15.58 cr, margin 10.9%", cite: "ebitda" },
      { label: "TNW / Total debt", value: "INR 33.08 cr / INR 37.05 cr", cite: "tnw" },
      { label: "Current ratio", value: "1.28x against a 1.20x floor", cite: "current-ratio" },
      { label: "TOL/TNW", value: "2.34x against a 3.00x ceiling", cite: "toltnw" },
      { label: "DSCR", value: "1.61x against a 1.25x floor", cite: "dscr" },
    ],
  },
  {
    id: "gst-bureau",
    number: "5",
    title: "GST and Bureau Findings",
    summary: "Independent filings, compliance record and registered charges.",
    drafted: "31 July 2026, 07:48",
    body: [
      "GST compliance is clean on process. All 24 GSTR-1 and GSTR-3B returns for FY2024-25 and FY2025-26 to date are on the GSTN ledger [[gst-filed]], none filed more than 20 days late, and no registration suspension appears against the GSTIN. Outward taxable supplies for FY2024-25 aggregate to INR 119.83 cr [[gst-turnover]].",
      "The bureau record supports the conduct assessment: CMR-4 [[conduct]], no reported overdues in 24 months, and no suit-filed or written-off entry against the borrower, its group entity or its directors.",
      "The registry search shows a subsisting CCB charge of INR 16.30 cr over current assets and a Horizon Bank charge of INR 3.10 cr satisfied on 18 February 2025 [[charges]]. No charge is recorded in favour of Crestline Financial Services, which is relevant to the finding in section 6.",
    ],
    facts: [
      { label: "GST filings", value: "24 of 24 filed, direct from GSTN", cite: "gst-filed" },
      { label: "GST turnover FY2024-25", value: "INR 119.83 cr", cite: "gst-turnover" },
      { label: "Charges", value: "CCB 16.30 cr subsisting; Horizon 3.10 cr satisfied", cite: "charges" },
      { label: "Adverse media", value: "Nothing material on the assessed window" },
    ],
  },
  {
    id: "cross-verification",
    number: "6",
    title: "Cross-Verification Results",
    summary: "Contradictions between sources, the evidence, and how each was adjudicated.",
    drafted: "31 July 2026, 07:48",
    body: [
      "Three cross-source contradictions were raised on this borrower; one is serious. Declared FY2025 turnover of INR 142.31 cr in the audited financials and the ITR is not supported by either independent source [[flag1]]. GST outward supplies for the same twelve months total INR 119.83 cr [[gst-turnover]] and customer credits into the two consented accounts total INR 121.44 cr [[bank-credits]], shortfalls of INR 22.48 cr and INR 20.87 cr respectively. The two independent sources agree with one another to within INR 1.61 cr, and the shortfall is present in all twelve months rather than in one or two periods, so an extraction or timing explanation is unlikely. Either turnover is overstated or a material part of collections is settled outside the banking and GST system.",
      "A recurring monthly debit of INR 4,37,500 to Crestline Financial Services, INR 52.50 lakh a year, appears in the Meridian Bank statement across twelve months but does not appear in the borrower's declared obligations [[flag2]]. No corresponding charge is registered [[charges]]. On the payment profile the implied residual is about INR 1.85 cr. Restating debt service for this obligation moves DSCR from 1.61x to 1.44x [[dscr]] and TOL/TNW from 2.34x to 2.40x.",
      "Buyer concentration is above the bank's soft cap: Meridian Auto Systems Ltd accounts for INR 54.65 cr, or 38.4% of sales, against a 35% cap [[flag3]]. The OEM supply contract runs to March 2028 and payment terms of 45 days have been honoured, which mitigates but does not remove the dependence.",
    ],
    facts: [
      { label: "Serious", value: "Turnover gap of INR 22.48 cr against GST", cite: "flag1" },
      { label: "Moderate", value: "Undisclosed Crestline obligation, INR 52.50 lakh a year", cite: "flag2" },
      { label: "Mild", value: "Buyer concentration 38.4% against a 35% cap", cite: "flag3" },
    ],
  },
  {
    id: "risk",
    number: "7",
    title: "Risk Assessment and Rating",
    summary: "The rating, the factors behind it, and the conditions attached.",
    drafted: "31 July 2026, 07:48",
    body: [
      "On the financial score alone the model places the borrower at CCB-3: growth is strong, leverage and coverage are inside policy [[toltnw]], and the conduct record is clean [[conduct]]. The evidence-quality overlay in the rating model applies a one-notch downgrade where a serious cross-verification finding is open or accepted [[policy-rating]], which produces a first-cut rating of CCB-4 (watch).",
      "The dominant risk is revenue quality [[flag1]]. Drawing power on an INR 18.50 cr Cash Credit is sized off the very turnover that two independent sources contradict; assessed on the evidenced turnover of INR 121.44 cr the supportable limit is INR 15.80 cr. The second risk is understated leverage and debt service arising from the undisclosed Crestline obligation [[flag2]], which takes DSCR to 1.44x on a restated basis — still above the floor, but with materially less headroom than the memo's face figures suggest.",
      "Mitigants are real but partial: a three-year OEM contract to March 2028, collateral cover of INR 11.40 cr, promoter guarantees, and a clean bureau and GST filing record [[gst-filed]]. The concentration finding [[flag3]] is reportable rather than adverse.",
    ],
    facts: [
      { label: "First-cut rating", value: "CCB-4 (watch), one notch below the financial score", cite: "policy-rating" },
      { label: "Weighs against", value: "Turnover discrepancy and undisclosed obligation", cite: "flag1" },
      { label: "Weighs for", value: "21.5% CAGR, clean conduct, collateral cover", cite: "turnover" },
    ],
  },
  {
    id: "recommendation",
    number: "8",
    title: "Recommendation",
    summary: "The analyst's recommendation to the credit committee.",
    drafted: "31 July 2026, 07:48",
    body: [
      "Recommended for sanction of the Cash Credit enhancement at a reduced limit of INR 15.80 cr rather than the INR 18.50 cr requested, together with the LC/BG line of INR 6.75 cr, pending the borrower's reconciliation of declared turnover [[flag1]]. The reduced limit is the drawing power supported by independently evidenced turnover [[bank-credits]]; the balance of INR 2.70 cr may be released on the committee's satisfaction with the reconciliation.",
      "Conditions recommended: (a) written reconciliation of FY2025 turnover against GST and bank credits within 30 days of sanction; (b) disclosure and registration of the Crestline Financial Services obligation [[flag2]], with a no-objection letter from that lender; (c) monthly stock and book-debt statements with quarterly GST turnover certification; (d) LEI renewal before 31 March 2027; (e) current ratio to be maintained at or above 1.20x [[current-ratio]] and TOL/TNW at or below 3.00x, tested half-yearly.",
      "This recommendation is made by the credit analyst on the evidence set out above and is subject to the credit manager's review and the committee's decision.",
    ],
    facts: [
      { label: "Recommended limit", value: "CC INR 15.80 cr + LC/BG INR 6.75 cr" },
      { label: "Against requested", value: "CC INR 18.50 cr, reduced by INR 2.70 cr", cite: "facility" },
      { label: "Conditions", value: "Five, including turnover reconciliation in 30 days", cite: "flag1" },
    ],
  },
];

export const getSection = (id: string) => SECTIONS.find((s) => s.id === id);

/* ---------------------------------------------------------- rating model */

export type Grade =
  | "CCB-1" | "CCB-2" | "CCB-3" | "CCB-4" | "CCB-5" | "CCB-6" | "CCB-7" | "CCB-8";

export const GRADES: { grade: Grade; label: string; band: string; tone: "positive" | "neutral" | "flag" | "critical" }[] = [
  { grade: "CCB-1", label: "Highest safety", band: "Prime", tone: "positive" },
  { grade: "CCB-2", label: "High safety", band: "Prime", tone: "positive" },
  { grade: "CCB-3", label: "Adequate safety", band: "Standard", tone: "neutral" },
  { grade: "CCB-4", label: "Watch", band: "Standard", tone: "flag" },
  { grade: "CCB-5", label: "Moderate risk", band: "Watch", tone: "flag" },
  { grade: "CCB-6", label: "High risk", band: "Watch", tone: "critical" },
  { grade: "CCB-7", label: "Substantial risk", band: "Sub-standard", tone: "critical" },
  { grade: "CCB-8", label: "Default or imminent default", band: "Sub-standard", tone: "critical" },
];

export const FIRST_CUT: Grade = "CCB-4";

export const RATING_FACTORS: { direction: "for" | "against"; title: string; detail: string; weight: string; cite?: string }[] = [
  {
    direction: "for",
    title: "Turnover CAGR of 21.5% over three years",
    detail: "INR 96.42 cr to INR 142.31 cr with an order book anchored on a tier-1 OEM contract to March 2028.",
    weight: "Financial score +1 notch",
    cite: "turnover",
  },
  {
    direction: "for",
    title: "Leverage and coverage inside policy",
    detail: "TOL/TNW 2.34x against a 3.00x ceiling and DSCR 1.61x against a 1.25x floor, with net worth built from retained earnings.",
    weight: "Financial score neutral to positive",
    cite: "toltnw",
  },
  {
    direction: "for",
    title: "Clean conduct and filing record",
    detail: "CMR-4 with no overdues in 24 months, 24 of 24 GST returns filed, no cheque returns in the assessed window.",
    weight: "Behavioural score neutral",
    cite: "conduct",
  },
  {
    direction: "against",
    title: "Declared turnover contradicted by two independent sources",
    detail: "Gap of INR 22.48 cr to GST and INR 20.87 cr to bank credits, present in all twelve months. Evidence-quality overlay applies a one-notch downgrade.",
    weight: "Overlay −1 notch",
    cite: "flag1",
  },
  {
    direction: "against",
    title: "Undisclosed Crestline Financial Services obligation",
    detail: "INR 52.50 lakh a year not in the declared obligations; restated DSCR falls from 1.61x to 1.44x and TOL/TNW rises to 2.40x.",
    weight: "Financial score −0.5 notch, disclosure concern",
    cite: "flag2",
  },
  {
    direction: "against",
    title: "Working capital cycle lengthened by 16 days",
    detail: "87 days in FY2025; growth is being funded on the cash conversion cycle and the current ratio has fallen in each of three years.",
    weight: "Financial score −0.5 notch",
    cite: "wc",
  },
];

export const DEFAULT_RECOMMENDATION =
  "Recommend sanction of the Cash Credit enhancement at a reduced limit of INR 15.80 cr, against INR 18.50 cr requested, together with the LC/BG line of INR 6.75 cr. The reduction reflects drawing power supported by independently evidenced turnover of INR 121.44 cr. Release of the balance INR 2.70 cr is recommended only on the committee's satisfaction with a written reconciliation of FY2025 turnover, and on disclosure and registration of the Crestline Financial Services obligation.";

/* --------------------------------------------------------------- routing */

export const ROUTING = {
  reviewer: "Sofia Almeida",
  reviewerRole: "Credit Manager, West Region",
  reviewerEmail: "sofia.almeida@contcombank.in",
  committee: "West Region Credit Committee",
  committeeChair: "Anand Iyer, Deputy General Manager",
  reviewTarget: "08 July 2026",
  committeeSitting: "14 July 2026",
  slaNote: "Credit manager review within two working days, committee sitting on the second Tuesday.",
};

/* ----------------------------------------------------------------- state */

export type SectionEdit = { text: string[]; by: string; at: string; reason?: string };
export type Override = {
  id: string;
  scope: string;
  field: string;
  original: string;
  override: string;
  reason: string;
  by: string;
  at: string;
};

export type MemoState = {
  edits: Record<string, SectionEdit>;
  regenerated: Record<string, { by: string; at: string }>;
  overrides: Override[];
  rating: Grade;
  ratingConfirmed: boolean;
  recommendation: string;
  recommendationConfirmed: boolean;
  submitted: null | { at: string; by: string; to: string; reference: string };
  returned: null | { at: string; reason: string };
  declined: null | { at: string; reason: string };
};

const NOW = "31 July 2026, 07:52";

let state: MemoState = {
  edits: {},
  regenerated: {},
  overrides: [],
  rating: FIRST_CUT,
  ratingConfirmed: false,
  recommendation: DEFAULT_RECOMMENDATION,
  recommendationConfirmed: false,
  submitted: null,
  returned: null,
  declined: null,
};

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const set = (patch: Partial<MemoState>) => {
  state = { ...state, ...patch };
  emit();
};

export function saveSectionEdit(sectionId: string, text: string[], by: string) {
  set({ edits: { ...state.edits, [sectionId]: { text, by, at: NOW } } });
}

export function revertSection(sectionId: string) {
  const edits = { ...state.edits };
  delete edits[sectionId];
  const regenerated = { ...state.regenerated };
  delete regenerated[sectionId];
  set({ edits, regenerated });
}

export function markRegenerated(sectionId: string, text: string[], by: string) {
  set({
    edits: { ...state.edits, [sectionId]: { text, by: `Copilot, accepted by ${by}`, at: NOW } },
    regenerated: { ...state.regenerated, [sectionId]: { by, at: NOW } },
  });
}

export function recordOverride(o: Omit<Override, "id" | "at">) {
  set({
    overrides: [...state.overrides, { ...o, id: `OV-${(state.overrides.length + 1).toString().padStart(2, "0")}`, at: NOW }],
  });
}

export function setRating(grade: Grade, reason: string, by: string) {
  if (grade !== state.rating) {
    recordOverride({
      scope: "Risk Assessment and Rating",
      field: "Internal risk rating",
      original: state.rating,
      override: grade,
      reason,
      by,
    });
  }
  set({ rating: grade, ratingConfirmed: false });
}

export function confirmRating(by: string) {
  set({ ratingConfirmed: true });
  void by;
}

export function setRecommendation(text: string) {
  set({ recommendation: text, recommendationConfirmed: false });
}

export function confirmRecommendation() {
  set({ recommendationConfirmed: true });
}

export function submitMemo(by: string) {
  set({
    submitted: { at: NOW, by, to: `${ROUTING.reviewer} · ${ROUTING.reviewerRole}`, reference: "SUB-2026-0418-01" },
    returned: null,
    declined: null,
  });
}

export function returnForData(reason: string) {
  set({ returned: { at: NOW, reason }, submitted: null });
}

export function declineMemo(reason: string) {
  set({ declined: { at: NOW, reason }, submitted: null });
}

export function useMemoState(): MemoState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}

export const bodyFor = (s: MemoState, section: MemoSection) => s.edits[section.id]?.text ?? section.body;
export const isEdited = (s: MemoState, sectionId: string) => Boolean(s.edits[sectionId]);

/** Copilot regeneration output, tighter wording with the same citations. */
export const REGENERATED: Record<string, string[]> = {
  risk: [
    "The financial score supports CCB-3 [[toltnw]], but the evidence-quality overlay applies a one-notch downgrade wherever a serious cross-verification finding stands [[policy-rating]]. The rating is therefore CCB-4 (watch).",
    "Revenue quality is the binding risk [[flag1]]: drawing power is sized off a turnover figure that two independent sources contradict by around INR 21 cr, and on evidenced turnover of INR 121.44 cr the supportable limit is INR 15.80 cr. Leverage is understated by an undisclosed obligation of INR 52.50 lakh a year [[flag2]], which restates DSCR to 1.44x [[dscr]].",
    "Against that stand a three-year OEM contract to March 2028, collateral cover of INR 11.40 cr, promoter guarantees and a clean filing and bureau record [[gst-filed]]. The rating should be revisited once the borrower's reconciliation is on file.",
  ],
  "cross-verification": [
    "Three contradictions were raised, one serious. FY2025 turnover of INR 142.31 cr is contradicted by GST outward supplies of INR 119.83 cr [[gst-turnover]] and bank credits of INR 121.44 cr [[bank-credits]], a shortfall present in every one of the twelve months and consistent across two sources that agree to within INR 1.61 cr [[flag1]].",
    "A monthly debit of INR 4,37,500 to Crestline Financial Services is unreported in the declared obligations and unregistered on the charge index [[flag2]] [[charges]]; restated, DSCR falls to 1.44x [[dscr]].",
    "Buyer concentration at 38.4% exceeds the 35% soft cap [[flag3]], mitigated by an OEM contract to March 2028.",
  ],
  financials: [
    "Turnover has compounded at 21.5% to INR 142.31 cr [[turnover]] while EBITDA margin has narrowed to 10.9% [[ebitda]] and PAT stands at INR 6.94 cr [[pat]].",
    "Net worth of INR 33.08 cr [[tnw]] against debt of INR 37.05 cr [[debt]] leaves gearing at 1.12x. Current ratio 1.28x [[current-ratio]], TOL/TNW 2.34x [[toltnw]] and DSCR 1.61x [[dscr]] are all inside policy, but the current ratio has fallen in each of three years and the working capital cycle has lengthened to 87 days [[wc]].",
  ],
};
