import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/new")({
  head: () => ({
    meta: [{ title: `${t("page.newApplication.title")} — ${t("tenant.product.name")}` }],
  }),
  component: NewApplication,
});

function NewApplication() {
  return (
    <div>
      <PageHeader
        eyebrow={t("page.newApplication.eyebrow")}
        title={t("page.newApplication.title")}
        purpose={t("page.newApplication.purpose")}
      />
      <ScreenPending feature="F-04 and F-05" />
    </div>
  );
}
