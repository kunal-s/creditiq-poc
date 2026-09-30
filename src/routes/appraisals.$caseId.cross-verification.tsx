import { createFileRoute } from "@tanstack/react-router";
import { TabSection } from "@/components/case/TabSection";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$caseId/cross-verification")({
  head: () => ({
    meta: [{ title: `${t("caseTab.crossVerification")} — ${t("tenant.product.name")}` }],
  }),
  component: PendingTab,
});

function PendingTab() {
  return (
    <div className="pb-10">
      <TabSection
        id="crossVerification"
        title={t("page.crossVerification.title")}
        purpose={t("page.crossVerification.purpose")}
      >
        <ScreenPending feature="F-18 and F-19" />
      </TabSection>
    </div>
  );
}
