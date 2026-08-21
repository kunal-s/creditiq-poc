import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Sparkles, FileText, GitCompareArrows } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/identity/chips";
import { docReadyActions, useDocReadyCase, type CheckOutcome } from "@/data/docready";
import { StatusChip } from "@/routes/docready.$caseId.checklist";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { openingPage } from "@/data/doc-manifest";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId/validation")({
  head: () => {
    const title = "DocReady Validation — CreditIQ";
    const description =
      "Automated document checks — legibility, period coverage, attestation and identifier match — with the exact defect behind every rejection.";
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
  component: ValidationScreen,
});

const ICON: Record<CheckOutcome, typeof CheckCircle2> = {
  pass: CheckCircle2,
  warn: AlertTriangle,
  fail: XCircle,
};
const TONE: Record<CheckOutcome, string> = {
  pass: "text-positive",
  warn: "text-flag",
  fail: "text-destructive",
};

const EXPLANATIONS: Record<string, string> = {
  "property-docs":
    "Extraction was clean at 91% — the defect is not the document, it is what the document says. The title deed for the Coimbatore industrial unit records a mortgage in favour of Meridian Bank dated March 2024. That is read against two other documents already on file: the client's own declaration of nil existing facilities dated 06 August 2026, and the CCB bank statement set, which covers one account when the client has declared a second account with Meridian Bank ending 8830. Three documents, cross-read at collection time, produce a contradiction that would otherwise have surfaced only at appraisal. The re-ask asks Lakshmi Iyer to explain the charge, and a charge search has been raised in parallel.",
  "bank-stmt":
    "Legibility and period coverage both passed for the CCB current account: twelve continuous months to 31 July 2026 with no gap. Account coverage failed. The application declares two operating accounts and only one has been supplied; the Meridian Bank account ending 8830 is absent. Drawing power and turnover-to-credits testing cannot be completed on one account of two, so this is blocking rather than a caveat.",
  "stock-statement":
    "Extraction is reliable at 88% and the format is the bank's own. The failure is recency: the statement is drawn as at 30 June 2026, which is 52 days old at today's date against a 30-day maximum for stock and book-debt statements under CCB working-capital policy. Drawing power on a INR 2.85 cr cash credit limit cannot be computed on a stock position that old, so the re-ask is specific — the same statement drawn as at 31 July 2026.",
  "board-resolution":
    "The text of the resolution is correct and names the right facility and the right authorised signatories. Two form rules failed: it carries no director signature, and it is not on company letterhead. A borrowing resolution that is unsigned is not evidence of authority, so it cannot be cleared. The re-ask is narrow — the same resolution, signed by both directors, on Southgate letterhead.",
  gst:
    "The eight returns supplied are genuine GSTR-3B filings and reconcile internally. Coverage failed: the requirement is twelve months and the set runs December 2025 to July 2026. August to November 2025 are absent, which is the exact ask. Nothing about the filings that did arrive is in doubt.",
  "fs-fy2026-prov":
    "The profit and loss for the part year is present and legible. Pages 3 to 5 are absent, which removes the balance sheet entirely, so no working-capital cycle or leverage position can be read for the current year. The audited FY2024 and FY2025 sets are unaffected and remain in the evidence set.",
};

function ValidationScreen() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  const [open, setOpen] = useState<string | null>("property-docs");
  const viewer = useDocViewer();

  if (!c) return null;
  const checked = c.items.filter((i) => (i.checks?.length ?? 0) > 0);
  const failing = checked.filter((i) => i.checks?.some((k) => k.outcome === "fail"));
  const warning = checked.filter(
    (i) => !i.checks?.some((k) => k.outcome === "fail") && i.checks?.some((k) => k.outcome === "warn"),
  );

  return (
    <div className="space-y-4 px-6 py-5">
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "Documents checked", value: checked.length, note: "machine checks run on receipt" },
          { label: "Failing a check", value: failing.length, note: "re-ask issued", tone: "text-destructive" },
          { label: "Passing with a caveat", value: warning.length, note: "usable, noted in the memo", tone: "text-flag" },
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
        title="Machine checks by document"
        subtitle="A rejection is only useful if it names the defect. Every failure below states the rule, the expected value and what arrived."
      >
        <ul className="divide-y divide-border">
          {checked.map((item) => {
            const expanded = open === item.id;
            const worst: CheckOutcome = item.checks?.some((k) => k.outcome === "fail")
              ? "fail"
              : item.checks?.some((k) => k.outcome === "warn")
                ? "warn"
                : "pass";
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => setOpen(expanded ? null : item.id)}
                  className="flex w-full flex-wrap items-center gap-2 px-4 py-2.5 text-left hover:bg-surface-muted/60"
                >
                  <span className="text-[13px] font-medium text-foreground">{item.name}</span>
                  {viewer.doc(item.fileName) ? (
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => {
                        e.stopPropagation();
                        viewer.open({ mode: "single", filename: item.fileName! });
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          e.stopPropagation();
                          viewer.open({ mode: "single", filename: item.fileName! });
                        }
                      }}
                      className="tabular inline-flex items-center gap-1 rounded border border-border bg-surface px-1.5 py-0.5 text-[11px] font-medium text-primary hover:bg-muted"
                    >
                      <FileText className="h-3 w-3" /> {item.fileName}
                    </span>
                  ) : (
                    <span className="tabular text-[11px] text-muted-foreground">{item.fileName}</span>
                  )}
                  <span className="ml-auto flex items-center gap-2">
                    <span className={cn("text-[11.5px] font-medium", TONE[worst])}>
                      {worst === "fail" ? "Check failed" : worst === "warn" ? "Caveat" : "All checks passed"}
                    </span>
                    <StatusChip status={item.status} />
                  </span>
                </button>

                {expanded && (
                  <div className="space-y-3 border-t border-border bg-surface-muted/40 px-4 py-3">
                    <ul className="space-y-1.5">
                      {item.checks?.map((k) => {
                        const Icon = ICON[k.outcome];
                        return (
                          <li key={k.key} className="flex items-start gap-2 text-[12.5px]">
                            <Icon className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", TONE[k.outcome])} />
                            <span>
                              <span className="font-medium text-foreground">{k.label}</span>
                              <span className="text-muted-foreground"> — {k.detail}</span>
                              {(() => {
                                const doc = viewer.doc(item.fileName);
                                const counterpart = doc?.contradicts?.[0];
                                if (k.outcome !== "fail" || !doc || !counterpart) return null;
                                const other = viewer.doc(counterpart);
                                return (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      viewer.open({
                                        mode: "compare",
                                        left: { filename: doc.filename!, page: openingPage(doc) },
                                        right: { filename: counterpart, page: openingPage(other) },
                                      })
                                    }
                                    className="ml-1.5 inline-flex items-center gap-1 rounded border border-destructive/35 bg-destructive/10 px-1.5 py-0.5 text-[11px] font-medium text-destructive align-middle hover:bg-destructive/15"
                                  >
                                    <GitCompareArrows className="h-3 w-3" /> Compare both documents
                                  </button>
                                );
                              })()}
                            </span>
                          </li>
                        );
                      })}
                    </ul>

                    {item.rejection && (
                      <p className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] leading-relaxed text-destructive">
                        Re-ask sent to the client — {item.rejection}
                      </p>
                    )}

                    {EXPLANATIONS[item.id] && (
                      <div className="rounded border border-border bg-surface p-3">
                        <p className="flex items-center gap-1.5 text-[12.5px] font-semibold">
                          <Sparkles className="h-3.5 w-3.5 text-primary" /> Why this outcome
                        </p>
                        <p className="mt-1.5 max-w-4xl text-[12.5px] leading-relaxed text-muted-foreground">
                          {EXPLANATIONS[item.id]}
                        </p>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2">
                      {item.status !== "accepted" && (
                        <button
                          type="button"
                          onClick={() => {
                            docReadyActions.accept(c.id, item.id);
                            toast.success("Accepted despite the caveat, reason recorded");
                          }}
                          className="rounded border border-positive/40 bg-positive-soft px-2.5 py-1 text-[12px] font-medium text-positive hover:bg-positive-soft/70"
                        >
                          Accept with the caveat noted
                        </button>
                      )}
                      {item.status !== "rejected" && (
                        <button
                          type="button"
                          onClick={() => {
                            docReadyActions.reject(
                              c.id,
                              item.id,
                              "Analyst returned the document after review of the machine checks; the failing rule was quoted to the client.",
                            );
                            toast("Precise re-ask issued");
                          }}
                          className="rounded border border-border px-2.5 py-1 text-[12px] font-medium hover:bg-muted"
                        >
                          Return to client
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </Panel>
    </div>
  );
}
