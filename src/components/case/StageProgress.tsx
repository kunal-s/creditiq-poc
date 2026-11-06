import { Link } from "@tanstack/react-router";
import { AlertTriangle, Check, Loader2 } from "lucide-react";
import type { CaseProgress, StageProgress as Stage, StageStatus } from "@/api/types";
import { CASE_TABS, caseTabPath, tabForStage } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { stageDetail } from "@/domain/progress";
import { useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The six processing stages in order (FRD §6), each with its own status.
// A stage the role may not open shows its status but is not a link.

const MARK: Record<StageStatus, string> = {
  not_started: "border-border bg-surface text-muted-foreground",
  in_progress: "border-info/50 bg-info-soft text-info",
  needs_attention: "border-flag/50 bg-flag-soft text-flag-foreground",
  done: "border-positive/50 bg-positive-soft text-positive",
};

export function StatusMark({ n, status }: { n: number; status: StageStatus }) {
  return (
    <span
      className={cn(
        "grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[11px] font-semibold tabular",
        MARK[status],
      )}
      aria-hidden
    >
      {status === "done" ? (
        <Check className="h-3.5 w-3.5" />
      ) : status === "in_progress" ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : status === "needs_attention" ? (
        <AlertTriangle className="h-3 w-3" />
      ) : (
        n
      )}
    </span>
  );
}

function StageItem({
  caseId,
  stage,
  n,
  active,
  canOpen,
}: {
  caseId: string;
  stage: Stage;
  n: number;
  active: boolean;
  canOpen: boolean;
}) {
  const body = (
    <>
      <StatusMark n={n} status={stage.status} />
      {/* The stage's name in full, over two lines where the strip is narrow; its detail in one
          line, whole on hover. */}
      <span className="min-w-0">
        <span className="line-clamp-2 block text-[12px] font-medium leading-snug text-foreground">
          {t(`progress.stage.${stage.key}`)}
        </span>
        <span
          className="block truncate text-[11px] text-muted-foreground"
          title={stageDetail(stage)}
        >
          {stageDetail(stage)}
        </span>
      </span>
    </>
  );
  const className = cn(
    "flex min-w-0 items-start gap-2 rounded px-2 py-1.5",
    active && "bg-muted",
    canOpen && "transition-colors hover:bg-muted",
  );
  return canOpen ? (
    <Link
      to={caseTabPath(caseId, tabForStage(stage.key))}
      className={className}
      data-testid={`stage-${stage.key}`}
      data-status={stage.status}
    >
      {body}
    </Link>
  ) : (
    <div className={className} data-testid={`stage-${stage.key}`} data-status={stage.status}>
      {body}
    </div>
  );
}

const PILL_TONE: Record<StageStatus, string> = {
  done: "bg-positive-soft text-positive",
  needs_attention: "bg-flag-soft text-flag-foreground",
  in_progress: "bg-info-soft text-info",
  not_started: "text-muted-foreground",
};

/** One stage as a pill: its name, coloured by where it stands; its detail on hover. */
function StagePill({
  caseId,
  stage,
  active,
  canOpen,
}: {
  caseId: string;
  stage: Stage;
  active: boolean;
  canOpen: boolean;
}) {
  const className = cn(
    "inline-flex items-center whitespace-nowrap rounded px-2 py-1 text-[11.5px] font-medium transition-colors",
    active ? "bg-primary text-primary-foreground" : PILL_TONE[stage.status],
    canOpen && !active && "hover:bg-muted hover:text-foreground",
  );
  // The step's short name, as in the side menu; the stage's full name and detail on hover.
  const label = t(`caseTab.${tabForStage(stage.key).key}`);
  const title = `${t(`progress.stage.${stage.key}`)} · ${stageDetail(stage)}`;
  return canOpen ? (
    <Link
      to={caseTabPath(caseId, tabForStage(stage.key))}
      className={className}
      title={title}
      aria-current={active ? "page" : undefined}
      data-testid={`stage-${stage.key}`}
      data-status={stage.status}
    >
      {label}
    </Link>
  ) : (
    <span
      className={className}
      title={title}
      data-testid={`stage-${stage.key}`}
      data-status={stage.status}
    >
      {label}
    </span>
  );
}

export function StageProgressBar({
  caseId,
  progress,
  activeStage,
  onOverview = false,
}: {
  caseId: string;
  progress: CaseProgress;
  activeStage?: string | undefined;
  /** The Overview is open: its pill, first in the row, is the dark one. */
  onOverview?: boolean;
}) {
  const permissions = useSession()?.user.permissions ?? [];
  const stages = progress.stages;
  const items = stages.map((stage, i) => (
    <li key={stage.key} className="min-w-0">
      <StageItem
        caseId={caseId}
        stage={stage}
        n={i + 1}
        active={activeStage === stage.key}
        canOpen={permissions.includes(tabForStage(stage.key).permission)}
      />
    </li>
  ));

  return (
    <nav aria-label={t("progress.label")} data-testid="stage-progress">
      {/* A pill a stage, as the original design: done tinted, the open one dark. */}
      <ol className="flex flex-wrap items-center gap-1 md:justify-end">
        {/* The way back to the Overview from any step. */}
        <li>
          <Link
            to={caseTabPath(caseId, CASE_TABS[0]!)}
            // Every step's path starts with the Overview's: only the Overview itself is current.
            activeOptions={{ exact: true }}
            className={cn(
              "inline-flex items-center whitespace-nowrap rounded px-2 py-1 text-[11.5px] font-medium transition-colors",
              onOverview ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-muted",
            )}
            aria-current={onOverview ? "page" : undefined}
            data-testid="stage-overview"
          >
            {t("caseTab.overview")}
          </Link>
        </li>
        {stages.map((stage) => (
          <li key={stage.key}>
            <StagePill
              caseId={caseId}
              stage={stage}
              active={activeStage === stage.key}
              canOpen={permissions.includes(tabForStage(stage.key).permission)}
            />
          </li>
        ))}
      </ol>
    </nav>
  );
}
