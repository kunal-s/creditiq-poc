import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PageHeader";
import { ScreenPending } from "@/components/shell/ScreenPending";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/scorecard")({
  head: () => ({
    meta: [{ title: `${t("page.scorecard.title")} — ${t("tenant.product.name")}` }],
  }),
  component: Scorecard,
});

function Scorecard() {
  return (
    <div>
      <PageHeader
        eyebrow={t("page.scorecard.eyebrow")}
        title={t("page.scorecard.title")}
        purpose={t("page.scorecard.purpose")}
      />
      <ScreenPending feature="F-26" />
    </div>
  );
}
