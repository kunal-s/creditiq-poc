import { useSyncExternalStore } from "react";
import { t } from "@/config/terminology";

/* ============================================================ ratio policy */

export type Kind = "min" | "max";
export type Band = "acceptable" | "marginal" | "adverse";

export type PolicyRatio = {
  key: string;
  label: string;
  unit: "x" | "%" | "days";
  kind: Kind;
  /** acceptable threshold, then the marginal cut-off; beyond it is adverse */
  acceptable: number;
  marginal: number;
  formula: string;
  applies: string;
  owner: string;
  note: string;
  /** hard regulatory or board floor that cannot be relaxed below */
  hardFloor?: string;
};

export const BASE_RATIOS: PolicyRatio[] = [
  {
    key: "current-ratio",
    label: "Current ratio",
    unit: "x",
    kind: "min",
    acceptable: 1.2,
    marginal: 1.1,
    formula: "Current assets ÷ Current liabilities",
    applies: "All working-capital exposures",
    owner: "Credit Risk Policy",
    note: "Board floor is 1.10x for manufacturing; anything below is an adverse classification and needs Chief Credit Officer sign-off.",
    hardFloor: "Board floor 1.10x — cannot be set lower",
  },
  {
    key: "tol-tnw",
    label: "TOL / TNW",
    unit: "x",
    kind: "max",
    acceptable: 3.0,
    marginal: 3.75,
    formula: "Total outside liabilities ÷ Tangible net worth",
    applies: "All fund-based exposures above INR 5 cr",
    owner: "Credit Risk Policy",
    note: "Ceiling recalibrated on 18 April 2026 from 2.75x after the sector review of auto components.",
  },
  {
    key: "dscr",
    label: "DSCR",
    unit: "x",
    kind: "min",
    acceptable: 1.5,
    marginal: 1.25,
    formula: "(PAT + depreciation + interest on term debt) ÷ (interest + principal repayments)",
    applies: "Term exposures and any borrower with instalment obligations",
    owner: "Credit Risk Policy",
    note: "The 1.25x marginal line is the hard floor below which the proposal cannot be recommended at branch level.",
    hardFloor: "Hard floor 1.25x — sanction blocked below this",
  },
  {
    key: "interest-coverage",
    label: "Interest coverage",
    unit: "x",
    kind: "min",
    acceptable: 2.5,
    marginal: 1.75,
    formula: "EBIT ÷ Interest and finance charges",
    applies: "All exposures",
    owner: "Credit Risk Policy",
    note: "Read alongside DSCR; a coverage above 2.50x with a DSCR below 1.50x usually points to a bunched repayment profile.",
  },
  {
    key: "buyer-concentration",
    label: "Buyer concentration",
    unit: "%",
    kind: "max",
    acceptable: 35,
    marginal: 45,
    formula: "Largest customer's share of gross sales",
    applies: "Manufacturing and trading exposures",
    owner: "Credit Risk Policy",
    note: "A soft cap. A breach does not block sanction but must be narrated with the mitigant in the memo.",
  },
  {
    key: "debt-equity",
    label: "Debt / equity",
    unit: "x",
    kind: "max",
    acceptable: 2.0,
    marginal: 2.5,
    formula: "Total debt ÷ Tangible net worth",
    applies: "All fund-based exposures",
    owner: "Credit Risk Policy",
    note: "Indicative rather than binding; the TOL/TNW ceiling is the operative leverage test.",
  },
  {
    key: "wc-cycle",
    label: "Working-capital cycle",
    unit: "days",
    kind: "max",
    acceptable: 75,
    marginal: 95,
    formula: "Inventory days + receivable days − payable days",
    applies: "Auto components and engineering goods",
    owner: "Sector benchmark, Credit Risk",
    note: "Sector benchmark for auto components. Drawing power is sized on the assessed cycle, not the declared one.",
  },
];

/** Ratios the bank has switched off, offered when adding to the set. */
export const AVAILABLE_RATIOS: PolicyRatio[] = [
  {
    key: "quick-ratio",
    label: "Quick ratio",
    unit: "x",
    kind: "min",
    acceptable: 0.9,
    marginal: 0.75,
    formula: "(Current assets − inventory) ÷ Current liabilities",
    applies: "Inventory-heavy exposures",
    owner: "Credit Risk Policy",
    note: "Not currently underwritten. Useful where inventory build is masking a liquidity strain in the current ratio.",
  },
  {
    key: "ebitda-margin",
    label: "EBITDA margin",
    unit: "%",
    kind: "min",
    acceptable: 9,
    marginal: 6,
    formula: "EBITDA ÷ Revenue from operations",
    applies: "Manufacturing exposures",
    owner: "Credit Risk Policy",
    note: "Not currently underwritten. Sector median for auto components is 10.4%.",
  },
  {
    key: "promoter-stake",
    label: "Promoter shareholding",
    unit: "%",
    kind: "min",
    acceptable: 51,
    marginal: 40,
    formula: "Promoter and promoter-group holding in paid-up capital",
    applies: "All exposures to closely held companies",
    owner: "Credit Risk Policy",
    note: "Not currently underwritten as a ratio; captured qualitatively in the memo today.",
  },
];

export function classify(r: PolicyRatio, v: number): Band {
  if (r.kind === "min")
    return v >= r.acceptable ? "acceptable" : v >= r.marginal ? "marginal" : "adverse";
  return v <= r.acceptable ? "acceptable" : v <= r.marginal ? "marginal" : "adverse";
}

export const BAND_LABEL: Record<Band, string> = {
  acceptable: "Acceptable",
  marginal: "Marginal",
  adverse: "Adverse",
};

export const BAND_TONE: Record<Band, string> = {
  acceptable: "border-positive/30 bg-positive-soft text-positive",
  marginal: "border-flag/35 bg-flag-soft text-flag-foreground",
  adverse: "border-critical/30 bg-critical-soft text-critical",
};

export const fmtRatio = (v: number, unit: PolicyRatio["unit"]) =>
  unit === "days"
    ? `${Math.round(v)} days`
    : unit === "%"
      ? `${v.toFixed(1)}%`
      : `${v.toFixed(2)}x`;

/* ------------------------------------------------------------- risk grid */

export type GridBand = {
  grade: string;
  label: string;
  band: string;
  scoreFrom: number;
  scoreTo: number;
  watch: boolean;
  guidance: string;
};

const GRADE = t("ratingGrid.gradePrefix");

export const BASE_GRID: GridBand[] = [
  {
    grade: `${GRADE}-1`,
    label: "Highest safety",
    band: "Prime",
    scoreFrom: 90,
    scoreTo: 100,
    watch: false,
    guidance: "Delegated to Credit Manager up to INR 25 cr.",
  },
  {
    grade: `${GRADE}-2`,
    label: "High safety",
    band: "Prime",
    scoreFrom: 80,
    scoreTo: 89,
    watch: false,
    guidance: "Delegated to Credit Manager up to INR 15 cr.",
  },
  {
    grade: `${GRADE}-3`,
    label: "Adequate safety",
    band: "Standard",
    scoreFrom: 70,
    scoreTo: 79,
    watch: false,
    guidance: "Regional committee for exposures above INR 10 cr.",
  },
  {
    grade: `${GRADE}-4`,
    label: "Watch",
    band: "Standard",
    scoreFrom: 60,
    scoreTo: 69,
    watch: true,
    guidance: "Regional committee mandatory; quarterly review; covenant monitoring.",
  },
  {
    grade: `${GRADE}-5`,
    label: "Moderate risk",
    band: "Watch",
    scoreFrom: 50,
    scoreTo: 59,
    watch: true,
    guidance:
      "Regional committee mandatory; no enhancement without Chief Credit Officer concurrence.",
  },
  {
    grade: `${GRADE}-6`,
    label: "High risk",
    band: "Watch",
    scoreFrom: 40,
    scoreTo: 49,
    watch: false,
    guidance: "Head office committee; exit or restructure plan required.",
  },
  {
    grade: `${GRADE}-7`,
    label: "Substantial risk",
    band: "Sub-standard",
    scoreFrom: 25,
    scoreTo: 39,
    watch: false,
    guidance: "Head office committee; account moved to the stressed-assets desk.",
  },
  {
    grade: `${GRADE}-8`,
    label: "Default or imminent default",
    band: "Sub-standard",
    scoreFrom: 0,
    scoreTo: 24,
    watch: false,
    guidance: "Recovery. No fresh exposure.",
  },
];

/* --------------------------------------------------- the book, for preview */

export type BookBorrower = {
  slug: string;
  name: string;
  appraisalId?: string;
  grade: string;
  score: number;
  exposure: string;
  analyst: string;
  values: Record<string, number>;
};

// No borrowers are on the book yet in this deployment.
export const BOOK: BookBorrower[] = [];

/** How many borrowers change band on a ratio between the published and draft policy. */
export function reclassified(published: PolicyRatio, draft: PolicyRatio) {
  return BOOK.filter((b) => {
    const v = b.values[draft.key];
    if (v === undefined) return false;
    return classify(published, v) !== classify(draft, v);
  }).map((b) => ({
    borrower: b,
    from: BAND_LABEL[classify(published, b.values[draft.key]!)],
    to: BAND_LABEL[classify(draft, b.values[draft.key]!)],
  }));
}

/* ============================================================== template */

export type TemplateSection = {
  id: string;
  title: string;
  purpose: string;
  required: boolean;
  enabled: boolean;
  words: number;
  citations: "every-figure" | "material-only" | "none";
};

export const BASE_TEMPLATE: TemplateSection[] = [
  {
    id: "profile",
    title: "Borrower and Group Profile",
    purpose: "Legal identity, group perimeter, directors and shareholding.",
    required: true,
    enabled: true,
    words: 320,
    citations: "every-figure",
  },
  {
    id: "facility",
    title: "Facility Requested and Purpose",
    purpose: "Limits sought, structure, security and end use.",
    required: false,
    enabled: true,
    words: 280,
    citations: "every-figure",
  },
  {
    id: "conduct",
    title: "Banking Conduct",
    purpose: "Utilisation, overdrawing, return of instruments, conduct with other banks.",
    required: false,
    enabled: true,
    words: 260,
    citations: "material-only",
  },
  {
    id: "financials",
    title: "Financial Analysis and Ratios",
    purpose: "Three-year spread, ratio table against policy, drawing-power assessment.",
    required: true,
    enabled: true,
    words: 520,
    citations: "every-figure",
  },
  {
    id: "bureau",
    title: "GST and Bureau Findings",
    purpose: "Filing discipline, bureau enquiries, existing obligations and charges.",
    required: false,
    enabled: true,
    words: 300,
    citations: "every-figure",
  },
  {
    id: "crossverify",
    title: "Cross-Verification Results",
    purpose: "Contradictions across sources and how each was adjudicated.",
    required: false,
    enabled: true,
    words: 380,
    citations: "every-figure",
  },
  {
    id: "risk",
    title: "Risk Assessment and Rating",
    purpose: "Rating grid, factors for and against, overlays and overrides.",
    required: true,
    enabled: true,
    words: 420,
    citations: "every-figure",
  },
  {
    id: "recommendation",
    title: "Recommendation",
    purpose: "The analyst's recommendation, conditions precedent and covenants.",
    required: true,
    enabled: true,
    words: 280,
    citations: "material-only",
  },
];

export const TONE_PRESETS = [
  {
    id: "rbl-house",
    label: t("memoTone.house"),
    detail:
      "Third person, past tense, no adjectives of praise, figures in INR crore to two decimals.",
  },
  {
    id: "plain",
    label: t("memoTone.plainCommittee"),
    detail: "Short sentences, consequence stated before evidence, jargon expanded on first use.",
  },
  {
    id: "regulatory",
    label: t("memoTone.regulatoryDefensive"),
    detail:
      "Every claim attributed in-line, hedged language where evidence is partial, no forward projections without basis.",
  },
];

export type TemplateSettings = {
  tone: string;
  figures: "crore-2dp" | "lakh-0dp" | "absolute";
  citations: "inline" | "endnote";
  header: string;
  annexures: string[];
};

export const BASE_TEMPLATE_SETTINGS: TemplateSettings = {
  tone: "rbl-house",
  figures: "crore-2dp",
  citations: "inline",
  header: `${t("tenant.bank.name")} · ${t("tenant.bank.unit")} · CAM template v1.0`,
  annexures: [
    "Annexure A — Financial spread",
    "Annexure B — Cross-verification evidence",
    "Annexure C — Charge and security schedule",
  ],
};

/* ============================================================ connectors */

export type Health = "healthy" | "degraded" | "down";

export type ConnectorRow = {
  id: string;
  name: string;
  provider: string;
  detail: string;
  enabled: boolean;
  health: Health;
  latency: string;
  successRate: string;
  lastCall: string;
  consent: "required" | "not-required";
  retentionDays: number;
  note: string;
  required?: boolean;
};

export const BASE_CONNECTORS: ConnectorRow[] = [
  {
    id: "gst",
    name: "GST returns",
    provider: `GSTN via ${t("tenant.bank.name")} API gateway`,
    detail: "GSTR-1 and GSTR-3B, 24 periods, filing status and outward supplies.",
    enabled: false,
    health: "down",
    latency: "—",
    successRate: "—",
    lastCall: "Not yet connected",
    consent: "not-required",
    retentionDays: 3650,
    note: "Primary independent evidence for turnover. Not connected in this environment (plan.md C13).",
    required: true,
  },
  {
    id: "bureau",
    name: "Commercial credit bureau",
    provider: "TransUnion CIBIL Commercial",
    detail: "Existing facilities, DPD history, enquiries and CMR rank.",
    enabled: false,
    health: "down",
    latency: "—",
    successRate: "—",
    lastCall: "Not yet connected",
    consent: "required",
    retentionDays: 2555,
    note: "Bureau pull is logged against the borrower's consent reference and is visible to the borrower on request.",
    required: true,
  },
  {
    id: "registry",
    name: "Company registry and charges",
    provider: "MCA21 and CERSAI",
    detail: "CIN master, directors, charge index and satisfaction records.",
    enabled: false,
    health: "down",
    latency: "—",
    successRate: "—",
    lastCall: "Not yet connected",
    consent: "not-required",
    retentionDays: 3650,
    note: "Also drives entity resolution and the group perimeter.",
    required: true,
  },
  {
    id: "aa",
    name: "Account Aggregator with PDF fallback",
    provider: "Sahamati AA network",
    detail:
      "Bank statements under borrower consent; PDF upload where consent is declined or expired.",
    enabled: false,
    health: "down",
    latency: "—",
    successRate: "—",
    lastCall: "Not yet connected",
    consent: "required",
    retentionDays: 1825,
    note: "Not enabled for this deployment — Manual upload is the active path (plan.md C13).",
    required: true,
  },
  {
    id: "lei",
    name: "LEI lookup",
    provider: "GLEIF public API",
    detail: "Legal entity identifier, registration status and parent relationships.",
    enabled: false,
    health: "down",
    latency: "—",
    successRate: "—",
    lastCall: "Not yet connected",
    consent: "not-required",
    retentionDays: 3650,
    note: "Cheap corroboration of legal name and status; no consent implication.",
  },
  {
    id: "media",
    name: "Adverse media and sanctions",
    provider: "Adverse-media screening feed",
    detail: "Negative news, litigation and sanctions screening on the entity and its directors.",
    enabled: false,
    health: "down",
    latency: "—",
    successRate: "—",
    lastCall: "Not yet connected",
    consent: "not-required",
    retentionDays: 1095,
    note: "Not connected in this environment.",
  },
  {
    id: "core",
    name: "Core banking and origination",
    provider: `${t("tenant.bank.name")} core banking and loan origination system`,
    detail: "Existing limits, conduct, internal ratings and prior sanction history.",
    enabled: false,
    health: "down",
    latency: "—",
    successRate: "—",
    lastCall: "Not yet connected",
    consent: "not-required",
    retentionDays: 3650,
    note: "Internal system of record. Never overwritten by this instance; read-only.",
    required: true,
  },
  {
    id: "identity",
    name: "Identity directory",
    provider: "Staff identity provider",
    detail: "Staff identity, role assignment and single sign-on.",
    enabled: true,
    health: "healthy",
    latency: "0.4 s median",
    successRate: "100%",
    lastCall: "just now",
    consent: "not-required",
    retentionDays: 3650,
    note: "Drives Users and Roles. Disabling it would lock every user out.",
    required: true,
  },
];

export const HEALTH_LABEL: Record<Health, string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  down: "Down",
};
export const HEALTH_TONE: Record<Health, string> = {
  healthy: "border-positive/30 bg-positive-soft text-positive",
  degraded: "border-flag/35 bg-flag-soft text-flag-foreground",
  down: "border-critical/30 bg-critical-soft text-critical",
};

/** What stops working in an appraisal if a source is switched off. */
export const CONNECTOR_IMPACT: Record<string, string[]> = {
  gst: [
    "Cross-verification rules that compare declared turnover against GST cannot run",
    "Filing-discipline paragraph in GST and Bureau Findings drops out",
    "Turnover in the memo rests on the borrower's own statements alone",
  ],
  bureau: [
    "Existing obligations and DPD history come only from the borrower's declaration",
    "Rule XV-11 loses one of its two corroborating sources for undisclosed lenders",
    `The rating model's conduct input falls back to internal conduct only, which caps the achievable grade at ${GRADE}-3`,
  ],
  registry: [
    "Entity resolution falls back to name matching, and the group perimeter must be entered by hand",
    "Charge index unavailable, so unregistered obligations cannot be detected",
  ],
  aa: [
    "Bank credits are unavailable, so the turnover triangulation drops from three sources to two",
    "Conduct analysis relies on the borrower's uploaded statements",
    "Consent journey is skipped entirely and every appraisal starts on the manual-upload path",
  ],
  lei: ["Legal-name corroboration is lost; low impact, no rule depends on it alone"],
  media: [
    "Negative-news and sanctions screening is skipped and the memo records the gap",
    "Reputational-risk paragraph in Risk Assessment is omitted",
  ],
  core: [
    "Existing limits and internal conduct are unavailable; enhancement proposals cannot be sized",
  ],
  identity: ["Every user loses access. This source cannot be switched off from here."],
};

export type ConsentSettings = {
  windowDays: number;
  purposeText: string;
  reminderDays: number;
  autoRevoke: boolean;
  retentionYears: number;
  piiMasking: boolean;
};

export const BASE_CONSENT: ConsentSettings = {
  windowDays: 30,
  purposeText: `Credit appraisal and periodic review of facilities sanctioned by ${t("tenant.bank.name")}.`,
  reminderDays: 5,
  autoRevoke: true,
  retentionYears: 10,
  piiMasking: true,
};

/* ============================================================ users, roles */

export type RoleId = "analyst" | "rm" | "credit-manager" | "cco" | "admin" | "compliance";

export const ROLES: {
  id: RoleId;
  label: string;
  summary: string;
  permissions: string[];
  approver: boolean;
  author: boolean;
}[] = [
  {
    id: "analyst",
    label: "Credit Analyst",
    summary: "Authors appraisals end to end and adjudicates findings.",
    author: true,
    approver: false,
    permissions: [
      "Create and edit appraisals",
      "Adjudicate cross-verification findings",
      "Set the first-cut rating and recommend",
      "Submit for review",
    ],
  },
  {
    id: "rm",
    label: "Relationship Manager",
    summary: "Originates, uploads borrower documents, cannot recommend.",
    author: true,
    approver: false,
    permissions: [
      "Create an appraisal",
      "Upload documents and request consent",
      "Read the memo",
      "Comment, but not edit the memo body",
    ],
  },
  {
    id: "credit-manager",
    label: "Credit Manager",
    summary: "Reviews and approves memos authored by others.",
    author: false,
    approver: true,
    permissions: [
      "Review submitted memos",
      "Approve, return or decline",
      "Reassign exceptions",
      "Read every appraisal in the region",
    ],
  },
  {
    id: "cco",
    label: "Chief Credit Officer",
    summary: "Final approval above delegated limits and policy exceptions.",
    author: false,
    approver: true,
    permissions: [
      "Approve above delegated authority",
      "Grant policy exceptions",
      "Override a rating with reason",
      "Read the whole book",
    ],
  },
  {
    id: "admin",
    label: "Administrator",
    summary: "Configures policy, templates, connectors and roles. No credit authority.",
    author: false,
    approver: false,
    permissions: [
      "Edit ratio policy and the rating grid",
      "Edit the CAM template",
      "Enable and test connectors",
      "Manage users and roles",
    ],
  },
  {
    id: "compliance",
    label: "Compliance and Audit",
    summary: "Read-only across the whole record, including the audit ledger.",
    author: false,
    approver: false,
    permissions: [
      "Read every memo and its audit ledger",
      "Export examiner records",
      "Cannot edit, adjudicate or approve",
    ],
  },
];

export type UserRow = {
  slug: string;
  name: string;
  role: RoleId;
  email: string;
  branch: string;
  status: "active" | "invited" | "suspended";
  lastActive: string;
  authored: number;
  approved: number;
  delegation: string;
};

// Mirrors config/roles.yaml's user roster (the sign-in directory); this
// copy is what the admin screen's local draft/publish actions mutate.
export const BASE_USERS: UserRow[] = [
  {
    slug: "ananya-krishnan",
    name: "Ananya Krishnan",
    role: "analyst",
    email: "ananya.krishnan@rblbank.com",
    branch: "Mumbai hub",
    status: "active",
    lastActive: "Not yet recorded",
    authored: 0,
    approved: 0,
    delegation: "None — authors only",
  },
  {
    slug: "arjun-deshpande",
    name: "Arjun Deshpande",
    role: "rm",
    email: "arjun.deshpande@rblbank.com",
    branch: "Pune Corporate Branch",
    status: "active",
    lastActive: "Not yet recorded",
    authored: 0,
    approved: 0,
    delegation: "None",
  },
  {
    slug: "meenal-kulkarni",
    name: "Meenal Kulkarni",
    role: "credit-manager",
    email: "meenal.kulkarni@rblbank.com",
    branch: "Mumbai hub",
    status: "active",
    lastActive: "Not yet recorded",
    authored: 0,
    approved: 0,
    delegation: `Up to INR 25 cr for ${GRADE}-1 to ${GRADE}-3`,
  },
  {
    slug: "rohan-ferreira",
    name: "Rohan Ferreira",
    role: "cco",
    email: "rohan.ferreira@rblbank.com",
    branch: "Mumbai hub",
    status: "active",
    lastActive: "Not yet recorded",
    authored: 0,
    approved: 0,
    delegation: "Unlimited within board policy",
  },
  {
    slug: "divya-menon",
    name: "Divya Menon",
    role: "admin",
    email: "divya.menon@rblbank.com",
    branch: "Mumbai hub",
    status: "active",
    lastActive: "Not yet recorded",
    authored: 0,
    approved: 0,
    delegation: "No credit authority",
  },
  {
    slug: "siddharth-rane",
    name: "Siddharth Rane",
    role: "compliance",
    email: "siddharth.rane@rblbank.com",
    branch: "Mumbai hub",
    status: "active",
    lastActive: "Not yet recorded",
    authored: 0,
    approved: 0,
    delegation: "Read-only",
  },
];

export type SoDConflict = {
  user: string;
  slug: string;
  detail: string;
  severity: "blocked" | "watch";
};

/** Segregation of duties: nobody may hold an authoring and an approving role at once. */
export function sodConflicts(users: UserRow[]): SoDConflict[] {
  const out: SoDConflict[] = [];
  for (const u of users) {
    const role = ROLES.find((r) => r.id === u.role)!;
    if (role.author && role.approver)
      out.push({
        user: u.name,
        slug: u.slug,
        detail: `${role.label} both authors and approves. Policy forbids one person holding both.`,
        severity: "blocked",
      });
    if (u.authored > 0 && role.approver)
      out.push({
        user: u.name,
        slug: u.slug,
        detail: `${u.name} has ${u.authored} authored memos on record and now holds ${role.label}. They must not approve any memo they authored.`,
        severity: "watch",
      });
  }
  return out;
}

/* ============================================================== live state */

export type AdminState = {
  ratios: PolicyRatio[];
  grid: GridBand[];
  policyPublished: null | { at: string; by: string; version: string };
  template: TemplateSection[];
  templateSettings: TemplateSettings;
  templatePublished: null | { at: string; by: string; version: string };
  connectors: ConnectorRow[];
  consent: ConsentSettings;
  tests: Record<string, { at: string; result: string; ok: boolean }>;
  users: UserRow[];
  log: { at: string; by: string; text: string }[];
};

let state: AdminState = {
  ratios: BASE_RATIOS.map((r) => ({ ...r })),
  grid: BASE_GRID.map((g) => ({ ...g })),
  policyPublished: null,
  template: BASE_TEMPLATE.map((s) => ({ ...s })),
  templateSettings: { ...BASE_TEMPLATE_SETTINGS },
  templatePublished: null,
  connectors: BASE_CONNECTORS.map((c) => ({ ...c })),
  consent: { ...BASE_CONSENT },
  tests: {},
  users: BASE_USERS.map((u) => ({ ...u })),
  log: [],
};

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const set = (patch: Partial<AdminState>) => {
  state = { ...state, ...patch };
  emit();
};
const now = () => new Date().toISOString();
const note = (text: string, by: string) => ({ at: now(), by, text });

export function useAdminState(): AdminState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => state,
  );
}

export function setThreshold(
  key: string,
  field: "acceptable" | "marginal",
  value: number,
  actor: string,
) {
  set({
    ratios: state.ratios.map((r) => (r.key === key ? { ...r, [field]: value } : r)),
    log: [note(`${key} ${field} threshold set to ${value}`, actor), ...state.log],
  });
}

export function addRatio(key: string, actor: string) {
  const r = AVAILABLE_RATIOS.find((a) => a.key === key);
  if (!r || state.ratios.some((x) => x.key === key)) return;
  set({
    ratios: [...state.ratios, { ...r }],
    log: [note(`${r.label} added to the underwritten set`, actor), ...state.log],
  });
}

export function removeRatio(key: string, actor: string) {
  const r = state.ratios.find((x) => x.key === key);
  set({
    ratios: state.ratios.filter((x) => x.key !== key),
    log: [note(`${r?.label ?? key} removed from the underwritten set`, actor), ...state.log],
  });
}

export function setGridBand(grade: string, patch: Partial<GridBand>, actor: string) {
  set({
    grid: state.grid.map((g) => (g.grade === grade ? { ...g, ...patch } : g)),
    log: [note(`${grade} band amended`, actor), ...state.log],
  });
}

export function publishPolicy(version: string, actor: string) {
  set({
    policyPublished: { at: now(), by: actor, version },
    log: [note(`Ratio policy ${version} published to every appraisal`, actor), ...state.log],
  });
}

export function resetPolicy(actor: string) {
  set({
    ratios: BASE_RATIOS.map((r) => ({ ...r })),
    grid: BASE_GRID.map((g) => ({ ...g })),
    log: [note("Draft policy discarded, published policy restored", actor), ...state.log],
  });
}

export function moveSection(id: string, dir: -1 | 1, actor: string) {
  const i = state.template.findIndex((s) => s.id === id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= state.template.length) return;
  const next = [...state.template];
  const a = next[i]!;
  const b = next[j]!;
  next[i] = b;
  next[j] = a;
  set({
    template: next,
    log: [note(`${a.title} moved to position ${j + 1}`, actor), ...state.log],
  });
}

export function updateSection(id: string, patch: Partial<TemplateSection>, actor: string) {
  set({
    template: state.template.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    log: [
      note(`Section "${state.template.find((s) => s.id === id)?.title}" amended`, actor),
      ...state.log,
    ],
  });
}

export function setTemplateSettings(patch: Partial<TemplateSettings>, actor: string) {
  set({
    templateSettings: { ...state.templateSettings, ...patch },
    log: [note("Template settings amended", actor), ...state.log],
  });
}

export function publishTemplate(version: string, actor: string) {
  set({
    templatePublished: { at: now(), by: actor, version },
    log: [note(`CAM template ${version} published`, actor), ...state.log],
  });
}

export function toggleConnector(id: string, actor: string) {
  const c = state.connectors.find((x) => x.id === id);
  if (!c || c.required) return;
  set({
    connectors: state.connectors.map((x) => (x.id === id ? { ...x, enabled: !x.enabled } : x)),
    log: [note(`${c.name} switched ${c.enabled ? "off" : "on"}`, actor), ...state.log],
  });
}

export function setRetention(id: string, days: number) {
  set({
    connectors: state.connectors.map((x) => (x.id === id ? { ...x, retentionDays: days } : x)),
  });
}

export function testConnector(id: string) {
  const c = state.connectors.find((x) => x.id === id);
  if (!c) return { ok: true, result: "" };
  const ok = c.health === "healthy";
  const result = ok
    ? `Handshake and sample read succeeded in ${c.latency.replace(" median", "")}.`
    : "Not connected in this environment.";
  set({ tests: { ...state.tests, [id]: { at: now(), result, ok } } });
  return { ok, result };
}

export function setConsent(patch: Partial<ConsentSettings>, actor: string) {
  set({
    consent: { ...state.consent, ...patch },
    log: [note("Consent and retention settings amended", actor), ...state.log],
  });
}

export function setUserRole(slug: string, role: RoleId, actor: string) {
  const u = state.users.find((x) => x.slug === slug);
  set({
    users: state.users.map((x) => (x.slug === slug ? { ...x, role } : x)),
    log: [
      note(`${u?.name ?? slug} role changed to ${ROLES.find((r) => r.id === role)?.label}`, actor),
      ...state.log,
    ],
  });
}

export function setUserStatus(slug: string, status: UserRow["status"]) {
  set({ users: state.users.map((x) => (x.slug === slug ? { ...x, status } : x)) });
}

export function addUser(u: UserRow, actor: string) {
  set({
    users: [...state.users, u],
    log: [
      note(`${u.name} invited as ${ROLES.find((r) => r.id === u.role)?.label}`, actor),
      ...state.log,
    ],
  });
}
