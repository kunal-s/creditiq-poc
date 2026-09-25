import { createFileRoute } from "@tanstack/react-router";
import { CaseStepPage } from "@/components/shell/CaseStepPage";
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
    <CaseStepPage
      id={id}
      eyebrow={t("nav.group.appraisal")}
      title={t("page.crossVerification.title")}
      purpose="Findings from comparing figures across sources, each with both sides and an evidence pointer."
      notBuiltDescription="Findings appear once triangulation has run against this case's extracted facts."
    />
  );
}
