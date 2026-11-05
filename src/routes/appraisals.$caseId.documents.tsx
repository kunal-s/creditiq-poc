import { createFileRoute } from "@tanstack/react-router";
import { DocumentsSection } from "@/components/case/DocumentsSection";
import { TabSection } from "@/components/case/TabSection";
import { useCan } from "@/domain/session";
import { stepKicker } from "@/domain/steps";
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
  const canUpload = useCan("document.upload");
  return (
    <div className="pb-10">
      <TabSection
        id="files"
        kicker={stepKicker(caseId, "documents")}
        title={t("page.documents.title")}
        purpose={t(canUpload ? "page.documents.purpose" : "page.documents.purposeRead")}
      >
        <DocumentsSection caseId={caseId} />
      </TabSection>
    </div>
  );
}
