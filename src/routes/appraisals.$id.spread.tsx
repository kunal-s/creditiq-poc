import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/spread")({
  head: () => ({
    meta: [{ title: `${t("page.spread.title")} — ${t("tenant.product.name")}` }],
  }),
  component: SpreadStep,
});

function SpreadStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.spread.title")}
            purpose={t("page.spread.purpose")}
          />
          <ScreenPending feature="F-22" />
        </div>
      )}
    </CaseScreen>
  );
}
