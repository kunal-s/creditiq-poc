import { Link } from "@tanstack/react-router";
import { Lock } from "lucide-react";
import type { StageStatus } from "@/api/types";
import { CASE_TABS, caseTabPath, type CaseTab } from "./nav";
import { t } from "@/config/terminology";
import { useCaseProgress } from "@/domain/progress";
import { useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The open appraisal's own steps in the side menu, under New appraisal as in the original design:
// each step with a dot for where its stage stands. Shown only inside a case.

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

/** The case's steps in the side menu: the first and last are listed alone, the six processing
 * steps in two groups. A grouped step is always listed; one the role may not open is locked. */
const LAYOUT: { group: string | null; keys: string[]; always: boolean }[] = [
  { group: null, keys: ["overview", "identity"], always: false },
  { group: "documents", keys: ["documents", "extraction", "completeness"], always: true },
  { group: "assessment", keys: ["crossVerification", "policy", "outputs"], always: true },
  { group: null, keys: ["rating", "submission", "comparison"], always: false },
];

export function CaseNav({
  caseId,
  pathname,
  onNavigate,
}: {
  caseId: string;
  pathname: string;
  onNavigate?: (() => void) | undefined;
}) {
  const permissions = useSession()?.user.permissions ?? [];
  const progress = useCaseProgress(caseId);
  const statusOf = (tab: CaseTab) =>
    tab.stage ? progress.data?.stages.find((s) => s.key === tab.stage)?.status : undefined;
  const isActive = (tab: CaseTab) =>
    decodeURIComponent(pathname) === decodeURIComponent(caseTabPath(caseId, tab));
  const can = (tab: CaseTab) => permissions.includes(tab.permission);

  return (
    <div className="mt-1" data-testid="case-nav">
      <p className="truncate px-2 pb-1 pl-5 text-[10.5px] text-sidebar-foreground/50">
        {t("nav.group.thisCase", { id: caseId })}
      </p>
      {LAYOUT.map((block, i) => {
        const tabs = block.keys
          .map((key) => CASE_TABS.find((tab) => tab.key === key)!)
          .filter((tab) => block.always || can(tab));
        if (tabs.length === 0) return null;
        return (
          <div key={block.group ?? `block-${i}`} className={cn(block.group && "mt-2")}>
            {block.group && (
              <p
                className="px-2 pb-1 pl-5 text-[10px] font-semibold uppercase tracking-[0.08em] text-sidebar-foreground/45"
                data-testid={`case-nav-group-${block.group}`}
              >
                {t(`nav.caseGroup.${block.group}`)}
              </p>
            )}
            <ul className="space-y-px">
              {tabs.map((tab) => (
                <li key={tab.key}>
                  <Row
                    to={caseTabPath(caseId, tab)}
                    label={t(`caseTab.${tab.key}`)}
                    active={isActive(tab)}
                    status={statusOf(tab) ?? "not_started"}
                    locked={!can(tab)}
                    onNavigate={onNavigate}
                  />
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
