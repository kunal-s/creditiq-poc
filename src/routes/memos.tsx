import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export const Route = createFileRoute("/memos")({
  head: () => ({
    meta: [
      { title: "Memo Library — CreditIQ" },
      { name: "description", content: "Every issued Credit Appraisal Memorandum for the West Region book, searchable by borrower, rating, facility and analyst." },
      { property: "og:title", content: "Memo Library — CreditIQ" },
      { property: "og:description", content: "Every issued Credit Appraisal Memorandum for the West Region book, searchable by borrower, rating, facility and analyst." },
    ],
  }),
  component: MemoLibrary,
});

function MemoLibrary() {
  return (
    <PlaceholderPage
      eyebrow="Portfolio"
      title="Memo Library"
      purpose="Every issued Credit Appraisal Memorandum for the West Region book, searchable by borrower, rating, facility and analyst."
      aiAction="Copilot compares a borrower against its previous memo and summarises what materially changed."
      facts={[
            { label: "Issued this month", value: "23 memos · 19 in June 2026" },
            { label: "Most recent", value: "Aurora Foods Ltd, CAM-2026-0402, rated CCB-2, completed 12 June 2026" },
            { label: "Retention", value: "10 years from sanction date, per bank record-retention policy" },
      ]}
    />
  );
}
