import { createFileRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { AlertTriangle, ArrowRight, ShieldCheck } from "lucide-react";
import type { CaseDetail, Stage } from "@/api/types";
import { CaseAssistant } from "@/components/case/CaseAssistant";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { DeleteCaseButton } from "@/components/cases/DeleteCaseButton";
import { StageProgressBar } from "@/components/case/StageProgress";
import { CASE_TABS, caseTabPath } from "@/components/shell/nav";
import { ScoreBar } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { formatInr, stageLabel, useLabels } from "@/domain/cases";
import { readinessBreakdown, readyForCredit, scoreText, useChecklist } from "@/domain/checklist";
import { useCaseProgress } from "@/domain/progress";
import { useCan, useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The case workspace (FRD §6): one header and the six processing stages.
// The side menu holds the case's steps; every step renders into the outlet.

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
  const activeTab = CASE_TABS.filter((tab) => permissions.includes(tab.permission)).find(
    (tab) => decodeURIComponent(caseTabPath(c.id, tab)) === pathname,
  );

  return (
    <div>
      <div className="border-b border-border bg-surface px-4 py-3 sm:px-6">
        <CaseHeader
          c={c}
          stage={progress.data?.stage ?? c.stage}
          stagesBar={
            progress.data && (
              <StageProgressBar
                caseId={c.id}
                progress={progress.data}
                activeStage={activeTab?.stage}
                onOverview={activeTab?.key === "overview"}
              />
            )
          }
        />
      </div>

      <Outlet />
      <CaseAssistant caseId={c.id} borrower={c.borrower} />
    </div>
  );
}

/** The case header: one card. What the case is and who it is for; the borrower; its identifiers
 * and who holds it; then readiness, the ask and the bank stage, and what stops it. */
function CaseHeader({ c }: { c: CaseDetail }) {
  const labels = useLabels();
  const checklist = useChecklist(c.id);
  const canReview = useCan("review.read");
  const r = checklist.data;
  const b = r ? readinessBreakdown(r.items) : undefined;
  const ids: [string, string | null | undefined][] = [
    [t("identifier.pan"), c.pan],
    [t("identifier.gstin"), c.gstin],
    [t("identifier.udyam"), c.udyam],
  ];

  return (
    <div
      className="relative rounded border border-border border-l-2 border-l-primary bg-surface px-5 py-4"
      data-testid="case-header"
    >
      <div className="min-w-0 max-w-full">
        <h1 className="break-words text-[15px] font-semibold tracking-tight text-foreground">
          {c.borrower}
        </h1>
        <div className="tabular mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
          <span>{labels.constitution(c.constitution)}</span>
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
          <span>{c.id}</span>
        </div>
      </div>

      <div className="flex min-w-0 flex-col items-end gap-2.5 max-md:w-full max-md:items-stretch">
        {stagesBar}
        <div className="flex flex-wrap items-end justify-end gap-x-5 gap-y-2 max-md:justify-start">
          {/* Document readiness as every screen says it: satisfied of all; the weighted score the
              review gate uses under it. */}
          <div className="w-48" data-testid="header-readiness">
            <div className="flex items-baseline justify-between gap-2">
              <span className="field-label">{t("caseHeader.readiness")}</span>
              <span
                className="tabular text-[12.5px] font-semibold leading-none text-foreground"
                data-testid="header-readiness-count"
              >
                {b ? t("journey.readiness.ofTotal", { n: b.satisfied, total: b.total }) : "—"}
              </span>
            </div>
            <ScoreBar
              className="mt-1"
              score={r?.score_pct ?? 0}
              gate={r?.gate_pct ?? 100}
              blocking={r?.blocking_open ?? 0}
            />
            <p
              className="tabular mt-0.5 text-[10.5px] text-muted-foreground"
              data-testid="header-readiness-score"
            >
              {r
                ? t("caseHeader.outstandingGate", {
                    score: scoreText(r.score_pct, r.gate_pct),
                    gate: Math.round(r.gate_pct),
                  })
                : checklist.isError
                  ? t("caseHeader.readinessUnavailable")
                  : t("state.loading")}
            {r?.provisional && ` · ${t("checklist.provisional")}`}
          </p>
        </div>
        <span className="hidden h-10 w-px bg-border sm:block" aria-hidden />
        <Fact label={t("caseHeader.ask")}>
          {labels.facilities(c.facilities)} · {formatInr(c.amount_inr)}
        </Fact>
        <Fact label={t("caseHeader.bankStage")} testId="header-bank-stage">
          {labels.bankStage(c.bank_stage)}
        </Fact>
        <div className="flex flex-wrap items-center gap-2">
          {r && r.blocking_open > 0 ? (
            <Link
              to="/appraisals/$caseId/completeness"
              params={{ caseId: c.id }}
              hash="checklist"
              className="rounded border border-destructive/25 bg-critical-soft/60 px-2 py-1 text-[11.5px] font-medium text-critical-text"
              data-testid="header-blocking"
            >
              {t("caseHeader.blockingGaps", { n: r.blocking_open })}
              <ArrowRight className="ml-0.5 inline h-3 w-3" />
            </Link>
          ) : r && readyForCredit(r) ? (
            <span
              className="inline-flex items-center gap-1 rounded border border-positive/40 bg-positive-soft px-2 py-1 text-[12px] font-medium text-positive"
              data-testid="header-ready"
            >
              <ShieldCheck className="h-3 w-3" /> {t("readinessGates.readyForCredit")}
            </span>
          ) : null}
          {c.open_review_items > 0 && canReview && (
            <Link
              to="/review"
              className="text-[12px] font-medium text-flag-foreground hover:underline"
            >
              {t("cases.reviewOpen", { n: c.open_review_items })}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

/** A fact in the header: its name small above, its value below. */
function Fact({
  label,
  testId,
  children,
}: {
  label: string;
  testId?: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <span className="field-label block">{label}</span>
      <span className="tabular block text-[12.5px] text-foreground" data-testid={testId}>
        {children}
      </span>
    </div>
  );
}
