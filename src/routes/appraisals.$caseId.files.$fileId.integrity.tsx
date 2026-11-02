import { createFileRoute } from "@tanstack/react-router";
import { IntegrityView } from "@/components/documents/IntegrityView";
import { t } from "@/config/terminology";

// F-07A: one received file's integrity, whole — its pages with every place a
// check points at, and every check run on it.

export const Route = createFileRoute("/appraisals/$caseId/files/$fileId/integrity")({
  head: () => ({
    meta: [{ title: `${t("fileIntegrity.title")} — ${t("tenant.product.name")}` }],
  }),
  component: IntegrityRoute,
});

function IntegrityRoute() {
  const { caseId, fileId } = Route.useParams();
  return <IntegrityView caseId={caseId} fileId={fileId} />;
}
