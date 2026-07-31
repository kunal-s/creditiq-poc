import { createFileRoute } from "@tanstack/react-router";
import { StepPage } from "@/components/shell/StepPage";
import { getAppraisal } from "@/data/seed";

export const Route = createFileRoute("/appraisals/$id/data")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Data — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description = "Gather and extract the evidence set: filings, financial statements, GST returns, bank statements and bureau reports, each retained with its citation.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
      ],
    };
  },
  component: DataStep,
});

function DataStep() {
  const { id } = Route.useParams();
  return (
    <StepPage
      id={id}
      title="Data"
      purpose="Gather and extract the evidence set: filings, financial statements, GST returns, bank statements and bureau reports, each retained with its citation."
      aiAction="Copilot lists what is still missing for a complete file and drafts the document request to the relationship manager."
    />
  );
}
