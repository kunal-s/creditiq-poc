import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const Route = createFileRoute("/admin/connectors")({
  head: () => ({
    meta: [
      { title: "Connectors and Consent — CreditIQ" },
      { name: "description", content: "Switch data sources on or off and govern borrower consent: what was granted, for what purpose, and until when." },
      { property: "og:title", content: "Connectors and Consent — CreditIQ" },
      { property: "og:description", content: "Switch data sources on or off and govern borrower consent: what was granted, for what purpose, and until when." },
    ],
  }),
  component: Connectors,
});

function Connectors() {
  return (
    <PlaceholderPage
      eyebrow="Admin"
      title="Connectors and Consent"
      purpose="Switch data sources on or off and govern borrower consent: what was granted, for what purpose, and until when."
      aiAction="Copilot explains which memo figures would go stale if a connector were disabled today."
      facts={[
            { label: "Live connectors", value: "MCA registry, GSTN, Account Aggregator, CIBIL Commercial, internal core banking" },
            { label: "Active consents", value: "9 borrower consents, each purpose-bound and revocable" },
            { label: "Expiring soon", value: "Northwind Manufacturing Ltd consent lapses 14 September 2026" },
      ]}
    />
  );
}
