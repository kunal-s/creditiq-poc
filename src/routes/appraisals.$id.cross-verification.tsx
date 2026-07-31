import { createFileRoute } from "@tanstack/react-router";
import { StepPage } from "@/components/shell/StepPage";
import { getAppraisal } from "@/data/seed";

export const Route = createFileRoute("/appraisals/$id/cross-verification")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Cross-Verification — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description = "Line the sources up against each other and surface every contradiction between declared financials, GST filings, bank conduct and bureau history.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
      ],
    };
  },
  component: CrossVerificationStep,
});

function CrossVerificationStep() {
  const { id } = Route.useParams();
  return (
    <StepPage
      id={id}
      title="Cross-Verification"
      purpose="Line the sources up against each other and surface every contradiction between declared financials, GST filings, bank conduct and bureau history."
      aiAction="Copilot ranks discrepancies by credit impact and drafts the query to put to the borrower."
    />
  );
}
