import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import type { CaseProgress } from "@/api/types";
import { Kpi, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { caseTabPath, tabForStage } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { nextStage, stageDetail, useCaseProgress } from "@/domain/progress";
import { useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The case Overview (FRD §6): where the case is, what needs a person next,
// and the counts behind each stage. It updates while processing runs.

export const Route = createFileRoute("/cases/$caseId/")({
  head: () => ({
    meta: [{ title: `${t("caseTab.overview")} — ${t("tenant.product.name")}` }],
  }),
  component: OverviewTab,
});

function OverviewTab() {
  const { caseId } = Route.useParams();
  const progress = useCaseProgress(caseId);
  return (
    <div className="px-4 py-5 sm:px-6">
      <QueryView query={progress}>
        {(p) => (
          <CaseScreen caseId={caseId}>
            {(c) => <Overview progress={p} openReview={c.open_review_items} />}
          </CaseScreen>
        )}
      </QueryView>
    </div>
  );
}

function Overview({ progress, openReview }: { progress: CaseProgress; openReview: number }) {
  const permissions = useSession()?.user.permissions ?? [];
  const canOpen = (key: CaseProgress["stages"][number]["key"]) =>
    permissions.includes(tabForStage(key).permission);
  const stage = (key: string) => progress.stages.find((s) => s.key === key)!;
  const docs = stage("documents");
  const completeness = stage("completeness");
  const next = nextStage(progress);

  return (
    <div className="space-y-4">
      <NextAction progress={progress} canOpen={canOpen} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label={t("progress.stage.documents")}
          value={docs.total ? `${docs.done}/${docs.total}` : "—"}
          note={stageDetail(docs)}
          {...(docs.status === "needs_attention" && { tone: "flag" as const })}
          testId="kpi-documents"
        />
        <Kpi
          label={t("page.home.counter.review")}
          value={openReview}
          note={t("page.home.counter.reviewSub")}
          {...(openReview > 0 && { tone: "flag" as const })}
          testId="kpi-review"
        />
        <Kpi
          label={t("progress.stage.completeness")}
          value={`${completeness.done}/${completeness.total}`}
          note={stageDetail(completeness)}
          tone={completeness.attention ? "critical" : "positive"}
          testId="kpi-completeness"
        />
        <Kpi
          label={t("term.stage")}
          value={t(`stage.${progress.stage.toLowerCase()}`)}
          note={next ? t(`progress.status.${next.status}`) : t("progress.status.done")}
          testId="kpi-stage"
        />
      </div>

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
                <span className="block text-[11.5px] text-muted-foreground">{stageDetail(s)}</span>
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
    </div>
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

/** One line saying what to do next, with the way there. */
function NextAction({
  progress,
  canOpen,
}: {
  progress: CaseProgress;
  canOpen: (key: CaseProgress["stages"][number]["key"]) => boolean;
}) {
  const docs = progress.stages[0]!;
  const next = nextStage(progress);
  let text: string;
  let to: string | undefined;
  if (docs.status === "not_started") {
    text = t("page.overview.nextUpload");
    to = caseTabPath(progress.case_id, tabForStage("documents"));
  } else if (next) {
    text = `${t(`progress.stage.${next.key}`)}: ${stageDetail(next)}`;
    to = canOpen(next.key) ? caseTabPath(progress.case_id, tabForStage(next.key)) : undefined;
  } else {
    text = t("page.overview.nextNone");
  }
  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded border border-primary/30 bg-surface px-4 py-3"
      data-testid="next-action"
    >
      <span className="field-label">{t("page.overview.next")}</span>
      <span className="min-w-0 flex-1 text-[13px] text-foreground">{text}</span>
      {to && (
        <Link
          to={to}
          className="inline-flex items-center gap-1 text-[12.5px] font-medium text-primary hover:underline"
        >
          {t("page.overview.open")} <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      )}
    </div>
  );
}
