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
import { countItems, readyForCredit, scoreText, useChecklist } from "@/domain/checklist";
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

/** The case header, as the original design: who the borrower is and their identifiers on the
 * left; on the right the stages as pills, then readiness, what is asked, the stage, the RM, and
 * what needs a person. */
function CaseHeader({
  c,
  stage,
  stagesBar,
}: {
  c: CaseDetail;
  stage: Stage;
  /** The stages as pills (absent until the case's progress is read). */
  stagesBar: ReactNode;
}) {
  const labels = useLabels();
  const checklist = useChecklist(c.id);
  const canReview = useCan("review.read");
  const r = checklist.data;
  const counts = r ? countItems(r.items) : undefined;
  const ids: [string, string | null | undefined][] = [
    [t("identifier.pan"), c.pan],
    [t("identifier.gstin"), c.gstin],
    [t("identifier.udyam"), c.udyam],
    [t("identifier.applicationId"), c.application_id],
  ];

  return (
    <div
      className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3"
      data-testid="case-header"
    >
      <div className="min-w-0 max-w-full">
        <h1 className="break-words text-[15px] font-semibold tracking-tight text-foreground">
          {c.borrower}
        </h1>
        <div className="tabular mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
          <span data-testid="header-product">
            {labels.product(c.product)} · {labels.caseType(c.case_type)}
          </span>
          <span className="text-border">|</span>
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
          <div className="w-32" data-testid="header-readiness">
            <div className="flex items-baseline justify-between gap-2">
              <span className="field-label">{t("caseHeader.readiness")}</span>
              <span className="tabular text-[12.5px] font-semibold leading-none text-foreground">
                {r ? `${scoreText(r.score_pct, r.gate_pct)}%` : "—"}
              </span>
            </div>
            <ScoreBar
              className="mt-1"
              score={r?.score_pct ?? 0}
              gate={r?.gate_pct ?? 100}
              blocking={r?.blocking_open ?? 0}
            />
            <p className="sr-only">
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
          <Fact label={t("caseHeader.ask")}>
            {labels.facilities(c.facilities)} · {formatInr(c.amount_inr)}
          </Fact>
          <Fact label={t("term.stage")} testId="header-stage">
            {stageLabel(stage)}
          </Fact>
          <Fact label={t("caseHeader.bankStage")} testId="header-bank-stage">
            {labels.bankStage(c.bank_stage)}
          </Fact>
          <Fact label={t("term.rm")} testId="header-rm">
            {c.rm}
            {c.branch ? ` · ${labels.branch(c.branch)}` : ""}
          </Fact>
          {r && r.blocking_open > 0 ? (
            <Link
              to="/appraisals/$caseId/completeness"
              params={{ caseId: c.id }}
              hash="readiness"
              className="rounded border border-destructive/35 bg-destructive/10 px-2 py-1 text-[11.5px] font-medium text-destructive"
              data-testid="header-blocking"
            >
              {t("caseHeader.blockingGaps", { n: r.blocking_open })}
              <ArrowRight className="ml-0.5 inline h-3 w-3" />
            </Link>
          ) : r && readyForCredit(r) ? (
            <span
              className="inline-flex items-center gap-1 rounded border border-positive/40 bg-positive-soft px-2 py-1 text-[11.5px] font-medium text-positive"
              data-testid="header-ready"
            >
              <ShieldCheck className="h-3 w-3" /> {t("readinessGates.readyForCredit")}
            </span>
          ) : null}
          {c.open_review_items > 0 && canReview && (
            <Link
              to="/review"
              className="inline-flex items-center gap-1 rounded border border-flag/40 bg-flag-soft px-2 py-1 text-[11.5px] font-medium text-flag-foreground"
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
