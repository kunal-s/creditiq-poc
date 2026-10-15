import { Link } from "@tanstack/react-router";
import { Lock } from "lucide-react";
import { gateConditions } from "@/components/case/gate/conditions";
import { t } from "@/config/terminology";
import { useCaseProgress } from "@/domain/progress";
import { cn } from "@/lib/utils";
import { ConditionList } from "./ConditionList";

/** Shown in place of a stage that the F-13 gate has shut: cross-verification, the policy
 * checks and the outputs. It says what is outstanding and where to go, rather than an empty
 * screen; the server refuses the same stages, so this is a courtesy, not the control. */
export function AssessmentLocked({ caseId, className }: { caseId: string; className?: string }) {
  const progress = useCaseProgress(caseId);
  const gate = progress.data?.gate ?? null;
  return (
    <section
      className={cn("rounded border border-border bg-surface p-6", className)}
      data-testid="assessment-locked"
    >
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full border border-border bg-surface-muted text-muted-foreground"
          aria-hidden
        >
          <Lock className="h-4 w-4" />
        </span>
        <div className="min-w-0 space-y-3">
          <div>
            <h2 className="text-[14px] font-medium text-foreground">
              {t("assessment.lockedTitle")}
            </h2>
            <p className="mt-1 max-w-prose text-[12.5px] text-muted-foreground">
              {t("assessment.lockedBody")}
            </p>
          </div>
          {gate && <ConditionList conditions={gateConditions(gate)} />}
          <Link
            to="/appraisals/$caseId/completeness"
            params={{ caseId }}
            className="inline-flex items-center rounded border border-border px-3 py-1.5 text-[12.5px] font-medium text-foreground hover:bg-surface-muted"
            data-testid="assessment-locked-action"
          >
            {t("assessment.lockedAction")}
          </Link>
        </div>
      </div>
    </section>
  );
}
