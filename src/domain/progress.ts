import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "@/api/client";
import type { CaseProgress, StageProgress } from "@/api/types";
import { t } from "@/config/terminology";

const POLL_MS = 3000;

/** The case's stage progress (FRD §6); polls while any stage is running, so
 * processing shows without a page reload (F-02.2). */
export function useCaseProgress(caseId: string) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["cases", caseId, "progress"],
    queryFn: () => api.caseProgress(caseId),
    refetchInterval: (q) => (running(q.state.data) ? POLL_MS : false),
  });
  // When processing moves on, everything else shown for the case (the
  // checklist, review items, the case header) is stale: refresh it too.
  const signature = query.data ? JSON.stringify(query.data) : undefined;
  const previous = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!signature) return;
    if (previous.current !== undefined && previous.current !== signature) {
      void client.invalidateQueries({
        predicate: (q) =>
          (q.queryKey[0] === "cases" &&
            (q.queryKey.length === 1 ||
              (q.queryKey[1] === caseId && q.queryKey[2] !== "progress"))) ||
          q.queryKey[0] === "review",
      });
    }
    previous.current = signature;
  }, [signature, caseId, client]);
  return query;
}

export function running(progress: CaseProgress | undefined): boolean {
  return progress?.stages.some((s) => s.status === "in_progress") ?? false;
}

/** The first stage waiting for a person, else the first still running. */
export function nextStage(progress: CaseProgress): StageProgress | undefined {
  return (
    progress.stages.find((s) => s.status === "needs_attention") ??
    progress.stages.find((s) => s.status === "in_progress")
  );
}

/** One line under the stage name: its counts, or what it is waiting for. */
export function stageDetail(stage: StageProgress): string {
  if (stage.status === "not_started") {
    return stage.key === "documents"
      ? t("progress.waiting.documents")
      : t("progress.waiting.other");
  }
  const counted = ["documents", "extraction", "completeness"].includes(stage.key);
  const count = counted
    ? t(`progress.count.${stage.key}`, { done: stage.done, total: stage.total })
    : t(`progress.status.${stage.status}`);
  return stage.attention > 0 && stage.status !== "done"
    ? `${count} · ${t("progress.attention", { n: stage.attention })}`
    : count;
}
