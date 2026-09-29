import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { ReviewDecision, ReviewDecisionRequest, ReviewKind } from "@/api/types";
import { useSession } from "./session";

export function useReviewQueue(options: { caseId?: string; includeDecided?: boolean } = {}) {
  const session = useSession();
  const allowed = session?.user.permissions.includes("review.read") ?? false;
  return useQuery({
    queryKey: ["review", options.caseId ?? "all", options.includeDecided ? "all" : "open"],
    queryFn: () => api.reviewQueue(options),
    enabled: allowed,
  });
}

export function useDecideReview() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ReviewDecisionRequest }) =>
      api.decideReview(id, body),
    onSuccess: (item) => {
      void client.invalidateQueries({ queryKey: ["review"] });
      void client.invalidateQueries({ queryKey: ["cases", item.case_id] });
      void client.invalidateQueries({ queryKey: ["cases"], exact: true });
    },
  });
}

/** The decisions each kind of review item admits, as the engine accepts
 * them (F-17.5, F-09.5, F-07.5, F-10.5). Findings are decided on their own
 * screen, not here. For a quality exception, "correct" is manual entry. */
export const DECISIONS_BY_KIND: Record<ReviewKind, ReviewDecision[]> = {
  type: ["assign", "waive"],
  field: ["confirm", "correct"],
  quality: ["confirm", "correct", "waive"],
  party: ["confirm", "correct"],
  split: ["confirm"],
  manual_entry: ["confirm"],
  finding: [],
};

/** What a review item points at: "field:<id>", "document:<id>" or "file:<id>". */
export function reviewTarget(ref: string): { kind: string; id: string } {
  const at = ref.indexOf(":");
  return at < 0 ? { kind: "", id: ref } : { kind: ref.slice(0, at), id: ref.slice(at + 1) };
}

/** Correct and waive need a reason (F-17.5). */
export function needsReason(decision: ReviewDecision): boolean {
  return decision === "correct" || decision === "waive";
}

export const REVIEW_KINDS: ReviewKind[] = [
  "type",
  "field",
  "quality",
  "party",
  "split",
  "manual_entry",
  "finding",
];
