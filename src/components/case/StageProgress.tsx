import { Link } from "@tanstack/react-router";
import { AlertTriangle, Check, Loader2, Lock } from "lucide-react";
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

const DOT_TONE: Partial<Record<StageStatus, string>> = {
  needs_attention: "bg-flag",
  in_progress: "bg-info",
};

/** One stage as a tab: its short name, underlined when open; a dot when it needs a person or is
 * running; its full name and detail on hover. */
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
    "-mb-px inline-flex items-center gap-1.5 whitespace-nowrap border-b-2 px-0.5 pb-2 pt-1 text-[12.5px] transition-colors",
    active
      ? "border-primary font-semibold text-foreground"
      : "border-transparent text-muted-foreground",
    canOpen && !active && "hover:border-border hover:text-foreground",
    !canOpen && "cursor-not-allowed text-muted-foreground/50",
  );
  const label = t(`caseTab.${tabForStage(stage.key).key}`);
  const title = canOpen
    ? `${t(`progress.stage.${stage.key}`)} · ${stageDetail(stage)}`
    : t("nav.lockedStep");
  const dot = canOpen ? DOT_TONE[stage.status] : undefined;
  const body = (
    <>
      {!canOpen && <Lock className="h-3 w-3" aria-hidden />}
      {label}
      {dot && <span className={cn("h-1.5 w-1.5 rounded-full", dot)} aria-hidden />}
    </>
  );
  return canOpen ? (
    <Link
      to={caseTabPath(caseId, tabForStage(stage.key))}
      className={className}
      title={title}
      aria-current={active ? "page" : undefined}
      data-testid={`stage-${stage.key}`}
      data-status={stage.status}
    >
      {body}
    </Link>
  ) : (
    <span
      className={className}
      title={title}
      aria-disabled="true"
      data-testid={`stage-${stage.key}`}
      data-status={stage.status}
    >
      {body}
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
  /** The Overview is open: its tab, first in the row, is the underlined one. */
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
      {/* A tab a stage: plain text, the open one underlined; the Overview first, the way back to it
          from any step. */}
      <ol className="flex items-center gap-5 overflow-x-auto">
        <li>
          <Link
            to={caseTabPath(caseId, CASE_TABS[0]!)}
            // Every step's path starts with the Overview's: only the Overview itself is current.
            activeOptions={{ exact: true }}
            className={cn(
              "-mb-px inline-flex items-center whitespace-nowrap border-b-2 px-0.5 pb-2 pt-1 text-[12.5px] transition-colors",
              onOverview
                ? "border-primary font-semibold text-foreground"
                : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
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
