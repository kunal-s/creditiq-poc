import { Link } from "@tanstack/react-router";
import { Lock } from "lucide-react";
import type { StageStatus } from "@/api/types";
import { CASE_TABS, caseTabPath } from "./nav";
import { t } from "@/config/terminology";
import { useCaseProgress } from "@/domain/progress";
import { cn } from "@/lib/utils";

// The open appraisal in the side menu, under New appraisal: its number, leading to its Overview,
// with a dot for where it stands. Its steps are the tab strip under the case header.

const DOT: Record<StageStatus, string> = {
  not_started: "bg-sidebar-foreground/25",
  in_progress: "bg-info",
  needs_attention: "bg-flag",
  done: "bg-positive",
};

function Row({
  to,
  label,
  active,
  status,
  locked,
  onNavigate,
}: {
  to: string;
  label: string;
  active: boolean;
  status?: StageStatus | undefined;
  /** The role may not open this step: listed, so the process reads whole, but not a link. */
  locked?: boolean;
  onNavigate?: (() => void) | undefined;
}) {
  const dot = status && (
    <span
      className={cn("h-1.5 w-1.5 shrink-0 rounded-full", DOT[status])}
      data-status={status}
      aria-hidden
    />
  );
  if (locked) {
    return (
      <span
        className="ml-3 flex cursor-not-allowed items-center gap-2 rounded px-2 py-1.5 text-[13px] text-sidebar-foreground/40"
        title={t("nav.lockedStep")}
        aria-disabled="true"
        data-locked="true"
      >
        <Lock className="h-3 w-3 shrink-0" aria-hidden />
        <span className="truncate">{label}</span>
      </span>
    );
  }
  return (
    <Link
      to={to}
      onClick={onNavigate}
      className={cn(
        "ml-3 flex items-center gap-2 rounded px-2 py-1.5 text-[13px] transition-colors",
        active
          ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
          : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
      )}
    >
      {dot}
      <span className="truncate">{label}</span>
    </Link>
  );
}

export function CaseNav({
  caseId,
  pathname,
  onNavigate,
}: {
  caseId: string;
  pathname: string;
  onNavigate?: (() => void) | undefined;
}) {
  const overview = CASE_TABS[0]!;
  const progress = useCaseProgress(caseId);
  // One dot for the case: amber while any step waits on a person, blue while one runs.
  const status: StageStatus = progress.data?.stages.some((s) => s.status === "needs_attention")
    ? "needs_attention"
    : progress.data?.stages.some((s) => s.status === "in_progress")
      ? "in_progress"
      : "done";
  return (
    <div className="mt-1" data-testid="case-nav">
      <Row
        to={caseTabPath(caseId, overview)}
        label={t("nav.group.thisCase", { id: caseId })}
        active={decodeURIComponent(pathname).startsWith(
          decodeURIComponent(caseTabPath(caseId, overview)),
        )}
        status={progress.data ? status : undefined}
        onNavigate={onNavigate}
      />
    </div>
  );
}
