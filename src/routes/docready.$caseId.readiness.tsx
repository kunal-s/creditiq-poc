import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/$caseId/readiness")({
  head: () => ({
    meta: [{ title: `${t("page.readiness.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ReadinessTab,
});

function ReadinessTab() {
  const { caseId } = Route.useParams();
  return (
    <CaseScreen caseId={caseId}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.docready")} · ${c.id}`}
            title={t("page.readiness.title")}
            purpose={t("page.readiness.purpose")}
          />
          <ScreenPending feature="F-13" />
        </div>
      )}
    </CaseScreen>
  );
}
