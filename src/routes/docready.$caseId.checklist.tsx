import { createFileRoute } from "@tanstack/react-router";
import { STATUS_LABEL, useDocReadyCase, type DocStatus } from "@/data/docready";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId/checklist")({
  head: () => ({
    meta: [{ title: `${t("intakeTabs.checklist")} — ${t("tenant.product.name")}` }],
  }),
  component: ChecklistTab,
});

export function StatusChip({ status }: { status: DocStatus }) {
  const tone: Record<DocStatus, string> = {
    "not-requested": "bg-muted text-muted-foreground",
    requested: "bg-info-soft text-info",
    received: "bg-accent text-accent-foreground",
    rejected: "bg-critical-soft text-critical",
    accepted: "bg-positive-soft text-positive",
    waived: "bg-muted text-muted-foreground",
  };
  return (
    <span
      className={cn("inline-block rounded px-1.5 py-0.5 text-[11px] font-medium", tone[status])}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

function ChecklistTab() {
  const { caseId } = Route.useParams();
  const c = useDocReadyCase(caseId);
  if (!c) return null; // parent layout ($caseId.tsx) already shows the "not in this workspace" state
  return (
    <div className="px-6 py-5">
      <EmptyState
        title="Not wired up yet"
        description="The document checklist is populated once this case has an active item set."
      />
    </div>
  );
}
