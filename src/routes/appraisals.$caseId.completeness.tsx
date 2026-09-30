import { createFileRoute } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { ChecklistPanel } from "@/components/case/ChecklistPanel";
import { QueriesPanel } from "@/components/case/QueriesPanel";
import { ReadinessSummary } from "@/components/case/ReadinessSummary";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { useAnchor } from "@/domain/anchor";
import { useChecklist } from "@/domain/checklist";

// Stage 3, validation and completeness (FRD §5, §6): readiness against the
// gates, then the checklist beside the query list the RM sends.

export const Route = createFileRoute("/appraisals/$caseId/completeness")({
  head: () => ({
    meta: [{ title: `${t("caseTab.completeness")} — ${t("tenant.product.name")}` }],
  }),
  component: CompletenessTab,
});

function Anchor({
  id,
  className,
  children,
}: {
  id: string;
  className?: string;
  children: ReactNode;
}) {
  const ref = useAnchor<HTMLElement>(id);
  return (
    <section
      ref={ref}
      id={id}
      className={`scroll-mt-4 ${className ?? ""}`}
      data-testid={`section-${id}`}
    >
      {children}
    </section>
  );
}

function CompletenessTab() {
  const { caseId } = Route.useParams();
  const checklist = useChecklist(caseId);
  return (
    <div className="space-y-4 px-4 py-5 pb-10 sm:px-6">
      <QueryView
        query={checklist}
        isEmpty={(r) => r.items.length === 0}
        empty={{ title: t("checklist.emptyTitle"), description: t("checklist.emptyDescription") }}
      >
        {(r) => (
          <>
            <Anchor id="readiness">
              <ReadinessSummary r={r} />
            </Anchor>
            <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
              <Anchor id="checklist" className="min-w-0">
                <ChecklistPanel caseId={caseId} r={r} />
              </Anchor>
              <Anchor id="queries" className="min-w-0 xl:sticky xl:top-4">
                <QueriesPanel caseId={caseId} />
              </Anchor>
            </div>
          </>
        )}
      </QueryView>
    </div>
  );
}
