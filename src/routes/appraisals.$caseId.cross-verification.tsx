import { createFileRoute } from "@tanstack/react-router";
import { AssessmentStage } from "@/components/case/gate/AssessmentStage";
import { CrossVerificationBoard } from "@/components/case/xv/Board";
import { t } from "@/config/terminology";

// Stage 4, cross-verification (FRD §5, §6, F-18, F-19): the board by area (identity, turnover,
// bank accounts, existing obligations), an overview card for each; in each area its discrepancies
// ranked by credit impact, each with its sources side by side and a decision, then what could not
// be checked, what passed, and the facts the checks compared. ?finding= (a finding id or its XV
// reference, from the draft CAM and the PD note) opens the board at that finding.

export const Route = createFileRoute("/appraisals/$caseId/cross-verification")({
  validateSearch: (search: Record<string, unknown>): { finding?: string } => {
    const finding = search["finding"];
    return typeof finding === "string" && finding !== "" ? { finding } : {};
  },
  head: () => ({
    meta: [{ title: `${t("caseTab.crossVerification")} — ${t("tenant.product.name")}` }],
  }),
  component: CrossVerificationTab,
});

function CrossVerificationTab() {
  const { caseId } = Route.useParams();
  const { finding } = Route.useSearch();
  return (
    <AssessmentStage caseId={caseId}>
      <CrossVerificationBoard caseId={caseId} finding={finding} />
    </AssessmentStage>
  );
}
