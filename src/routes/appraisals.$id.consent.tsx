import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { EmptyState } from "@/components/shell/EmptyState";
import { DEPLOYMENT_FEATURES } from "@/config/deploymentFeatures";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/consent")({
  head: () => ({
    meta: [{ title: `${t("page.consent.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ConsentStep,
});

function ConsentStep() {
  const { id } = Route.useParams();
  return (
    <div>
      <PageHeader
        eyebrow={t("nav.group.appraisal")}
        title={t("page.consent.title")}
        purpose="Borrower-facing consent for sharing bank-account data."
      />
      <div className="px-6 py-5">
        <EmptyState
          title={
            DEPLOYMENT_FEATURES.accountAggregatorEnabled
              ? "Not wired up yet"
              : "Account Aggregator not enabled"
          }
          description={
            DEPLOYMENT_FEATURES.accountAggregatorEnabled
              ? "The consent journey runs once this case reaches the data step."
              : "This deployment collects bank data through Manual upload rather than a live Account Aggregator consent flow."
          }
          action={
            <Link
              to="/appraisals/$id/upload"
              params={{ id }}
              className="text-[12.5px] font-medium text-primary hover:underline"
            >
              Go to Manual upload
            </Link>
          }
        />
      </div>
    </div>
  );
}
