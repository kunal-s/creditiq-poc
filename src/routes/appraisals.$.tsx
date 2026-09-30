import { createFileRoute, redirect } from "@tanstack/react-router";
import { legacyTarget } from "@/domain/legacyRoutes";

// An earlier case route; redirects to its place in the case workspace (FRD §6).
export const Route = createFileRoute("/appraisals/$")({
  beforeLoad: ({ params }) => {
    const target = legacyTarget("appraisals", params._splat ?? "");
    throw redirect(target);
  },
});
