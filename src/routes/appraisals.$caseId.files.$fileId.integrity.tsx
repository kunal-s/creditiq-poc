import { createFileRoute, Navigate } from "@tanstack/react-router";
import { LoadingBlock } from "@/components/common/States";
import { IntegrityView } from "@/components/documents/IntegrityView";
import { t } from "@/config/terminology";
import { useFeatureState } from "@/domain/features";

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
  // A deployment with the integrity checks switched off (config/app.yaml) has no such page: back to
  // the case's files.
  const on = useFeatureState("integrity_checks");
  if (on === false)
    return <Navigate to="/appraisals/$caseId/documents" params={{ caseId }} replace />;
  // The page's margins, as on every other step of the case.
  return (
    <div className="px-4 py-5 sm:px-6">
      {on ? <IntegrityView caseId={caseId} fileId={fileId} /> : <LoadingBlock />}
    </div>
  );
}
