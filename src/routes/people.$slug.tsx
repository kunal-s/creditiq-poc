import { createFileRoute, notFound } from "@tanstack/react-router";
import { getDirector } from "@/data/identity";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/people/$slug")({
  head: () => ({
    meta: [{ title: `Director — ${t("tenant.product.name")}` }],
  }),
  component: PersonDetail,
});

function PersonDetail() {
  const { slug } = Route.useParams();
  const d = getDirector(slug);
  if (!d) throw notFound();
  // No directors are resolved yet in this deployment, so getDirector() never
  // returns — this branch is wired in once identity resolution runs.
  return null;
}
