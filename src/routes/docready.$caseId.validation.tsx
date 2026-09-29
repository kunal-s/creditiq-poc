import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/$caseId/validation")({
  head: () => ({
    meta: [{ title: `${t("page.validation.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ValidationTab,
});

function ValidationTab() {
  const { caseId } = Route.useParams();
  return (
    <CaseScreen caseId={caseId}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.docready")} · ${c.id}`}
            title={t("page.validation.title")}
            purpose={t("page.validation.purpose")}
          />
          <ScreenPending feature="F-07, F-09 and F-13" />
        </div>
      )}
    </CaseScreen>
  );
}
