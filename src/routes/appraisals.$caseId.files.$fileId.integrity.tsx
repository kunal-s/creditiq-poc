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
  // The page's margins, as on every other step of the case.
  return (
    <div className="px-4 py-5 sm:px-6">
      <IntegrityView caseId={caseId} fileId={fileId} />
    </div>
  );
}
