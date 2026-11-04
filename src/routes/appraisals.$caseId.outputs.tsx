import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { AssessmentStage } from "@/components/case/gate/AssessmentStage";
import { CamReviewView } from "@/components/case/cam/CamReview";
import { PdNoteView } from "@/components/case/Outputs";
import { TabSection } from "@/components/case/TabSection";
import { stepKicker } from "@/domain/steps";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

// Stage 6, outputs (FRD §5, §6): the draft CAM and the PD note, each a view within the tab. The
// spread moved to the Financials section of the Financials and Policy tab; ?view=spread, from an
// earlier link, goes there.

const VIEWS = ["cam", "pd"] as const;
type View = (typeof VIEWS)[number];

export const Route = createFileRoute("/appraisals/$caseId/outputs")({
  validateSearch: (search: Record<string, unknown>): { view?: View | "spread" } => {
    const view = search["view"];
    return VIEWS.includes(view as View) || view === "spread" ? { view: view as View } : {};
  },
  beforeLoad: ({ search, params }) => {
    if (search.view === "spread")
      throw redirect({ to: "/appraisals/$caseId/policy", params, hash: "financials" });
  },
  head: () => ({
    meta: [{ title: `${t("caseTab.outputs")} — ${t("tenant.product.name")}` }],
  }),
  component: OutputsTab,
});

function OutputsTab() {
  const { caseId } = Route.useParams();
  const search = Route.useSearch().view;
  const view: View = search === "pd" ? "pd" : "cam";
  return (
    <AssessmentStage caseId={caseId}>
      <div className="pb-10">
        <TabSection
          id={view}
          kicker={stepKicker(caseId, "outputs")}
          title={t("page.draft.title")}
          purpose={t("page.draft.purpose")}
          actions={
            <nav className="flex gap-1" aria-label={t("caseTab.outputs")}>
              {VIEWS.map((v) => (
                <Link
                  key={v}
                  to="/appraisals/$caseId/outputs"
                  params={{ caseId }}
                  search={{ view: v }}
                  data-testid={`view-${v}`}
                  className={cn(
                    "rounded px-2.5 py-1 text-[12px] font-medium transition-colors",
                    v === view
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted",
                  )}
                >
                  {t(`outputs.view.${v}`)}
                </Link>
              ))}
            </nav>
          }
        >
          <div className="px-4 py-4 sm:px-6">
            {view === "cam" ? <CamReviewView caseId={caseId} /> : <PdNoteView caseId={caseId} />}
          </div>
        </TabSection>
      </div>
    </AssessmentStage>
  );
}
