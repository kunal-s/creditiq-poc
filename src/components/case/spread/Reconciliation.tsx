import { CheckCircle2, Eye, TriangleAlert } from "lucide-react";
import { useState } from "react";
import type { Spread, SpreadCheck } from "@/api/types";
import { evidenceRequest, useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { inRupees } from "@/domain/statementEdits";
import { cn } from "@/lib/utils";

/** The statements checked against themselves: each balance sheet's two totals, and each year's figures against
 * the comparatives the next year's report prints. Where two disagree, the page of each is one click away. */
export function Reconciliation({ caseId, spread }: { caseId: string; spread: Spread }) {
  const [showAgreeing, setShowAgreeing] = useState(false);
  const checks = spread.checks ?? [];
  if (checks.length === 0) return null;
  const differing = checks.filter((c) => c.outcome === "differs");
  const agreeing = checks.filter((c) => c.outcome === "agrees");
  return (
    <section
      className="min-w-0 rounded border border-border bg-surface"
      data-testid="spread-reconciliation"
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <h3 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t("spreadPage.reconcile.title")}
        </h3>
        <span
          className={cn(
            "tabular text-[12px] font-medium",
            differing.length > 0 ? "text-flag-foreground" : "text-positive",
          )}
          data-testid="spread-reconciliation-summary"
        >
          {t("spreadPage.reconcile.summary", { agree: agreeing.length, total: checks.length })}
        </span>
      </header>
      {differing.length === 0 && (
        <p className="px-4 py-3 text-[12.5px] text-muted-foreground">
          {t("spreadPage.reconcile.allAgree")}
        </p>
      )}
      <ul className="divide-y divide-border">
        {differing.map((c) => (
          <CheckRow key={c.id} caseId={caseId} check={c} />
        ))}
        {showAgreeing && agreeing.map((c) => <CheckRow key={c.id} caseId={caseId} check={c} />)}
      </ul>
      {agreeing.length > 0 && (
        <div className="space-y-1 border-t border-border px-4 py-2.5">
          <button
            type="button"
            onClick={() => setShowAgreeing((v) => !v)}
            className="text-[12px] font-medium text-primary hover:underline"
            data-testid="spread-reconciliation-toggle"
          >
            {t(showAgreeing ? "spreadPage.reconcile.hide" : "spreadPage.reconcile.show")}
          </button>
          <p className="text-[11.5px] text-muted-foreground">
            {t("spreadPage.reconcile.tolerance", {
              n: inRupees(Math.max(...checks.map((c) => c.tolerance))),
            })}
          </p>
        </div>
      )}
    </section>
  );
}

function CheckRow({ caseId, check }: { caseId: string; check: SpreadCheck }) {
  const viewer = useDocViewer();
  const differs = check.outcome === "differs";
  const Icon = differs ? TriangleAlert : CheckCircle2;
  return (
    <li
      className="flex items-start gap-2.5 px-4 py-2.5"
      data-testid="spread-check"
      data-outcome={check.outcome}
    >
      <Icon
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0",
          differs ? "text-flag-foreground" : "text-positive",
        )}
        aria-hidden
      />
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-[12.5px] font-medium text-foreground">
          {check.label}
          <span className="sr-only">
            {" "}
            · {t(differs ? "spreadPage.reconcile.differs" : "spreadPage.reconcile.agrees")}
          </span>
        </p>
        <p className="text-[12px] text-muted-foreground">{check.detail}</p>
        <p className="tabular text-[11.5px] text-muted-foreground">
          {check.left_label}: {inRupees(check.left)} · {check.right_label}: {inRupees(check.right)}
        </p>
      </div>
      {(check.evidence ?? []).length > 0 && (
        <button
          type="button"
          onClick={() => {
            const request = evidenceRequest(caseId, check.evidence ?? []);
            if (request) viewer.open(request);
          }}
          title={t("spreadPage.reconcile.open")}
          aria-label={`${t("spreadPage.reconcile.open")}: ${check.label}`}
          className="mt-0.5 text-muted-foreground hover:text-primary"
          data-testid="spread-check-open"
        >
          <Eye className="h-4 w-4" aria-hidden />
        </button>
      )}
    </li>
  );
}
