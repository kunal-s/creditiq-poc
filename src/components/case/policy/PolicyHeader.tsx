import type { PolicyAssessment } from "@/api/types";
import { useSpread } from "@/domain/findings";
import { useApprovingAuthority } from "@/domain/policy";
import { money, useDisplayUnit } from "@/domain/units";
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
      <LendingHeadline caseId={caseId} policy={policy} />
    </div>
  );
}

/** The step's answer first: the bank finance the working-capital assessment allows against the
 * amount asked, the gap when it falls short, the deviations and who must approve. Each figure is
 * the engine's; the shortfall is the only one in colour. */
function LendingHeadline({
  caseId,
  policy,
}: {
  caseId: string;
  policy: PolicyAssessment | undefined;
}) {
  const unit = useDisplayUnit();
  const wc = useSpread(caseId).data?.working_capital;
  const authority = useApprovingAuthority(caseId).data;
  if (!wc || wc.eligible === null || wc.eligible === undefined) return null;
  const short = wc.requested - wc.eligible;
  const deviations = policy?.counts?.deviations ?? 0;
  return (
    <dl
      className="tabular mt-3 flex flex-wrap items-baseline gap-x-6 gap-y-2 text-[13px]"
      data-testid="lending-headline"
    >
      <div className="flex items-baseline gap-1.5">
        <dt className="text-muted-foreground">{t("policy.headline.eligible")}</dt>
        <dd className="text-[15px] font-semibold text-foreground" data-testid="lending-eligible">
          {money(wc.eligible, unit)}
        </dd>
      </div>
      <div className="flex items-baseline gap-1.5">
        <dt className="text-muted-foreground">{t("policy.headline.asked")}</dt>
        <dd className="text-[15px] font-semibold text-foreground">{money(wc.requested, unit)}</dd>
      </div>
      {short > 0 && (
        <div className="flex items-baseline gap-1.5" data-testid="lending-short">
          <dt className="text-muted-foreground">{t("policy.headline.short")}</dt>
          <dd className="font-semibold text-critical-text">{money(short, unit)}</dd>
        </div>
      )}
      <div className="flex items-baseline gap-1.5">
        <dt className="sr-only">{t("policy.headline.deviationsLabel")}</dt>
        <dd className="text-foreground">{t("policy.headline.deviations", { n: deviations })}</dd>
      </div>
      {authority?.required && (
        <div className="flex items-baseline gap-1.5">
          <dt className="text-muted-foreground">{t("policy.headline.approver")}</dt>
          <dd className="text-foreground" data-testid="lending-approver">
            {authority.required.label}
          </dd>
        </div>
      )}
    </dl>
  );
}
