import { createFileRoute } from "@tanstack/react-router";
import { StepPage } from "@/components/shell/StepPage";
import { getAppraisal } from "@/data/seed";

export const Route = createFileRoute("/appraisals/$id/identity")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Identity — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description = "Resolve the borrower from name, PAN and GSTIN into a single confirmed legal entity with its group, directors and registered addresses.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
      ],
    };
  },
  component: IdentityStep,
});

function IdentityStep() {
  const { id } = Route.useParams();
  return (
    <StepPage
      id={id}
      title="Identity"
      purpose="Resolve the borrower from name, PAN and GSTIN into a single confirmed legal entity with its group, directors and registered addresses."
      aiAction="Copilot reconciles registry, tax and bureau names and explains any mismatch before the entity is confirmed."
    />
  );
}
