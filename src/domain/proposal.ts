import type { CaseCreate, CaseProposal, HeaderField, Meta, Option, Span } from "@/api/types";

/** The fields a proposal carries (F-04.2), in display order. */
export const PROPOSAL_FIELDS = [
  "borrower",
  "constitution",
  "facilities",
  "amount_inr",
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
};

function matchOption(options: Option[], raw: string): string | undefined {
  const needle = raw.trim().toLowerCase();
  if (!needle) return undefined;
  return options.find((o) => o.id.toLowerCase() === needle || o.label.toLowerCase() === needle)?.id;
}

/** Normalise a proposed value into the form the editor holds. */
export function normalise(field: string, raw: string | null, meta: Meta | undefined): string {
  if (raw === null) return "";
  if (field === "constitution" && meta) return matchOption(meta.constitutions, raw) ?? "";
  if (field === "facilities" && meta) {
    const ids = raw
      .split(/[,;|+/]|\band\b/i)
      .map((part) => matchOption(meta.facilities, part))
      .filter((id): id is string => Boolean(id));
    return Array.from(new Set(ids)).join(",");
  }
  if (field === "amount_inr" || field === "declared_turnover_inr") {
    const digits = raw.replace(/[^\d]/g, "");
    return digits;
  }
  return raw;
}

export function draftFrom(proposal: CaseProposal, meta: Meta | undefined): Draft {
  const values: Record<string, string> = {};
  const spans: Record<string, Span | null> = {};
  for (const [key, f] of Object.entries(proposal.fields)) {
    values[key] = f.status === "not_found" ? "" : normalise(key, f.value, meta);
    spans[key] = f.span ?? null;
  }
  return { values, spans, settled: {} };
}

export function fieldKeys(proposal: CaseProposal): string[] {
  const known: string[] = PROPOSAL_FIELDS.filter((k) => k in proposal.fields);
  const extra = Object.keys(proposal.fields).filter((k) => !known.includes(k));
  return [...known, ...extra];
}

/** Unclear or invalid fields still waiting for the RM (F-04.3, F-04.4). */
export function unsettled(proposal: CaseProposal, draft: Draft): string[] {
  return Object.entries(proposal.fields)
    .filter(([key, f]) => (f.status === "unclear" || f.status === "invalid") && !draft.settled[key])
    .map(([key]) => key);
}

/** Minimum fields still empty (F-04.6), from configuration. */
export function missingMinimum(minimum: string[], draft: Draft): string[] {
  return minimum.filter((key) => {
    const v = (draft.values[key] ?? "").trim();
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
    const proposed = proposal.fields[key]?.value ?? null;
    const value = v(key);
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
