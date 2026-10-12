import { createFileRoute } from "@tanstack/react-router";
import { PolicyPage } from "@/components/case/policy/PolicyPage";
import { t } from "@/config/terminology";

// Stage 5, policy checks (FRD §5, §6, F-20, F-21): an overview card per family of norms and one
// for the approving authority; then each family's norms, every one with its required and actual
// value and the figures it used, and the authority with the steps of the matrix that applied.

export const Route = createFileRoute("/appraisals/$caseId/policy")({
  head: () => ({
    meta: [{ title: `${t("caseTab.policy")} — ${t("tenant.product.name")}` }],
  }),
  component: PolicyTab,
});

function PolicyTab() {
  const { caseId } = Route.useParams();
  return <PolicyPage caseId={caseId} />;
}
