import { createFileRoute } from "@tanstack/react-router";
import { FactsPanels, FindingsPanel } from "@/components/case/CrossVerification";
import { TabSection } from "@/components/case/TabSection";
import { t } from "@/config/terminology";

// Stage 4, cross-verification (FRD §5, §6, F-18, F-19): the checks' outcomes,
// then the aligned facts they compared.

export const Route = createFileRoute("/appraisals/$caseId/cross-verification")({
  head: () => ({
    meta: [{ title: `${t("caseTab.crossVerification")} — ${t("tenant.product.name")}` }],
  }),
  component: CrossVerificationTab,
});

function CrossVerificationTab() {
  const { caseId } = Route.useParams();
  return (
    <div className="pb-10">
      <TabSection
        id="findings"
        title={t("page.crossVerification.title")}
        purpose={t("page.crossVerification.purpose")}
      >
        <div className="px-4 py-4 sm:px-6">
          <FindingsPanel caseId={caseId} />
        </div>
      </TabSection>
      <TabSection id="facts" title={t("facts.title")} purpose={t("facts.purpose")}>
        <div className="px-4 py-4 sm:px-6">
          <FactsPanels caseId={caseId} />
        </div>
      </TabSection>
    </div>
  );
}
