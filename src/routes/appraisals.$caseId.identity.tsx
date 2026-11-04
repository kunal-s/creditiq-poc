import { createFileRoute } from "@tanstack/react-router";
import { IdentitySection } from "@/components/case/IdentitySection";
import { TabSection } from "@/components/case/TabSection";
import { stepKicker } from "@/domain/steps";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { t } from "@/config/terminology";

// The appraisal's first step, as the original design: who the borrower is, its identifiers with
// where each came from, and the promoters, directors or partners with the KYC attributed to them.

export const Route = createFileRoute("/appraisals/$caseId/identity")({
  head: () => ({
    meta: [{ title: `${t("caseTab.identity")} — ${t("tenant.product.name")}` }],
  }),
  component: IdentityTab,
});

function IdentityTab() {
  const { caseId } = Route.useParams();
  return (
    <CaseScreen caseId={caseId}>
      {(c) => (
        <div className="pb-10">
          <TabSection
            id="identity"
            kicker={stepKicker(c.id, "identity")}
            title={t("page.identity.title")}
            purpose={t("page.identity.purpose")}
          >
            <IdentitySection c={c} />
          </TabSection>
        </div>
      )}
    </CaseScreen>
  );
}
