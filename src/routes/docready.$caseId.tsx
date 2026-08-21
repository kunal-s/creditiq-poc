import { createFileRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useDocReadyCase, readiness } from "@/data/docready";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId")({
  component: CaseLayout,
});

const TABS = [
  { to: "checklist", label: "Checklist" },
  { to: "collection", label: "Collection" },
  { to: "validation", label: "Validation" },
  { to: "readiness", label: "Readiness" },
  { to: "portal", label: "Client portal" },
] as const;

function CaseLayout() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  if (!c) {
    return (
      <div className="px-6 py-10 text-[13px] text-muted-foreground">
        Case {caseId} is not in this workspace.{" "}
        <Link to="/docready" className="font-medium text-primary hover:underline">
          Back to the Readiness Console
        </Link>
        .
      </div>
    );
  }

  const r = readiness(c);

  return (
    <div>
      <div className="border-b border-border bg-surface-muted/60 px-6 pt-4">
        <div className="rounded-md border border-border bg-surface shadow-sm">
          <div className="flex flex-wrap items-stretch justify-between gap-x-8 gap-y-4 border-l-2 border-primary px-4 py-3.5">
            <div className="min-w-0">
              <p className="field-label">
                DocReady case · {c.segment} enterprise · {c.constitution}
              </p>
              <h1 className="text-[19px] font-semibold tracking-tight text-foreground">{c.borrower}</h1>
              <div className="tabular mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                <span>{c.id}</span>
                <span className="text-border">|</span>
                <span>PAN {c.pan}</span>
                <span className="text-border">|</span>
                <span>GSTIN {c.gstin}</span>
                <span className="text-border">|</span>
                <span>Udyam {c.udyam}</span>
                <span className="text-border">|</span>
                <span>
                  {c.branch} · {c.rm}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <div className="min-w-[168px]">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="field-label">Readiness</span>
                  <span className="tabular text-[15px] font-semibold leading-none text-foreground">{r.score}%</span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      r.reviewGate ? "bg-positive" : r.blockingOpen > 0 ? "bg-destructive" : "bg-flag",
                    )}
                    style={{ width: `${r.score}%` }}
                  />
                </div>
                <p className="tabular mt-1 text-[11px] text-muted-foreground">
                  {r.outstanding} outstanding · 85% review gate
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-border sm:border-l sm:pl-6">
                <div>
                  <span className="field-label block">Ask</span>
                  <span className="tabular text-[12.5px] text-foreground">{c.requested}</span>
                </div>
                <div>
                  <span className="field-label block">Target sanction</span>
                  <span className="tabular text-[12.5px] text-foreground">{c.targetSanction}</span>
                </div>
              </div>

              {c.handedOffTo ? (
                <Link
                  to="/appraisals/$id/identity"
                  params={{ id: c.handedOffTo }}
                  className="rounded border border-positive/40 bg-positive-soft px-2.5 py-1.5 text-[11.5px] font-medium text-positive"
                >
                  Appraisal {c.handedOffTo}
                  <ArrowRight className="ml-0.5 inline h-3 w-3" />
                </Link>
              ) : r.blockingOpen > 0 ? (
                <Link
                  to="/docready/$caseId/readiness"
                  params={{ caseId: c.id }}
                  className="rounded border border-destructive/35 bg-destructive/10 px-2.5 py-1.5 text-[11.5px] font-medium text-destructive"
                >
                  {r.blockingOpen} blocking gap{r.blockingOpen === 1 ? "" : "s"}
                  <ArrowRight className="ml-0.5 inline h-3 w-3" />
                </Link>
              ) : (
                <span className="inline-flex items-center gap-1 rounded border border-positive/40 bg-positive-soft px-2.5 py-1.5 text-[11.5px] font-medium text-positive">
                  <ShieldCheck className="h-3 w-3" /> Ready for handoff
                </span>
              )}
            </div>
          </div>
        </div>

        <nav className="-mb-px mt-3 flex flex-wrap gap-4">
          {TABS.map((t) => {
            const to = `/docready/${c.id}/${t.to}`;
            const active = pathname === to;
            return (
              <Link
                key={t.to}
                to={to}
                className={cn(
                  "border-b-2 pb-2 text-[12.5px] font-medium transition-colors",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                )}
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
      </div>


      <Outlet />
    </div>
  );
}
