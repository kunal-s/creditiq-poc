import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/draft")({
  head: () => ({
    meta: [{ title: `${t("page.draft.title")} — ${t("tenant.product.name")}` }],
  }),
  component: DraftStep,
});

function DraftStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.draft.title")}
            purpose={t("page.draft.purpose")}
          />
          <ScreenPending feature="F-23 and F-24" />
        </div>
      )}
    </CaseScreen>
  );
}
