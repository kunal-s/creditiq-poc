import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/comparison")({
  head: () => ({
    meta: [{ title: `${t("page.comparison.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ComparisonStep,
});

function ComparisonStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.comparison.title")}
            purpose={t("page.comparison.purpose")}
          />
          <ScreenPending feature="F-25" />
        </div>
      )}
    </CaseScreen>
  );
}
