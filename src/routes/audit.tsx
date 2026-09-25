import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: `${t("page.audit.title")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content:
          "Reconstruct any credit decision end to end: what each source returned, what the system drafted, every human edit and override with author and reason, how each discrepancy was adjudicated, and who approved.",
      },
    ],
  }),
  component: AuditLedger,
});

function AuditLedger() {
  return (
    <div>
      <PageHeader
        eyebrow={t("page.audit.eyebrow")}
        title={t("page.audit.title")}
        purpose="Every source return, system draft, human edit and override, with author and reason, reconstructable end to end."
      />
      <div className="px-6 py-5">
        <EmptyState
          title="No audit events yet"
          description="The ledger populates once a case starts moving through the pipeline."
        />
      </div>
    </div>
  );
}
