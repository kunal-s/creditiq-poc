import { useSyncExternalStore } from "react";
import { t } from "@/config/terminology";

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

// No memo has any citations yet in this deployment — populated once a case
// reaches the draft step and the drafting engine cites its sources.
export const CITATIONS: Record<string, Citation> = {};

export const citationsFor = (ids: string[]) =>
  ids.map((i) => CITATIONS[i]).filter(Boolean) as Citation[];

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

// No memo has any section content yet in this deployment — populated
// once a case reaches the draft step.
export const SECTIONS: MemoSection[] = [];

export const getSection = (id: string) => SECTIONS.find((s) => s.id === id);

/* ---------------------------------------------------------- rating model */

const GRADE = t("ratingGrid.gradePrefix");

export type Grade = `${typeof GRADE}-${1 | 2 | 3 | 4 | 5 | 6 | 7 | 8}`;

export const GRADES: {
  grade: Grade;
  label: string;
  band: string;
  tone: "positive" | "neutral" | "flag" | "critical";
}[] = [
  { grade: `${GRADE}-1`, label: "Highest safety", band: "Prime", tone: "positive" },
  { grade: `${GRADE}-2`, label: "High safety", band: "Prime", tone: "positive" },
  { grade: `${GRADE}-3`, label: "Adequate safety", band: "Standard", tone: "neutral" },
  { grade: `${GRADE}-4`, label: "Watch", band: "Standard", tone: "flag" },
  { grade: `${GRADE}-5`, label: "Moderate risk", band: "Watch", tone: "flag" },
  { grade: `${GRADE}-6`, label: "High risk", band: "Watch", tone: "critical" },
  { grade: `${GRADE}-7`, label: "Substantial risk", band: "Sub-standard", tone: "critical" },
  {
    grade: `${GRADE}-8`,
    label: "Default or imminent default",
    band: "Sub-standard",
    tone: "critical",
  },
];

export const FIRST_CUT: Grade = `${GRADE}-1`;

// No case has reached rating yet in this deployment.
export const RATING_FACTORS: {
  direction: "for" | "against";
  title: string;
  detail: string;
  weight: string;
  cite?: string;
}[] = [];

export const DEFAULT_RECOMMENDATION = "";

/* --------------------------------------------------------------- routing */

export const ROUTING = {
  reviewerRole: t("routing.reviewerRole"),
  committee: t("routing.committee"),
  committeeChairRole: t("routing.committeeChairRole"),
  slaNote:
    "Credit manager review within two working days, committee sitting on the second Tuesday.",
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

const now = () => new Date().toISOString();

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
  set({ edits: { ...state.edits, [sectionId]: { text, by, at: now() } } });
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
    edits: { ...state.edits, [sectionId]: { text, by: `Copilot, accepted by ${by}`, at: now() } },
    regenerated: { ...state.regenerated, [sectionId]: { by, at: now() } },
  });
}

export function recordOverride(o: Omit<Override, "id" | "at">) {
  set({
    overrides: [
      ...state.overrides,
      { ...o, id: `OV-${(state.overrides.length + 1).toString().padStart(2, "0")}`, at: now() },
    ],
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
    submitted: { at: now(), by, to: ROUTING.reviewerRole, reference: `SUB-${Date.now()}` },
    returned: null,
    declined: null,
  });
}

export function returnForData(reason: string) {
  set({ returned: { at: now(), reason }, submitted: null });
}

export function declineMemo(reason: string) {
  set({ declined: { at: now(), reason }, submitted: null });
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

export const bodyFor = (s: MemoState, section: MemoSection) =>
  s.edits[section.id]?.text ?? section.body;
export const isEdited = (s: MemoState, sectionId: string) => Boolean(s.edits[sectionId]);
