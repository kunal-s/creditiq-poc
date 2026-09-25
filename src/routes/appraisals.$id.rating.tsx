import { createFileRoute } from "@tanstack/react-router";
import { CaseStepPage } from "@/components/shell/CaseStepPage";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/rating")({
  head: () => ({
    meta: [{ title: `${t("page.rating.title")} — ${t("tenant.product.name")}` }],
  }),
  component: RatingStep,
});

function RatingStep() {
  const { id } = Route.useParams();
  return (
    <CaseStepPage
      id={id}
      eyebrow={t("nav.group.appraisal")}
      title={t("page.rating.title")}
      purpose={`${t("term.ratingInternal")} and the recommendation to the ${t("term.committee")}.`}
      notBuiltDescription="A rating is computed once the draft memo and its supporting ratios are in place."
    />
  );
}
