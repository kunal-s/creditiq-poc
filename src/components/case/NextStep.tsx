import { Link } from "@tanstack/react-router";
import { ArrowRight, Lock } from "lucide-react";
import type { CaseDetail, CaseProgress } from "@/api/types";
import { caseTabPath, nextStepOf, type CaseTab } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { caseCreated, stageDetail } from "@/domain/progress";
import { useSession } from "@/domain/session";

// The way on from every step (one bar, the same on each): where this step stands, in one line from
// the engine's progress, and the next step in the case's order. Before the case is created,
// Document readiness points at creating it instead; the Overview leaves the way on to its case
// progress. The last step leads to the Memo Library. It sits
// at the end of the step's content, so nothing moves when a page loads.
//
// Test ids: next-step (data-step, the open step), next-step-state, next-step-link (data-to),
// next-step-locked.

export function NextStepBar({
  c,
  progress,
  active,
}: {
  c: CaseDetail;
  progress: CaseProgress | undefined;
  active: CaseTab | undefined;
}) {
  const permissions = useSession()?.user.permissions ?? [];
  if (!active || active.key === "comparison") return null;
  // The Overview's case progress names the next thing to do itself.
  if (active.key === "overview") return null;
  const stage = active.stage ? progress?.stages.find((s) => s.key === active.stage) : undefined;
  const next = nextStepOf(active.key);
  const createFirst = active.key === "completeness" && progress && !caseCreated(progress);
  const link =
    "inline-flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";

  return (
    <div
      className="mx-4 mb-6 mt-2 flex flex-wrap items-center justify-between gap-3 rounded border border-border bg-surface px-4 py-3 sm:mx-6"
      data-testid="next-step"
      data-step={active.key}
    >
      <p className="min-w-0 text-[12.5px] text-muted-foreground" data-testid="next-step-state">
        <span className="font-medium text-foreground">{t(`caseTab.${active.key}`)}</span>
        {stage && <> · {stageDetail(stage)}</>}
      </p>
      {createFirst ? (
        <Link
          to="/appraisals/$caseId/completeness"
          params={{ caseId: c.id }}
          hash="readiness"
          className={link}
          data-testid="next-step-link"
          data-to="create"
        >
          {t("nextStep.createFirst")} <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      ) : next ? (
        permissions.includes(next.permission) ? (
          <Link
            to={caseTabPath(c.id, next)}
            className={link}
            data-testid="next-step-link"
            data-to={next.key}
          >
            {t("nextStep.next", { step: t(`caseTab.${next.key}`) })}{" "}
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        ) : (
          <span
            className="inline-flex h-9 cursor-not-allowed items-center gap-1.5 rounded border border-border px-3.5 text-[13px] text-muted-foreground"
            title={t("nav.lockedStep")}
            data-testid="next-step-locked"
          >
            <Lock className="size-3.5" aria-hidden />
            {t("nextStep.next", { step: t(`caseTab.${next.key}`) })}
          </span>
        )
      ) : (
        <Link to="/memos" className={link} data-testid="next-step-link" data-to="memos">
          {t("nextStep.library")} <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      )}
    </div>
  );
}
