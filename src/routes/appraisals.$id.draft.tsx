import { createFileRoute } from "@tanstack/react-router";
import { StepPage } from "@/components/shell/StepPage";
import { getAppraisal } from "@/data/seed";

export const Route = createFileRoute("/appraisals/$id/draft")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Draft and Review — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description = "Read the drafted memo in the bank's house format, follow every citation, edit freely and record a reason for each override.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
      ],
    };
  },
  component: DraftStep,
});

function DraftStep() {
  const { id } = Route.useParams();
  return (
    <StepPage
      id={id}
      title="Draft and Review"
      purpose="Read the drafted memo in the bank's house format, follow every citation, edit freely and record a reason for each override."
      aiAction="Copilot rewrites a section in the bank's voice while keeping every citation intact."
    />
  );
}
