import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  CalendarClock,
  ArrowUpRight,
  Plus,
  Sparkles,
  TrendingDown,
} from "lucide-react";
import {
  APPRAISALS,
  ATTENTION,
  COUNTERS,
  CURRENT_USER,
  PORTFOLIO,
  STAGE_ROUTE,
  type Stage,
} from "@/data/seed";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Credit Workbench — CreditIQ" },
      {
        name: "description",
        content:
          "CreditIQ workbench",
      },
      { property: "og:title", content: "Credit Workbench — CreditIQ" },
      {
        property: "og:description",
        content:
          "CreditIQ workbench",
      },
    ],
  }),
  component: Workbench,
});

const stageTone: Record<Stage, string> = {
  Identity: "bg-muted text-muted-foreground",
  Data: "bg-info-soft text-info",
  Spread: "bg-info-soft text-info",
  "Cross-Verification": "bg-flag-soft text-flag-foreground",
  Draft: "bg-accent text-accent-foreground",
  Submission: "bg-accent text-accent-foreground",
  Completed: "bg-positive-soft text-positive",
};

function Counter({
  value,
  label,
  sub,
  to,
  tone,
}: {
  value: number;
  label: string;
  sub: string;
  to: string;
  tone?: "flag";
}) {
  return (
    <Link
      to={to}
      className="group flex min-w-[9.5rem] flex-1 items-start gap-3 rounded border border-border bg-surface px-4 py-3 transition-colors hover:border-primary/40"
    >
      <span
        className={cn(
          "text-[28px] font-semibold leading-none tabular",
          tone === "flag" ? "text-flag-foreground" : "text-foreground",
        )}
      >
        {value}
      </span>
      <span className="min-w-0">
        <span className="block text-[12.5px] font-medium text-foreground">{label}</span>
        <span className="block text-[11.5px] text-muted-foreground">{sub}</span>
      </span>
      <ArrowUpRight className="ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </Link>
  );
}

function Workbench() {
  const maxRating = Math.max(...PORTFOLIO.ratingDistribution.map((r) => r.count));

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 px-6 py-5">
      {/* Greeting */}
      <section className="flex flex-wrap items-center gap-4">
        <div className="min-w-[16rem] flex-1">
          <h1 className="text-[20px] font-semibold tracking-tight">
            Good morning, {CURRENT_USER.name.split(" ")[0]}
          </h1>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Friday, 31 July 2026 · West Region corporate desk · 2 items were escalated to you
            overnight
          </p>
        </div>
        <div className="flex flex-1 flex-wrap gap-2">
          <Counter
            value={COUNTERS.inProgress}
            label="Appraisals in progress"
            sub="across 4 borrowers"
            to="/appraisals"
          />
          <Counter
            value={COUNTERS.awaitingReview}
            label="Awaiting my review"
            sub="drafts ready to sign"
            to="/appraisals"
            tone="flag"
          />
          <Counter
            value={COUNTERS.dueThisWeek}
            label="Due this week"
            sub="committee cut-off Thu"
            to="/appraisals"
          />
        </div>
        <Link
          to="/appraisals/new"
          className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" /> New appraisal
        </Link>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)]">
        {/* In-flight appraisals */}
        <section className="rounded border border-border bg-surface">
          <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <div>
              <h2 className="text-[14px] font-semibold">In-flight appraisals</h2>
              <p className="text-[11.5px] text-muted-foreground">
                Assigned to {CURRENT_USER.name} · sorted by stage urgency
              </p>
            </div>
            <Link to="/appraisals" className="text-[12px] font-medium text-primary hover:underline">
              View all
            </Link>
          </header>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-[12.5px]">
              <thead>
                <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Borrower</th>
                  <th className="px-3 py-2 font-medium">Proposal</th>
                  <th className="px-3 py-2 font-medium">Stage</th>
                  <th className="px-3 py-2 font-medium">RM</th>
                  <th className="px-3 py-2 font-medium">Started</th>
                  <th className="px-3 py-2 font-medium">Rating</th>
                  <th className="px-4 py-2 font-medium">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {APPRAISALS.map((a) => (
                  <tr
                    key={a.id}
                    className={cn(
                      "align-top transition-colors hover:bg-surface-muted",
                      a.discrepancies >= 2 && "bg-flag-soft/50 hover:bg-flag-soft",
                    )}
                  >
                    <td className="px-4 py-3">
                      <Link
                        to="/appraisals/$id/identity"
                        params={{ id: a.id }}
                        className="font-medium text-foreground hover:text-primary hover:underline"
                      >
                        {a.borrower}
                      </Link>
                      <div className="mt-0.5 text-[11px] text-muted-foreground">
                        {a.id} · {a.sector}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="text-foreground">{a.proposal}</div>
                      <div className="mt-0.5 text-[11px] text-muted-foreground tabular">
                        {a.facilities}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <Link
                        to={"/appraisals/$id/" + STAGE_ROUTE[a.stage]}
                        params={{ id: a.id }}
                        className={cn(
                          "inline-block rounded px-1.5 py-0.5 text-[11.5px] font-medium",
                          stageTone[a.stage],
                        )}
                      >
                        {a.stage}
                      </Link>
                    </td>
                    <td className="px-3 py-3 text-foreground">{a.rm}</td>
                    <td className="px-3 py-3 text-muted-foreground tabular">
                      {a.completed ? `Completed ${a.completed}` : a.started}
                    </td>
                    <td className="px-3 py-3">
                      <span className="font-medium text-foreground tabular">{a.rating}</span>
                      <div className="text-[11px] text-muted-foreground">{a.ratingLabel}</div>
                    </td>
                    <td className="px-4 py-3">
                      {a.discrepancies > 0 ? (
                        <Link
                          to="/appraisals/$id/cross-verification"
                          params={{ id: a.id }}
                          className="inline-flex items-center gap-1 rounded border border-flag/40 bg-flag-soft px-1.5 py-0.5 text-[11.5px] font-medium text-flag-foreground"
                        >
                          <AlertTriangle className="h-3 w-3" />
                          {a.discrepancies} open
                        </Link>
                      ) : (
                        <span className="text-[11.5px] text-muted-foreground">Clear</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Needs attention */}
        <section className="rounded border border-border bg-surface">
          <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <h2 className="text-[14px] font-semibold">Needs attention</h2>
            <span className="rounded bg-flag-soft px-1.5 py-0.5 text-[11px] font-medium text-flag-foreground">
              {ATTENTION.length} items
            </span>
          </header>
          <ul className="divide-y divide-border">
            {ATTENTION.map((item) => (
              <li key={item.id}>
                <Link
                  to={"/appraisals/$id/" + item.step}
                  params={{ id: item.appraisalId }}
                  className="flex gap-3 px-4 py-3 transition-colors hover:bg-surface-muted"
                >
                  <span
                    className={cn(
                      "mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded",
                      item.kind === "discrepancy"
                        ? "bg-critical-soft text-critical"
                        : "bg-info-soft text-info",
                    )}
                  >
                    {item.kind === "discrepancy" ? (
                      <AlertTriangle className="h-3.5 w-3.5" />
                    ) : (
                      <CalendarClock className="h-3.5 w-3.5" />
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[12.5px] font-medium text-foreground">
                      {item.title}
                    </span>
                    <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">
                      {item.detail}
                    </span>
                    <span className="mt-1 block text-[11px] text-muted-foreground">
                      {item.borrower} · {item.id}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex items-start gap-2 border-t border-border bg-surface-muted px-4 py-3">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              Copilot can draft the Northwind discrepancy note and the RM query email from the
              underlying evidence.
            </p>
          </div>
        </section>
      </div>

      {/* Portfolio at a glance */}
      <section className="rounded border border-border bg-surface">
        <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <h2 className="text-[14px] font-semibold">Portfolio at a glance</h2>
          <Link to="/memos" className="text-[12px] font-medium text-primary hover:underline">
            Memo Library
          </Link>
        </header>
        <div className="grid gap-4 px-4 py-4 md:grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,1.6fr)]">
          <div>
            <p className="field-label">Memos this month</p>
            <p className="mt-1 text-[24px] font-semibold leading-none tabular">
              {PORTFOLIO.memosThisMonth}
            </p>
            <p className="mt-1 text-[11.5px] text-muted-foreground">
              {PORTFOLIO.memosLastMonth} in June · West Region
            </p>
          </div>
          <div>
            <p className="field-label">Turnaround before CreditIQ</p>
            <p className="mt-1 text-[24px] font-semibold leading-none tabular text-muted-foreground">
              {PORTFOLIO.turnaroundBefore}
            </p>
            <p className="mt-1 text-[11.5px] text-muted-foreground">Manual assembly, FY25 median</p>
          </div>
          <div>
            <p className="field-label">Turnaround after CreditIQ</p>
            <p className="mt-1 flex items-center gap-1.5 text-[24px] font-semibold leading-none tabular text-positive">
              {PORTFOLIO.turnaroundAfter}
              <TrendingDown className="h-4 w-4" />
            </p>
            <p className="mt-1 text-[11.5px] text-muted-foreground">
              Median review session {PORTFOLIO.medianReviewSession}
            </p>
          </div>
          <div>
            <p className="field-label">Rating distribution · CCB-1 to CCB-8</p>
            <div className="mt-2 flex items-end gap-1.5">
              {PORTFOLIO.ratingDistribution.map((r) => (
                <div key={r.grade} className="flex flex-1 flex-col items-center gap-1">
                  <span className="text-[10.5px] text-muted-foreground tabular">{r.count}</span>
                  <div
                    className={cn(
                      "w-full rounded-sm",
                      Number(r.grade.split("-")[1]) >= 6 ? "bg-flag/70" : "bg-primary/75",
                    )}
                    style={{ height: `${8 + (r.count / maxRating) * 40}px` }}
                  />
                  <span className="text-[10px] text-muted-foreground">
                    {r.grade.replace("CCB-", "")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}