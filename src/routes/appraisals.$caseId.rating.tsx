import { createFileRoute } from "@tanstack/react-router";
import { AssessmentStage } from "@/components/case/gate/AssessmentStage";
import { Summary } from "@/components/case/Outputs";
import { RecommendationEditor } from "@/components/case/RecommendationEditor";
import { AuthoritySection } from "@/components/case/policy/AuthoritySection";
import { StepHeader } from "@/components/case/TabSection";
import { stepKicker } from "@/domain/steps";
import { Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { t } from "@/config/terminology";
import { formatInr, useLabels } from "@/domain/cases";
import { useCam } from "@/domain/findings";
import { useApprovingAuthority } from "@/domain/policy";

// Rating and recommendation, as the original design: where a rating would be (no rating model is
// configured, and the memo says so), what the recommendation rests on, the recommendation credit
// writes, and who must approve the case.

export const Route = createFileRoute("/appraisals/$caseId/rating")({
  head: () => ({
    meta: [{ title: `${t("caseTab.rating")} — ${t("tenant.product.name")}` }],
  }),
  component: RatingTab,
});

function RatingTab() {
  const { caseId } = Route.useParams();
  return (
    <div className="pb-10">
      <StepHeader
        kicker={stepKicker(caseId, "rating")}
        title={t("page.rating.title")}
        purpose={t("page.rating.purpose")}
      />
      <AssessmentStage caseId={caseId}>
        <RatingBody caseId={caseId} />
      </AssessmentStage>
    </div>
  );
}

function RatingBody({ caseId }: { caseId: string }) {
  const cam = useCam(caseId);
  const authority = useApprovingAuthority(caseId);
  const labels = useLabels();
  return (
    <div className="grid items-start gap-4 px-4 py-5 sm:px-6 @min-[60rem]/main:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <QueryView query={cam}>
        {(m) => (
          <div className="min-w-0 space-y-4">
            <Panel title={t("page.rating.ratingTitle")} testId="rating-panel">
              <p className="px-4 py-3 text-[13px] text-muted-foreground" data-testid="rating-note">
                {m.rating_note ?? t("page.rating.noRating")}
              </p>
            </Panel>
            <Panel title={t("page.rating.restsOn")} testId="rating-rests-on">
              <div className="px-4 py-3">
                <Summary caseId={caseId} m={m} headed={false} />
              </div>
            </Panel>
            <div id="recommendation" className="scroll-mt-4">
              <Panel title={m.recommendation_title} testId="rating-recommendation">
                <div className="px-4 py-3">
                  {/* Keyed by the stored words, so a save (or a change made in Outputs) starts the
                      boxes from what the memo now holds. */}
                  <RecommendationEditor key={m.recommendation ?? ""} caseId={caseId} m={m} />
                </div>
              </Panel>
            </div>
          </div>
        )}
      </QueryView>
      <div className="min-w-0 space-y-4">
        <CaseScreen caseId={caseId}>
          {(c) => (
            <Panel title={t("page.rating.facility")} testId="rating-facility">
              <dl className="divide-y divide-border text-[12.5px]">
                <div className="flex justify-between gap-3 px-4 py-2.5">
                  <dt className="text-muted-foreground">{t("caseHeader.ask")}</dt>
                  <dd className="text-right">{labels.facilities(c.facilities)}</dd>
                </div>
                <div className="flex justify-between gap-3 px-4 py-2.5">
                  <dt className="text-muted-foreground">{t("cases.col.amount")}</dt>
                  <dd className="tabular text-right">{formatInr(c.amount_inr)}</dd>
                </div>
                <div className="flex justify-between gap-3 px-4 py-2.5">
                  <dt className="text-muted-foreground">{t("term.rm")}</dt>
                  <dd className="text-right">{c.rm}</dd>
                </div>
              </dl>
            </Panel>
          )}
        </CaseScreen>
        <AuthoritySection caseId={caseId} query={authority} />
      </div>
    </div>
  );
}
