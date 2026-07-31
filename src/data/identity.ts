export type Confidence = "high" | "medium" | "low";

export type ResolvedField = {
  label: string;
  value: string;
  confidence: Confidence;
  source: string;
  note?: string;
};

export type Director = {
  slug: string;
  name: string;
  din: string;
  role: string;
  appointed: string;
  age: number;
  nationality: string;
  shareholding: string;
  otherDirectorships: { name: string; entitySlug?: string; role: string; status: string }[];
  disqualified: boolean;
  source: string;
};

export type EntityRecord = {
  slug: string;
  name: string;
  cin: string;
  pan: string;
  panMasked: string;
  gstin: string;
  lei?: string;
  leiValidTo?: string;
  leiNote?: string;
  incorporated: string;
  registeredOffice: string;
  status: string;
  sector: string;
  authorisedCapital: string;
  paidUpCapital: string;
  lastFilingAgm: string;
  directorSlugs: string[];
  exposure?: string;
  appraisalId?: string;
  relationship: "Borrower" | "Related party";
};

export const DIRECTORS: Director[] = [
  {
    slug: "rajesh-malhotra",
    name: "Rajesh Malhotra",
    din: "01847362",
    role: "Managing Director",
    appointed: "14 August 2009",
    age: 58,
    nationality: "Indian",
    shareholding: "41.20% of paid-up equity",
    otherDirectorships: [
      {
        name: "Northwind Logistics Ltd",
        entitySlug: "northwind-logistics",
        role: "Director",
        status: "Active since 3 February 2016",
      },
      { name: "Malhotra Family Holdings Pvt Ltd", role: "Director", status: "Active since 2011" },
    ],
    disqualified: false,
    source: "MCA DIN master · refreshed 29 July 2026",
  },
  {
    slug: "anita-malhotra",
    name: "Anita Malhotra",
    din: "01847388",
    role: "Whole-time Director",
    appointed: "14 August 2009",
    age: 54,
    nationality: "Indian",
    shareholding: "22.65% of paid-up equity",
    otherDirectorships: [
      { name: "Malhotra Family Holdings Pvt Ltd", role: "Director", status: "Active since 2011" },
    ],
    disqualified: false,
    source: "MCA DIN master · refreshed 29 July 2026",
  },
  {
    slug: "sameer-deshpande",
    name: "Sameer Deshpande",
    din: "02911574",
    role: "Independent Director",
    appointed: "27 September 2018",
    age: 61,
    nationality: "Indian",
    shareholding: "Nil",
    otherDirectorships: [
      { name: "Deccan Toolings Ltd", role: "Independent Director", status: "Active since 2019" },
    ],
    disqualified: false,
    source: "MCA DIN master · refreshed 29 July 2026",
  },
];

export const getDirector = (slug: string) => DIRECTORS.find((d) => d.slug === slug);

export const ENTITIES: EntityRecord[] = [
  {
    slug: "northwind-manufacturing",
    name: "Northwind Manufacturing Ltd",
    cin: "U27310MH2009PLC198435",
    pan: "AABCN4521Q",
    panMasked: "AABCN••••Q",
    gstin: "27AABCN4521Q1ZP",
    lei: "894500XYZ7NORTHWIND12",
    leiValidTo: "31 March 2027",
    incorporated: "14 August 2009",
    registeredOffice: "Plot D-42, Chakan Industrial Area Phase II, Pune 410501, Maharashtra",
    status: "Active — compliant",
    sector: "Engineering goods manufacturing (precision sheet metal, OEM tier-2)",
    authorisedCapital: "INR 12.00 cr",
    paidUpCapital: "INR 8.40 cr",
    lastFilingAgm: "AOC-4 and MGT-7 filed for FY25 on 24 October 2025",
    directorSlugs: ["rajesh-malhotra", "anita-malhotra", "sameer-deshpande"],
    exposure: "Cash Credit INR 12.20 cr outstanding INR 10.86 cr, sanctioned 30 August 2025",
    appraisalId: "CAM-2026-0418",
    relationship: "Borrower",
  },
  {
    slug: "northwind-logistics",
    name: "Northwind Logistics Ltd",
    cin: "U63030MH2016PLC276104",
    pan: "AABCL8890R",
    panMasked: "AABCL••••R",
    gstin: "27AABCL8890R1Z4",
    leiNote: "LEI not obtained — entity is below the reporting threshold and has no derivative exposure.",
    incorporated: "3 February 2016",
    registeredOffice: "Gat 118/2, Talegaon Dabhade, Pune 410507, Maharashtra",
    status: "Active — compliant",
    sector: "Third-party road logistics and warehousing",
    authorisedCapital: "INR 4.00 cr",
    paidUpCapital: "INR 2.75 cr",
    lastFilingAgm: "AOC-4 and MGT-7 filed for FY25 on 11 November 2025",
    directorSlugs: ["rajesh-malhotra"],
    exposure: "No facilities with Continental Commercial Bank. Vehicle loans of INR 3.15 cr with HDFC Bank per bureau.",
    relationship: "Related party",
  },
];

export const getEntity = (slug: string) => ENTITIES.find((e) => e.slug === slug);

export const RESOLVED_FIELDS: ResolvedField[] = [
  { label: "Legal name", value: "Northwind Manufacturing Ltd", confidence: "high", source: "MCA registry" },
  { label: "CIN", value: "U27310MH2009PLC198435", confidence: "high", source: "MCA registry" },
  { label: "PAN", value: "AABCN••••Q", confidence: "high", source: "Income Tax PAN verification" },
  { label: "GSTIN", value: "27AABCN4521Q1ZP", confidence: "high", source: "GSTN taxpayer search" },
  {
    label: "Registered office",
    value: "Chakan Industrial Area Phase II, Pune 410501, Maharashtra",
    confidence: "high",
    source: "MCA registry",
    note: "Matches the GST principal place of business.",
  },
  { label: "Date of incorporation", value: "14 August 2009", confidence: "high", source: "MCA registry" },
  {
    label: "LEI",
    value: "894500XYZ7NORTHWIND12",
    confidence: "medium",
    source: "LEIL registry",
    note: "Valid to 31 March 2027 — renewal falls inside the proposed facility tenor.",
  },
];

export type RelatedLink = {
  entitySlug: string;
  name: string;
  pan: string;
  gstin: string;
  basis: string;
  confidence: Confidence;
  source: string;
  leiNote?: string;
  suggested: boolean;
};

export const SUGGESTED_LINKS: RelatedLink[] = [
  {
    entitySlug: "northwind-logistics",
    name: "Northwind Logistics Ltd",
    pan: "AABCL8890R",
    gstin: "27AABCL8890R1Z4",
    basis: "Shares director Rajesh Malhotra (DIN 01847362) and a common registered-office pincode district (Pune).",
    confidence: "high",
    source: "MCA DIN linkage · GSTN address match",
    leiNote: "LEI not obtained for this entity.",
    suggested: true,
  },
];

export type DuplicateCandidate = {
  name: string;
  cin: string;
  pan: string;
  gstin: string;
  incorporated: string;
  registeredOffice: string;
  status: string;
  distinguishers: string[];
};

export const NEAR_DUPLICATE: DuplicateCandidate = {
  name: "Northwind Manufacturing Private Ltd",
  cin: "U28999MH2014PTC258771",
  pan: "AAHCN7712L",
  gstin: "27AAHCN7712L1ZM",
  incorporated: "19 May 2014",
  registeredOffice: "Unit 7, Bhosari MIDC, Pune 411026, Maharashtra",
  status: "Active — no common directors with the confirmed entity",
  distinguishers: [
    "Different CIN and PAN; the PAN supplied by the relationship manager matches only the confirmed entity.",
    "No director overlap: promoters are Vikram Joshi and Neelam Joshi.",
    "GST turnover band INR 5–10 cr against the declared FY25 turnover of INR 84.60 cr.",
  ],
};

export const RECENT_BORROWERS = [
  {
    name: "Northwind Manufacturing Ltd",
    pan: "AABCN••••Q",
    gstin: "27AABCN4521Q1ZP",
    context: "Cash Credit INR 12.20 cr on the books · Pune Corporate Branch",
    prefill: true,
  },
  {
    name: "Trident Industrial Packaging Ltd",
    pan: "AABCT••••J",
    gstin: "24AABCT••••J1ZQ",
    context: "Term Loan appraisal CAM-2026-0421 at draft stage",
    prefill: false,
  },
  {
    name: "Sahyadri Pharma Distributors Pvt Ltd",
    pan: "AAGCS••••M",
    gstin: "27AAGCS••••M1Z4",
    context: "Fresh working capital appraisal CAM-2026-0426",
    prefill: false,
  },
];

export const DEMO_INTAKE = {
  borrower: "Northwind Manufacturing Ltd",
  pan: "AABCN4521Q",
  gstin: "27AABCN4521Q1ZP",
  facilityType: "Cash Credit enhancement with LC/BG sub-limit",
  amount: "18.50",
  subLimit: "6.75",
  purpose:
    "Cash Credit enhancement to INR 18.50 cr plus LC/BG INR 6.75 cr, working capital for a new OEM order book.",
};

export const SANCTION_REQUEST_TEXT = `From: Marcus Chen, Relationship Manager, Pune Corporate Branch
Subject: Enhancement request — Northwind Manufacturing Ltd

Northwind Manufacturing Ltd (PAN AABCN4521Q, GSTIN 27AABCN4521Q1ZP) has requested an enhancement of the existing Cash Credit limit from INR 12.20 cr to INR 18.50 cr, together with an LC/BG sub-limit of INR 6.75 cr, to fund working capital for a newly awarded OEM order book. Security remains the existing hypothecation of stock and book debts.`;
