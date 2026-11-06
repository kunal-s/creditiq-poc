import { Loader2, ShieldCheck } from "lucide-react";
import type { AssessmentGate } from "@/api/types";
import { t } from "@/config/terminology";
import { useOpenAssessment } from "@/domain/cases";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { gateConditions } from "./conditions";

/** Creating the case (F-13 gate), at the head of the required document set: how many of the
 * gate's conditions are met and, for a role holding `review.decide`, the action, which stays shut
 * until every one is; its hover names those still unmet. Once created, the day it was. */
export function CreateCaseAction({
  caseId,
  gate,
}: {
  caseId: string;
  /** The case-creation gate, once the engine has worked it out. */
  gate: AssessmentGate | null;
}) {
  const mutation = useOpenAssessment(caseId);
  const mayCreate = useCan("review.decide");
  if (!gate) return null;
  if (gate.open) {
    return gate.opened_at ? (
      <span
        className="inline-flex items-center gap-1 text-[12px] font-medium text-primary"
        data-testid="assessment-created"
      >
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
        {t("assessment.created", { at: gate.opened_at.slice(0, 10) })}
      </span>
    ) : null;
  }

  const conditions = gateConditions(gate);
  const met = conditions.filter((c) => c.met).length;
  const unmet = conditions
    .filter((c) => !c.met)
    .map((c) => c.label)
    .join("; ");
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <span
        className="flex items-center gap-2"
        title={unmet || undefined}
        data-testid="gate-progress"
      >
        <span className="flex gap-1" aria-hidden>
          {conditions.map((c) => (
            <span
              key={c.key}
              className={cn("h-1.5 w-5 rounded-full", c.met ? "bg-primary" : "bg-border")}
            />
          ))}
        </span>
        <span className="text-[12px] text-muted-foreground">
          {t("assessment.conditionsMet", { met, total: conditions.length })}
        </span>
      </span>
      {mayCreate && (
        <button
          type="button"
          disabled={!gate.can_open || mutation.isPending}
          onClick={() => mutation.mutate()}
          title={
            gate.can_open ? t("assessment.createHelp") : `${t("assessment.createBlocked")} ${unmet}`
          }
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
      )}
      {mutation.isError && (
        <span className="text-[12px] text-destructive" data-testid="create-case-error">
          {t("assessment.error.failed")}
        </span>
      )}
    </span>
  );
}
