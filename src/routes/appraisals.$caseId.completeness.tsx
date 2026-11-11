import { createFileRoute } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { ChecklistPanel } from "@/components/case/ChecklistPanel";
import { CreateCaseAction } from "@/components/case/gate/CreateCaseAction";
import { QueriesPanel } from "@/components/case/QueriesPanel";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { StepHeader } from "@/components/case/TabSection";
import { stepKicker } from "@/domain/steps";
import { useAnchor } from "@/domain/anchor";
import { useChecklist, type Filter } from "@/domain/checklist";
import { useFindings } from "@/domain/findings";
import { useCaseProgress } from "@/domain/progress";
import { useCan } from "@/domain/session";

// Stage 3, document readiness (FRD §5, §6): the required document set, each document with
// where it stands and the action that creates the case, beside the query list the RM sends.
// The counts and the verdict are on the Overview.

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
  const [filter, setFilter] = useState<Filter>("all");
  const { caseId } = Route.useParams();
  const checklist = useChecklist(caseId);
  const canReadFindings = useCan("finding.read");
  const findings = useFindings(caseId, canReadFindings);
  const gate = useCaseProgress(caseId).data?.gate ?? null;
  const blockingFindings = canReadFindings
    ? (findings.data ?? []).filter((f) => f.outcome === "fail" && f.blocking).length
    : 0;
  return (
    <>
      <StepHeader
        kicker={stepKicker(caseId, "completeness")}
        title={t("page.completeness.title")}
        purpose={t("page.completeness.purpose")}
      />
      <div className="space-y-4 px-4 py-5 pb-10 sm:px-6">
        <QueryView
          query={checklist}
          isEmpty={(r) => r.items.length === 0}
          empty={{ title: t("checklist.emptyTitle"), description: t("checklist.emptyDescription") }}
        >
          {(r) => (
            <>
              <div className="grid items-start gap-4 @min-[65rem]/main:grid-cols-[minmax(0,1fr)_380px]">
                <Anchor id="checklist" className="min-w-0">
                  <ChecklistPanel
                    caseId={caseId}
                    r={r}
                    filter={filter}
                    onFilter={setFilter}
                    action={<CreateCaseAction caseId={caseId} gate={gate} />}
                    blockingFindings={blockingFindings}
                  />
                </Anchor>
                <Anchor
                  id="queries"
                  className="min-w-0 @min-[65rem]/main:sticky @min-[65rem]/main:top-4"
                >
                  <QueriesPanel caseId={caseId} />
                </Anchor>
              </div>
            </>
          )}
        </QueryView>
      </div>
    </>
  );
}
