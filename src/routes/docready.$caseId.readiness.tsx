import { createFileRoute } from "@tanstack/react-router";
import { useDocReadyCase } from "@/data/docready";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/$caseId/readiness")({
  head: () => ({
    meta: [
      { title: `${t("intakeTabs.readiness")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content:
          "Weighted readiness score, blocking versus non-blocking gaps, and the handoff that carries a complete MSME file into credit appraisal.",
      },
    ],
  }),
  component: ReadinessTab,
});

function ReadinessTab() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  if (!c) return null;
  return (
    <div className="px-6 py-5">
      <EmptyState
        title="Not wired up yet"
        description="The readiness score and handoff action appear once this case has a checklist."
      />
    </div>
  );
}
