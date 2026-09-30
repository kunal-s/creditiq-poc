import { createFileRoute } from "@tanstack/react-router";
import { TabSection } from "@/components/case/TabSection";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$caseId/comparison")({
  head: () => ({
    meta: [{ title: `${t("caseTab.comparison")} — ${t("tenant.product.name")}` }],
  }),
  component: PendingTab,
});

function PendingTab() {
  return (
    <div className="pb-10">
      <TabSection
        id="comparison"
        title={t("page.comparison.title")}
        purpose={t("page.comparison.purpose")}
      >
        <ScreenPending feature="F-25" />
      </TabSection>
    </div>
  );
}
