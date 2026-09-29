import { Link } from "@tanstack/react-router";
import type { CaseSummary, Stage } from "@/api/types";
import { formatInr } from "@/domain/cases";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

const stageTone: Record<Stage, string> = {
  Intake: "bg-muted text-muted-foreground",
  Readiness: "bg-info-soft text-info",
  Appraisal: "bg-accent text-accent-foreground",
  Outputs: "bg-accent text-accent-foreground",
  Completed: "bg-positive-soft text-positive",
};

export function CasesTable({ cases }: { cases: CaseSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-[12.5px]">
        <thead>
          <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
            <th className="px-4 py-2 font-medium">{t("term.borrower.title")}</th>
            <th className="px-3 py-2 font-medium">Facilities and amount</th>
            <th className="px-3 py-2 font-medium">{t("term.stage")}</th>
            <th className="px-3 py-2 font-medium">RM</th>
            <th className="px-3 py-2 font-medium">Created</th>
            <th className="px-4 py-2 font-medium">Review items</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {cases.map((c) => (
            <tr key={c.id} className="align-top transition-colors hover:bg-surface-muted">
              <td className="px-4 py-3">
                <Link
                  to="/docready/$caseId/checklist"
                  params={{ caseId: c.id }}
                  className="font-medium text-foreground hover:text-primary hover:underline"
                >
                  {c.borrower}
                </Link>
                <div className="mt-0.5 text-[11px] text-muted-foreground">{c.id}</div>
              </td>
              <td className="px-3 py-3">
                <div className="text-foreground">{c.facilities.join(", ")}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground tabular">
                  {formatInr(c.amount_inr)}
                </div>
              </td>
              <td className="px-3 py-3">
                <span
                  className={cn(
                    "inline-block rounded px-1.5 py-0.5 text-[11.5px] font-medium",
                    stageTone[c.stage],
                  )}
                >
                  {c.stage}
                </span>
              </td>
              <td className="px-3 py-3 text-foreground">{c.rm}</td>
              <td className="px-3 py-3 text-muted-foreground tabular">
                {c.created_at.slice(0, 10)}
              </td>
              <td className="px-4 py-3 tabular">{c.open_review_items}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
