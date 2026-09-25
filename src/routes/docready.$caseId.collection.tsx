import { createFileRoute } from "@tanstack/react-router";
import { useDocReadyCase } from "@/data/docready";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/$caseId/collection")({
  head: () => ({
    meta: [
      { title: `${t("intakeTabs.collection")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content:
          "Every request, reminder, client upload, rejection and waiver on a document collection case, recorded against the case rather than lost in an inbox.",
      },
    ],
  }),
  component: CollectionTab,
});

function CollectionTab() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  if (!c) return null;
  return (
    <div className="px-6 py-5">
      <EmptyState
        title="Not wired up yet"
        description="The collection trail fills in once requests and uploads start on this case."
      />
    </div>
  );
}
