import { createFileRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { AlertTriangle, ArrowRight, ShieldCheck } from "lucide-react";
import type { CaseDetail } from "@/api/types";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { DOCREADY_TABS } from "@/components/shell/nav";
import { ScoreBar } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { formatInr, stageLabel, useLabels } from "@/domain/cases";
import { countItems, readyForCredit, useChecklist } from "@/domain/checklist";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId")({
  component: CaseLayout,
});

function CaseLayout() {
  const { caseId } = Route.useParams();
  return <CaseScreen caseId={caseId}>{(c) => <Layout c={c} />}</CaseScreen>;
}

/** The prototype's DocReady case header (readiness, ask, blocking count) and tab bar. */
function Layout({ c }: { c: CaseDetail }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const labels = useLabels();
  const checklist = useChecklist(c.id);
  const r = checklist.data;
  const counts = r ? countItems(r.items) : undefined;

  return (
    <div>
      <div className="border-b border-border bg-surface-muted/60 px-4 pt-4 sm:px-6">
        <div
          className="rounded-md border border-border bg-surface shadow-sm"
          data-testid="docready-header"
        >
          <div className="flex flex-wrap items-stretch justify-between gap-x-8 gap-y-4 border-l-2 border-primary px-4 py-3.5">
            <div className="min-w-0">
              <p className="field-label">
                {t("docready.eyebrow")} · {labels.constitution(c.constitution)}
              </p>
              <h1 className="break-words text-[19px] font-semibold tracking-tight text-foreground">
                {c.borrower}
              </h1>
              <div className="tabular mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                <span>{c.id}</span>
                {c.pan && (
                  <>
                    <span className="text-border">|</span>
                    <span>
                      {t("identifier.pan")} {c.pan}
                    </span>
                  </>
                )}
                {c.gstin && (
                  <>
                    <span className="text-border">|</span>
                    <span>
                      {t("identifier.gstin")} {c.gstin}
                    </span>
                  </>
                )}
                {c.udyam && (
                  <>
                    <span className="text-border">|</span>
                    <span>
                      {t("identifier.udyam")} {c.udyam}
                    </span>
                  </>
                )}
                <span className="text-border">|</span>
                <span>{c.rm}</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <div className="min-w-[168px]" data-testid="header-readiness">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="field-label">{t("docready.readiness")}</span>
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
                    ? t("docready.outstandingGate", {
                        n: counts.outstanding,
                        gate: Math.round(r.gate_pct),
                      })
                    : checklist.isError
                      ? t("docready.readinessUnavailable")
                      : t("state.loading")}
                  {r?.provisional && ` · ${t("checklist.provisional")}`}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-border sm:border-l sm:pl-6">
                <div>
                  <span className="field-label block">{t("docready.ask")}</span>
                  <span className="tabular text-[12.5px] text-foreground">
                    {labels.facilities(c.facilities)} · {formatInr(c.amount_inr)}
                  </span>
                </div>
                <div>
                  <span className="field-label block">{t("term.stage")}</span>
                  <span className="text-[12.5px] text-foreground">{stageLabel(c.stage)}</span>
                </div>
              </div>

              {r && r.blocking_open > 0 ? (
                <Link
                  to="/docready/$caseId/readiness"
                  params={{ caseId: c.id }}
                  className="rounded border border-destructive/35 bg-destructive/10 px-2.5 py-1.5 text-[11.5px] font-medium text-destructive"
                  data-testid="header-blocking"
                >
                  {t("docready.blockingGaps", { n: r.blocking_open })}
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
              {c.open_review_items > 0 && (
                <Link
                  to="/exceptions"
                  className="inline-flex items-center gap-1 rounded border border-flag/40 bg-flag-soft px-2.5 py-1.5 text-[11.5px] font-medium text-flag-foreground"
                >
                  <AlertTriangle className="h-3 w-3" />
                  {t("cases.reviewOpen", { n: c.open_review_items })}
                </Link>
              )}
            </div>
          </div>
        </div>

        <nav className="-mb-px mt-3 flex gap-4 overflow-x-auto" aria-label={t("docready.tabs")}>
          {DOCREADY_TABS.map((tab) => {
            const to = `/docready/${encodeURIComponent(c.id)}/${tab.to}`;
            const active =
              pathname === to || decodeURIComponent(pathname) === decodeURIComponent(to);
            return (
              <Link
                key={tab.to}
                to={to}
                className={cn(
                  "shrink-0 border-b-2 pb-2 text-[12.5px] font-medium transition-colors",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                )}
              >
                {t(`docreadyTab.${tab.key}`)}
              </Link>
            );
          })}
        </nav>
      </div>

      <Outlet />
    </div>
  );
}
