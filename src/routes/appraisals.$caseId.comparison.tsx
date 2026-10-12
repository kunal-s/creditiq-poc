import { createFileRoute } from "@tanstack/react-router";
import { ComparisonPanel } from "@/components/case/Comparison";
import { TabSection } from "@/components/case/TabSection";
import { t } from "@/config/terminology";

// RBL's record beside CreditIQ's output, for adjudication (FRD F-25): the
// deviations and approving-authority areas.

export const Route = createFileRoute("/appraisals/$caseId/comparison")({
  head: () => ({
    meta: [{ title: `${t("caseTab.comparison")} — ${t("tenant.product.name")}` }],
  }),
  component: ComparisonTab,
});

function ComparisonTab() {
  const { caseId } = Route.useParams();
  return (
    <div className="pb-10">
      <TabSection
        id="comparison"
        title={t("page.comparison.title")}
        purpose={t("page.comparison.purpose")}
      >
        <div className="px-4 py-4 sm:px-6">
          <ComparisonPanel caseId={caseId} />
        </div>
      </TabSection>
    </div>
  );
}
