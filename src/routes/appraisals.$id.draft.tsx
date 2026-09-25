import { createFileRoute } from "@tanstack/react-router";
import { CaseStepPage } from "@/components/shell/CaseStepPage";
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
    <CaseStepPage
      id={id}
      eyebrow={t("nav.group.appraisal")}
      title={t("page.draft.title")}
      purpose={`${t("term.memo.full")} draft, template-driven from facts, with every figure pointing to its source.`}
      notBuiltDescription="The memo draft is assembled once the spread and cross-verification steps are complete."
    />
  );
}
