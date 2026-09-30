import { createFileRoute, redirect } from "@tanstack/react-router";
import { legacyTarget } from "@/domain/legacyRoutes";

// An earlier case route; redirects to its place in the case workspace (FRD §6).
export const Route = createFileRoute("/docready/$")({
  beforeLoad: ({ params }) => {
    const target = legacyTarget("docready", params._splat ?? "");
    throw redirect(target);
  },
});
