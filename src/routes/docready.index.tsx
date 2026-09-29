import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/docready/")({
  head: () => ({
    meta: [{ title: `${t("page.readinessConsole.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ReadinessConsole,
});

function ReadinessConsole() {
  return (
    <div>
      <PageHeader
        eyebrow={t("page.readinessConsole.eyebrow")}
        title={t("page.readinessConsole.title")}
        purpose={t("page.readinessConsole.purpose")}
      />
      <ScreenPending feature="F-13" />
    </div>
  );
}
