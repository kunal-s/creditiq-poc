import { createFileRoute } from "@tanstack/react-router";
import { useDocReadyCase } from "@/data/docready";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/$caseId/validation")({
  head: () => ({
    meta: [
      { title: `${t("intakeTabs.validation")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content:
          "Automated document checks — legibility, period coverage, attestation and identifier match — with the exact defect behind every rejection.",
      },
    ],
  }),
  component: ValidationTab,
});

function ValidationTab() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  if (!c) return null;
  return (
    <div className="px-6 py-5">
      <EmptyState
        title="Not wired up yet"
        description="Machine checks appear once a document has been received for this case."
      />
    </div>
  );
}
