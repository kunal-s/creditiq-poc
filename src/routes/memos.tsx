import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/shell/PlaceholderPage";
import { ROUTING, useMemoState } from "@/data/memo";

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
  const m = useMemoState();
  return (
    <PlaceholderPage
      eyebrow="Portfolio"
      title="Memo Library"
      purpose="Every issued Credit Appraisal Memorandum for the West Region book, searchable by borrower, rating, facility and analyst."
      aiAction="Copilot compares a borrower against its previous memo and summarises what materially changed."
      facts={[
            ...(m.submitted
              ? [
                  {
                    label: "Awaiting review",
                    value: `Northwind Manufacturing Ltd, CAM-2026-0418, rated ${m.rating}, submitted ${m.submitted.at} by ${m.submitted.by} — with ${ROUTING.reviewer}, ${ROUTING.reviewerRole}`,
                  },
                ]
              : []),
            { label: "Issued this month", value: "23 memos · 19 in June 2026" },
            { label: "Most recent", value: "Aurora Foods Ltd, CAM-2026-0402, rated CCB-2, completed 12 June 2026" },
            { label: "Retention", value: "10 years from sanction date, per bank record-retention policy" },
      ]}
    />
  );
}
