import { createFileRoute } from "@tanstack/react-router";
import { CaseStepPage } from "@/components/shell/CaseStepPage";
import { DEPLOYMENT_FEATURES } from "@/config/deploymentFeatures";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/data")({
  head: () => ({
    meta: [{ title: `${t("page.data.title")} — ${t("tenant.product.name")}` }],
  }),
  component: DataStep,
});

function DataStep() {
  const { id } = Route.useParams();
  return (
    <CaseStepPage
      id={id}
      eyebrow={t("nav.group.appraisal")}
      title={t("page.data.title")}
      purpose="Every permitted source with provenance, freshness and confidence."
      notBuiltDescription={
        DEPLOYMENT_FEATURES.accountAggregatorEnabled
          ? "Sources populate once bank, bureau and registry data have been fetched for this case."
          : "Account Aggregator consent is not enabled for this deployment — documents are collected through Manual upload instead."
      }
    />
  );
}
