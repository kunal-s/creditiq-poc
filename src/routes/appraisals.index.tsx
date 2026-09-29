import { createFileRoute } from "@tanstack/react-router";
import { useCases } from "@/domain/cases";
import { t } from "@/config/terminology";
import { PageHeader } from "@/components/shell/PageHeader";
import { EmptyState } from "@/components/shell/EmptyState";
import { CasesTable } from "@/components/cases/CasesTable";

export const Route = createFileRoute("/appraisals/")({
  head: () => ({
    meta: [{ title: `${t("page.appraisals.title")} — ${t("tenant.product.name")}` }],
  }),
  component: MyAppraisals,
});

function MyAppraisals() {
  const { data: cases = [], isLoading, isError } = useCases();
  return (
    <div>
      <PageHeader
        eyebrow={t("page.appraisals.eyebrow")}
        title={t("page.appraisals.title")}
        purpose={t("page.appraisals.purpose")}
      />
      <div className="px-6 py-5">
        {isError ? (
          <EmptyState
            title="The case service is not reachable"
            description="Cases cannot be listed right now. Check that the engine service is running, then reload."
          />
        ) : isLoading ? null : cases.length === 0 ? (
          <EmptyState
            title={`No ${t("term.application.plural")} yet`}
            description={`${t("term.application.pluralTitle")} appear here once they are created.`}
          />
        ) : (
          <section className="rounded border border-border bg-surface">
            <CasesTable cases={cases} />
          </section>
        )}
      </div>
    </div>
  );
}
