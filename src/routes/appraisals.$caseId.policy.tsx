import { createFileRoute } from "@tanstack/react-router";
import { TabSection } from "@/components/case/TabSection";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$caseId/policy")({
  head: () => ({
    meta: [{ title: `${t("caseTab.policy")} — ${t("tenant.product.name")}` }],
  }),
  component: PendingTab,
});

function PendingTab() {
  return (
    <div className="pb-10">
      <TabSection id="policy" title={t("page.policy.title")} purpose={t("page.policy.purpose")}>
        <ScreenPending feature="F-20 and F-21" />
      </TabSection>
    </div>
  );
}
