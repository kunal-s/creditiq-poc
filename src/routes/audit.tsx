import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: "Audit and Examiner Walk-through — CreditIQ" },
      { name: "description", content: "Reconstruct any memo: every figure back to its source document, every analyst override back to its stated reason." },
      { property: "og:title", content: "Audit and Examiner Walk-through — CreditIQ" },
      { property: "og:description", content: "Reconstruct any memo: every figure back to its source document, every analyst override back to its stated reason." },
    ],
  }),
  component: AuditPage,
});

function AuditPage() {
  return (
    <PlaceholderPage
      eyebrow="Governance"
      title="Audit and Examiner Walk-through"
      purpose="Reconstruct any memo: every figure back to its source document, every analyst override back to its stated reason."
      aiAction="Copilot assembles a walk-through narrative for a selected memo, citing each evidence item in order."
      facts={[
            { label: "Reconstructable memos", value: "412 memos, earliest 4 April 2024" },
            { label: "Overrides logged", value: "37 analyst overrides in FY26 to date, each with a recorded reason" },
            { label: "Last examiner pack", value: "Prepared 14 May 2026 for the RBI inspection cycle" },
      ]}
    />
  );
}
