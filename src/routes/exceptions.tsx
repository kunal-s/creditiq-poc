import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/exceptions")({
  head: () => ({
    meta: [{ title: `${t("page.exceptions.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ExceptionQueue,
});

function ExceptionQueue() {
  return (
    <div>
      <PageHeader
        eyebrow={t("page.exceptions.eyebrow")}
        title={t("page.exceptions.title")}
        purpose={t("page.exceptions.purpose")}
      />
      <ScreenPending feature="F-17" />
    </div>
  );
}
