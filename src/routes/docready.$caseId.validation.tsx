import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/identity/chips";
import { docReadyActions, useDocReadyCase, type CheckOutcome } from "@/data/docready";
import { StatusChip } from "@/routes/docready.$caseId.checklist";
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
  "kyc-directors":
    "Two independent rules failed. Completeness compares the KYC set against the MCA director list for CIN U17120PN2011PTC141288, which carries three directors — Anita Kulkarni, Rajeev Kulkarni and Vikram Sethi; only the first two were covered. Recency applies the two-month address-proof rule under the KYC Master Direction, and the mobile bill supplied for Vikram Sethi is dated 12 January 2026, seven months old. Neither is a judgement call, so the re-ask names exactly those two defects and nothing else.",
  "fs-3y":
    "The FY2024 and FY2025 statements are audited, signed and carry UDINs, so they are accepted and already usable for two years of the spread. The FY2026 set fails attestation: no auditor signature, no UDIN and the balance sheet is headed 'provisional'. CCB ratio policy requires three audited years for a term loan of this size, so this is blocking. The auditor has committed to 19 August 2026, which still clears the 29 August target sanction date.",
  "sanction-others":
    "Legibility passed. Completeness is a warning rather than a failure: the Kolhapur District Co-operative Bank letter is genuine and readable, but the CIBIL commercial report shows two live term loans against this borrower. One sanction letter is therefore missing, which understates total obligations and would flow through to the debt-service ratio at spread stage.",
  gst:
    "Coverage is complete for twenty-four months with no missing filing. The warning is filing discipline, not data quality: three FY2026 filings were late by 9, 14 and 17 days. That does not stop the appraisal, but it belongs in the memo's conduct narrative.",
};

function ValidationScreen() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  const [open, setOpen] = useState<string | null>("kyc-directors");

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
                  <span className="tabular text-[11px] text-muted-foreground">{item.fileName}</span>
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
