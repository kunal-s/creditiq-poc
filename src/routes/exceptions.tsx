import { createFileRoute, redirect } from "@tanstack/react-router";

// The earlier name of the review queue (FRD §6).
export const Route = createFileRoute("/exceptions")({
  beforeLoad: () => {
    throw redirect({ to: "/review" });
  },
});
