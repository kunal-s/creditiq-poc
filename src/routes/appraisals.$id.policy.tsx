import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/policy")({
  head: () => ({
    meta: [{ title: `${t("page.policy.title")} — ${t("tenant.product.name")}` }],
  }),
  component: PolicyStep,
});

function PolicyStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.policy.title")}
            purpose={t("page.policy.purpose")}
          />
          <ScreenPending feature="F-20 and F-21" />
        </div>
      )}
    </CaseScreen>
  );
}
