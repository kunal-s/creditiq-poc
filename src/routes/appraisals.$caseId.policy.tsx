import { createFileRoute } from "@tanstack/react-router";
import { PolicyPanel } from "@/components/case/PolicyNorms";
import { TabSection } from "@/components/case/TabSection";
import { t } from "@/config/terminology";

// Stage 5, policy checks (FRD §5, §6, F-20): every norm, and the deviations.

export const Route = createFileRoute("/appraisals/$caseId/policy")({
  head: () => ({
    meta: [{ title: `${t("caseTab.policy")} — ${t("tenant.product.name")}` }],
  }),
  component: PolicyTab,
});

function PolicyTab() {
  const { caseId } = Route.useParams();
  return (
    <div className="pb-10">
      <TabSection id="policy" title={t("page.policy.title")} purpose={t("page.policy.purpose")}>
        <div className="px-4 py-4 sm:px-6">
          <PolicyPanel caseId={caseId} />
        </div>
      </TabSection>
    </div>
  );
}
