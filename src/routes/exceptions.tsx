import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/exceptions")({
  head: () => ({
    meta: [
      { title: `${t("page.exceptions.title")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content:
          "Every unresolved cross-verification exception, with borrower, severity, age and owner, so nothing open is dropped before submission.",
      },
    ],
  }),
  component: ExceptionQueue,
});

function ExceptionQueue() {
  return (
    <div>
      <PageHeader
        eyebrow={t("page.exceptions.eyebrow")}
        title={t("page.exceptions.title")}
        purpose="Every unresolved cross-verification exception, with borrower, severity, age and owner."
      />
      <div className="px-6 py-5">
        <EmptyState
          title="No exceptions yet"
          description="Exceptions appear here once cross-verification has run on a case."
        />
      </div>
    </div>
  );
}
