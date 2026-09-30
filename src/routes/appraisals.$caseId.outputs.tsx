import { createFileRoute, Link } from "@tanstack/react-router";
import { CamView, PdNoteView, SpreadView } from "@/components/case/Outputs";
import { TabSection } from "@/components/case/TabSection";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

// Stage 6, outputs (FRD §5, §6): the spread, the draft CAM and the PD note,
// each a view within the tab.

const VIEWS = ["spread", "cam", "pd"] as const;
type View = (typeof VIEWS)[number];

const SECTION: Record<View, { page: string }> = {
  spread: { page: "spread" },
  cam: { page: "draft" },
  pd: { page: "draft" },
};

export const Route = createFileRoute("/appraisals/$caseId/outputs")({
  validateSearch: (search: Record<string, unknown>): { view?: View } => {
    const view = search["view"];
    return VIEWS.includes(view as View) ? { view: view as View } : {};
  },
  head: () => ({
    meta: [{ title: `${t("caseTab.outputs")} — ${t("tenant.product.name")}` }],
  }),
  component: OutputsTab,
});

function OutputsTab() {
  const { caseId } = Route.useParams();
  const view: View = Route.useSearch().view ?? "spread";
  const section = SECTION[view];
  return (
    <div className="pb-10">
      <nav className="flex gap-1 px-4 pt-4 sm:px-6" aria-label={t("caseTab.outputs")}>
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
      <TabSection
        id={view}
        title={t(`page.${section.page}.title`)}
        purpose={t(`page.${section.page}.purpose`)}
      >
        <div className="px-4 py-4 sm:px-6">
          {view === "spread" ? (
            <SpreadView caseId={caseId} />
          ) : view === "cam" ? (
            <CamView caseId={caseId} />
          ) : (
            <PdNoteView caseId={caseId} />
          )}
        </div>
      </TabSection>
    </div>
  );
}
