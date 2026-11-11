import { CircleDashed, Info } from "lucide-react";
import type { Readiness } from "@/api/types";
import { t } from "@/config/terminology";
import type { Filter } from "@/domain/checklist";
import { cn } from "@/lib/utils";
import { DocumentReadiness, DocumentStatusList } from "./Readiness";

// Document readiness on the Overview, under the line that says whether the case can go to credit
// review: how many requirements are satisfied of all, the rest as not satisfied broken down by why
// (each count also shows only those in the list below), and every document named under its
// section with its mark and its status. A white card: the colour is in the marks and the chips.

const SHELL = "@container/glance relative rounded-md border border-border bg-surface";

const BODY =
  "grid gap-x-8 gap-y-5 p-4 @min-[40rem]/glance:p-5 @min-[60rem]/glance:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)]";

const STATUS_COLUMN =
  "min-w-0 @min-[60rem]/glance:border-l @min-[60rem]/glance:border-border @min-[60rem]/glance:pl-8";

/** The counts beside every document by section; a provisional checklist says so over them. */
export function ReadinessCard({
  r,
  sections,
  filter,
  onFilter,
  onJump,
}: {
  r: Readiness;
  sections: string[] | undefined;
  filter: Filter;
  onFilter: (f: Filter) => void;
  onJump: (itemId: string) => void;
}) {
  return (
    <section className={SHELL} data-testid="journey-readiness">
      {r.provisional && (
        <p
          className="flex items-start gap-2 border-b border-border bg-info-soft/60 px-4 py-2 text-[12px] leading-5 text-foreground @min-[40rem]/glance:px-5"
          data-testid="journey-provisional"
        >
          <Info className="mt-0.5 size-3.5 shrink-0 text-info" aria-hidden />
          {t("checklist.provisionalHelp")}
        </p>
      )}
      <div className={BODY}>
        <DocumentReadiness items={r.items} filter={filter} onFilter={onFilter} />
        <div className={STATUS_COLUMN}>
          <DocumentStatusList items={r.items} sections={sections} onJump={onJump} />
        </div>
      </div>
    </section>
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

/** The Overview's head while the checklist is read: the status line and the card, each at the
 * height it takes once read, so nothing jumps when it arrives. */
export function OverviewSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" data-testid="journey-loading">
      <p className="sr-only">{t("state.loading")}</p>
      <div className="h-[46px] rounded border border-border bg-surface px-4 py-3" aria-hidden>
        <Line className="h-5" bar="h-3 w-2/3" />
      </div>
      <section className={SHELL} aria-hidden>
        <div className={BODY}>
          <div className="min-w-0">
            <Line className="h-[17px]" bar="h-2.5 w-28" />
            <Pulse className="mt-1 h-[34px] w-28 rounded bg-muted" />
            <Pulse className="mt-2.5 h-2 rounded-full bg-muted" />
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Pulse className="h-[66px] rounded-md bg-muted/60" />
              <Pulse className="h-[66px] rounded-md bg-muted/60" />
            </div>
            <Pulse className="mt-2.5 h-[78px] rounded-md bg-muted/50" />
          </div>
          <div className={STATUS_COLUMN}>
            <Line className="h-[17px]" bar="h-2.5 w-28" />
            <div className="mt-2 space-y-3">
              {[3, 2, 3, 1].map((rows, i) => (
                <div key={i}>
                  <Line className="h-[18px]" bar="h-3 w-36" />
                  <div className="mt-1 divide-y divide-border/70 rounded-md border border-border">
                    {Array.from({ length: rows }, (_, k) => (
                      <div key={k} className="flex h-[41px] items-center gap-2.5 px-2.5">
                        <Pulse className="size-[18px] rounded-full bg-muted" />
                        <Pulse className="h-3 flex-1 rounded bg-muted/70" />
                        <Pulse className="h-3 w-16 rounded bg-muted/70" />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

/** When the checklist could not be read, or there is none yet: what it means, and a retry. */
export function ChecklistNotice({
  state,
  onRetry,
}: {
  state: "error" | "empty";
  onRetry: () => void;
}) {
  return (
    <div
      className="flex items-start gap-3 px-4 py-4"
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
