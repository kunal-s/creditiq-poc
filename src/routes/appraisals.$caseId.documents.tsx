import { createFileRoute } from "@tanstack/react-router";
import { DocumentsSection } from "@/components/case/DocumentsSection";
import { TabSection } from "@/components/case/TabSection";
import { t } from "@/config/terminology";

// Stage 1, quality and classification (FRD §5, §6): upload, then one row per
// document with its track, its flags and what to do about each.

export const Route = createFileRoute("/appraisals/$caseId/documents")({
  head: () => ({
    meta: [{ title: `${t("caseTab.documents")} — ${t("tenant.product.name")}` }],
  }),
  component: DocumentsTab,
});

function DocumentsTab() {
  const { caseId } = Route.useParams();
  return (
    <div className="pb-10">
      <TabSection
        id="files"
        title={t("page.documents.title")}
        purpose={t("page.documents.purpose")}
      >
        <DocumentsSection caseId={caseId} />
      </TabSection>
    </div>
  );
}
