import { createFileRoute, redirect } from "@tanstack/react-router";

// An earlier case list; the Cases screen replaces it (FRD §6).
export const Route = createFileRoute("/appraisals/")({
  beforeLoad: () => {
    throw redirect({ to: "/" });
  },
});
