import { createFileRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { AlertTriangle, ArrowRight, ShieldCheck } from "lucide-react";
import type { CaseDetail, CaseProgress, Stage } from "@/api/types";
import { CaseAssistant } from "@/components/case/CaseAssistant";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { CaseMoreMenu } from "@/components/cases/DeleteCaseButton";
import { NextStepBar } from "@/components/case/NextStep";
import { StageProgressBar } from "@/components/case/StageProgress";
import { CASE_TABS, caseTabPath } from "@/components/shell/nav";
import { ScoreBar } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { formatInr, stageLabel, useLabels } from "@/domain/cases";
import { formatDay } from "@/domain/outputs";
import { readinessBreakdown, readyForCredit, scoreText, useChecklist } from "@/domain/checklist";
import { readinessWait, useCaseProgress } from "@/domain/progress";
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
      <div className="border-b border-border px-4 pt-4 sm:px-6">
        <CaseHeader c={c} />
        <div className="mt-3 min-h-9">
          {progress.data && (
            <StageProgressBar caseId={c.id} progress={progress.data} activeKey={activeTab?.key} />
          )}
        </div>
      </div>

      <Outlet />
      <NextStepBar c={c} progress={progress.data} active={activeTab} />
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
  // Until the documents are in and read, a score of 0 with every item blocking says nothing:
  // the header says what readiness is waiting on instead.
  const progress = useCaseProgress(c.id);
  const wait = readinessWait(progress.data, checklist.data);
  const r = wait ? undefined : checklist.data;
  const b = r ? readinessBreakdown(r.items) : undefined;
  const ids: (string | null)[] = [
    c.id,
    c.pan ? `${t("identifier.pan")} ${c.pan}` : null,
    c.gstin ? `${t("identifier.gstin")} ${c.gstin}` : null,
    c.udyam ? `${t("identifier.udyam")} ${c.udyam}` : null,
    c.application_id ? `${t("identifier.applicationId")} ${c.application_id}` : null,
  ];

  return (
    <div
      className="relative rounded border border-border border-l-2 border-l-primary bg-surface px-5 py-4"
      data-testid="case-header"
    >
      <div className="absolute right-3 top-3">
        <CaseMoreMenu caseId={c.id} borrower={c.borrower} />
      </div>
      {/* A field with no value is left out, never written as "not recorded". */}
      <p className="pr-10 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
        <span data-testid="header-product">
          {labels.product(c.product)}
          {c.case_type ? ` · ${labels.caseType(c.case_type)}` : ""}
        </span>
        {" · "}
        {labels.constitution(c.constitution)}
      </p>
      <h1 className="mt-1 break-words text-[17px] font-semibold tracking-tight text-foreground">
        {c.borrower}
      </h1>
      <p className="tabular mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[12px] text-muted-foreground">
        {ids
          .filter((v): v is string => Boolean(v))
          .map((v) => (
            <span key={v} className="after:ml-2 after:text-border after:content-['|']">
              {v}
            </span>
          ))}
        <span data-testid="header-rm">
          {c.rm}
          {c.branch ? ` · ${labels.branch(c.branch)}` : ""}
        </span>
      </p>

      <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-3">
        <div
          className="w-44"
          data-testid="header-readiness"
          data-state={wait ? `waiting-${wait.kind}` : undefined}
        >
          <div className="flex items-baseline justify-between gap-2">
            <span className="field-label">{t("caseHeader.readiness")}</span>
            <span
              className="tabular whitespace-nowrap text-[13px] font-semibold leading-none text-foreground"
              data-testid="header-readiness-count"
            >
              {b ? t("journey.readiness.ofTotal", { n: b.satisfied, total: b.total }) : "—"}
            </span>
          </div>
          {wait ? (
            <div
              className={cn(
                "mt-1 h-1.5 rounded-full bg-muted",
                wait.kind === "reading" && "animate-pulse bg-info/30",
              )}
              aria-hidden
            />
          ) : (
            <ScoreBar
              className="mt-1"
              score={r?.score_pct ?? 0}
              gate={r?.gate_pct ?? 100}
              blocking={r?.blocking_open ?? 0}
            />
          )}
          <p
            className="tabular mt-1 text-[11px] text-muted-foreground"
            data-testid="header-readiness-score"
          >
            {wait
              ? wait.kind === "documents"
                ? t("caseHeader.waitingDocuments")
                : wait.total > 0
                  ? t("caseHeader.readingDocuments", { done: wait.done, total: wait.total })
                  : t("caseHeader.readingStarted")
              : r
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
        {c.bank_stage && (
          <Fact label={t("caseHeader.bankStage")} testId="header-bank-stage">
            {labels.bankStage(c.bank_stage)}
          </Fact>
        )}
        <Fact label={t("caseHeader.caseDate")} testId="header-case-date">
          <span title={t("caseHeader.caseDateHelp")}>{formatDay(c.as_of)}</span>
        </Fact>
        <div className="flex flex-wrap items-center gap-2">
          {r && r.blocking_open > 0 ? (
            <Link
              to="/appraisals/$caseId/completeness"
              params={{ caseId: c.id }}
              hash="checklist"
              className="rounded border border-destructive/25 bg-critical-soft/60 px-2 py-1 text-[12px] font-medium text-critical-text hover:bg-critical-soft"
              data-testid="header-blocking"
            >
              {t("caseHeader.blockingGaps", { n: r.blocking_open })}
              <ArrowRight className="ml-0.5 inline h-3 w-3" />
            </Link>
          ) : progress.data?.gate?.open ? (
            // Only when the engine says the case is created: until then readiness is the news.
            <span
              className="inline-flex items-center gap-1 rounded border border-primary/30 bg-primary/5 px-2 py-1 text-[12px] font-medium text-primary"
              data-testid="header-stage"
            >
              {t(`caseHeader.caseStage.${caseStage(progress.data)}`)}
            </span>
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

/** Where a created case stands, from the engine's stage progress: in assessment until the memo
 * is drafted, then the memo in draft. */
function caseStage(progress: CaseProgress | undefined): "assessment" | "memo" {
  const outputs = progress?.stages.find((s) => s.key === "outputs");
  return outputs && outputs.status !== "not_started" ? "memo" : "assessment";
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
