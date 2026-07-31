import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CircleDashed,
  Send,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { CURRENT_USER, getAppraisal } from "@/data/seed";
import { FLAGS, OUTCOME_LABEL, useXVState } from "@/data/crossverify";
import { ROUTING, SECTIONS, declineMemo, isEdited, returnForData, submitMemo, useMemoState } from "@/data/memo";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/appraisals/$id/submission")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Submission and routing — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description =
      "Pre-submission checklist against the true state of the appraisal, then route the memo to the credit manager and the West Region credit committee.";
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
  component: SubmissionScreen,
});

function SubmissionScreen() {
  const { id } = Route.useParams();
  const a = getAppraisal(id);
  if (!a) throw notFound();

  const m = useMemoState();
  const xv = useXVState();
  const [returnReason, setReturnReason] = useState("");
  const [declineReason, setDeclineReason] = useState("");
  const [panel, setPanel] = useState<"none" | "return" | "decline">("none");

  const seriousOpen = FLAGS.filter((f) => f.severity === "serious" && !xv.adjudications[f.id]);
  const allFlagsDone = FLAGS.every((f) => xv.adjudications[f.id]);

  const checks: {
    key: string;
    label: string;
    detail: string;
    ok: boolean;
    to?: { label: string; el: React.ReactNode };
    hard: boolean;
  }[] = [
    {
      key: "serious",
      label: "All serious cross-verification findings adjudicated",
      detail:
        seriousOpen.length === 0
          ? `XV-0418-01 (turnover) ${xv.adjudications["XV-0418-01"] ? OUTCOME_LABEL[xv.adjudications["XV-0418-01"]!.outcome].toLowerCase() : "adjudicated"} by ${xv.adjudications["XV-0418-01"]?.by ?? CURRENT_USER.name}.`
          : "XV-0418-01, declared turnover of INR 142.31 cr against GST of INR 119.83 cr and bank credits of INR 121.44 cr, is still open. Submission is blocked until it is dealt with.",
      ok: seriousOpen.length === 0,
      hard: true,
      to: {
        label: "Open the discrepancy board",
        el: (
          <Link
            to="/appraisals/$id/cross-verification"
            params={{ id: a.id }}
            className="text-[12px] font-medium text-primary hover:underline"
          >
            Open the discrepancy board →
          </Link>
        ),
      },
    },
    {
      key: "all-flags",
      label: "Moderate and mild findings dealt with",
      detail: allFlagsDone
        ? "All three findings carry a recorded outcome and reasoning."
        : `${FLAGS.filter((f) => !xv.adjudications[f.id] && f.severity !== "serious").length} finding(s) still open. These do not block, but they will be listed as open to the committee.`,
      ok: allFlagsDone,
      hard: false,
    },
    {
      key: "sources",
      label: "All sources accounted for",
      detail:
        "GST direct from GSTN, bureau from TransUnion CIBIL, registry from MCA and CERSAI, bank data under consent CONS-2026-0418-A, financials by fallback upload. Adverse media returned partial on the first attempt and completed on retry.",
      ok: true,
      hard: true,
    },
    {
      key: "rating",
      label: "Rating set and confirmed by the analyst",
      detail: m.ratingConfirmed
        ? `${m.rating} confirmed by ${CURRENT_USER.name}, ${CURRENT_USER.role}.`
        : `${m.rating} is still the model's first cut. The rating must be confirmed by a human before the memo leaves this desk.`,
      ok: m.ratingConfirmed,
      hard: true,
      to: {
        label: "Rating panel",
        el: (
          <Link
            to="/appraisals/$id/rating"
            params={{ id: a.id }}
            className="text-[12px] font-medium text-primary hover:underline"
          >
            Settle the rating →
          </Link>
        ),
      },
    },
    {
      key: "recommendation",
      label: "Recommendation confirmed",
      detail: m.recommendationConfirmed
        ? "Section 8 carries the analyst's confirmed recommendation, reduced limit of INR 15.80 cr with five conditions."
        : "The recommendation is still as drafted and has not been confirmed.",
      ok: m.recommendationConfirmed,
      hard: true,
    },
    {
      key: "memo",
      label: "Memo reviewed section by section",
      detail: `${Object.keys(m.edits).length} of ${SECTIONS.length} sections carry your wording; ${SECTIONS.filter((s) => !isEdited(m, s.id)).length} remain as drafted. Every quantitative claim is cited.`,
      ok: true,
      hard: false,
    },
    {
      key: "overrides",
      label: "Overrides carry a reason",
      detail:
        m.overrides.length === 0
          ? "No figure has been overridden. The memo carries the extracted and confirmed values."
          : `${m.overrides.length} override(s) recorded, each with the original value, your reason, your name and the timestamp.`,
      ok: true,
      hard: false,
    },
  ];

  const blockers = checks.filter((c) => c.hard && !c.ok);
  const canSubmit = blockers.length === 0;

  const submit = () => {
    if (!canSubmit) {
      toast.error("Submission is blocked", { description: blockers[0]!.label });
      return;
    }
    submitMemo(`${CURRENT_USER.name} · ${CURRENT_USER.role}`);
    toast.success("Memo submitted and routed", {
      description: `${ROUTING.reviewer}, ${ROUTING.reviewerRole}, has it. Committee sitting ${ROUTING.committeeSitting}.`,
    });
  };

  return (
    <div>
      <PageHeader
        eyebrow={`Appraisal ${a.id} · Submission and routing`}
        title="Submission and routing"
        purpose={`Everything the credit committee will see, checked against the true state of this appraisal before it leaves your desk. Routed to ${ROUTING.reviewer}, ${ROUTING.reviewerRole}, then to the ${ROUTING.committee}.`}
        actions={
          <>
            <Link
              to="/appraisals/$id/draft"
              params={{ id: a.id }}
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Draft
            </Link>
            <Link
              to="/memos"
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              Memo library
            </Link>
          </>
        }
      />

      <div className="grid gap-4 px-6 py-5 xl:grid-cols-[minmax(0,1fr)_310px] 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-4">
          {m.submitted ? (
            <div className="rounded border border-positive/30 bg-positive-soft px-4 py-3">
              <p className="flex items-center gap-2 text-[13.5px] font-semibold text-foreground">
                <Check className="h-4 w-4 text-positive" /> Submitted {m.submitted.at} · reference{" "}
                {m.submitted.reference}
              </p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-foreground/90">
                The memo for {a.borrower} is with {m.submitted.to} for review, targeted {ROUTING.reviewTarget}, and is
                listed for the {ROUTING.committee} sitting on {ROUTING.committeeSitting}. It now appears in the{" "}
                <Link to="/memos" className="font-medium text-primary hover:underline">
                  memo library
                </Link>{" "}
                and in {ROUTING.reviewer}'s review queue. The evidence pack, all citations and the override trail travel
                with it.
              </p>
            </div>
          ) : !canSubmit ? (
            <div className="flex items-start gap-2 rounded border border-critical/30 bg-critical-soft px-4 py-3">
              <ShieldAlert className="mt-[2px] h-4 w-4 shrink-0 text-critical" />
              <p className="text-[12.5px] leading-relaxed text-foreground">
                Submission is closed. {blockers.length} item{blockers.length > 1 ? "s" : ""} on the checklist{" "}
                {blockers.length > 1 ? "are" : "is"} not satisfied: {blockers.map((b) => b.label).join("; ")}.
              </p>
            </div>
          ) : (
            <div className="flex items-start gap-2 rounded border border-positive/30 bg-positive-soft px-4 py-3">
              <Check className="mt-[2px] h-4 w-4 shrink-0 text-positive" />
              <p className="text-[12.5px] leading-relaxed text-foreground">
                Every hard check is satisfied. The memo is ready to route to {ROUTING.reviewer}.
              </p>
            </div>
          )}

          <Panel title="Pre-submission checklist" subtitle="Read from the live state of this appraisal, not from a template.">
            <ul className="divide-y divide-border">
              {checks.map((c) => (
                <li key={c.key} className="flex items-start gap-3 px-4 py-3">
                  {c.ok ? (
                    <Check className="mt-[2px] h-4 w-4 shrink-0 text-positive" />
                  ) : c.hard ? (
                    <AlertTriangle className="mt-[2px] h-4 w-4 shrink-0 text-critical" />
                  ) : (
                    <CircleDashed className="mt-[2px] h-4 w-4 shrink-0 text-flag" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p
                      className={cn(
                        "text-[12.5px] font-medium",
                        c.ok ? "text-foreground" : c.hard ? "text-critical" : "text-flag-foreground",
                      )}
                    >
                      {c.label}
                      {!c.hard && <span className="ml-1.5 text-[11px] font-normal text-muted-foreground">advisory</span>}
                    </p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">{c.detail}</p>
                    {!c.ok && c.to && <div className="mt-1">{c.to.el}</div>}
                  </div>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Final confirmation">
            <div className="space-y-3 p-4">
              <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                On submitting, you confirm that the memo reflects your assessment, that every override carries your
                reason, and that no unresolved serious finding is being passed on silently. Your name, role and the
                timestamp are attached to the submission.
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={submit}
                  disabled={!canSubmit || Boolean(m.submitted)}
                  className="flex h-9 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Send className="h-3.5 w-3.5" />
                  {m.submitted ? "Submitted" : `Submit and route to ${ROUTING.reviewer}`}
                </button>
                <button
                  type="button"
                  onClick={() => setPanel(panel === "return" ? "none" : "return")}
                  className="h-9 rounded border border-border bg-surface px-3 text-[12.5px] text-foreground hover:bg-muted"
                >
                  Return for more data
                </button>
                <button
                  type="button"
                  onClick={() => setPanel(panel === "decline" ? "none" : "decline")}
                  className="h-9 rounded border border-border bg-surface px-3 text-[12.5px] text-foreground hover:bg-muted"
                >
                  Mark declined
                </button>
              </div>

              {panel === "return" && (
                <div className="rounded border border-flag/30 bg-flag-soft/40 p-3">
                  <label className="text-[11.5px] text-muted-foreground">
                    What is still needed, and from whom
                    <input
                      value={returnReason}
                      onChange={(e) => setReturnReason(e.target.value)}
                      placeholder="e.g. Written turnover reconciliation from the borrower via Marcus Chen"
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      if (returnReason.trim().length < 8) {
                        toast.error("Say what is needed before returning the appraisal.");
                        return;
                      }
                      returnForData(returnReason.trim());
                      setPanel("none");
                      toast.success("Returned to data acquisition", {
                        description: "The request is recorded on the appraisal and notified to the RM.",
                      });
                    }}
                    className="mt-2 h-8 rounded bg-primary px-3 text-[12px] font-medium text-primary-foreground hover:opacity-90"
                  >
                    Return the appraisal
                  </button>
                </div>
              )}

              {panel === "decline" && (
                <div className="rounded border border-critical/30 bg-critical-soft/60 p-3">
                  <label className="text-[11.5px] text-muted-foreground">
                    Evidenced reason for declining — retained on the borrower's record
                    <input
                      value={declineReason}
                      onChange={(e) => setDeclineReason(e.target.value)}
                      placeholder="e.g. Turnover overstatement unexplained after two requests; XV-0418-01 refers"
                      className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      if (declineReason.trim().length < 8) {
                        toast.error("A decline must be evidenced.");
                        return;
                      }
                      declineMemo(declineReason.trim());
                      setPanel("none");
                      toast.success("Recorded as declined", {
                        description: "The reason and the evidence set are retained on the borrower's record.",
                      });
                    }}
                    className="mt-2 h-8 rounded bg-critical px-3 text-[12px] font-medium text-background hover:opacity-90"
                  >
                    Record decline
                  </button>
                </div>
              )}

              {m.returned && (
                <p className="flex items-start gap-2 text-[12.5px] text-flag-foreground">
                  <ArrowLeft className="mt-[2px] h-3.5 w-3.5" /> Returned {m.returned.at}: {m.returned.reason}
                </p>
              )}
              {m.declined && (
                <p className="flex items-start gap-2 text-[12.5px] text-critical">
                  <X className="mt-[2px] h-3.5 w-3.5" /> Declined {m.declined.at}: {m.declined.reason}
                </p>
              )}
            </div>
          </Panel>
        </div>

        <aside className="space-y-3">
          <Panel title="Routing">
            <ol className="divide-y divide-border">
              {[
                {
                  name: `${ROUTING.reviewer} · ${ROUTING.reviewerRole}`,
                  detail: `Review targeted ${ROUTING.reviewTarget}. ${ROUTING.slaNote}`,
                  state: m.submitted ? "In queue" : "Next",
                },
                {
                  name: ROUTING.committee,
                  detail: `Chaired by ${ROUTING.committeeChair}. Sitting ${ROUTING.committeeSitting}. Exposure of INR 25.25 cr is inside the committee's INR 50 cr delegation.`,
                  state: "After review",
                },
                {
                  name: "Sanction and documentation",
                  detail: "Sanction letter, charge modification with the registry, and the five recommended conditions.",
                  state: "On approval",
                },
              ].map((r) => (
                <li key={r.name} className="px-3 py-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[12.5px] font-medium text-foreground">{r.name}</p>
                    <span className="shrink-0 rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[10.5px] text-muted-foreground">
                      {r.state}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">{r.detail}</p>
                </li>
              ))}
            </ol>
          </Panel>

          <Panel title="What travels with the memo">
            <ul className="divide-y divide-border text-[12px]">
              {[
                ["Memo", `8 sections, CCB CAM template v4.2, ${Object.keys(m.edits).length} analyst-authored`],
                ["Evidence pack", "GST ledger, bureau report, MCA and CERSAI extracts, AA bank bundle, audited FS and ITR"],
                ["Findings", `3 cross-verification findings, ${Object.keys(xv.adjudications).length} adjudicated`],
                ["Overrides", m.overrides.length === 0 ? "None" : `${m.overrides.length}, each with reason and author`],
                ["Rating", `${m.rating}${m.ratingConfirmed ? ", confirmed by the analyst" : ", first cut"}`],
              ].map(([k, v]) => (
                <li key={k} className="flex items-baseline justify-between gap-3 px-3 py-2">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="text-right text-foreground">{v}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <div className="rounded border border-border bg-surface p-3">
            <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-foreground">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> Committee cover note
            </p>
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
              Ask the copilot to summarise this memo into a one-paragraph cover note for the committee papers, with the
              finding and the reduced limit up front.
            </p>
            <Link
              to="/appraisals/$id/draft"
              params={{ id: a.id }}
              className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
            >
              Back to the draft <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
