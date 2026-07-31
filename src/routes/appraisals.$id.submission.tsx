import { createFileRoute } from "@tanstack/react-router";
import { StepPage } from "@/components/shell/StepPage";
import { getAppraisal } from "@/data/seed";

export const Route = createFileRoute("/appraisals/$id/submission")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Submission — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description = "Sign the memo, attach the evidence pack and route it to the credit committee with the approval trail intact.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
      ],
    };
  },
  component: SubmissionStep,
});

function SubmissionStep() {
  const { id } = Route.useParams();
  return (
    <StepPage
      id={id}
      title="Submission"
      purpose="Sign the memo, attach the evidence pack and route it to the credit committee with the approval trail intact."
      aiAction="Copilot assembles the committee pack and checks that no unresolved discrepancy is being submitted silently."
    />
  );
}
