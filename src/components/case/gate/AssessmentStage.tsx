import type { ReactNode } from "react";
import { useCaseProgress } from "@/domain/progress";
import { AssessmentLocked } from "./AssessmentLocked";

/** Wraps a stage that the F-13 gate controls. While the gate is shut the stage shows what is
 * outstanding instead of its content; the server refuses the same stages, so nothing is
 * reachable by going straight to the URL either.
 *
 * Nothing is rendered until the progress is known, so the content never flashes before the
 * lock replaces it. */
export function AssessmentStage({ caseId, children }: { caseId: string; children: ReactNode }) {
  const progress = useCaseProgress(caseId);
  if (progress.isPending) return null;
  const gate = progress.data?.gate;
  // A progress without a gate predates it: the stage behaves as it always did.
  if (gate && !gate.open) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <AssessmentLocked caseId={caseId} />
      </div>
    );
  }
  return <>{children}</>;
}
