import { createFileRoute, notFound } from "@tanstack/react-router";
import { getBorrower } from "@/data/portfolio";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/borrowers/$slug")({
  head: () => ({
    meta: [{ title: `Borrower dossier — ${t("tenant.product.name")}` }],
  }),
  component: BorrowerDossier,
});

function BorrowerDossier() {
  const { slug } = Route.useParams();
  const b = getBorrower(slug);
  if (!b) throw notFound();
  // No borrower has a memo history in this deployment yet, so getBorrower()
  // never returns — this branch is wired in once memos.tsx has real data.
  return null;
}
