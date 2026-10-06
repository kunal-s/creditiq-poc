import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PageHeader";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/help")({
  head: () => ({
    meta: [{ title: `${t("page.help.title")} — ${t("tenant.product.name")}` }],
  }),
  component: Help,
});

const STEPS = ["documents", "extraction", "completeness", "crossVerification", "policy", "outputs"];
const STATUSES = ["not_started", "in_progress", "needs_attention", "done"];

function Help() {
  return (
    <div>
      <PageHeader
        eyebrow={t("page.help.eyebrow")}
        title={t("page.help.title")}
        purpose={t("page.help.purpose")}
      />
      <div className="max-w-3xl space-y-8 px-4 py-6 sm:px-6">
        <section aria-labelledby="help-steps">
          <h2 id="help-steps" className="text-[15px] font-semibold tracking-tight">
            {t("page.help.stepsTitle")}
          </h2>
          <ol className="mt-3 space-y-4">
            {STEPS.map((key, i) => (
              <li key={key} className="flex gap-3" data-testid={`help-step-${key}`}>
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-border text-[11px] font-semibold tabular">
                  {i + 1}
                </span>
                <div>
                  <h3 className="text-[13.5px] font-medium">{t(`page.help.step.${key}.title`)}</h3>
                  <p className="mt-0.5 text-[13px] text-muted-foreground">
                    {t(`page.help.step.${key}.body`)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
        <section aria-labelledby="help-status">
          <h2 id="help-status" className="text-[15px] font-semibold tracking-tight">
            {t("page.help.statusTitle")}
          </h2>
          <dl className="mt-3 space-y-3">
            {STATUSES.map((key) => (
              <div key={key}>
                <dt className="text-[13.5px] font-medium">{t(`progress.status.${key}`)}</dt>
                <dd className="text-[13px] text-muted-foreground">
                  {t(`page.help.status.${key}`)}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </div>
  );
}
