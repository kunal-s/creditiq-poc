import { Link } from "@tanstack/react-router";
import type { StageStatus } from "@/api/types";
import { caseTabPath, topTabs, type CaseTab } from "./nav";
import { t } from "@/config/terminology";
import { useCaseProgress } from "@/domain/progress";
import { useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The open appraisal's own steps in the side menu: its two flows with their
// sub-tabs and where each stands. Shown only inside a case.

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
  indent,
  onNavigate,
}: {
  to: string;
  label: string;
  active: boolean;
  status?: StageStatus | undefined;
  indent?: boolean;
  onNavigate?: (() => void) | undefined;
}) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      className={cn(
        "flex items-center gap-2 rounded px-2 py-1.5 text-[13px] transition-colors",
        indent && "ml-3",
        active
          ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
          : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
      )}
    >
      {status && (
        <span
          className={cn("h-1.5 w-1.5 shrink-0 rounded-full", DOT[status])}
          data-status={status}
          aria-hidden
        />
      )}
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
  const permissions = useSession()?.user.permissions ?? [];
  const progress = useCaseProgress(caseId);
  const statusOf = (tab: CaseTab) =>
    tab.stage ? progress.data?.stages.find((s) => s.key === tab.stage)?.status : undefined;
  const isActive = (tab: CaseTab) =>
    decodeURIComponent(pathname) === decodeURIComponent(caseTabPath(caseId, tab));

  return (
    <div className="mb-4 px-2.5" data-testid="case-nav">
      <p className="truncate px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.09em] text-sidebar-foreground/45">
        {t("nav.group.thisCase", { id: caseId })}
      </p>
      <ul className="space-y-px">
        {topTabs(permissions).map((o) =>
          o.kind === "tab" ? (
            <li key={o.tab.key}>
              <Row
                to={caseTabPath(caseId, o.tab)}
                label={t(`caseTab.${o.tab.key}`)}
                active={isActive(o.tab)}
                status={statusOf(o.tab)}
                onNavigate={onNavigate}
              />
            </li>
          ) : (
            <li key={o.flow.id} className="pt-1.5">
              <p className="px-2 pb-0.5 text-[11px] font-medium text-sidebar-foreground/55">
                {t(`caseFlow.${o.flow.id}`)}
              </p>
              <ul className="space-y-px">
                {o.tabs.map((tab) => (
                  <li key={tab.key}>
                    <Row
                      to={caseTabPath(caseId, tab)}
                      label={t(`caseTab.${tab.key}`)}
                      active={isActive(tab)}
                      status={statusOf(tab)}
                      indent
                      onNavigate={onNavigate}
                    />
                  </li>
                ))}
              </ul>
            </li>
          ),
        )}
      </ul>
    </div>
  );
}
