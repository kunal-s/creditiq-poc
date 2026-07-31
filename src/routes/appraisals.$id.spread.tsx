import { createFileRoute } from "@tanstack/react-router";
import { StepPage } from "@/components/shell/StepPage";
import { getAppraisal } from "@/data/seed";

export const Route = createFileRoute("/appraisals/$id/spread")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Spread — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description = "Normalise the borrower's financials into the bank's spread and compute the ratios underwritten under CAM v4.2.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
      ],
    };
  },
  component: SpreadStep,
});

function SpreadStep() {
  const { id } = Route.useParams();
  return (
    <StepPage
      id={id}
      title="Spread"
      purpose="Normalise the borrower's financials into the bank's spread and compute the ratios underwritten under CAM v4.2."
      aiAction="Copilot explains any ratio that breaches a policy threshold and traces the figure to its source statement."
    />
  );
}
