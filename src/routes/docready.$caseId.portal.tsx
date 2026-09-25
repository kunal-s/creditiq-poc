import { createFileRoute } from "@tanstack/react-router";
import { useDocReadyCase } from "@/data/docready";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/$caseId/portal")({
  head: () => ({
    meta: [
      { title: `${t("intakeTabs.borrowerPortal")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content:
          "The RM-facing view of what a case still needs, why each item is needed, and what was rejected and why.",
      },
    ],
  }),
  component: PortalTab,
});

function PortalTab() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  if (!c) return null;
  return (
    <div className="px-6 py-5">
      <EmptyState
        title="Not wired up yet"
        description="The RM portal preview is available once this case has open requests."
      />
    </div>
  );
}
