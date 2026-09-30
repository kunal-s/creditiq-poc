import { createFileRoute, redirect } from "@tanstack/react-router";
import { legacyTarget } from "@/domain/legacyRoutes";

// An earlier appraisal step (upload, identity, data, spread, draft);
// redirects to the tab that now holds it (FRD §6). The current tabs are
// static routes, so they never reach here.
export const Route = createFileRoute("/appraisals/$caseId/$step")({
  beforeLoad: ({ params }) => {
    throw redirect(legacyTarget("appraisals", `${params.caseId}/${params.step}`));
  },
});
