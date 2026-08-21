import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ChevronDown, ChevronRight, Sparkles, Upload } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/identity/chips";
import {
  docReadyActions,
  readiness,
  SECTIONS,
  SECTION_WEIGHT,
  INSUFFICIENCY_LABEL,
  STATUS_LABEL,
  useDocReadyCase,
  type ChecklistItem,
  type DocStatus,
} from "@/data/docready";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId/checklist")({
  head: () => {
    const title = "DocReady Checklist — CreditIQ";
    const description =
      "The required document set for an MSME credit proposal, derived from constitution, segment and product, with the status and reason behind every item.";
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
  component: ChecklistScreen,
});

export const STATUS_TONE: Record<DocStatus, string> = {
  accepted: "border-positive/30 bg-positive-soft text-positive",
  waived: "border-border bg-surface-muted text-muted-foreground",
  received: "border-primary/35 bg-primary/10 text-primary",
  rejected: "border-destructive/30 bg-destructive/10 text-destructive",
  requested: "border-flag/35 bg-flag-soft text-flag-foreground",
  "not-requested": "border-border bg-surface-muted text-muted-foreground",
};

export function StatusChip({ status }: { status: DocStatus }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[10.5px] font-medium",
        STATUS_TONE[status],
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

const CATEGORIES: ChecklistItem["category"][] = SECTIONS;

function ChecklistScreen() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  const [open, setOpen] = useState<string | null>("property-docs");
  const [derived, setDerived] = useState(false);

  if (!c) return null;
  const r = readiness(c);

  return (
    <div className="grid gap-4 px-6 py-5 [@media(min-width:1500px)]:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-4">
        <Panel
          title="Required document set"
          subtitle={`${r.total} requirements derived from ${c.constitution.toLowerCase()}, ${c.segment.toLowerCase()} segment and the ${c.product.toLowerCase()} ask — not a static list. Blocking items stop credit review; the rest do not.`}
          action={
            <button
              type="button"
              onClick={() => docReadyActions.sendReminder(c.id)}
              className="rounded border border-border px-2.5 py-1 text-[12px] font-medium hover:bg-muted"
            >
              Chase everything outstanding
            </button>
          }
        >
          <div className="divide-y divide-border">
            {CATEGORIES.filter((cat) => c.items.some((i) => i.category === cat)).map((cat) => (
              <div key={cat}>
                <p className="flex items-center justify-between gap-2 bg-surface-muted/70 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  <span>{cat}</span>
                  <span className="tabular font-medium normal-case tracking-normal">
                    weight {SECTION_WEIGHT[cat]}%
                  </span>
                </p>
                <ul className="divide-y divide-border">
                  {c.items
                    .filter((i) => i.category === cat)
                    .map((item) => {
                      const expanded = open === item.id;
                      return (
                        <li key={item.id}>
                          <button
                            type="button"
                            onClick={() => setOpen(expanded ? null : item.id)}
                            className="flex w-full items-start gap-2.5 px-4 py-2.5 text-left hover:bg-surface-muted/60"
                          >
                            {expanded ? (
                              <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                            )}
                            <span className="min-w-0 flex-1">
                              <span className="flex flex-wrap items-center gap-2">
                                <span className="text-[13px] font-medium text-foreground">{item.name}</span>
                                {item.blocking && (
                                  <span className="rounded border border-destructive/25 bg-destructive/5 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-destructive">
                                    Blocking
                                  </span>
                                )}
                                {item.insufficiency && (
                                  <span className="rounded border border-flag/35 bg-flag-soft px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-flag-foreground">
                                    {INSUFFICIENCY_LABEL[item.insufficiency]}
                                  </span>
                                )}
                                {item.escalate && (
                                  <span className="rounded border border-destructive/35 bg-destructive/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-destructive">
                                    Due for escalation
                                  </span>
                                )}
                              </span>
                              <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
                                {item.basis}
                                {typeof item.confidence === "number" && ` · extraction confidence ${item.confidence}%`}
                                {typeof item.ageDays === "number" &&
                                  item.status !== "accepted" &&
                                  ` · open ${item.ageDays} days`}
                                {typeof item.remindersSent === "number" &&
                                  ` · ${item.remindersSent} reminder${item.remindersSent === 1 ? "" : "s"} sent`}
                              </span>
                            </span>
                            <StatusChip status={item.status} />
                          </button>

                          {expanded && (
                            <div className="space-y-3 border-t border-border bg-surface-muted/40 px-4 py-3 pl-11">
                              <p className="max-w-3xl text-[12.5px] leading-relaxed text-foreground">{item.why}</p>

                              {item.fileName && (
                                <dl className="grid gap-x-6 gap-y-1 text-[12px] sm:grid-cols-2">
                                  <div className="flex gap-2">
                                    <dt className="w-24 shrink-0 text-muted-foreground">File</dt>
                                    <dd className="min-w-0 text-foreground">{item.fileName}</dd>
                                  </div>
                                  <div className="flex gap-2">
                                    <dt className="w-24 shrink-0 text-muted-foreground">Received</dt>
                                    <dd className="text-foreground">{item.receivedAt}</dd>
                                  </div>
                                  <div className="flex gap-2">
                                    <dt className="w-24 shrink-0 text-muted-foreground">From</dt>
                                    <dd className="min-w-0 text-foreground">{item.receivedFrom}</dd>
                                  </div>
                                  <div className="flex gap-2">
                                    <dt className="w-24 shrink-0 text-muted-foreground">Extent</dt>
                                    <dd className="text-foreground">{item.pages}</dd>
                                  </div>
                                </dl>
                              )}

                              {item.rejection && (
                                <p className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] leading-relaxed text-destructive">
                                  {item.insufficiency ? INSUFFICIENCY_LABEL[item.insufficiency] : "Insufficient"} —{" "}
                                  {item.rejection}
                                </p>
                              )}
                              {item.waiverReason && (
                                <p className="rounded border border-border bg-surface px-3 py-2 text-[12px] leading-relaxed text-muted-foreground">
                                  {item.waiverReason}
                                </p>
                              )}

                              <div className="flex flex-wrap gap-2">
                                {(item.status === "not-requested" || item.status === "rejected") && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      docReadyActions.request(c.id, item.id);
                                      toast.success("Request added to the client's open ask");
                                    }}
                                    className="rounded bg-primary px-2.5 py-1 text-[12px] font-medium text-primary-foreground hover:bg-primary/90"
                                  >
                                    {item.status === "rejected" ? "Send precise re-ask" : "Request from client"}
                                  </button>
                                )}
                                {item.status === "requested" && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      docReadyActions.simulateUpload(c.id, item.id);
                                      toast.success("Client upload received, checks queued");
                                    }}
                                    className="inline-flex items-center gap-1.5 rounded border border-border px-2.5 py-1 text-[12px] font-medium hover:bg-muted"
                                  >
                                    <Upload className="h-3.5 w-3.5" /> Simulate client upload
                                  </button>
                                )}
                                {(item.status === "received" || item.status === "rejected") && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      docReadyActions.accept(c.id, item.id);
                                      toast.success("Document accepted into the evidence set");
                                    }}
                                    className="rounded border border-positive/40 bg-positive-soft px-2.5 py-1 text-[12px] font-medium text-positive hover:bg-positive-soft/70"
                                  >
                                    Accept document
                                  </button>
                                )}
                                {item.status === "received" && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      docReadyActions.reject(
                                        c.id,
                                        item.id,
                                        "Analyst rejected on review; a precise re-ask has been issued to the client.",
                                      );
                                      toast("Re-ask issued to the client");
                                    }}
                                    className="rounded border border-border px-2.5 py-1 text-[12px] font-medium hover:bg-muted"
                                  >
                                    Reject with reason
                                  </button>
                                )}
                                {!item.blocking && item.status !== "waived" && item.status !== "accepted" && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      docReadyActions.waive(
                                        c.id,
                                        item.id,
                                        "Waived by Elena Rossi — not blocking for this product and segment; reason recorded for the examiner.",
                                      );
                                      toast("Waiver recorded with reason");
                                    }}
                                    className="rounded border border-border px-2.5 py-1 text-[12px] font-medium text-muted-foreground hover:bg-muted"
                                  >
                                    Waive with reason
                                  </button>
                                )}
                                {item.checks && item.checks.length > 0 && (
                                  <Link
                                    to="/docready/$caseId/validation"
                                    params={{ caseId: c.id }}
                                    className="rounded border border-border px-2.5 py-1 text-[12px] font-medium text-primary hover:bg-muted"
                                  >
                                    See machine checks
                                  </Link>
                                )}
                              </div>
                            </div>
                          )}
                        </li>
                      );
                    })}
                </ul>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="min-w-0 space-y-3">
        <div className="rounded border border-border bg-surface p-4">
          <p className="field-label">Readiness</p>
          <p className="tabular mt-1 text-[26px] font-semibold leading-none text-foreground">{r.score}%</p>
          <div className="mt-3 space-y-1.5 text-[12px]">
            {[
              { k: "Settled", v: `${r.accepted} of ${r.total}` },
              { k: "In review", v: r.inReview },
              { k: "Outstanding", v: r.outstanding },
              { k: "Blocking open", v: r.blockingOpen },
            ].map((row) => (
              <div key={row.k} className="flex justify-between">
                <span className="text-muted-foreground">{row.k}</span>
                <span className="tabular text-foreground">{row.v}</span>
              </div>
            ))}
          </div>
          <Link
            to="/docready/$caseId/readiness"
            params={{ caseId: c.id }}
            className="mt-3 block rounded border border-border px-3 py-1.5 text-center text-[12.5px] font-medium hover:bg-muted"
          >
            Open readiness and handoff
          </Link>
        </div>

        <div className="rounded border border-border bg-surface p-4">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold">
            <Sparkles className="h-3.5 w-3.5 text-primary" /> Derive the required set
          </p>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
            {derived
              ? "Re-derived against CCB SME checklist v3.1. Twelve items stand. Two would drop if the constitution were a proprietorship: director KYC and the board resolution. Two would be added above INR 5 cr: CMA data and a working capital projection — this ask is INR 4.55 cr, so they stay out. CGTMSE cover is not applicable because the term loan is secured on the Ichalkaranji unit."
              : "Re-derive the checklist from constitution, MSME segment, product mix and ticket size, and see which items policy would add or drop."}
          </p>
          <button
            type="button"
            onClick={() => {
              setDerived(true);
              toast.success("Checklist re-derived — no change to the twelve items");
            }}
            className="mt-3 w-full rounded bg-primary px-3 py-1.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
          >
            Re-derive with copilot
          </button>
        </div>

        <div className="rounded border border-border bg-surface p-4 text-[12.5px] leading-relaxed text-muted-foreground">
          <p className="field-label mb-1.5">Client contact</p>
          <p className="text-foreground">{c.contact.name}</p>
          <p>{c.contact.role}</p>
          <p className="tabular mt-1">{c.contact.phone}</p>
          <p className="tabular break-all">{c.contact.email}</p>
          <Link
            to="/docready/$caseId/portal"
            params={{ caseId: c.id }}
            className="mt-2 inline-block font-medium text-primary hover:underline"
          >
            See what the client sees
          </Link>
        </div>
      </div>
    </div>
  );
}
