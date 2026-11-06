import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { AlertTriangle, CheckCircle2, Search } from "lucide-react";
import { Kpi, Panel, ScoreBar } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { PageHeader } from "@/components/shell/PageHeader";
import { t } from "@/config/terminology";
import { formatDate, formatInr, useCases, useLabels } from "@/domain/cases";
import { countItems, readyForCredit, scoreText, useChecklists } from "@/domain/checklist";
import { cn } from "@/lib/utils";

// The readiness console, as the original design: every appraisal still collecting documents,
// how complete its file is against the review gate, and what is still outstanding.

export const Route = createFileRoute("/docready/")({
  head: () => ({
    meta: [{ title: `${t("nav.readinessConsole")} — ${t("tenant.product.name")}` }],
  }),
  component: ReadinessConsole,
});

type Show = "all" | "blocking" | "ready";

function ReadinessConsole() {
  const cases = useCases();
  const labels = useLabels();
  const open = (cases.data ?? []).filter((c) => c.stage !== "Completed");
  const checklists = useChecklists(open.map((c) => c.id));
  const [show, setShow] = useState<Show>("all");
  const [query, setQuery] = useState("");

  const rows = open.map((c, i) => ({ c, r: checklists[i]?.data }));
  const read = rows.filter((x) => x.r);
  const blockingGaps = read.reduce((n, x) => n + (x.r?.blocking_open ?? 0), 0);
  const ready = read.filter((x) => x.r && readyForCredit(x.r)).length;
  const outstanding = read.reduce((n, x) => {
    const k = countItems(x.r!.items);
    return n + k.insufficient + k.missing;
  }, 0);
  const q = query.trim().toLowerCase();
  const shown = rows
    .filter((x) => !q || [x.c.borrower, x.c.id, x.c.rm].some((v) => v.toLowerCase().includes(q)))
    .filter((x) =>
      show === "all"
        ? true
        : show === "blocking"
          ? (x.r?.blocking_open ?? 0) > 0
          : Boolean(x.r && readyForCredit(x.r)),
    );

  return (
    <div>
      <PageHeader
        eyebrow={t("page.readinessConsole.eyebrow")}
        title={t("nav.readinessConsole")}
        purpose={t("page.readinessConsole.purpose")}
      />
      <div className="space-y-4 px-4 py-5 sm:px-6">
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Kpi
            label={t("page.readinessConsole.kpi.open")}
            value={open.length}
            note={t("page.readinessConsole.kpi.openNote")}
          />
          <Kpi
            label={t("page.readinessConsole.kpi.blocking")}
            value={blockingGaps}
            note={t("page.readinessConsole.kpi.blockingNote")}
          />
          <Kpi
            label={t("page.readinessConsole.kpi.ready")}
            value={ready}
            note={t("page.readinessConsole.kpi.readyNote")}
          />
          <Kpi
            label={t("page.readinessConsole.kpi.outstanding")}
            value={outstanding}
            note={t("page.readinessConsole.kpi.outstandingNote")}
          />
        </section>
        <Panel
          title={t("page.readinessConsole.table")}
          subtitle={t("page.readinessConsole.tableSub")}
          testId="readiness-console"
        >
          <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
            <label className="relative min-w-[12rem] flex-1 sm:max-w-xs">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("page.readinessConsole.search")}
                aria-label={t("page.readinessConsole.search")}
                className="h-8 w-full rounded border border-border bg-surface pl-8 pr-2 text-[12.5px]"
              />
            </label>
            <div
              className="flex flex-wrap items-center gap-0.5 rounded bg-muted p-0.5"
              role="group"
            >
              {(["all", "blocking", "ready"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setShow(s)}
                  aria-pressed={show === s}
                  className={cn(
                    "rounded px-2 py-1 text-[11.5px] font-medium",
                    show === s
                      ? "bg-surface text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t(`page.readinessConsole.show.${s}`)}
                </button>
              ))}
            </div>
          </div>
          <QueryView
            query={cases}
            isEmpty={() => shown.length === 0}
            empty={{
              title: t("page.readinessConsole.none"),
              description: t("page.readinessConsole.noneHelp"),
            }}
          >
            {() => (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-[12.5px]">
                  <thead>
                    <tr className="border-b border-border bg-surface-muted text-left text-[10.5px] uppercase tracking-wide text-muted-foreground">
                      <th className="px-4 py-2 font-medium">{t("term.borrower.title")}</th>
                      <th className="px-3 py-2 font-medium">
                        {t("page.readinessConsole.col.ask")}
                      </th>
                      <th className="px-3 py-2 font-medium">{t("caseHeader.readiness")}</th>
                      <th className="px-3 py-2 font-medium">
                        {t("page.readinessConsole.col.outstanding")}
                      </th>
                      <th className="px-3 py-2 font-medium">{t("cases.col.created")}</th>
                      <th className="px-4 py-2 font-medium">{t("cases.col.rm")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {shown.map(({ c, r }) => {
                      const k = r ? countItems(r.items) : null;
                      return (
                        <tr key={c.id} className="align-top" data-testid="readiness-row">
                          <td className="px-4 py-2.5">
                            <Link
                              to="/appraisals/$caseId/completeness"
                              params={{ caseId: c.id }}
                              className="font-medium text-foreground hover:text-primary hover:underline"
                            >
                              {c.borrower}
                            </Link>
                            <p className="tabular text-[11px] text-muted-foreground">
                              {c.id} · {labels.constitution(c.constitution)}
                            </p>
                          </td>
                          <td className="px-3 py-2.5">
                            {labels.facilities(c.facilities)}
                            <p className="tabular text-[11px] text-muted-foreground">
                              {formatInr(c.amount_inr)}
                            </p>
                          </td>
                          <td className="w-48 px-3 py-2.5">
                            {r && k ? (
                              <>
                                <div className="flex items-center gap-2">
                                  <ScoreBar
                                    className="flex-1"
                                    score={r.score_pct}
                                    gate={r.gate_pct}
                                    blocking={r.blocking_open}
                                  />
                                  <span className="tabular min-w-9 text-right font-semibold">
                                    {scoreText(r.score_pct, r.gate_pct)}%
                                  </span>
                                </div>
                                <p className="mt-1 text-[11px] text-muted-foreground">
                                  {t("page.readinessConsole.satisfied", {
                                    n: k.satisfied,
                                    total: r.items.length,
                                    gate: Math.round(r.gate_pct),
                                  })}
                                </p>
                              </>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {r && k && (
                              <>
                                <p>
                                  {t("page.readinessConsole.outstanding", {
                                    insufficient: k.insufficient,
                                    missing: k.missing,
                                  })}
                                </p>
                                {r.blocking_open > 0 ? (
                                  <span className="mt-1 inline-flex items-center gap-1 rounded border border-destructive/30 bg-destructive/10 px-1.5 py-0.5 text-[11px] font-medium text-destructive">
                                    <AlertTriangle className="h-3 w-3" aria-hidden />
                                    {t("caseHeader.blockingGaps", { n: r.blocking_open })}
                                  </span>
                                ) : (
                                  <span className="mt-1 inline-flex items-center gap-1 rounded border border-positive/30 bg-positive-soft px-1.5 py-0.5 text-[11px] font-medium text-positive">
                                    <CheckCircle2 className="h-3 w-3" aria-hidden />
                                    {t("page.readinessConsole.nothingBlocking")}
                                  </span>
                                )}
                              </>
                            )}
                          </td>
                          <td className="tabular px-3 py-2.5 text-muted-foreground">
                            {formatDate(c.created_at)}
                          </td>
                          <td className="px-4 py-2.5">{c.rm}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </QueryView>
        </Panel>
      </div>
    </div>
  );
}
