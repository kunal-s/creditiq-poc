import { createFileRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { AlertTriangle, ArrowRight, ShieldCheck } from "lucide-react";
import type { CaseDetail, Stage } from "@/api/types";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { DeleteCaseButton } from "@/components/cases/DeleteCaseButton";
import { StageProgressBar } from "@/components/case/StageProgress";
import { CASE_TABS, caseTabPath } from "@/components/shell/nav";
import { ScoreBar } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { formatInr, stageLabel, useLabels } from "@/domain/cases";
import { countItems, readyForCredit, useChecklist } from "@/domain/checklist";
import { useCaseProgress } from "@/domain/progress";
import { useCan, useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The case workspace (FRD §6): one header, the six processing stages, and
// the tabs in processing order. Every tab renders into the outlet.

export const Route = createFileRoute("/appraisals/$caseId")({
  component: CaseLayout,
});

function CaseLayout() {
  const { caseId } = Route.useParams();
  return <CaseScreen caseId={caseId}>{(c) => <Layout c={c} />}</CaseScreen>;
}

function Layout({ c }: { c: CaseDetail }) {
  const pathname = decodeURIComponent(useRouterState({ select: (s) => s.location.pathname }));
  const permissions = useSession()?.user.permissions ?? [];
  const progress = useCaseProgress(c.id);
  const tabs = CASE_TABS.filter((tab) => permissions.includes(tab.permission));
  const activeTab = tabs.find((tab) => decodeURIComponent(caseTabPath(c.id, tab)) === pathname);

  return (
    <div>
      <div className="border-b border-border bg-surface-muted/60 px-4 pt-4 sm:px-6">
        <CaseHeader c={c} stage={progress.data?.stage ?? c.stage} />
        {progress.data && (
          <div className="mt-3">
            <StageProgressBar
              caseId={c.id}
              progress={progress.data}
              activeStage={activeTab?.stage}
            />
          </div>
        )}
        <nav className="-mb-px mt-3 flex gap-4 overflow-x-auto" aria-label={t("caseHeader.tabs")}>
          {tabs.map((tab) => {
            const to = caseTabPath(c.id, tab);
            return (
              <Link
                key={tab.key}
                to={to}
                data-testid={`tab-${tab.key}`}
                className={cn(
                  "shrink-0 border-b-2 pb-2 text-[12.5px] font-medium transition-colors",
                  tab === activeTab
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                )}
              >
                {t(`caseTab.${tab.key}`)}
              </Link>
            );
          })}
        </nav>
      </div>

      <Outlet />
    </div>
  );
}

/** The prototype's case header: who, what is asked, readiness and what needs a person. */
function CaseHeader({ c, stage }: { c: CaseDetail; stage: Stage }) {
  const labels = useLabels();
  const checklist = useChecklist(c.id);
  const canReview = useCan("review.read");
  const r = checklist.data;
  const counts = r ? countItems(r.items) : undefined;
  const ids: [string, string | null | undefined][] = [
    [t("identifier.pan"), c.pan],
    [t("identifier.gstin"), c.gstin],
    [t("identifier.udyam"), c.udyam],
  ];

  return (
    <div className="rounded-md border border-border bg-surface shadow-sm" data-testid="case-header">
      <div className="flex flex-wrap items-stretch justify-between gap-x-8 gap-y-4 border-l-2 border-primary px-4 py-3.5">
        <div className="min-w-0">
          <p className="field-label">{labels.constitution(c.constitution)}</p>
          <h1 className="break-words text-[19px] font-semibold tracking-tight text-foreground">
            {c.borrower}
          </h1>
          <div className="tabular mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
            <span>{c.id}</span>
            {ids.map(([label, value]) =>
              value ? (
                <span key={label} className="contents">
                  <span className="text-border">|</span>
                  <span>
                    {label} {value}
                  </span>
                </span>
              ) : null,
            )}
            <span className="text-border">|</span>
            <span>{c.rm}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="min-w-[168px]" data-testid="header-readiness">
            <div className="flex items-baseline justify-between gap-3">
              <span className="field-label">{t("caseHeader.readiness")}</span>
              <span className="tabular text-[15px] font-semibold leading-none text-foreground">
                {r ? `${Math.round(r.score_pct)}%` : "—"}
              </span>
            </div>
            <ScoreBar
              className="mt-1.5"
              score={r?.score_pct ?? 0}
              gate={r?.gate_pct ?? 100}
              blocking={r?.blocking_open ?? 0}
            />
            <p className="tabular mt-1 text-[11px] text-muted-foreground">
              {r && counts
                ? t("caseHeader.outstandingGate", {
                    n: counts.outstanding,
                    gate: Math.round(r.gate_pct),
                  })
                : checklist.isError
                  ? t("caseHeader.readinessUnavailable")
                  : t("state.loading")}
              {r?.provisional && ` · ${t("checklist.provisional")}`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-border sm:border-l sm:pl-6">
            <div>
              <span className="field-label block">{t("caseHeader.ask")}</span>
              <span className="tabular text-[12.5px] text-foreground">
                {labels.facilities(c.facilities)} · {formatInr(c.amount_inr)}
              </span>
            </div>
            <div>
              <span className="field-label block">{t("term.stage")}</span>
              <span className="text-[12.5px] text-foreground" data-testid="header-stage">
                {stageLabel(stage)}
              </span>
            </div>
          </div>

          {r && r.blocking_open > 0 ? (
            <Link
              to="/appraisals/$caseId/completeness"
              params={{ caseId: c.id }}
              hash="readiness"
              className="rounded border border-destructive/35 bg-destructive/10 px-2.5 py-1.5 text-[11.5px] font-medium text-destructive"
              data-testid="header-blocking"
            >
              {t("caseHeader.blockingGaps", { n: r.blocking_open })}
              <ArrowRight className="ml-0.5 inline h-3 w-3" />
            </Link>
          ) : r && readyForCredit(r) ? (
            <span
              className="inline-flex items-center gap-1 rounded border border-positive/40 bg-positive-soft px-2.5 py-1.5 text-[11.5px] font-medium text-positive"
              data-testid="header-ready"
            >
              <ShieldCheck className="h-3 w-3" /> {t("readinessGates.readyForCredit")}
            </span>
          ) : null}
          {c.open_review_items > 0 && canReview && (
            <Link
              to="/review"
              className="inline-flex items-center gap-1 rounded border border-flag/40 bg-flag-soft px-2.5 py-1.5 text-[11.5px] font-medium text-flag-foreground"
            >
              <AlertTriangle className="h-3 w-3" />
              {t("cases.reviewOpen", { n: c.open_review_items })}
            </Link>
          )}
          <DeleteCaseButton caseId={c.id} borrower={c.borrower} />
        </div>
      </div>
    </div>
  );
}
