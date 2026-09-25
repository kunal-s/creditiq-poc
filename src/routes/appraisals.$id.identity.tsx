import { createFileRoute } from "@tanstack/react-router";
import { CaseStepPage } from "@/components/shell/CaseStepPage";
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
    <CaseStepPage
      id={id}
      eyebrow={t("nav.group.appraisal")}
      title={t("page.identity.title")}
      purpose="Entity resolution, near-duplicate disambiguation, directors and group perimeter."
      notBuiltDescription="Entity resolution runs once the intake pipeline classifies this case's registration documents."
    />
  );
}
