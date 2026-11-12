import { Link } from "@tanstack/react-router";
import { AlertTriangle, CheckCircle2, CircleDashed, Clock, Info, Loader2 } from "lucide-react";
import type { CaseProgress, Readiness } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { readyForCredit, scoreText, useChecklist, useTaxonomy } from "@/domain/checklist";
import { readinessWait, type ReadinessWait } from "@/domain/progress";
import { cn } from "@/lib/utils";
import { DocumentReadiness, DocumentStatusList } from "./Readiness";

// The head of the Overview: one line on whether the case can go to credit review, then document
// readiness (satisfied of all, and why the rest are not) and, under it, every document by section
// with its mark and status. White panels: the colour is in the marks and the chips.
//
// Test ids: journey-verdict (the status line; data-state ready, not_ready, waiting-documents,
// waiting-reading, error, empty), journey-readiness (both panels), readiness-panel-readiness and
// readiness-panel-status, journey-provisional, journey-loading (the skeleton).

/** The Overview's head for a case: the status line, then document readiness once there is
 * something to count. */
export function OverviewReadiness({
  caseId,
  progress,
}: {
  caseId: string;
  progress: CaseProgress | undefined;
}) {
  const checklist = useChecklist(caseId);
  const taxonomy = useTaxonomy();
  const r = checklist.data;

  if (!r) {
    if (!checklist.isError) return <OverviewSkeleton />;
    return <ChecklistNotice state="error" onRetry={() => void checklist.refetch()} />;
  }
  if (r.items.length === 0)
    return <ChecklistNotice state="empty" onRetry={() => void checklist.refetch()} />;

  // Until the documents are in and read, the counts would only say "nothing yet": the status
  // line says what readiness waits on, and the counts follow once there is something to count.
  const wait = readinessWait(progress, r);
  // Once the engine says the case is created, the documents are history: the status line and the
  // counts fold into one line (the case progress above says the same), opened on request.
  if (progress?.gate?.open && !wait) {
    return (
      <details
        className="group rounded border border-border bg-surface"
        data-testid="journey-folded"
      >
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-[12.5px] hover:bg-surface-muted">
          <span className="font-medium text-foreground">
            {t("journey.readiness.title")}
            <span className="ml-2 font-normal text-muted-foreground">
              {t("journey.foldedCount", {
                n: r.items.filter((i) => i.status === "satisfied").length,
                total: r.items.length,
              })}
            </span>
          </span>
          <span className="text-[12px] font-medium text-primary group-open:hidden">
            {t("journey.show")}
          </span>
        </summary>
        <div className="space-y-4 border-t border-border p-4">
          <OverviewStatus r={r} wait={wait} caseId={caseId} />
          <ReadinessCard r={r} sections={taxonomy.data?.sections} />
        </div>
      </details>
    );
  }
  return (
    <div className="space-y-4">
      <OverviewStatus r={r} wait={wait} caseId={caseId} />
      {!wait && <ReadinessCard r={r} sections={taxonomy.data?.sections} />}
    </div>
  );
}

/** Whether the case can go to credit review, in one line; or, before the documents are in and
 * read, what readiness is waiting on. */
function OverviewStatus({
  r,
  wait,
  caseId,
}: {
  r: Readiness;
  wait: ReadinessWait;
  caseId: string;
}) {
  // Before the documents are in and read, the score and blocking count would only say "nothing
  // received yet": say what readiness waits on instead.
  if (wait) {
    const text =
      wait.kind === "documents"
        ? t("overviewStatus.waitingDocuments")
        : wait.total > 0
          ? t("overviewStatus.reading", { done: wait.done, total: wait.total })
          : t("overviewStatus.readingStarted");
    const Icon = wait.kind === "documents" ? Clock : Loader2;
    return (
      <section
        className="flex flex-wrap items-start gap-2.5 rounded border border-border bg-surface-muted px-4 py-3 text-[13px] text-foreground"
        data-testid="journey-verdict"
        data-state={`waiting-${wait.kind}`}
        role="status"
      >
        <Icon
          className={cn(
            "mt-0.5 size-4 shrink-0 text-muted-foreground",
            wait.kind === "reading" && "animate-spin",
          )}
          aria-hidden
        />
        <p className="min-w-0 flex-1 font-medium">{text}</p>
        {wait.kind === "documents" && (
          <Link
            to="/appraisals/$caseId/documents"
            params={{ caseId }}
            className="text-[12.5px] font-medium text-primary hover:underline"
            data-testid="verdict-upload"
          >
            {t("overviewStatus.uploadDocuments")}
          </Link>
        )}
      </section>
    );
  }
  const ready = readyForCredit(r);
  const score = scoreText(r.score_pct, r.gate_pct);
  const gate = Math.round(r.gate_pct);
  const text = ready
    ? t("overviewStatus.ready", { score, gate })
    : r.blocking_open > 0
      ? t("overviewStatus.notReady", { score, gate, n: r.blocking_open })
      : t("overviewStatus.notReadyScore", { score, gate });
  const Icon = ready ? CheckCircle2 : AlertTriangle;
  // White, as every card is: the colour is in the edge and the icon, the words stay readable.
  return (
    <section
      className={cn(
        "flex items-start gap-2.5 rounded border border-l-2 border-border bg-surface px-4 py-3 text-[13px] text-foreground",
        ready
          ? "border-l-positive/60 [&>svg]:text-positive"
          : "border-l-destructive/50 [&>svg]:text-destructive",
      )}
      data-testid="journey-verdict"
      data-state={ready ? "ready" : "not_ready"}
      role="status"
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p className="font-medium">{text}</p>
    </section>
  );
}

/** Document readiness, then every document's status under it; a provisional checklist says so
 * over the counts. */
function ReadinessCard({ r, sections }: { r: Readiness; sections: string[] | undefined }) {
  return (
    <div className="space-y-4" data-testid="journey-readiness">
      <Panel title={t("journey.readiness.title")} testId="readiness-panel-readiness">
        {r.provisional && <ProvisionalNote />}
        <div className="px-4 py-4">
          <DocumentReadiness items={r.items} />
        </div>
      </Panel>
      <Panel title={t("journey.status.title")} testId="readiness-panel-status">
        <div className="px-4 py-4">
          <DocumentStatusList items={r.items} sections={sections} />
        </div>
      </Panel>
    </div>
  );
}

function ProvisionalNote() {
  return (
    <p
      className="flex items-start gap-2 border-b border-border bg-info-soft/60 px-4 py-2 text-[12px] leading-5 text-foreground"
      data-testid="journey-provisional"
    >
      <Info className="mt-0.5 size-3.5 shrink-0 text-info" aria-hidden />
      {t("checklist.provisionalHelp")}
    </p>
  );
}

// --- Before the checklist is read, when it cannot be, and when there is none ---

function Pulse({ className }: { className: string }) {
  return <div className={cn("animate-pulse motion-reduce:animate-none", className)} />;
}

/** A bar centred in a line of text's height, so a placeholder takes the line's room. */
function Line({ className, bar }: { className: string; bar: string }) {
  return (
    <div className={cn("flex items-center", className)}>
      <Pulse className={cn("rounded bg-muted", bar)} />
    </div>
  );
}

/** The Overview's head while the checklist is read: the status line and the readiness panel at
 * the heights they take once read, so nothing jumps when they arrive. */
function OverviewSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" data-testid="journey-loading">
      <p className="sr-only">{t("state.loading")}</p>
      <div className="h-[46px] rounded border border-border bg-surface px-4 py-3" aria-hidden>
        <Line className="h-5" bar="h-3 w-2/3" />
      </div>
      <section className="rounded border border-border bg-surface" aria-hidden>
        <div className="border-b border-border px-4 py-2.5">
          <Line className="h-[18px]" bar="h-2.5 w-36" />
        </div>
        <div className="px-4 py-4">
          <Pulse className="h-[34px] w-28 rounded bg-muted" />
          <Pulse className="mt-2.5 h-2 rounded-full bg-muted" />
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Pulse className="h-[66px] rounded-md bg-muted/60" />
            <Pulse className="h-[66px] rounded-md bg-muted/60" />
          </div>
          <Pulse className="mt-2.5 h-[78px] rounded-md bg-muted/50" />
        </div>
      </section>
    </div>
  );
}

/** When the checklist could not be read, or there is none yet: what it means, and a retry. */
function ChecklistNotice({ state, onRetry }: { state: "error" | "empty"; onRetry: () => void }) {
  return (
    <div
      className="flex items-start gap-3 rounded border border-border bg-surface px-4 py-4"
      data-testid="journey-verdict"
      data-state={state}
    >
      <span
        aria-hidden
        className="grid size-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground"
      >
        <CircleDashed className="size-[18px]" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold text-foreground">
          {state === "error" ? t("caseHeader.readinessUnavailable") : t("checklist.emptyTitle")}
        </p>
        {state === "error" ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 inline-flex h-8 items-center rounded border border-border bg-surface px-3 text-[12px] font-medium hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            {t("action.retry")}
          </button>
        ) : (
          <p className="mt-1 text-[12.5px] text-muted-foreground">
            {t("checklist.emptyDescription")}
          </p>
        )}
      </div>
    </div>
  );
}
