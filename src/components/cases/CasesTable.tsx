import { Link } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";
import type { CaseSummary, Stage } from "@/api/types";
import { formatDate, formatInr, stageKey, stageLabel, useLabels } from "@/domain/cases";
import { CASE_TABS, caseTabPath, tabForStage } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { useCan, useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

const stageTone: Record<Stage, string> = {
  Intake: "bg-muted text-muted-foreground",
  Documents: "bg-info-soft text-info",
  Extraction: "bg-info-soft text-info",
  Completeness: "bg-info-soft text-info",
  CrossVerification: "bg-accent text-accent-foreground",
  Policy: "bg-accent text-accent-foreground",
  Outputs: "bg-accent text-accent-foreground",
  Completed: "bg-positive-soft text-positive",
};

export function StageLink({ c }: { c: CaseSummary }) {
  const permissions = useSession()?.user.permissions ?? [];
  const key = stageKey(c.stage);
  const tab = key ? tabForStage(key) : undefined;
  // A stage the role may not open links to the case Overview instead.
  const to =
    tab && permissions.includes(tab.permission)
      ? caseTabPath(c.id, tab)
      : caseTabPath(c.id, CASE_TABS[0]!);
  return (
    <Link
      to={to}
      className={cn(
        "inline-block rounded px-1.5 py-0.5 text-[11.5px] font-medium",
        stageTone[c.stage],
      )}
    >
      {stageLabel(c.stage)}
    </Link>
  );
}

export function ReviewFlag({ count }: { count: number }) {
  const canReview = useCan("review.read");
  const className =
    "inline-flex items-center gap-1 rounded border border-flag/40 bg-flag-soft px-1.5 py-0.5 text-[11.5px] font-medium text-flag-foreground";
  const body = (
    <>
      <AlertTriangle className="h-3 w-3" />
      {t("cases.reviewOpen", { n: count })}
    </>
  );
  return count > 0 ? (
    canReview ? (
      <Link to="/review" className={className}>
        {body}
      </Link>
    ) : (
      <span className={className}>{body}</span>
    )
  ) : (
    <span className="text-[11.5px] text-muted-foreground">{t("cases.clear")}</span>
  );
}

/** The prototype's in-flight table on wide screens, cards on phones (F-06.1). */
export function CasesTable({ cases }: { cases: CaseSummary[] }) {
  const labels = useLabels();
  return (
    <>
      <ul className="divide-y divide-border md:hidden" data-testid="cases-cards">
        {cases.map((c) => (
          <li key={c.id} className="px-4 py-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <Link
                  to="/cases/$caseId"
                  params={{ caseId: c.id }}
                  className="break-words text-[13px] font-medium text-foreground hover:text-primary hover:underline"
                >
                  {c.borrower}
                </Link>
                <p className="mt-0.5 text-[11px] text-muted-foreground tabular">{c.id}</p>
              </div>
              <StageLink c={c} />
            </div>
            <p className="mt-1.5 text-[12px] text-foreground">
              {labels.facilities(c.facilities)} ·{" "}
              <span className="tabular">{formatInr(c.amount_inr)}</span>
            </p>
            <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
              <span>
                {c.rm} · {formatDate(c.created_at)}
              </span>
              <ReviewFlag count={c.open_review_items} />
            </div>
          </li>
        ))}
      </ul>
      <div className="hidden overflow-x-auto md:block" data-testid="cases-table">
        <table className="w-full min-w-[720px] text-[12.5px]">
          <thead>
            <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
              <th className="px-4 py-2 font-medium">{t("term.borrower.title")}</th>
              <th className="px-3 py-2 font-medium">{t("cases.col.proposal")}</th>
              <th className="px-3 py-2 font-medium">{t("term.stage")}</th>
              <th className="px-3 py-2 font-medium">{t("cases.col.rm")}</th>
              <th className="px-3 py-2 font-medium">{t("cases.col.created")}</th>
              <th className="px-4 py-2 font-medium">{t("cases.col.review")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {cases.map((c) => (
              <tr
                key={c.id}
                className={cn(
                  "align-top transition-colors hover:bg-surface-muted",
                  c.open_review_items >= 2 && "bg-flag-soft/50 hover:bg-flag-soft",
                )}
              >
                <td className="px-4 py-3">
                  <Link
                    to="/cases/$caseId"
                    params={{ caseId: c.id }}
                    className="font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {c.borrower}
                  </Link>
                  <div className="mt-0.5 text-[11px] text-muted-foreground">
                    {c.id} · {labels.constitution(c.constitution)}
                  </div>
                </td>
                <td className="px-3 py-3">
                  <div className="text-foreground">{labels.facilities(c.facilities)}</div>
                  <div className="mt-0.5 text-[11px] text-muted-foreground tabular">
                    {formatInr(c.amount_inr)}
                  </div>
                </td>
                <td className="px-3 py-3">
                  <StageLink c={c} />
                </td>
                <td className="px-3 py-3 text-foreground">{c.rm}</td>
                <td className="px-3 py-3 text-muted-foreground tabular">
                  {formatDate(c.created_at)}
                </td>
                <td className="px-4 py-3">
                  <ReviewFlag count={c.open_review_items} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
