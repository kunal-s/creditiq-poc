import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/api/client";
import type {
  AdjudicationRequest,
  ComparisonArea,
  ComparisonItem,
  ComparisonStatus,
} from "@/api/types";

// CreditIQ against RBL's reference record (FRD F-25): the deviations and
// approving-authority areas. Decisions here sit beside the output and never
// change it (F-25.5), so mutations refresh only the comparison, never the
// policy, the memo or the PD note.

export function useComparison(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "comparison"],
    queryFn: () => api.caseComparison(caseId),
  });
}

export function useConfirmReference(caseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.confirmReference(caseId),
    onSuccess: () => client.invalidateQueries({ queryKey: ["cases", caseId, "comparison"] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });
}

export function useAdjudicate(caseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      area,
      key,
      body,
    }: {
      area: ComparisonArea;
      key: string;
      body: AdjudicationRequest;
    }) => api.adjudicate(caseId, area, key, body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["cases", caseId, "comparison"] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
  });
}

export type ComparisonFilter = "all" | "toAdjudicate" | ComparisonStatus;

export const FILTERS: ComparisonFilter[] = [
  "all",
  "toAdjudicate",
  "agree",
  "differ",
  "new",
  "missed",
];

/** An item still waiting for the reviewer: a difference or a new deviation with no current decision. */
export function awaitsDecision(item: ComparisonItem): boolean {
  return item.adjudicable && (!item.adjudication || Boolean(item.adjudication.stale));
}

export function matches(item: ComparisonItem, filter: ComparisonFilter): boolean {
  if (filter === "all") return true;
  if (filter === "toAdjudicate") return awaitsDecision(item);
  return item.status === filter;
}

export const AREAS: ComparisonArea[] = ["deviations", "approving_authority"];
