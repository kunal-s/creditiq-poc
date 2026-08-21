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
      <div className="border-b border-border bg-surface px-6 py-3.5">
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
          <div className="min-w-0">
            <p className="field-label">
              DocReady case · {c.segment} enterprise · {c.constitution}
            </p>
            <h1 className="text-[18px] font-semibold tracking-tight text-foreground">{c.borrower}</h1>
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

          <div className="flex flex-wrap items-center gap-5 text-[11px]">
            <div>
              <span className="field-label block">Ask</span>
              <span className="tabular text-[12px] text-foreground">{c.requested}</span>
            </div>
            <div>
              <span className="field-label block">Readiness</span>
              <span className="tabular text-[12px] text-foreground">
                {r.score}% · {r.outstanding} outstanding
              </span>
            </div>
            <div>
              <span className="field-label block">Target sanction</span>
              <span className="tabular text-[12px] text-foreground">{c.targetSanction}</span>
            </div>
            {c.handedOffTo ? (
              <Link
                to="/appraisals/$id/identity"
                params={{ id: c.handedOffTo }}
                className="rounded border border-positive/40 bg-positive-soft px-2 py-1 text-[11px] font-medium text-positive"
              >
                Appraisal {c.handedOffTo}
                <ArrowRight className="ml-0.5 inline h-3 w-3" />
              </Link>
            ) : r.blockingOpen > 0 ? (
              <Link
                to="/docready/$caseId/readiness"
                params={{ caseId: c.id }}
                className="rounded border border-destructive/35 bg-destructive/10 px-2 py-1 text-[11px] font-medium text-destructive"
              >
                {r.blockingOpen} blocking gap{r.blockingOpen === 1 ? "" : "s"}
                <ArrowRight className="ml-0.5 inline h-3 w-3" />
              </Link>
            ) : (
              <span className="inline-flex items-center gap-1 rounded border border-positive/40 bg-positive-soft px-2 py-1 text-[11px] font-medium text-positive">
                <ShieldCheck className="h-3 w-3" /> Ready for handoff
              </span>
            )}
          </div>
        </div>

        <nav className="mt-3 flex flex-wrap gap-1">
          {TABS.map((t) => {
            const to = `/docready/${c.id}/${t.to}`;
            const active = pathname === to;
            return (
              <Link
                key={t.to}
                to={to}
                className={cn(
                  "rounded px-2.5 py-1 text-[12px] font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
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
