import { createFileRoute } from "@tanstack/react-router";
import { CaseStepPage } from "@/components/shell/CaseStepPage";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/$id/submission")({
  head: () => ({
    meta: [{ title: `${t("page.submission.title")} — ${t("tenant.product.name")}` }],
  }),
  component: SubmissionStep,
});

function SubmissionStep() {
  const { id } = Route.useParams();
  return (
    <CaseStepPage
      id={id}
      eyebrow={t("nav.group.appraisal")}
      title={t("page.submission.title")}
      purpose={`Route the finished memo to its reviewer and the ${t("term.committee")}.`}
      notBuiltDescription="Submission opens once the memo has been drafted and rated."
    />
  );
}
