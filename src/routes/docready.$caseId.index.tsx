import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/docready/$caseId/")({
  beforeLoad: ({ params }) => {
    throw redirect({
      to: "/docready/$caseId/checklist",
      params: { caseId: params.caseId },
    });
  },
});
