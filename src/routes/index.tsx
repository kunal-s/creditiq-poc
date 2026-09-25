import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, ArrowUpRight, Plus } from "lucide-react";
import { useCases } from "@/domain/cases";
import { useSession } from "@/domain/session";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";
import type { Case, Stage } from "@/api/types";
import { STAGE_ROUTE } from "@/api/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: t("tenant.product.documentTitleTemplate") },
      { name: "description", content: t("tenant.product.metaDescription") },
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
}: {
  value: number;
  label: string;
  sub: string;
  to: string;
}) {
  return (
    <Link
      to={to}
      className="group flex min-w-[9.5rem] flex-1 items-start gap-3 rounded border border-border bg-surface px-4 py-3 transition-colors hover:border-primary/40"
    >
      <span className="text-[28px] font-semibold leading-none tabular text-foreground">
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

function AppraisalsTable({ cases }: { cases: Case[] }) {
  if (cases.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
        <p className="text-[13px] text-muted-foreground">No applications yet.</p>
        <Link
          to="/applications/new"
          className="text-[12.5px] font-medium text-primary hover:underline"
        >
          Start one
        </Link>
      </div>
    );
  }
  return (
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
          {cases.map((a) => (
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
  );
}

function Workbench() {
  const session = useSession();
  const { data: cases = [] } = useCases();
  const inProgress = cases.filter((c) => c.stage !== "Completed").length;

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 px-6 py-5">
      <section className="flex flex-wrap items-center gap-4">
        <div className="min-w-[16rem] flex-1">
          <h1 className="text-[20px] font-semibold tracking-tight">
            Good morning{session ? `, ${session.user.name.split(" ")[0]}` : ""}
          </h1>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            {t("tenant.bank.unit")} · {t("tenant.bank.hub")}
          </p>
        </div>
        <div className="flex flex-1 flex-wrap gap-2">
          <Counter
            value={inProgress}
            label="Appraisals in progress"
            sub="across all borrowers"
            to="/appraisals"
          />
          <Counter
            value={0}
            label="Awaiting my review"
            sub="drafts ready to sign"
            to="/appraisals"
          />
          <Counter value={0} label="Due this week" sub="committee cut-off" to="/appraisals" />
        </div>
        <Link
          to="/applications/new"
          className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" /> {t("nav.newApplication")}
        </Link>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)]">
        <section className="rounded border border-border bg-surface">
          <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <div>
              <h2 className="text-[14px] font-semibold">In-flight appraisals</h2>
              <p className="text-[11.5px] text-muted-foreground">sorted by stage urgency</p>
            </div>
            <Link to="/appraisals" className="text-[12px] font-medium text-primary hover:underline">
              View all
            </Link>
          </header>
          <AppraisalsTable cases={cases} />
        </section>

        <section className="rounded border border-border bg-surface">
          <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <h2 className="text-[14px] font-semibold">Needs attention</h2>
            <Link to="/exceptions" className="text-[12px] font-medium text-primary hover:underline">
              {t("nav.exceptionQueue")}
            </Link>
          </header>
          <div className="px-4 py-10 text-center text-[13px] text-muted-foreground">
            Nothing needs attention yet.
          </div>
        </section>
      </div>

      <section className="rounded border border-border bg-surface">
        <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <h2 className="text-[14px] font-semibold">Portfolio at a glance</h2>
          <Link to="/memos" className="text-[12px] font-medium text-primary hover:underline">
            {t("nav.memoLibrary")}
          </Link>
        </header>
        <div className="px-4 py-10 text-center text-[13px] text-muted-foreground">
          Portfolio metrics appear once memos have been issued.
        </div>
      </section>
    </div>
  );
}
