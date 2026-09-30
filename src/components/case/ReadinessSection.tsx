import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, ArrowRight, FileText, ShieldCheck } from "lucide-react";
import type { ChecklistItemState, Readiness } from "@/api/types";
import { Panel, ScoreBar } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { ChecklistStatusChip } from "@/components/documents/chips";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { countItems, isOpen, readyForCredit, useChecklist, useTaxonomy } from "@/domain/checklist";
import { useCaseDocuments } from "@/domain/documents";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/docready/$caseId/readiness")({
  head: () => ({
    meta: [{ title: `${t("page.readiness.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ReadinessTab,
});

function ReadinessTab() {
  const { caseId } = Route.useParams();
  const checklist = useChecklist(caseId);
  return (
    <div className="px-4 py-5 sm:px-6">
      <QueryView
        query={checklist}
        isEmpty={(r) => r.items.length === 0}
        empty={{ title: t("checklist.emptyTitle"), description: t("checklist.emptyDescription") }}
      >
        {(r) => <ReadinessView caseId={caseId} r={r} />}
      </QueryView>
    </div>
  );
}

function ReadinessView({ caseId, r }: { caseId: string; r: Readiness }) {
  const taxonomy = useTaxonomy();
  const counts = countItems(r.items);
  const blocking = r.items.filter((i) => i.blocking && isOpen(i));
  const soft = r.items.filter((i) => !i.blocking && isOpen(i));
  const satisfied = r.items.filter((i) => i.status === "satisfied");
  const ready = readyForCredit(r);
  const score = Math.round(r.score_pct);
  const gates = [
    { label: t("readiness.reviewGate"), threshold: r.gate_pct, met: r.gate_met },
    ...(taxonomy.data
      ? [
          {
            label: t("readiness.disbursementGate"),
            threshold: taxonomy.data.disbursement_gate_threshold,
            met: r.score_pct >= taxonomy.data.disbursement_gate_threshold && r.blocking_open === 0,
          },
        ]
      : []),
  ];

  return (
    <div className="grid gap-4 [@media(min-width:1280px)]:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-4">
        {ready ? (
          <div
            className="flex items-start gap-3 rounded border border-positive/40 bg-positive-soft px-4 py-3"
            data-testid="gate-banner"
            data-ready="true"
          >
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-positive">
                {t("readinessGates.readyForCredit")}
              </p>
              <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-positive/90">
                {t("readiness.readyHelp", { gate: Math.round(r.gate_pct) })}
              </p>
            </div>
          </div>
        ) : (
          <div
            className="flex items-start gap-3 rounded border border-destructive/35 bg-destructive/10 px-4 py-3"
            data-testid="gate-banner"
            data-ready="false"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-destructive">
                {t("readiness.notReady", { score, gate: Math.round(r.gate_pct) })}
                {blocking.length > 0 && ` ${t("readiness.withBlocking", { n: blocking.length })}`}
              </p>
              <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-destructive/90">
                {t("readiness.notReadyHelp")}
              </p>
            </div>
          </div>
        )}

        <Panel title={t("readiness.score")} subtitle={t("readiness.scoreHelp")}>
          <div className="px-4 py-4">
            <div className="flex flex-wrap items-end gap-4">
              <p
                className="tabular text-[38px] font-semibold leading-none text-foreground"
                data-testid="readiness-score"
              >
                {score}%
              </p>
              <div className="min-w-[10rem] flex-1">
                <ScoreBar
                  score={r.score_pct}
                  gate={r.gate_pct}
                  blocking={r.blocking_open}
                  className="h-2"
                />
                <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                  {t("readiness.counts", {
                    satisfied: counts.satisfied,
                    insufficient: counts.insufficient,
                    missing: counts.missing,
                    total: counts.total,
                  })}
                </p>
              </div>
            </div>
            {r.provisional && (
              <p className="mt-2 text-[12px] text-flag-foreground">
                {t("checklist.provisionalHelp")}
              </p>
            )}
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {gates.map((g) => (
                <div
                  key={g.label}
                  className={cn(
                    "rounded border px-3 py-2",
                    g.met
                      ? "border-positive/40 bg-positive-soft"
                      : "border-border bg-surface-muted/50",
                  )}
                  data-testid="gate"
                >
                  <p className="flex items-center justify-between gap-2 text-[12.5px] font-medium text-foreground">
                    <span>{g.label}</span>
                    <span
                      className={cn(
                        "tabular text-[11.5px]",
                        g.met ? "text-positive" : "text-muted-foreground",
                      )}
                    >
                      {g.met ? t("readiness.met") : t("readiness.notMet")}
                    </span>
                  </p>
                  <p className="tabular mt-0.5 text-[11.5px] text-muted-foreground">
                    {t("readiness.threshold", { threshold: Math.round(g.threshold), score })}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </Panel>

        <Gaps
          caseId={caseId}
          title={t("readiness.blocking")}
          subtitle={t("readiness.blockingHelp")}
          items={blocking}
          empty={t("readiness.noBlocking")}
          testId="blocking-gaps"
        />
        <Gaps
          caseId={caseId}
          title={t("readiness.nonBlocking")}
          subtitle={t("readiness.nonBlockingHelp")}
          items={soft}
          empty={t("readiness.noNonBlocking")}
          testId="non-blocking-gaps"
        />
      </div>

      <div className="min-w-0 space-y-3">
        <div className="rounded border border-border bg-surface p-4">
          <p className="field-label">{t("readiness.next")}</p>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
            {ready ? t("readiness.nextReady") : t("readiness.nextNotReady")}
          </p>
          <div className="mt-3 flex flex-col gap-2">
            <Link
              to="/docready/$caseId/collection"
              params={{ caseId }}
              className="flex items-center justify-center gap-1.5 rounded border border-border px-3 py-1.5 text-[12.5px] font-medium hover:bg-muted"
            >
              {t("term.queryList")} <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              to="/appraisals/$id/upload"
              params={{ id: caseId }}
              className="flex items-center justify-center gap-1.5 rounded border border-border px-3 py-1.5 text-[12.5px] font-medium hover:bg-muted"
            >
              {t("step.documents")} <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        <div className="rounded border border-border bg-surface p-4">
          <p className="field-label mb-2">{t("readiness.satisfied")}</p>
          {satisfied.length === 0 ? (
            <p className="text-[12px] text-muted-foreground">{t("readiness.noneSatisfied")}</p>
          ) : (
            <ul className="space-y-1 text-[12px]">
              {satisfied.map((i) => (
                <li key={i.item_id} className="flex items-start gap-2">
                  <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0 text-positive" />
                  <span className="text-foreground">{i.name}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function Gaps({
  caseId,
  title,
  subtitle,
  items,
  empty,
  testId,
}: {
  caseId: string;
  title: string;
  subtitle: string;
  items: ChecklistItemState[];
  empty: string;
  testId: string;
}) {
  const viewer = useDocViewer();
  const documents = useCaseDocuments(caseId);
  return (
    <Panel title={title} subtitle={subtitle} testId={testId}>
      {items.length === 0 ? (
        <p className="px-4 py-3 text-[12.5px] text-muted-foreground">{empty}</p>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((i) => {
            const doc = documents.data?.find((d) => (i.document_ids ?? []).includes(d.id));
            return (
              <li
                key={i.item_id}
                className="flex flex-wrap items-start gap-2 px-4 py-2.5"
                data-testid="gap"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-foreground">{i.name}</span>
                  <span className="mt-0.5 block text-[12px] leading-relaxed text-muted-foreground">
                    {i.deficiency ?? i.why}
                  </span>
                  {doc && (
                    <button
                      type="button"
                      onClick={() =>
                        viewer.open({ caseId, documentId: doc.id, page: doc.page_from })
                      }
                      className="mt-1.5 inline-flex items-center gap-1.5 rounded border border-border bg-surface px-2 py-0.5 text-[11.5px] font-medium text-primary hover:bg-muted"
                    >
                      <FileText className="h-3 w-3" />{" "}
                      {t("readiness.openEvidence", { page: doc.page_from })}
                    </button>
                  )}
                </span>
                <ChecklistStatusChip status={i.status} />
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
