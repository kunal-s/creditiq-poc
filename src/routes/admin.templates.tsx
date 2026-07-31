import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const Route = createFileRoute("/admin/templates")({
  head: () => ({
    meta: [
      { title: "Template Designer — CreditIQ" },
      { name: "description", content: "Define the bank's CAM sections, order and narrative voice so output lands in Continental Commercial Bank's own house format." },
      { property: "og:title", content: "Template Designer — CreditIQ" },
      { property: "og:description", content: "Define the bank's CAM sections, order and narrative voice so output lands in Continental Commercial Bank's own house format." },
    ],
  }),
  component: TemplateDesigner,
});

function TemplateDesigner() {
  return (
    <PlaceholderPage
      eyebrow="Admin"
      title="Template Designer"
      purpose="Define the bank's CAM sections, order and narrative voice so output lands in Continental Commercial Bank's own house format."
      aiAction="Copilot previews how a section change would have altered the last ten memos before you publish it."
      facts={[
            { label: "Active template", value: "CAM v4.2, published 2 March 2026 by Ananya Deshmukh, Credit Policy" },
            { label: "Sections", value: "14 sections, 3 of them mandatory for exposures above INR 15 cr" },
            { label: "Draft in review", value: "CAM v4.3 — revised industry-outlook section" },
      ]}
    />
  );
}
