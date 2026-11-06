import { createFileRoute, Link } from "@tanstack/react-router";
import type { CaseProgress } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { reviewItemPath } from "@/components/review/reviewLinks";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { caseTabPath, tabForStage } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { StepHeader } from "@/components/case/TabSection";
import { DocumentChecklist } from "@/components/case/DocumentChecklist";
import { stepKicker } from "@/domain/steps";
import { stageDetail, useCaseProgress } from "@/domain/progress";
import { useReviewQueue } from "@/domain/review";
import { useCan, useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The case Overview (FRD §6): where the case is, what needs a person next,
// and the counts behind each stage. It updates while processing runs.

export const Route = createFileRoute("/appraisals/$caseId/")({
  head: () => ({
    meta: [{ title: `${t("caseTab.overview")} — ${t("tenant.product.name")}` }],
  }),
  component: OverviewTab,
});

function OverviewTab() {
  const { caseId } = Route.useParams();
  const progress = useCaseProgress(caseId);
  return (
    <>
      <StepHeader
        kicker={stepKicker(caseId, "overview")}
        title={t("page.overview.title")}
        purpose={t("page.overview.purpose")}
      />
      <div className="px-4 py-5 sm:px-6">
        <QueryView query={progress}>
          {(p) => <CaseScreen caseId={caseId}>{() => <Overview progress={p} />}</CaseScreen>}
        </QueryView>
      </div>
    </>
  );
}

function Overview({ progress }: { progress: CaseProgress }) {
  const permissions = useSession()?.user.permissions ?? [];
  const canOpen = (key: CaseProgress["stages"][number]["key"]) =>
    permissions.includes(tabForStage(key).permission);

  return (
    <div className="space-y-4">
      {/* The readiness glance (verdict, score against the gate, what blocks it, the counts, what
          to do next and what to ask the customer), then what this appraisal needs, row by row. */}
      <DocumentChecklist caseId={progress.case_id} progress={progress} canOpen={canOpen} />

      <div className="grid items-start gap-4 @min-[65rem]/main:grid-cols-[minmax(0,1fr)_380px]">
        <Panel title={t("progress.label")} testId="overview-stages">
          <ol className="divide-y divide-border">
            {progress.stages.map((s, i) => (
              <li key={s.key} className="flex items-center gap-3 px-4 py-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-border text-[11px] font-semibold tabular text-muted-foreground">
                  {i + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium">
                    {t(`progress.stage.${s.key}`)}
                  </span>
                  <span className="block text-[11.5px] text-muted-foreground">
                    {stageDetail(s)}
                  </span>
                </span>
                <StatusChip status={s.status} />
                {canOpen(s.key) && s.status !== "not_started" && (
                  <Link
                    to={caseTabPath(progress.case_id, tabForStage(s.key))}
                    className="text-[12px] font-medium text-primary hover:underline"
                  >
                    {t("page.overview.open")}
                  </Link>
                )}
              </li>
            ))}
          </ol>
        </Panel>
        <div className="min-w-0 space-y-4">
          <WaitingForDecision caseId={progress.case_id} />
        </div>
      </div>
    </div>
  );
}

const MAX_LIST = 6;

/** This appraisal's open review items, each linked to where it is decided. */
function WaitingForDecision({ caseId }: { caseId: string }) {
  const canReview = useCan("review.read");
  const review = useReviewQueue({ caseId });
  if (!canReview) return null;
  const items = (review.data ?? []).filter((i) => i.status === "open");
  return (
    <Panel
      title={t("page.overview.waiting")}
      subtitle={review.data ? t("page.overview.waitingCount", { n: items.length }) : undefined}
      testId="waiting-decision"
    >
      {items.length === 0 ? (
        <p className="px-4 py-4 text-[12.5px] text-muted-foreground">
          {review.data ? t("page.home.attentionEmpty") : t("state.loading")}
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {items.slice(0, MAX_LIST).map((item) => (
            <li key={item.id}>
              <Link
                to={reviewItemPath(item.kind, caseId)}
                className="block px-4 py-2 hover:bg-surface-muted"
              >
                <span className="block text-[12.5px] font-medium">
                  {t(`reviewKind.${item.kind}`)}
                </span>
                <span className="block break-words text-[11.5px] text-muted-foreground">
                  {item.summary}
                </span>
              </Link>
            </li>
          ))}
          {items.length > MAX_LIST && (
            <li className="px-4 py-2 text-[11.5px]">
              <Link to="/review" className="font-medium text-primary hover:underline">
                {t("page.overview.more", { n: items.length - MAX_LIST })}
              </Link>
            </li>
          )}
        </ul>
      )}
    </Panel>
  );
}

const CHIP = {
  not_started: "bg-muted text-muted-foreground",
  in_progress: "bg-info-soft text-info",
  needs_attention: "bg-flag-soft text-flag-foreground",
  done: "bg-positive-soft text-positive",
} as const;

function StatusChip({ status }: { status: keyof typeof CHIP }) {
  return (
    <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium", CHIP[status])}>
      {t(`progress.status.${status}`)}
    </span>
  );
}
