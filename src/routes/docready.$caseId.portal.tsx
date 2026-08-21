import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, Lock, Upload, Building2 } from "lucide-react";
import { toast } from "sonner";
import { docReadyActions, useDocReadyCase } from "@/data/docready";
import { TENANT } from "@/data/seed";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId/portal")({
  head: () => {
    const title = "DocReady Client Portal Preview — CreditIQ";
    const description =
      "The borrower-facing upload view: only the documents still needed, why each is needed, and what was rejected and why.";
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
  component: PortalPreview,
});

function PortalPreview() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  if (!c) return null;

  const open = c.items.filter((i) => i.status === "requested" || i.status === "rejected");
  const done = c.items.filter((i) => i.status === "accepted");

  return (
    <div className="px-6 py-5">
      <div className="mb-3 flex flex-wrap items-center gap-2 rounded border border-border bg-surface-muted px-3 py-2 text-[12px] text-muted-foreground">
        <Lock className="h-3.5 w-3.5" />
        Preview of the borrower-facing view sent to {c.contact.name} ({c.contact.email}). Link expires 17 August 2026;
        uploads are encrypted and visible only to the {c.branch} credit team.
      </div>

      <div className="mx-auto max-w-3xl overflow-hidden rounded border border-border bg-surface">
        <div className="flex flex-wrap items-center gap-3 border-b border-border bg-surface-muted px-5 py-4">
          <span className="grid h-9 w-9 place-items-center rounded bg-primary text-[13px] font-bold text-primary-foreground">
            CI
          </span>
          <div className="min-w-0">
            <p className="text-[14px] font-semibold text-foreground">{TENANT.bank}</p>
            <p className="text-[11.5px] text-muted-foreground">
              Document request for {c.borrower} · reference {c.id}
            </p>
          </div>
        </div>

        <div className="space-y-4 px-5 py-5">
          <p className="text-[13px] leading-relaxed text-foreground">
            Dear {c.contact.name}, {open.length} item{open.length === 1 ? "" : "s"} {open.length === 1 ? "is" : "are"}{" "}
            still needed to complete your application for {c.requested} ({c.facilities}). They are grouped below by the
            part of your file they belong to, and numbered so you can work through them in order. You do not need to
            send anything else.
          </p>

          <div>
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <p className="field-label">Still needed — {open.length} item{open.length === 1 ? "" : "s"}</p>
              <p className="tabular text-[11.5px] text-muted-foreground">
                {done.length} of {done.length + open.length} already received
              </p>
            </div>

            {open.length === 0 ? (
              <p className="rounded border border-positive/30 bg-positive-soft px-3.5 py-3 text-[12.5px] text-positive">
                Nothing further is needed from you. Thank you.
              </p>
            ) : (
              <div className="space-y-4">
                {(() => {
                  let n = 0;
                  return SECTIONS.filter((s) => open.some((i) => i.category === s)).map((section) => {
                    const items = open.filter((i) => i.category === section);
                    return (
                      <div key={section}>
                        <p className="mb-1.5 flex items-baseline gap-2 border-b border-border pb-1 text-[12.5px] font-semibold text-foreground">
                          {SECTION_LABEL[section] ?? section}
                          <span className="tabular text-[11px] font-normal text-muted-foreground">
                            {items.length} item{items.length === 1 ? "" : "s"}
                          </span>
                        </p>
                        <ul className="space-y-2">
                          {items.map((i) => {
                            n += 1;
                            return (
                              <li
                                key={i.id}
                                className={cn(
                                  "rounded border px-3.5 py-3",
                                  i.status === "rejected"
                                    ? "border-destructive/30 bg-destructive/5"
                                    : "border-border bg-background",
                                )}
                              >
                                <div className="flex flex-wrap items-start justify-between gap-2">
                                  <div className="flex min-w-0 gap-2.5">
                                    <span className="tabular mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border border-border bg-surface-muted text-[11px] font-semibold text-muted-foreground">
                                      {n}
                                    </span>
                                    <div className="min-w-0">
                                      <p className="text-[13px] font-medium text-foreground">{i.name}</p>
                                      <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">{i.why}</p>
                                      {i.rejection && (
                                        <p className="mt-1.5 text-[12px] leading-relaxed text-destructive">
                                          Returned to you — {i.rejection}
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      docReadyActions.simulateUpload(c.id, i.id);
                                      toast.success(`${i.name} uploaded`);
                                    }}
                                    className="inline-flex shrink-0 items-center gap-1.5 rounded bg-primary px-2.5 py-1.5 text-[12px] font-medium text-primary-foreground hover:bg-primary/90"
                                  >
                                    <Upload className="h-3.5 w-3.5" /> Upload
                                  </button>
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    );
                  });
                })()}
              </div>
            )}
          </div>


          <div className="rounded border border-border bg-background px-3.5 py-3">
            <p className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
              <Building2 className="h-3.5 w-3.5 text-primary" /> Faster option for bank statements
            </p>
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
              Grant Account Aggregator consent for your operating accounts and we retrieve twelve months of statements
              directly, in about two minutes, with no PDFs to find. Consent covers statements only, for this
              application, and expires on 3 November 2026.
            </p>
            <button
              type="button"
              onClick={() => {
                docReadyActions.simulateUpload(c.id, "bank-stmt");
                toast.success("Consent granted — statements retrieved for both accounts");
              }}
              className="mt-2.5 rounded border border-primary/40 bg-primary/10 px-2.5 py-1.5 text-[12px] font-medium text-primary hover:bg-primary/15"
            >
              Grant consent and retrieve statements
            </button>
          </div>

          <div>
            <p className="field-label mb-2">Already received</p>
            <ul className="space-y-1">
              {done.map((i) => (
                <li key={i.id} className="flex items-start gap-2 text-[12.5px]">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" />
                  <span className="text-foreground">{i.name}</span>
                </li>
              ))}
            </ul>
          </div>

          <p className="border-t border-border pt-3 text-[11.5px] leading-relaxed text-muted-foreground">
            Questions? Contact {c.rm} at the {c.branch}. {TENANT.bank} will use these documents only to assess this
            credit application and retains them per its RBI-aligned retention policy.
          </p>
        </div>
      </div>
    </div>
  );
}
