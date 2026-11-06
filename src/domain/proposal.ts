import type { CaseCreate, CaseProposal, HeaderField, Meta, Option, Span } from "@/api/types";

/** The case's place in the bank's process (T2.1), shown first, in display order. */
export const APPLICATION_FIELDS = [
  "product",
  "case_type",
  "application_id",
  "customer_id",
  "branch",
  "bank_stage",
] as const;

/** The fields a proposal carries (F-04.2), in display order. */
export const PROPOSAL_FIELDS = [
  "borrower",
  "constitution",
  "facilities",
  "amount_inr",
  "proposed_emi_inr",
  "pan",
  "gstin",
  "cin",
  "udyam",
  "promoters",
  "declared_turnover_inr",
  "existing_banking",
  "contact",
] as const;

export type Draft = {
  /** What the RM will create with, per field (facilities: comma-joined ids). */
  values: Record<string, string>;
  /** The message span each value came from, if any. */
  spans: Record<string, Span | null>;
  /** Unclear or invalid fields the RM has explicitly settled. */
  settled: Record<string, boolean>;
  /** Values the system pre-filled (T2.1), with where each came from:
   * "default:config" (the configured default) or "default:rm" (the RM's branch). */
  defaults: Record<string, { value: string; source: string }>;
};

/** Fields whose value is one id from a configured list. */
const OPTION_LISTS = {
  constitution: "constitutions",
  product: "products",
  case_type: "case_types",
  branch: "branches",
  bank_stage: "bank_stages",
} as const satisfies Record<string, keyof Meta>;

export function optionsFor(field: string, meta: Meta): Option[] {
  if (field === "facilities") return meta.facilities;
  const key = OPTION_LISTS[field as keyof typeof OPTION_LISTS];
  return key ? (meta[key] as Option[]) : [];
}

function matchOption(options: Option[], raw: string): string | undefined {
  const needle = raw.trim().toLowerCase();
  if (!needle) return undefined;
  return options.find((o) => o.id.toLowerCase() === needle || o.label.toLowerCase() === needle)?.id;
}

/** Normalise a proposed value into the form the editor holds. */
export function normalise(field: string, raw: string | null, meta: Meta | undefined): string {
  if (raw === null) return "";
  if (field in OPTION_LISTS && meta) {
    const id = matchOption(optionsFor(field, meta), raw) ?? "";
    // "unknown" is how a case stores "not yet confirmed"; the editor holds it as empty.
    return id === "unknown" ? "" : id;
  }
  if (field === "facilities" && meta) {
    const ids = raw
      .split(/[,;|+/]|\band\b/i)
      .map((part) => matchOption(meta.facilities, part))
      .filter((id): id is string => Boolean(id));
    return Array.from(new Set(ids)).join(",");
  }
  if (field === "amount_inr" || field === "declared_turnover_inr" || field === "proposed_emi_inr") {
    const digits = raw.replace(/[^\d]/g, "");
    return digits;
  }
  return raw;
}

/** The branch id whose label matches the RM's own branch. */
export function branchFor(label: string | null | undefined, meta: Meta | undefined): string | null {
  if (!label || !meta) return null;
  const needle = label.trim().toLowerCase();
  return meta.branches.find((b) => b.label.toLowerCase() === needle)?.id ?? null;
}

export function draftFrom(
  proposal: CaseProposal,
  meta: Meta | undefined,
  rmBranch?: string | null,
): Draft {
  const values: Record<string, string> = {};
  const spans: Record<string, Span | null> = {};
  for (const [key, f] of Object.entries(proposal.fields)) {
    values[key] = f.status === "not_found" ? "" : normalise(key, f.value, meta);
    spans[key] = f.span ?? null;
  }
  // T2.1: product and stage start at their configured defaults, the branch at
  // the RM's own, unless the message named one. Each keeps where it came from.
  const defaults: Draft["defaults"] = {};
  const prefill = (key: string, value: string | null | undefined, source: string) => {
    if (!value || values[key]) return;
    values[key] = value;
    spans[key] = null;
    defaults[key] = { value, source };
  };
  prefill("product", meta?.product_default, "default:config");
  prefill("bank_stage", meta?.bank_stage_default, "default:config");
  prefill("branch", branchFor(rmBranch, meta), "default:rm");
  return { values, spans, settled: {}, defaults };
}

/** Application fields first (T2.1), then the proposal's own fields. */
export function fieldKeys(proposal: CaseProposal): string[] {
  const known: string[] = PROPOSAL_FIELDS.filter((k) => k in proposal.fields);
  const app: string[] = [...APPLICATION_FIELDS];
  const extra = Object.keys(proposal.fields).filter((k) => !known.includes(k) && !app.includes(k));
  return [...app, ...known, ...extra];
}

/** The value is still the one the system pre-filled. */
export function isDefaulted(draft: Draft, key: string): boolean {
  const d = draft.defaults[key];
  return d !== undefined && (draft.values[key] ?? "") === d.value;
}

/** Unclear or invalid fields still waiting for the RM (F-04.3, F-04.4). */
export function unsettled(proposal: CaseProposal, draft: Draft): string[] {
  return Object.entries(proposal.fields)
    .filter(([key, f]) => (f.status === "unclear" || f.status === "invalid") && !draft.settled[key])
    .map(([key]) => key);
}

/** Minimum fields still empty (F-04.6), from configuration. A field with a
 * configured default (product, bank stage) is never missing: the case takes
 * the default unless the RM chooses otherwise. */
export function missingMinimum(
  minimum: string[],
  draft: Draft,
  defaults: Record<string, string | null | undefined> = {},
): string[] {
  return minimum.filter((key) => {
    const v = (draft.values[key] ?? "").trim();
    if (v === "" && defaults[key]) return false;
    if (key === "amount_inr") return !(Number(v) > 0);
    return v === "";
  });
}

function spanSource(span: Span | null | undefined): string | null {
  return span ? `message:${span.start}-${span.end}` : null;
}

/** The CaseCreate body: confirmed values, with the proposed value and its
 * source kept beside each (F-01.2, F-04.8). */
export function toCaseCreate(
  proposal: CaseProposal,
  draft: Draft,
  channel: string,
  duplicateReason: string | null,
  messageText: string,
): CaseCreate {
  const v = (key: string) => {
    const value = (draft.values[key] ?? "").trim();
    return value === "" ? null : value;
  };
  const header: Record<string, HeaderField> = {};
  for (const key of new Set([...Object.keys(proposal.fields), ...Object.keys(draft.values)])) {
    const value = v(key);
    if (isDefaulted(draft, key)) {
      // A default the RM left alone is recorded as a default, not as the RM's choice.
      const d = draft.defaults[key]!;
      header[key] = { value, proposed: d.value, source: d.source };
      continue;
    }
    const proposed = proposal.fields[key]?.value ?? null;
    if (value === null && proposed === null) continue;
    header[key] = {
      value,
      proposed,
      source: spanSource(draft.spans[key]) ?? (value !== null ? "person" : null),
    };
  }
  const body: CaseCreate = {
    borrower: v("borrower") ?? "",
    constitution: v("constitution") ?? "unknown",
    facilities: (v("facilities") ?? "").split(",").filter(Boolean),
    amount_inr: Number(v("amount_inr") ?? 0),
    channel,
    pan: v("pan"),
    gstin: v("gstin"),
    cin: v("cin"),
    udyam: v("udyam"),
    collateral_present: false,
    product: v("product"),
    case_type: v("case_type") ?? "unknown",
    application_id: v("application_id"),
    customer_id: v("customer_id"),
    branch: v("branch"),
    bank_stage: v("bank_stage"),
    header,
    // Stored unchanged as the case's first document (F-04.1, F-04.8).
    message_text: messageText,
  };
  if (duplicateReason) body.duplicate_override_reason = duplicateReason;
  return body;
}

export type Mark = {
  start: number;
  end: number;
  level: "stripped" | "found" | "candidate" | "selected";
};

/** Split the message into runs, each with the strongest mark covering it. */
export function markRuns(
  text: string,
  marks: Mark[],
): { text: string; start: number; level: Mark["level"] | null }[] {
  const rank = { stripped: 0, found: 1, candidate: 2, selected: 3 } as const;
  const bounds = new Set<number>([0, text.length]);
  for (const m of marks) {
    bounds.add(Math.max(0, Math.min(text.length, m.start)));
    bounds.add(Math.max(0, Math.min(text.length, m.end)));
  }
  const points = Array.from(bounds).sort((a, b) => a - b);
  const runs: { text: string; start: number; level: Mark["level"] | null }[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i]!;
    const end = points[i + 1]!;
    if (end <= start) continue;
    let level: Mark["level"] | null = null;
    for (const m of marks) {
      if (m.start <= start && m.end >= end && (!level || rank[m.level] > rank[level])) {
        level = m.level;
      }
    }
    runs.push({ text: text.slice(start, end), start, level });
  }
  return runs;
}
