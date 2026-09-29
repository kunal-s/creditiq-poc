import { createFileRoute } from "@tanstack/react-router";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/cross-verification")({
  head: () => ({
    meta: [{ title: `${t("page.crossVerification.title")} — ${t("tenant.product.name")}` }],
  }),
  component: CrossVerificationStep,
});

function CrossVerificationStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.crossVerification.title")}
            purpose={t("page.crossVerification.purpose")}
          />
          <ScreenPending feature="F-19" />
        </div>
      )}
    </CaseScreen>
  );
}
