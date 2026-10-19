import { createFileRoute } from "@tanstack/react-router";
import { AssessmentStage } from "@/components/case/gate/AssessmentStage";
import { SpreadPage } from "@/components/case/spread/SpreadPage";
import { t } from "@/config/terminology";

// The spread (FRD F-22, F-18.1, F-20): the audited years line by line, turnover from every
// source year by year with what the cross-checks made of it, and the ratios against the policy.

export const Route = createFileRoute("/appraisals/$caseId/spread")({
  head: () => ({
    meta: [{ title: `${t("caseTab.spread")} — ${t("tenant.product.name")}` }],
  }),
  component: SpreadTab,
});

function SpreadTab() {
  const { caseId } = Route.useParams();
  return (
    <AssessmentStage caseId={caseId}>
      <SpreadPage caseId={caseId} />
    </AssessmentStage>
  );
}
