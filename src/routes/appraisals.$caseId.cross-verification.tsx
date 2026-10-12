import { createFileRoute } from "@tanstack/react-router";
import { CrossVerificationBoard } from "@/components/case/xv/Board";
import { t } from "@/config/terminology";

// Stage 4, cross-verification (FRD §5, §6, F-18, F-19): the board by area (identity, turnover,
// bank accounts, existing obligations), an overview card for each; in each area its discrepancies
// ranked by credit impact, each with its sources side by side and a decision, then what could not
// be checked, what passed, and the facts the checks compared.

export const Route = createFileRoute("/appraisals/$caseId/cross-verification")({
  head: () => ({
    meta: [{ title: `${t("caseTab.crossVerification")} — ${t("tenant.product.name")}` }],
  }),
  component: CrossVerificationTab,
});

function CrossVerificationTab() {
  const { caseId } = Route.useParams();
  return <CrossVerificationBoard caseId={caseId} />;
}
