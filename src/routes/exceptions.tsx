import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowUpRight, Lock, Sparkles, UserRoundCog } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import {
  OTHER_EXCEPTIONS,
  OUTCOME_LABEL,
  OUTCOME_TONE,
  REVIEWERS,
  SEVERITY_LABEL,
  SEVERITY_TONE,
  northwindExceptions,
  reassignFlag,
  useXVState,
  type Exception,
  type Outcome,
  type Severity,
} from "@/data/crossverify";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/exceptions")({
  head: () => {
    const title = "Exception queue — CreditIQ";
    const description =
      "Every unresolved cross-verification exception across the West Region book, with borrower, severity, age and owner, so nothing open is dropped before submission.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary" },
      ],
    };
  },
  component: ExceptionQueue,
});

const SEV_ORDER: Record<Severity, number> = { serious: 0, moderate: 1, mild: 2 };

function ExceptionQueue() {
  const s = useXVState();
  const [sev, setSev] = useState<Severity | "all">("all");
  const [sort, setSort] = useState<"severity" | "age">("severity");
  const [showClosed, setShowClosed] = useState(false);

  const all = useMemo(() => [...northwindExceptions(s), ...OTHER_EXCEPTIONS], [s]);

  const rows = useMemo(() => {
    const filtered = all.filter((e) => {
      const closed = Boolean(s.adjudications[e.flagId]);
      if (!showClosed && closed) return false;
      return sev === "all" || e.severity === sev;
    });
    return filtered.sort((a, b) =>
      sort === "severity" ? SEV_ORDER[a.severity] - SEV_ORDER[b.severity] || b.ageDays - a.ageDays : b.ageDays - a.ageDays,
    );
  }, [all, sev, sort, showClosed, s]);

  const openRows = all.filter((e) => !s.adjudications[e.flagId]);
  const blocking = openRows.filter((e) => e.blocking);

  return (
    <div>
      <PageHeader
        eyebrow="Governance · Exceptions"
        title="Exception queue"
        purpose="Every cross-verification finding that is still open, across every appraisal on the West Region book. A memo cannot be submitted while one of its blocking exceptions sits here."
        actions={
          <Link
            to="/"
            className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
          >
            Credit Workbench
          </Link>
        }
      />

      <div className="space-y-4 px-6 py-5">
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Open exceptions" value={openRows.length} caption="across 4 appraisals" />
          <Stat
            label="Blocking submission"
            value={blocking.length}
            caption={blocking.map((b) => b.appraisalId).join(" · ") || "none"}
            tone="critical"
          />
          <Stat
            label="Oldest open"
            value={Math.max(0, ...openRows.map((e) => e.ageDays))}
            suffix=" days"
            caption="Sahyadri Pharma · GST returns not filed"
          />
          <Stat
            label="Owned by you"
            value={openRows.filter((e) => e.owner.startsWith("Elena")).length}
            caption="Elena Rossi · Credit Analyst"
          />
        </section>

        <section className="rounded border border-border bg-surface">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
            <h2 className="text-[14px] font-semibold">Open exceptions</h2>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 rounded border border-border p-0.5">
                {(["all", "serious", "moderate", "mild"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setSev(v)}
                    className={cn(
                      "rounded px-2 py-1 text-[11.5px] font-medium capitalize",
                      sev === v ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {v === "all" ? "All severities" : v}
                  </button>
                ))}
              </div>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as "severity" | "age")}
                className="h-8 rounded border border-border bg-surface px-2 text-[12px]"
                aria-label="Sort exceptions"
              >
                <option value="severity">Sort by severity</option>
                <option value="age">Sort by age</option>
              </select>
              <label className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                <input
                  type="checkbox"
                  checked={showClosed}
                  onChange={(e) => setShowClosed(e.target.checked)}
                  className="h-3.5 w-3.5 accent-[var(--primary)]"
                />
                Show adjudicated
              </label>
            </div>
          </header>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1040px] text-[12.5px]">
              <thead>
                <tr className="border-b border-border bg-surface-muted text-left">
                  <th className="px-4 py-2 font-medium text-muted-foreground">Borrower and flag</th>
                  <th className="px-3 py-2 font-medium text-muted-foreground">Severity</th>
                  <th className="px-3 py-2 font-medium text-muted-foreground">Stage</th>
                  <th className="px-3 py-2 font-medium text-muted-foreground">Age</th>
                  <th className="px-3 py-2 font-medium text-muted-foreground">Owner</th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((e) => (
                  <Row key={e.flagId} e={e} closed={s.adjudications[e.flagId]?.outcome} />
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
                      Nothing open at this severity. Every finding has been adjudicated and recorded.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-start gap-2 border-t border-border bg-surface-muted px-4 py-3">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              Ask the copilot which open exceptions are blocking a submission — it reads this queue and the
              blocking rule in CAM template v4.2, and cites the flag it is talking about.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

function Row({ e, closed }: { e: Exception; closed: Outcome | undefined }) {
  const [reassigning, setReassigning] = useState(false);
  const target = e.appraisalId === "CAM-2026-0418" ? "cross-verification" : e.stage === "Data" ? "data" : "cross-verification";

  return (
    <tr className={cn("align-top", e.blocking && !closed && "bg-critical-soft/40")}>
      <td className="px-4 py-2.5">
        <Link
          to="/appraisals/$id/cross-verification"
          params={{ id: e.appraisalId }}
          hash={e.flagId}
          className="text-[13px] font-medium text-foreground hover:text-primary hover:underline"
        >
          {e.title}
        </Link>
        <p className="mt-0.5 max-w-2xl text-[11.5px] leading-snug text-muted-foreground">{e.detail}</p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          {e.borrower} · {e.appraisalId} · <span className="font-mono">{e.flagId}</span>
        </p>
      </td>
      <td className="px-3 py-2.5">
        <span className={cn("rounded border px-1.5 py-0.5 text-[10.5px] font-medium", SEVERITY_TONE[e.severity])}>
          {SEVERITY_LABEL[e.severity]}
        </span>
        {e.blocking && !closed && (
          <span className="mt-1 flex items-center gap-1 text-[10.5px] font-medium text-critical">
            <Lock className="h-3 w-3" /> Blocking
          </span>
        )}
        {closed && (
          <span className={cn("mt-1 block rounded border px-1.5 py-0.5 text-[10.5px] font-medium", OUTCOME_TONE[closed])}>
            {OUTCOME_LABEL[closed]}
          </span>
        )}
      </td>
      <td className="px-3 py-2.5 text-muted-foreground">{e.stage}</td>
      <td className="px-3 py-2.5 tabular">
        {e.ageDays === 0 ? "Today" : `${e.ageDays} days`}
        <span className="block text-[11px] text-muted-foreground">{e.raised}</span>
      </td>
      <td className="px-3 py-2.5">
        {reassigning && e.appraisalId === "CAM-2026-0418" ? (
          <select
            autoFocus
            defaultValue={e.owner}
            onChange={(ev) => {
              reassignFlag(e.flagId, ev.target.value);
              setReassigning(false);
              toast(`${e.flagId} reassigned`, { description: `Now owned by ${ev.target.value}.` });
            }}
            onBlur={() => setReassigning(false)}
            className="h-8 rounded border border-border bg-surface px-2 text-[12px]"
          >
            {REVIEWERS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        ) : (
          <button
            type="button"
            onClick={() =>
              e.appraisalId === "CAM-2026-0418"
                ? setReassigning(true)
                : toast("Reassignment sits with the owning analyst", {
                    description: `${e.owner} owns ${e.flagId} on ${e.borrower}.`,
                  })
            }
            className="inline-flex items-center gap-1 text-left text-[12px] text-foreground hover:text-primary"
          >
            <UserRoundCog className="h-3.5 w-3.5 text-muted-foreground" />
            {e.owner}
          </button>
        )}
      </td>
      <td className="px-3 py-2.5 text-right">
        <Link
          to="/appraisals/$id/cross-verification"
          params={{ id: e.appraisalId }}
          hash={e.flagId}
          className="inline-flex items-center gap-1 rounded border border-border bg-surface px-2.5 py-1.5 text-[12px] font-medium hover:bg-muted"
        >
          {closed ? "Review" : "Open and adjudicate"} <ArrowUpRight className="h-3 w-3" />
        </Link>
        <span className="sr-only">{target}</span>
      </td>
    </tr>
  );
}

function Stat({
  label,
  value,
  caption,
  suffix,
  tone,
}: {
  label: string;
  value: number;
  caption: string;
  suffix?: string;
  tone?: "critical";
}) {
  return (
    <div className={cn("rounded border bg-surface p-3", tone === "critical" && value > 0 ? "border-critical/30" : "border-border")}>
      <p className="field-label flex items-center gap-1">
        {tone === "critical" && value > 0 && <AlertTriangle className="h-3 w-3 text-critical" />}
        {label}
      </p>
      <p className="mt-1 text-[24px] font-semibold leading-none tabular">
        {value}
        {suffix && <span className="text-[14px] font-normal text-muted-foreground">{suffix}</span>}
      </p>
      <p className="mt-2 truncate text-[11.5px] text-muted-foreground">{caption}</p>
    </div>
  );
}
