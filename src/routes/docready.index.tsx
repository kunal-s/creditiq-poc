import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { ArrowRight, Search, Sparkles, AlertTriangle, Clock } from "lucide-react";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { useDocReady, readiness, type DocReadyCase } from "@/data/docready";
import { TENANT } from "@/data/seed";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/")({
  head: () => {
    const title = "DocReady Readiness Console — CreditIQ";
    const description =
      "Document readiness across MSME and SME onboarding cases: readiness score, outstanding documents, blocking gaps, days in collection and owner.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: ReadinessConsole,
});

function ScoreBar({ score }: { score: number }) {
  const tone = score >= 90 ? "bg-positive" : score >= 65 ? "bg-flag" : "bg-destructive";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${score}%` }} />
      </div>
      <span className="tabular text-[12px] font-medium text-foreground">{score}%</span>
    </div>
  );
}

const FILTERS = ["All cases", "Blocking gaps", "Ready for credit review", "Ageing over 14 days"] as const;

function matches(c: DocReadyCase, f: (typeof FILTERS)[number]) {
  const r = readiness(c);
  if (f === "Blocking gaps") return r.blockingOpen > 0;
  if (f === "Ready for credit review") return r.blockingOpen === 0 && r.reviewGate;
  if (f === "Ageing over 14 days") return c.daysInCollection > 14;
  return true;
}

function ReadinessConsole() {
  const { cases } = useDocReady();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All cases");
  const [q, setQ] = useState("");

  const rows = useMemo(
    () =>
      cases
        .filter((c) => matches(c, filter))
        .filter((c) =>
          q.trim()
            ? (c.borrower + c.id + c.product + c.branch).toLowerCase().includes(q.trim().toLowerCase())
            : true,
        ),
    [cases, filter, q],
  );

  const totals = useMemo(() => {
    const scores = cases.map((c) => readiness(c));
    return {
      open: cases.length,
      blocking: scores.filter((s) => s.blockingOpen > 0).length,
      ready: scores.filter((s) => s.blockingOpen === 0).length,
      outstanding: scores.reduce((n, s) => n + s.outstanding, 0),
      avgAge: Math.round(cases.reduce((n, c) => n + c.daysInCollection, 0) / cases.length),
    };
  }, [cases]);

  return (
    <div>
      <PageHeader
        eyebrow="DocReady · stage one"
        title="Readiness Console"
        purpose={`Document collection for MSME and SME proposals across ${TENANT.region}. A case leaves this console only when the file is complete enough to underwrite, then hands off into credit appraisal.`}
        actions={
          <Link
            to="/docready/$caseId/checklist"
            params={{ caseId: "DR-2026-0142" }}
            className="rounded bg-primary px-3 py-1.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
          >
            Open Southgate Textiles
          </Link>
        }
      />

      <div className="space-y-4 px-6 py-5">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {[
            { label: "Open cases", value: totals.open, note: "in collection now" },
            { label: "Blocking gaps", value: totals.blocking, note: "cannot be appraised yet", tone: "text-destructive" },
            { label: "Ready for handoff", value: totals.ready, note: "no blocking document missing", tone: "text-positive" },
            { label: "Documents outstanding", value: totals.outstanding, note: "across all open cases" },
            { label: "Average age", value: `${totals.avgAge} days`, note: "against a 12-day target" },
          ].map((k) => (
            <div key={k.label} className="rounded border border-border bg-surface px-4 py-3">
              <p className="field-label">{k.label}</p>
              <p className={cn("tabular mt-1 text-[22px] font-semibold leading-none", k.tone ?? "text-foreground")}>
                {k.value}
              </p>
              <p className="mt-1.5 text-[11.5px] text-muted-foreground">{k.note}</p>
            </div>
          ))}
        </div>

        <Panel
          title="Cases in collection"
          subtitle="Readiness is weighted by document importance, not a plain count."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search borrower or case"
                  aria-label="Search cases"
                  className="h-7 w-52 rounded border border-border bg-background pl-7 pr-2 text-[12px] focus:outline-none focus:ring-1 focus:ring-ring"
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
                    {f}
                  </button>
                ))}
              </div>
            </div>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-[12.5px]">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Borrower</th>
                  <th className="px-4 py-2 font-medium">Product and ask</th>
                  <th className="px-4 py-2 font-medium">Readiness</th>
                  <th className="px-4 py-2 font-medium">Outstanding</th>
                  <th className="px-4 py-2 font-medium">Age</th>
                  <th className="px-4 py-2 font-medium">Branch and RM</th>
                  <th className="px-4 py-2 font-medium">Target sanction</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((c) => {
                  const r = readiness(c);
                  return (
                    <tr key={c.id} className="align-top hover:bg-surface-muted/60">
                      <td className="px-4 py-2.5">
                        <Link
                          to="/docready/$caseId/checklist"
                          params={{ caseId: c.id }}
                          className="font-medium text-foreground hover:text-primary"
                        >
                          {c.borrower}
                        </Link>
                        <div className="tabular mt-0.5 text-[11px] text-muted-foreground">
                          {c.id} · {c.segment} enterprise · {c.constitution}
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="text-foreground">{c.product}</div>
                        <div className="tabular mt-0.5 text-[11px] text-muted-foreground">{c.facilities}</div>
                      </td>
                      <td className="px-4 py-2.5">
                        <ScoreBar score={r.score} />
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          {r.accepted} of {r.total} settled
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="tabular text-foreground">{r.outstanding} documents</div>
                        {r.blockingOpen > 0 ? (
                          <span className="mt-1 inline-flex items-center gap-1 rounded border border-destructive/30 bg-destructive/10 px-1.5 py-0.5 text-[10.5px] font-medium text-destructive">
                            <AlertTriangle className="h-3 w-3" /> {r.blockingOpen} blocking
                          </span>
                        ) : (
                          <span className="mt-1 inline-flex rounded border border-positive/30 bg-positive-soft px-1.5 py-0.5 text-[10.5px] font-medium text-positive">
                            Nothing blocking
                          </span>
                        )}
                      </td>
                      <td className="tabular px-4 py-2.5 text-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          {c.daysInCollection}d
                        </span>
                        <div className="mt-0.5 text-[11px] text-muted-foreground">last contact {c.lastContact}</div>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="text-foreground">{c.branch}</div>
                        <div className="mt-0.5 text-[11px] text-muted-foreground">{c.rm}</div>
                      </td>
                      <td className="tabular px-4 py-2.5 text-foreground">{c.targetSanction}</td>
                      <td className="px-4 py-2.5 text-right">
                        <Link
                          to="/docready/$caseId/readiness"
                          params={{ caseId: c.id }}
                          className="inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
                        >
                          Readiness <ArrowRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-center text-[12.5px] text-muted-foreground">
                      No case matches this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="rounded border border-border bg-surface p-4">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold">
            <Sparkles className="h-3.5 w-3.5 text-primary" /> Copilot read on the queue
          </p>
          <p className="mt-1.5 max-w-4xl text-[12.5px] leading-relaxed text-muted-foreground">
            Two cases will slip their target sanction date unless the outstanding ask closes this week. Southgate
            Textiles is one signed audited statement and one stock statement away from handoff; Vashi Cold Storage
            LLP has been open 21 days with three blocking documents and has not responded since 1 August 2026, which
            is the pattern that usually ends in a withdrawn application.
          </p>
        </div>
      </div>
    </div>
  );
}
