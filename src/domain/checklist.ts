import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { ChecklistItemState, ChecklistStatus, Readiness } from "@/api/types";
import { t } from "@/config/terminology";

export function useChecklist(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "checklist"],
    queryFn: () => api.caseChecklist(caseId),
  });
}

/** The checklist of every listed case, for the Readiness console. */
export function useChecklists(caseIds: string[]) {
  return useQueries({
    queries: caseIds.map((id) => ({
      queryKey: ["cases", id, "checklist"],
      queryFn: () => api.caseChecklist(id),
    })),
  });
}

export function useQueryList(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "queries"],
    queryFn: () => api.caseQueries(caseId),
  });
}

/** Section weights and gates as published (F-00). */
export function useTaxonomy() {
  return useQuery({
    queryKey: ["config", "checklist-taxonomy"],
    queryFn: api.checklistTaxonomy,
    staleTime: Infinity,
  });
}

export type ReadinessCounts = Record<ChecklistStatus, number> & {
  total: number;
  outstanding: number;
};

export function countItems(items: ChecklistItemState[]): ReadinessCounts {
  const counts: ReadinessCounts = {
    satisfied: 0,
    insufficient: 0,
    missing: 0,
    in_review: 0,
    waived: 0,
    total: items.length,
    outstanding: 0,
  };
  for (const item of items) counts[item.status] += 1;
  counts.outstanding = counts.insufficient + counts.missing;
  return counts;
}

/** Items that still stand between the case and its gate. */
export function isOpen(item: Pick<ChecklistItemState, "status">): boolean {
  return item.status !== "satisfied" && item.status !== "waived";
}

/** Ready for credit as the engine decides it (F-13.5). */
export function readyForCredit(r: Readiness): boolean {
  return r.ready_for_credit;
}

/** Items grouped by section, in the published section order where known. */
export function bySection(
  items: ChecklistItemState[],
  order: string[] | undefined,
): { section: string; items: ChecklistItemState[] }[] {
  const sections: string[] = [];
  for (const s of order ?? []) if (items.some((i) => i.section === s)) sections.push(s);
  for (const i of items) if (!sections.includes(i.section)) sections.push(i.section);
  return sections.map((section) => ({
    section,
    items: items.filter((i) => i.section === section),
  }));
}

// --- The readiness glance and the banded checklist ---

/** What the checklist shows: everything, or one kind of requirement. */
export type Filter = "all" | "blocking" | "todo" | "in_review" | "satisfied";

export function passes(item: Pick<ChecklistItemState, "status" | "blocking">, f: Filter): boolean {
  switch (f) {
    case "all":
      return true;
    case "blocking":
      return item.blocking && isOpen(item);
    case "todo":
      return item.status === "missing" || item.status === "insufficient";
    case "in_review":
      return item.status === "in_review";
    case "satisfied":
      return item.status === "satisfied" || item.status === "waived";
  }
}

/** Where a requirement sits in the list: what stops the case, what is asked but does not stop
 * it, what waits for a person, and what is done. */
export type Band = "blocking" | "nonblocking" | "inreview" | "done";
export const BAND_ORDER: Band[] = ["blocking", "nonblocking", "inreview", "done"];

export function bandOf(item: Pick<ChecklistItemState, "status" | "blocking">): Band {
  if (item.status === "satisfied" || item.status === "waived") return "done";
  if (item.blocking) return "blocking";
  if (item.status === "in_review") return "inreview";
  return "nonblocking";
}

/** Most pressing first within a section. */
export const STATUS_ORDER: Record<ChecklistStatus, number> = {
  missing: 0,
  insufficient: 1,
  in_review: 2,
  satisfied: 3,
  waived: 4,
};

/** Done first in a section's cells, so the cells fill from the left as the file completes. */
export const CELL_ORDER: Record<ChecklistStatus, number> = {
  satisfied: 0,
  waived: 1,
  in_review: 2,
  insufficient: 3,
  missing: 4,
};

function sectionIndex(section: string, sections: string[] | undefined): number {
  const i = (sections ?? []).indexOf(section);
  return i < 0 ? Number.MAX_SAFE_INTEGER : i;
}

/** By published section (unknown sections last), then most pressing, then as the engine sent
 * them. `statusOf` lets a row keep the place it had when a file was sent from it. */
export function sortInBand<T extends ChecklistItemState>(
  items: T[],
  sections: string[] | undefined,
  statusOf: (item: T) => ChecklistStatus = (item) => item.status,
): T[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort(
      (a, b) =>
        sectionIndex(a.item.section, sections) - sectionIndex(b.item.section, sections) ||
        STATUS_ORDER[statusOf(a.item)] - STATUS_ORDER[statusOf(b.item)] ||
        a.index - b.index,
    )
    .map(({ item }) => item);
}

/** The requirements that stop the case reaching credit review, most pressing first. */
export function blockers(
  items: ChecklistItemState[],
  sections: string[] | undefined,
): ChecklistItemState[] {
  return sortInBand(
    items.filter((i) => i.blocking && isOpen(i)),
    sections,
  );
}

export type SectionGroup = {
  section: string;
  cells: ChecklistItemState[];
  satisfied: number;
  counts: ReadinessCounts;
};

/** One group a section, in the published order, each with its requirements as cells. */
export function sectionGroups(
  items: ChecklistItemState[],
  sections: string[] | undefined,
): SectionGroup[] {
  return bySection(items, sections).map(({ section, items: own }) => ({
    section,
    cells: own
      .map((item, index) => ({ item, index }))
      .sort((a, b) => CELL_ORDER[a.item.status] - CELL_ORDER[b.item.status] || a.index - b.index)
      .map(({ item }) => item),
    satisfied: own.filter((i) => i.status === "satisfied").length,
    counts: countItems(own),
  }));
}

/** The readiness score as printed everywhere (the case header and the Overview). Rounded, except
 * that within a point below the gate it keeps one decimal, so it never reads as the gate while
 * the gate is unmet. */
export function scoreText(score: number, gate: number): string {
  const n = Math.round(score);
  return n >= gate && score < gate ? (Math.floor(score * 10) / 10).toFixed(1) : String(n);
}

/** Points still needed to reach the gate, to one decimal (rounded up, so the score and the
 * points always reach the gate), never negative. 85 − 84.6 is 0.4000000000000057 in floating
 * point; the epsilon keeps that from rounding up to 0.5. */
export function pointsToGo(r: Pick<Readiness, "score_pct" | "gate_pct">): number {
  return Math.max(0, Math.ceil((r.gate_pct - r.score_pct) * 10 - 1e-9) / 10);
}

export function formatPoints(x: number): string {
  return Number.isInteger(x) ? String(x) : x.toFixed(1);
}

/** "27 points to go", "1 point to go", "0.4 points to go". */
export function toGoText(points: number): string {
  return points === 1
    ? t("assessment.tile.toGoOne")
    : t("assessment.tile.toGo", { n: formatPoints(points) });
}

export type Verdict = "ready" | "blocked" | "belowGate" | "gateMet";

/** Where the case stands, as one word. Never ready while the checklist is provisional. */
export function verdictOf(
  r: Pick<
    Readiness,
    "ready_for_credit" | "provisional" | "blocking_open" | "score_pct" | "gate_pct"
  >,
): Verdict {
  if (r.ready_for_credit && !r.provisional) return "ready";
  if (r.blocking_open > 0) return "blocked";
  if (r.score_pct < r.gate_pct) return "belowGate";
  return "gateMet";
}
