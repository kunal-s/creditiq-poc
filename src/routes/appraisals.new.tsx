import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const Route = createFileRoute("/appraisals/new")({
  head: () => ({
    meta: [
      { title: "New Appraisal — CreditIQ" },
      { name: "description", content: "Start an appraisal from the bare minimum identifiers: borrower name, PAN and GSTIN." },
      { property: "og:title", content: "New Appraisal — CreditIQ" },
      { property: "og:description", content: "Start an appraisal from the bare minimum identifiers: borrower name, PAN and GSTIN." },
    ],
  }),
  component: NewAppraisal,
});

function NewAppraisal() {
  return (
    <PlaceholderPage
      eyebrow="Appraisal"
      title="New Appraisal"
      purpose="Start an appraisal from the bare minimum identifiers: borrower name, PAN and GSTIN."
      aiAction="Copilot resolves the identifier against MCA, GST and bureau records and flags name or address mismatches before you commit."
      facts={[
            { label: "Requested by", value: "Marcus Chen, Relationship Manager, Pune Corporate Branch" },
            { label: "Template", value: "Continental Commercial Bank CAM v4.2 (West Region)" },
            { label: "Consent posture", value: "Account aggregator consent requested at submission, purpose-bound to this appraisal" },
      ]}
    />
  );
}
