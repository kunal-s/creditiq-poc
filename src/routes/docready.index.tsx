import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { AlertTriangle, ArrowRight, Search } from "lucide-react";
import type { Readiness } from "@/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Kpi, Panel, ScoreBar } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { StageLink } from "@/components/cases/CasesTable";
import { t } from "@/config/terminology";
import { formatInr, useCases, useLabels } from "@/domain/cases";
import { countItems, readyForCredit, useChecklists } from "@/domain/checklist";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/")({
  head: () => ({
    meta: [{ title: `${t("page.readinessConsole.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ReadinessConsole,
});

const FILTERS = ["all", "blocking", "ready"] as const;
type Filter = (typeof FILTERS)[number];

function ReadinessConsole() {
  const cases = useCases();
  return (
    <div>
      <PageHeader
        eyebrow={t("page.readinessConsole.eyebrow")}
        title={t("page.readinessConsole.title")}
        purpose={t("page.readinessConsole.purpose")}
      />
      <div className="space-y-4 px-4 py-5 sm:px-6">
        <QueryView
          query={cases}
          isEmpty={(d) => d.length === 0}
          empty={{ title: t("state.noCases.title"), description: t("state.noCases.description") }}
        >
          {(list) => <Console cases={list.filter((c) => c.stage !== "Completed")} />}
        </QueryView>
      </div>
    </div>
  );
}

function Console({ cases }: { cases: NonNullable<ReturnType<typeof useCases>["data"]> }) {
  const labels = useLabels();
  const checklists = useChecklists(cases.map((c) => c.id));
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const byId = new Map<string, Readiness | undefined>(
    cases.map((c, i) => [c.id, checklists[i]?.data]),
  );
  const loaded = checklists.filter((c) => c.data).map((c) => c.data!);

  const totals = {
    open: cases.length,
    blocking: loaded.filter((r) => r.blocking_open > 0).length,
    ready: loaded.filter(readyForCredit).length,
    outstanding: loaded.reduce((n, r) => n + countItems(r.items).outstanding, 0),
    inReview: loaded.reduce((n, r) => n + countItems(r.items).in_review, 0),
  };

  const rows = cases
    .filter((c) => {
      const r = byId.get(c.id);
      if (filter === "blocking") return (r?.blocking_open ?? 0) > 0;
      if (filter === "ready") return r ? readyForCredit(r) : false;
      return true;
    })
    .filter((c) =>
      q.trim() ? (c.borrower + c.id).toLowerCase().includes(q.trim().toLowerCase()) : true,
    );

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Kpi
          label={t("console.kpi.open")}
          value={totals.open}
          note={t("console.kpi.openNote")}
          testId="kpi-open"
        />
        <Kpi
          label={t("console.kpi.blocking")}
          value={totals.blocking}
          note={t("console.kpi.blockingNote")}
          tone="critical"
          testId="kpi-blocking"
        />
        <Kpi
          label={t("readinessGates.readyForCredit")}
          value={totals.ready}
          note={t("console.kpi.readyNote")}
          tone="positive"
          testId="kpi-ready"
        />
        <Kpi
          label={t("console.kpi.outstanding")}
          value={totals.outstanding}
          note={t("console.kpi.outstandingNote")}
        />
        <Kpi
          label={t("docStatus.in_review")}
          value={totals.inReview}
          note={t("console.kpi.inReviewNote")}
        />
      </div>

      <Panel
        title={t("console.cases")}
        subtitle={t("console.casesHelp")}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t("console.search")}
                aria-label={t("console.search")}
                className="h-7 w-52 max-w-full rounded border border-border bg-background pl-7 pr-2 text-[12px] focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="flex flex-wrap gap-1">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={cn(
                    "rounded border px-2 py-1 text-[11.5px] transition-colors",
                    filter === f
                      ? "border-primary/50 bg-primary/10 font-medium text-primary"
                      : "border-border text-muted-foreground hover:bg-muted",
                  )}
                >
                  {t(`console.filter.${f}`)}
                </button>
              ))}
            </div>
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-[12.5px]">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2 font-medium">{t("term.borrower.title")}</th>
                <th className="px-4 py-2 font-medium">{t("cases.col.proposal")}</th>
                <th className="px-4 py-2 font-medium">{t("docready.readiness")}</th>
                <th className="px-4 py-2 font-medium">{t("console.outstanding")}</th>
                <th className="px-4 py-2 font-medium">{t("term.stage")}</th>
                <th className="px-4 py-2 font-medium">{t("cases.col.rm")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((c) => {
                const r = byId.get(c.id);
                const counts = r ? countItems(r.items) : undefined;
                const failed = checklists[cases.indexOf(c)]?.isError;
                return (
                  <tr
                    key={c.id}
                    className="align-top hover:bg-surface-muted/60"
                    data-testid="console-row"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        to="/docready/$caseId/checklist"
                        params={{ caseId: c.id }}
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {c.borrower}
                      </Link>
                      <div className="tabular mt-0.5 text-[11px] text-muted-foreground">
                        {c.id} · {labels.constitution(c.constitution)}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="text-foreground">{labels.facilities(c.facilities)}</div>
                      <div className="tabular mt-0.5 text-[11px] text-muted-foreground">
                        {formatInr(c.amount_inr)}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      {r && counts ? (
                        <>
                          <div className="flex items-center gap-2">
                            <ScoreBar
                              score={r.score_pct}
                              gate={r.gate_pct}
                              blocking={r.blocking_open}
                              className="w-20"
                            />
                            <span className="tabular text-[12px] font-medium text-foreground">
                              {Math.round(r.score_pct)}%
                            </span>
                          </div>
                          <div className="mt-1 text-[11px] text-muted-foreground">
                            {t("console.satisfiedOf", { x: counts.satisfied, y: counts.total })}
                            {" · "}
                            {r.gate_met
                              ? t("console.gateMet")
                              : t("console.belowGate", { gate: Math.round(r.gate_pct) })}
                          </div>
                        </>
                      ) : (
                        <span className="text-[11.5px] text-muted-foreground">
                          {failed ? t("docready.readinessUnavailable") : t("state.loading")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {r && counts && (
                        <>
                          <div className="tabular text-foreground">
                            {t("console.insufficientMissing", {
                              insufficient: counts.insufficient,
                              missing: counts.missing,
                            })}
                          </div>
                          {r.blocking_open > 0 ? (
                            <span className="mt-1 inline-flex items-center gap-1 rounded border border-destructive/30 bg-destructive/10 px-1.5 py-0.5 text-[10.5px] font-medium text-destructive">
                              <AlertTriangle className="h-3 w-3" />{" "}
                              {t("console.blocking", { n: r.blocking_open })}
                            </span>
                          ) : (
                            <span className="mt-1 inline-flex rounded border border-positive/30 bg-positive-soft px-1.5 py-0.5 text-[10.5px] font-medium text-positive">
                              {t("console.nothingBlocking")}
                            </span>
                          )}
                        </>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <StageLink c={c} />
                    </td>
                    <td className="px-4 py-2.5 text-foreground">{c.rm}</td>
                    <td className="px-4 py-2.5 text-right">
                      <Link
                        to="/docready/$caseId/readiness"
                        params={{ caseId: c.id }}
                        className="inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
                      >
                        {t("docreadyTab.readiness")} <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-6 text-center text-[12.5px] text-muted-foreground"
                  >
                    {t("console.noMatch")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
