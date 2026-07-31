import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const Route = createFileRoute("/admin/policy")({
  head: () => ({
    meta: [
      { title: "Ratio and Policy — CreditIQ" },
      { name: "description", content: "Set the ratio set, thresholds and the CCB-1 to CCB-8 risk-rating grid that every appraisal is underwritten against." },
      { property: "og:title", content: "Ratio and Policy — CreditIQ" },
      { property: "og:description", content: "Set the ratio set, thresholds and the CCB-1 to CCB-8 risk-rating grid that every appraisal is underwritten against." },
    ],
  }),
  component: RatioPolicy,
});

function RatioPolicy() {
  return (
    <PlaceholderPage
      eyebrow="Admin"
      title="Ratio and Policy"
      purpose="Set the ratio set, thresholds and the CCB-1 to CCB-8 risk-rating grid that every appraisal is underwritten against."
      aiAction="Copilot back-tests a threshold change against the live book and reports which borrowers would change grade."
      facts={[
            { label: "Ratios underwritten", value: "18 ratios including current ratio, TOL/TNW, DSCR and interest coverage" },
            { label: "Hard floors", value: "DSCR 1.25x, current ratio 1.10x for manufacturing exposures" },
            { label: "Grid owner", value: "Credit Risk Policy, last recalibrated 18 April 2026" },
      ]}
    />
  );
}
