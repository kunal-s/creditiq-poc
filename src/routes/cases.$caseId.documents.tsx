import { createFileRoute } from "@tanstack/react-router";
import { DocumentChecksSection } from "@/components/case/DocumentChecksSection";
import { DocumentsSection } from "@/components/case/DocumentsSection";
import { TabSection } from "@/components/case/TabSection";
import { t } from "@/config/terminology";

// Stage 1, quality and classification (FRD §5, §6): upload, the file
// register, and each document's machine checks.

export const Route = createFileRoute("/cases/$caseId/documents")({
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
      <TabSection
        id="checks"
        title={t("page.validation.title")}
        purpose={t("page.validation.purpose")}
      >
        <DocumentChecksSection caseId={caseId} />
      </TabSection>
    </div>
  );
}
