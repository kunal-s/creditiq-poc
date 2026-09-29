import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/$caseId/collection")({
  head: () => ({
    meta: [{ title: `${t("page.queries.title")} — ${t("tenant.product.name")}` }],
  }),
  component: QueriesTab,
});

function QueriesTab() {
  const { caseId } = Route.useParams();
  return (
    <CaseScreen caseId={caseId}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.docready")} · ${c.id}`}
            title={t("page.queries.title")}
            purpose={t("page.queries.purpose")}
          />
          <ScreenPending feature="F-14" />
        </div>
      )}
    </CaseScreen>
  );
}
