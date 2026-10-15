import { createFileRoute } from "@tanstack/react-router";
import { AssessmentStage } from "@/components/case/gate/AssessmentStage";
import { PolicyPage } from "@/components/case/policy/PolicyPage";
import { t } from "@/config/terminology";

// Stage 5, policy checks (FRD §5, §6, F-20, F-21): an overview card per family of norms and one
// for the approving authority; then each family's norms, every one with its required and actual
// value and the figures it used, and the authority with the steps of the matrix that applied.
// ?norm= (a norm id, from the draft CAM and the PD note) opens the page at that norm.

export const Route = createFileRoute("/appraisals/$caseId/policy")({
  validateSearch: (search: Record<string, unknown>): { norm?: string } => {
    const norm = search["norm"];
    return typeof norm === "string" && norm !== "" ? { norm } : {};
  },
  head: () => ({
    meta: [{ title: `${t("caseTab.policy")} — ${t("tenant.product.name")}` }],
  }),
  component: PolicyTab,
});

function PolicyTab() {
  const { caseId } = Route.useParams();
  return (
    <AssessmentStage caseId={caseId}>
      <PolicyPage caseId={caseId} />
    </AssessmentStage>
  );
}
