import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/appraisals/$id/")({
  beforeLoad: ({ params }) => {
    throw redirect({ to: "/appraisals/$id/identity", params });
  },
});
