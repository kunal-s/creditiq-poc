import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/identity")({
  head: () => ({
    meta: [{ title: `${t("page.identity.title")} — ${t("tenant.product.name")}` }],
  }),
  component: IdentityStep,
});

function IdentityStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.identity.title")}
            purpose={t("page.identity.purpose")}
          />
          <ScreenPending feature="F-10 and F-15" />
        </div>
      )}
    </CaseScreen>
  );
}
