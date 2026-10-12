import { Info } from "lucide-react";
import type { PolicyAssessment } from "@/api/types";
import { t } from "@/config/terminology";
import { countParts } from "@/domain/policy";

/** "2 deviations · 1 cannot be evaluated · 9 passed · 1 not applicable · FY 2025-26 · provisional
 * norms": the engine's counts, the year the financial figures come from, and whether the norms
 * are interim proposals. */
function summaryLine(policy: PolicyAssessment): string {
  const parts = policy.counts ? countParts(policy.counts, { passed: true }) : [];
  if (policy.period) parts.push(policy.period);
  if (policy.norms.some((n) => n.provisional)) parts.push(t("policy.provisionalNorms"));
  return parts.join(" · ");
}

/** The tab's header: where the case stands against the policy norms. */
export function PolicyHeader({
  caseId,
  policy,
}: {
  caseId: string;
  policy: PolicyAssessment | undefined;
}) {
  const summary = policy && policy.norms.length > 0 ? summaryLine(policy) : "";
  return (
    <div
      className="border-b border-border bg-surface px-4 py-4 sm:px-6"
      data-testid="policy-header"
    >
      <p className="field-label break-words">{t("policy.kicker", { id: caseId })}</p>
      <h2 className="text-[19px] font-semibold tracking-tight text-foreground">
        {t("page.policy.title")}
      </h2>
      {summary && (
        <p
          className="tabular mt-1 max-w-3xl break-words text-[13px] text-muted-foreground"
          data-testid="policy-summary-line"
        >
          {summary}
        </p>
      )}
      {policy?.norms.some((n) => n.provisional) && (
        <p
          className="mt-2 flex max-w-3xl items-start gap-1.5 text-[12px] text-info"
          data-testid="policy-interim"
        >
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {t("policy.interimNotice")}
        </p>
      )}
    </div>
  );
}
