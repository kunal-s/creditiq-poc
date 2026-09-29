import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { ChecklistItemState, ChecklistStatus, Readiness } from "@/api/types";

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
export function isOpen(item: ChecklistItemState): boolean {
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
