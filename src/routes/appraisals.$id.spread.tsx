import { createFileRoute } from "@tanstack/react-router";
import { CaseStepPage } from "@/components/shell/CaseStepPage";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/spread")({
  head: () => ({
    meta: [{ title: `${t("page.spread.title")} — ${t("tenant.product.name")}` }],
  }),
  component: SpreadStep,
});

function SpreadStep() {
  const { id } = Route.useParams();
  return (
    <CaseStepPage
      id={id}
      eyebrow={t("nav.group.appraisal")}
      title={t("page.spread.title")}
      purpose="Three-year normalised P&L and balance sheet, with policy ratios and per-cell source pointers."
      notBuiltDescription="The spread is built once financial statements have been extracted and normalised for this case."
    />
  );
}
