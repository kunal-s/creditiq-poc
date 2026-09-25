import { useSyncExternalStore } from "react";

/* ------------------------------------------------------- library records */

export type MemoStatus =
  "In committee review" | "Completed" | "In preparation" | "Drafting" | "Refresh due";

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

// No memos have been issued yet in this deployment.
export const BORROWERS: BorrowerRecord[] = [];

export const getBorrower = (slug: string) => BORROWERS.find((b) => b.slug === slug);
export const borrowerForAppraisal = (id: string) => BORROWERS.find((b) => b.appraisalId === id);

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

export const CHANGES: RefreshChange[] = [];

/* ------------------------------------------------------------ refresh UI */

export type RefreshState = {
  status: "idle" | "running" | "done";
  consent: "expired" | "requested" | "granted";
  bankRefreshedAt: string | null;
  accepted: null | { at: string; by: string };
  reviewStarted: boolean;
};

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
export const grantConsent = () =>
  set({ consent: "granted", bankRefreshedAt: new Date().toISOString() });
export const acceptNoChange = (by: string) =>
  set({ accepted: { at: new Date().toISOString(), by } });
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
