import { createFileRoute } from "@tanstack/react-router";
import { ChecklistSection } from "@/components/case/ChecklistSection";
import { QueriesSection } from "@/components/case/QueriesSection";
import { ReadinessSection } from "@/components/case/ReadinessSection";
import { TabSection } from "@/components/case/TabSection";
import { t } from "@/config/terminology";

// Stage 3, validation and completeness (FRD §5, §6): readiness against the
// gates, the checklist, and the pre-login query list.

export const Route = createFileRoute("/cases/$caseId/completeness")({
  head: () => ({
    meta: [{ title: `${t("caseTab.completeness")} — ${t("tenant.product.name")}` }],
  }),
  component: CompletenessTab,
});

function CompletenessTab() {
  const { caseId } = Route.useParams();
  return (
    <div className="pb-10">
      <TabSection
        id="readiness"
        title={t("page.readiness.title")}
        purpose={t("page.readiness.purpose")}
      >
        <ReadinessSection caseId={caseId} />
      </TabSection>
      <TabSection
        id="checklist"
        title={t("page.checklist.title")}
        purpose={t("page.checklist.purpose")}
      >
        <ChecklistSection caseId={caseId} />
      </TabSection>
      <TabSection id="queries" title={t("page.queries.title")} purpose={t("page.queries.purpose")}>
        <QueriesSection caseId={caseId} />
      </TabSection>
    </div>
  );
}
