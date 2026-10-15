import { Loader2 } from "lucide-react";
import type { AssessmentGate } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { useOpenAssessment } from "@/domain/cases";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { gateConditions } from "./conditions";
import { ConditionList } from "./ConditionList";

/** The F-13 gate at the foot of the completeness step: the three conditions, then the action
 * that creates the case and opens cross-verification, the policy checks and the outputs.
 * Only a role holding `review.decide` sees the action; everyone sees where the case stands. */
export function CreateCasePanel({ caseId, gate }: { caseId: string; gate: AssessmentGate }) {
  const mutation = useOpenAssessment(caseId);
  const mayCreate = useCan("review.decide");

  if (gate.open) {
    return (
      <Panel title={t("assessment.gateTitle")} testId="create-case-panel">
        <div className="px-4 py-3" data-testid="assessment-created">
          <p className="text-[12.5px] text-muted-foreground">
            {gate.opened_at ? t("assessment.created", { at: gate.opened_at.slice(0, 10) }) : ""}
          </p>
        </div>
      </Panel>
    );
  }

  return (
    <Panel
      title={gate.can_open ? t("assessment.gateTitle") : t("assessment.gateTitleBlocked")}
      subtitle={t("assessment.gateIntro")}
      testId="create-case-panel"
    >
      <div className="space-y-3 px-4 py-3">
        <ConditionList conditions={gateConditions(gate)} />
        {mayCreate && (
          <div className="space-y-1.5">
            <button
              type="button"
              disabled={!gate.can_open || mutation.isPending}
              onClick={() => mutation.mutate()}
              data-testid="create-case"
              className={cn(
                "inline-flex items-center gap-2 rounded px-3 py-1.5 text-[12.5px] font-medium",
                gate.can_open && !mutation.isPending
                  ? "bg-primary text-primary-foreground hover:opacity-90"
                  : "cursor-not-allowed border border-border text-muted-foreground",
              )}
            >
              {mutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
              {mutation.isPending ? t("assessment.creating") : t("assessment.create")}
            </button>
            <p className="text-[11.5px] text-muted-foreground">{t("assessment.createHelp")}</p>
            {mutation.isError && (
              <p className="text-[12px] text-destructive" data-testid="create-case-error">
                {t("assessment.error.failed")}
              </p>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
