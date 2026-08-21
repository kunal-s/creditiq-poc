import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, ShieldCheck, AlertTriangle, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/identity/chips";
import { docReadyActions, readiness, useDocReadyCase } from "@/data/docready";
import { StatusChip } from "@/routes/docready.$caseId.checklist";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId/readiness")({
  head: () => {
    const title = "DocReady Readiness and Handoff — CreditIQ";
    const description =
      "Weighted readiness score, blocking versus non-blocking gaps, and the handoff that carries a complete MSME file into credit appraisal.";
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
  component: ReadinessScreen,
});

function ReadinessScreen() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  const navigate = useNavigate();

  if (!c) return null;
  const r = readiness(c);
  const blocking = c.items.filter((i) => i.blocking && i.status !== "accepted" && i.status !== "waived");
  const soft = c.items.filter((i) => !i.blocking && i.status !== "accepted" && i.status !== "waived");
  const accepted = c.items.filter((i) => i.status === "accepted");

  const handoff = () => {
    const camId = docReadyActions.handoff(c.id);
    if (!camId) {
      toast.error("Blocking documents are still outstanding");
      return;
    }
    toast.success(`Appraisal ${camId} created for ${c.borrower}`);
    void navigate({ to: "/appraisals/$id/identity", params: { id: camId } });
  };

  return (
    <div className="grid gap-4 px-6 py-5 [@media(min-width:1500px)]:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-4">
        {blocking.length > 0 ? (
          <div className="flex flex-wrap items-start gap-3 rounded border border-destructive/35 bg-destructive/10 px-4 py-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-destructive">
                {blocking.length} blocking document{blocking.length === 1 ? "" : "s"} outstanding — handoff is disabled
              </p>
              <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-destructive/90">
                An appraisal started on this file would stall at spread or cross-verification, so the handoff stays
                shut until each of these is accepted or waived with a reason.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-start gap-3 rounded border border-positive/40 bg-positive-soft px-4 py-3">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-positive">
                File is complete enough to underwrite
              </p>
              <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-positive/90">
                Nothing blocking remains. Handing off creates the appraisal, carries the identifiers and facility ask
                across, and registers the accepted documents as already present.
              </p>
            </div>
          </div>
        )}

        <Panel title="Readiness score" subtitle="Weighted by document importance, not a plain count of files.">
          <div className="px-4 py-4">
            <div className="flex items-end gap-4">
              <p className="tabular text-[38px] font-semibold leading-none text-foreground">{r.score}%</p>
              <div className="flex-1">
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      r.score >= 90 ? "bg-positive" : r.score >= 65 ? "bg-flag" : "bg-destructive",
                    )}
                    style={{ width: `${r.score}%` }}
                  />
                </div>
                <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                  {r.accepted} of {r.total} items settled · {r.inReview} in review · {r.outstanding} outstanding
                </p>
              </div>
            </div>
          </div>
        </Panel>

        <Panel title="Blocking gaps" subtitle="Each of these stops the appraisal pipeline.">
          {blocking.length === 0 ? (
            <p className="px-4 py-3 text-[12.5px] text-muted-foreground">No blocking gap remains on this case.</p>
          ) : (
            <ul className="divide-y divide-border">
              {blocking.map((i) => (
                <li key={i.id} className="flex flex-wrap items-start gap-2 px-4 py-2.5">
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-medium text-foreground">{i.name}</span>
                    <span className="mt-0.5 block text-[12px] leading-relaxed text-muted-foreground">
                      {i.rejection ?? i.why}
                    </span>
                  </span>
                  <StatusChip status={i.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Non-blocking gaps" subtitle="Recorded, chased, but not allowed to hold the case up.">
          {soft.length === 0 ? (
            <p className="px-4 py-3 text-[12.5px] text-muted-foreground">Nothing outstanding outside the blocking set.</p>
          ) : (
            <ul className="divide-y divide-border">
              {soft.map((i) => (
                <li key={i.id} className="flex flex-wrap items-start gap-2 px-4 py-2.5">
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-medium text-foreground">{i.name}</span>
                    <span className="mt-0.5 block text-[12px] text-muted-foreground">{i.basis}</span>
                  </span>
                  <StatusChip status={i.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="min-w-0 space-y-3">
        <div className="rounded border border-border bg-surface p-4">
          <p className="field-label">Handoff into credit appraisal</p>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
            Creates a Credit Appraisal Memorandum for {c.borrower} and opens it at the identity step, with PAN, GSTIN,
            Udyam number, constitution, {c.facilities} and the {c.branch} relationship already carried across.
          </p>
          {c.handedOffTo ? (
            <Link
              to="/appraisals/$id/identity"
              params={{ id: c.handedOffTo }}
              className="mt-3 flex items-center justify-center gap-1.5 rounded border border-positive/40 bg-positive-soft px-3 py-2 text-[12.5px] font-medium text-positive"
            >
              Open appraisal {c.handedOffTo} <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          ) : (
            <button
              type="button"
              onClick={handoff}
              disabled={blocking.length > 0}
              className={cn(
                "mt-3 flex w-full items-center justify-center gap-1.5 rounded px-3 py-2 text-[12.5px] font-medium",
                blocking.length > 0
                  ? "cursor-not-allowed bg-muted text-muted-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90",
              )}
            >
              Start credit appraisal <ArrowRight className="h-3.5 w-3.5" />
            </button>
          )}
          <p className="mt-2 text-[11.5px] text-muted-foreground">
            {blocking.length > 0
              ? `Disabled until ${blocking.length} blocking item${blocking.length === 1 ? " is" : "s are"} settled.`
              : "The handoff is written to the audit trail with the accepted document set attached."}
          </p>
        </div>

        <div className="rounded border border-border bg-surface p-4">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold">
            <Sparkles className="h-3.5 w-3.5 text-primary" /> Predicted readiness
          </p>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
            {blocking.length > 0
              ? "On the auditor's 19 August commitment for the signed FY2026 statement, and the client's two-day median response on portal asks, this case reaches handoff on 20 August 2026 — nine days ahead of the 29 August target sanction date. The single risk is the bank statements: if Account Aggregator consent is not granted, manual statements for two accounts historically add four to six days."
              : "Nothing is pending. On the last four MSME cases, a file handed off at this readiness level reached sanction in 6.2 days against a 12-day book average."}
          </p>
        </div>

        <div className="rounded border border-border bg-surface p-4">
          <p className="field-label mb-2">Carried into appraisal</p>
          <ul className="space-y-1 text-[12px]">
            {accepted.map((i) => (
              <li key={i.id} className="flex items-start gap-2">
                <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0 text-positive" />
                <span className="text-foreground">{i.name}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11.5px] text-muted-foreground">
            The pipeline treats these as present, so the borrower is not asked for them a second time.
          </p>
        </div>
      </div>
    </div>
  );
}
