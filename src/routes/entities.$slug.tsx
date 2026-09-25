import { createFileRoute, notFound } from "@tanstack/react-router";
import { getEntity } from "@/data/identity";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/entities/$slug")({
  head: () => ({
    meta: [{ title: `Entity — ${t("tenant.product.name")}` }],
  }),
  component: EntityDetail,
});

function EntityDetail() {
  const { slug } = Route.useParams();
  const e = getEntity(slug);
  if (!e) throw notFound();
  // No entities are resolved yet in this deployment, so getEntity() never
  // returns — this branch is wired in once identity resolution runs.
  return null;
}
