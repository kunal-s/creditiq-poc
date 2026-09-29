import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/upload")({
  head: () => ({
    meta: [{ title: `${t("page.documents.title")} — ${t("tenant.product.name")}` }],
  }),
  component: DocumentsStep,
});

function DocumentsStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.documents.title")}
            purpose={t("page.documents.purpose")}
          />
          <ScreenPending feature="F-05 and F-08" />
        </div>
      )}
    </CaseScreen>
  );
}
