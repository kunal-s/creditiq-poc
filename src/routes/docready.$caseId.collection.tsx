import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Sparkles, Send } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/identity/chips";
import { docReadyActions, useDocReadyCase, type ChaseEvent } from "@/data/docready";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId/collection")({
  head: () => {
    const title = "DocReady Collection Trail — CreditIQ";
    const description =
      "Every request, reminder, client upload, rejection and waiver on a document collection case, recorded against the case rather than lost in an inbox.";
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
  component: CollectionScreen,
});

const KIND_TONE: Record<ChaseEvent["kind"], string> = {
  request: "border-primary/40 bg-primary/10 text-primary",
  reminder: "border-flag/35 bg-flag-soft text-flag-foreground",
  upload: "border-border bg-surface-muted text-foreground",
  rejection: "border-destructive/30 bg-destructive/10 text-destructive",
  acceptance: "border-positive/30 bg-positive-soft text-positive",
  call: "border-border bg-surface-muted text-muted-foreground",
  waiver: "border-border bg-surface-muted text-muted-foreground",
  handoff: "border-positive/40 bg-positive-soft text-positive",
};

const KIND_LABEL: Record<ChaseEvent["kind"], string> = {
  request: "Request",
  reminder: "Reminder",
  upload: "Client upload",
  rejection: "Rejection",
  acceptance: "Acceptance",
  call: "Call note",
  waiver: "Waiver",
  handoff: "Handoff",
};

const DEFAULT_MESSAGE = `Dear Ms Kulkarni,

Thank you for the documents uploaded on 6 August. Four items remain before we can take Southgate Textiles' proposal into appraisal:

1. Audited FY2026 financial statements, signed with UDIN. CA Bhide has confirmed the audit closes on 19 August.
2. Director KYC for Vikram Sethi, plus an address proof dated within the last two months.
3. Bank statements for the twelve months to 31 July 2026 for all operating accounts. The quickest route is the Account Aggregator consent on your portal link, which takes about two minutes.
4. Stock and debtors statement as at 31 July 2026 on your usual format.

Nothing else is outstanding. The portal link in your earlier email remains valid until 17 August 2026.

Kind regards,
Rohan Deshpande, Ichalkaranji SME Branch`;

function CollectionScreen() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [drafted, setDrafted] = useState(false);

  if (!c) return null;
  const openItems = c.items.filter((i) => i.status === "requested" || i.status === "rejected");

  return (
    <div className="grid gap-4 px-6 py-5 [@media(min-width:1500px)]:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0">
        <Panel
          title="Collection trail"
          subtitle={`${c.chase.length} recorded events since the case opened on ${c.opened}. Chases are consolidated, so the client never receives four messages for four documents.`}
        >
          <ol className="divide-y divide-border">
            {[...c.chase].reverse().map((ev) => (
              <li key={ev.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "rounded border px-1.5 py-0.5 text-[10.5px] font-medium",
                      KIND_TONE[ev.kind],
                    )}
                  >
                    {KIND_LABEL[ev.kind]}
                  </span>
                  <span className="text-[13px] font-medium text-foreground">{ev.title}</span>
                  <span className="tabular ml-auto text-[11px] text-muted-foreground">{ev.at}</span>
                </div>
                <p className="mt-1 text-[11.5px] text-muted-foreground">{ev.actor}</p>
                <p className="mt-1.5 max-w-4xl text-[12.5px] leading-relaxed text-foreground">{ev.detail}</p>
                {ev.items && ev.items.length > 0 && (
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {ev.items.map((i) => (
                      <li
                        key={i}
                        className="rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[10.5px] text-muted-foreground"
                      >
                        {i}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        </Panel>
      </div>

      <div className="min-w-0 space-y-3">
        <div className="rounded border border-border bg-surface p-4">
          <p className="field-label">The open ask</p>
          {openItems.length === 0 ? (
            <p className="mt-1.5 text-[12.5px] text-muted-foreground">
              Nothing is outstanding with the client.
            </p>
          ) : (
            <ul className="mt-1.5 space-y-1.5 text-[12.5px]">
              {openItems.map((i) => (
                <li key={i.id} className="flex items-start gap-2">
                  <span
                    className={cn(
                      "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                      i.status === "rejected" ? "bg-destructive" : "bg-flag",
                    )}
                  />
                  <span className="text-foreground">
                    {i.name}
                    <span className="block text-[11.5px] text-muted-foreground">
                      {i.status === "rejected" ? "rejected, re-ask outstanding" : "requested, not yet received"}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded border border-border bg-surface">
          <div className="border-b border-border px-4 py-2.5">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> Draft the next chase
            </p>
            <p className="mt-1 text-[11.5px] text-muted-foreground">
              {drafted
                ? "Redrafted from the current open ask. Edit before sending — the wording is yours."
                : "Copilot writes from the open ask only, naming the exact defect on rejected items."}
            </p>
          </div>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            aria-label="Chase message"
            className="h-72 w-full resize-y bg-background px-4 py-3 text-[12.5px] leading-relaxed text-foreground focus:outline-none"
          />
          <div className="flex flex-wrap gap-2 border-t border-border px-4 py-2.5">
            <button
              type="button"
              onClick={() => {
                setDrafted(true);
                setMessage(DEFAULT_MESSAGE);
                toast.success("Chase redrafted from the open ask");
              }}
              className="rounded border border-border px-2.5 py-1 text-[12px] font-medium hover:bg-muted"
            >
              Redraft with copilot
            </button>
            <button
              type="button"
              onClick={() => {
                docReadyActions.sendReminder(c.id);
                toast.success(`Reminder sent to ${c.contact.name}`);
              }}
              className="inline-flex items-center gap-1.5 rounded bg-primary px-2.5 py-1 text-[12px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Send className="h-3.5 w-3.5" /> Send to {c.contact.name.split(" ")[0]}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
