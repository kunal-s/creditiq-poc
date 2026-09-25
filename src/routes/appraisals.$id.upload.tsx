import { createFileRoute } from "@tanstack/react-router";
import { CaseStepPage } from "@/components/shell/CaseStepPage";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/upload")({
  head: () => ({
    meta: [{ title: `${t("page.upload.title")} — ${t("tenant.product.name")}` }],
  }),
  component: UploadStep,
});

function UploadStep() {
  const { id } = Route.useParams();
  return (
    <CaseStepPage
      id={id}
      eyebrow={t("nav.group.appraisal")}
      title={t("page.upload.title")}
      purpose="Manual document ingestion, the primary path in this deployment."
      notBuiltDescription="File upload for this case is enabled once the case reaches the data step."
    />
  );
}
