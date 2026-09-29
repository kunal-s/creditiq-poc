import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/$caseId/checklist")({
  head: () => ({
    meta: [{ title: `${t("page.checklist.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ChecklistTab,
});

function ChecklistTab() {
  const { caseId } = Route.useParams();
  return (
    <CaseScreen caseId={caseId}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.docready")} · ${c.id}`}
            title={t("page.checklist.title")}
            purpose={t("page.checklist.purpose")}
          />
          <ScreenPending feature="F-12 and F-13" />
        </div>
      )}
    </CaseScreen>
  );
}
