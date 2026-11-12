import { Link } from "@tanstack/react-router";
import { Lock } from "lucide-react";
import type { CaseProgress, StageProgress as Stage, StageStatus } from "@/api/types";
import { CASE_TABS, STEP_GROUPS, caseTabPath, type CaseTab } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { stageDetail } from "@/domain/progress";
import { useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The case's steps as one tab strip (FRD §6). A step the role may not open is listed, locked.

const DOT_TONE: Partial<Record<StageStatus, string>> = {
  needs_attention: "bg-flag",
  in_progress: "bg-info",
};

/** One step as a tab: its short name, underlined when open; a dot when its stage needs a person or
 * is running; its full name and detail on hover. A step the role may not open is listed, locked. */
function StepTab({
  caseId,
  tab,
  stage,
  active,
  canOpen,
}: {
  caseId: string;
  tab: CaseTab;
  stage: Stage | undefined;
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
  const label = t(`caseTab.${tab.key}`);
  const title = !canOpen
    ? t("nav.lockedStep")
    : stage
      ? `${t(`progress.stage.${stage.key}`)} · ${stageDetail(stage)}`
      : undefined;
  const dot = canOpen && stage ? DOT_TONE[stage.status] : undefined;
  const testId = `stage-${stage?.key ?? tab.key}`;
  const body = (
    <>
      {!canOpen && <Lock className="h-3 w-3" aria-hidden />}
      {label}
      {dot && <span className={cn("h-1.5 w-1.5 rounded-full", dot)} aria-hidden />}
    </>
  );
  return canOpen ? (
    <Link
      to={caseTabPath(caseId, tab)}
      // Every step's path starts with the Overview's: only the Overview itself is current there.
      activeOptions={{ exact: true }}
      className={className}
      title={title}
      aria-current={active ? "page" : undefined}
      data-testid={testId}
      data-status={stage?.status}
    >
      {body}
    </Link>
  ) : (
    <span
      className={className}
      title={title}
      aria-disabled="true"
      data-testid={testId}
      data-status={stage?.status}
    >
      {body}
    </span>
  );
}

/** The case's one list of steps (FRD §6): every step in the order a case moves through them, in
 * three groups divided by a rule, each named for assistive technology. It scrolls inside its own
 * box where the screen is narrow; the page never does. */
export function StageProgressBar({
  caseId,
  progress,
  activeKey,
}: {
  caseId: string;
  progress: CaseProgress;
  /** The open step's tab key. */
  activeKey?: string | undefined;
}) {
  const permissions = useSession()?.user.permissions ?? [];
  return (
    <nav aria-label={t("progress.label")} data-testid="stage-progress">
      <ol className="flex items-center gap-5 overflow-x-auto">
        {STEP_GROUPS.map((group, g) => {
          const tabs = group.keys
            .map((k) => CASE_TABS.find((tab) => tab.key === k)!)
            // Comparison is a tool for the role that adjudicates it, not a step every role sees.
            .filter((tab) => tab.key !== "comparison" || permissions.includes(tab.permission));
          return (
            <li
              key={group.id}
              className="flex items-center gap-5"
              data-testid={`step-group-${group.id}`}
            >
              {g > 0 && <span className="h-4 w-px shrink-0 bg-border" aria-hidden />}
              <ul className="flex items-center gap-5" aria-label={t(`nav.stepGroup.${group.id}`)}>
                {tabs.map((tab) => (
                  <li key={tab.key}>
                    <StepTab
                      caseId={caseId}
                      tab={tab}
                      stage={
                        tab.stage ? progress.stages.find((s) => s.key === tab.stage) : undefined
                      }
                      active={activeKey === tab.key}
                      canOpen={permissions.includes(tab.permission)}
                    />
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
