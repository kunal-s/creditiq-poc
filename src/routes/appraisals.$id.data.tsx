import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/data")({
  head: () => ({
    meta: [{ title: `${t("page.data.title")} — ${t("tenant.product.name")}` }],
  }),
  component: DataStep,
});

function DataStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.data.title")}
            purpose={t("page.data.purpose")}
          />
          <ScreenPending feature="F-15 and F-16" />
        </div>
      )}
    </CaseScreen>
  );
}
