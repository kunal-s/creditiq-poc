import { createFileRoute } from "@tanstack/react-router";
import { ExtractedDataSection } from "@/components/case/ExtractedDataSection";
import { IdentitySection } from "@/components/case/IdentitySection";
import { TabSection } from "@/components/case/TabSection";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { t } from "@/config/terminology";

// Stage 2, extraction (FRD §5, §6): the entity and its parties, then every
// extracted field with its confidence and page.

export const Route = createFileRoute("/cases/$caseId/extraction")({
  head: () => ({
    meta: [{ title: `${t("caseTab.extraction")} — ${t("tenant.product.name")}` }],
  }),
  component: ExtractionTab,
});

function ExtractionTab() {
  const { caseId } = Route.useParams();
  return (
    <CaseScreen caseId={caseId}>
      {(c) => (
        <div className="pb-10">
          <TabSection
            id="identity"
            title={t("page.identity.title")}
            purpose={t("page.identity.purpose")}
          >
            <IdentitySection c={c} />
          </TabSection>
          <TabSection id="fields" title={t("page.data.title")} purpose={t("page.data.purpose")}>
            <ExtractedDataSection caseId={c.id} />
          </TabSection>
        </div>
      )}
    </CaseScreen>
  );
}
