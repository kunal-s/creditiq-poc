import { Link } from "@tanstack/react-router";
import { AlertTriangle, Check, ChevronDown, Loader2 } from "lucide-react";
import { useState } from "react";
import type { CaseProgress, StageProgress as Stage, StageStatus } from "@/api/types";
import { caseTabPath, tabForStage } from "@/components/shell/nav";
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

function StatusMark({ n, status }: { n: number; status: StageStatus }) {
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
      <span className="min-w-0">
        <span className="block truncate text-[12px] font-medium text-foreground">
          {t(`progress.stage.${stage.key}`)}
        </span>
        <span className="block truncate text-[11px] text-muted-foreground">
          {stageDetail(stage)}
        </span>
      </span>
    </>
  );
  const className = cn(
    "flex min-w-0 items-center gap-2 rounded px-2 py-1.5",
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

export function StageProgressBar({
  caseId,
  progress,
  activeStage,
}: {
  caseId: string;
  progress: CaseProgress;
  activeStage?: string | undefined;
}) {
  const permissions = useSession()?.user.permissions ?? [];
  const [open, setOpen] = useState(false);
  const stages = progress.stages;
  const current = Math.max(
    0,
    stages.findIndex((s) => s.status !== "done"),
  );
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
      {/* Phones: the current stage, with the full list on demand. */}
      <button
        type="button"
        className="flex w-full items-center gap-2 rounded border border-border bg-surface px-3 py-2 text-left md:hidden"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <StatusMark n={current + 1} status={stages[current]!.status} />
        <span className="min-w-0 flex-1">
          <span className="block text-[11px] text-muted-foreground">
            {t("progress.stageOf", { n: current + 1, total: stages.length })}
          </span>
          <span className="block truncate text-[12.5px] font-medium">
            {t(`progress.stage.${stages[current]!.key}`)}
          </span>
        </span>
        <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
      </button>
      {open && <ol className="mt-1 space-y-0.5 md:hidden">{items}</ol>}
      <ol className="hidden grid-cols-6 gap-1 md:grid">{items}</ol>
    </nav>
  );
}
