import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  Check,
  CircleCheckBig,
  CircleDashed,
  Info,
  OctagonX,
  ShieldCheck,
  X,
  type LucideIcon,
} from "lucide-react";
import type { CaseProgress, ChecklistItemState, Readiness } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { scoreTone } from "@/components/common/scoreTone";
import { t } from "@/config/terminology";
import {
  formatPoints,
  pointsToGo,
  scoreText,
  toGoText,
  verdictOf,
  type Filter,
  type Verdict,
} from "@/domain/checklist";
import { cn } from "@/lib/utils";
import { GlanceRail, type CanOpen } from "./GlanceRail";
import { DocumentReadiness, DocumentStatusList } from "./Readiness";
import { prefersReducedMotion } from "./useJump";

// The readiness glance: the answer to "can this case go to credit review?" in one read. The
// verdict and the gate conditions; document readiness as satisfied of all, the two halves and
// why the rest are not (each count also shows only those in the list below); the weighted score
// the review gate uses; and every document named under its section with a tick or a cross. On
// the Overview a rail under it says what to do next and what to ask the customer.

/** Each verdict's colour, on its icon tile and its words; the card itself stays white.
 * Saturated colour is kept for small signals; anything wide is a pale tint. */
const VERDICT: Record<Verdict, { icon: LucideIcon; tile: string; text: string }> = {
  blocked: {
    icon: OctagonX,
    tile: "bg-critical-soft text-destructive",
    text: "text-destructive",
  },
  belowGate: {
    icon: AlertTriangle,
    tile: "bg-flag-soft text-flag-foreground",
    text: "text-flag-foreground",
  },
  gateMet: {
    icon: CircleCheckBig,
    tile: "bg-positive-soft text-positive",
    text: "text-positive",
  },
  ready: {
    icon: ShieldCheck,
    tile: "bg-positive-soft text-positive",
    text: "text-positive",
  },
};

function verdictTitle(v: Verdict): string {
  return v === "ready"
    ? t("readinessGates.readyForCredit")
    : v === "gateMet"
      ? t("journey.verdict.gateMet")
      : t("readiness.notReady");
}

// Relative, so the screen-reader-only text inside is placed within the card and never past the
// end of the scrolling content.
const SHELL =
  "@container/glance relative overflow-hidden rounded-md border border-border bg-surface shadow-[0_1px_2px_0_oklch(0.22_0.017_250/0.06)]";

const BODY =
  "grid gap-x-8 gap-y-5 p-4 @min-[40rem]/glance:p-5 @min-[60rem]/glance:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)]";

// The verdict, the score and what blocks the case. One column on a phone; from 40rem, while the
// card is still one column, the verdict and the score share a row; from 60rem the column sits
// beside the counts, its parts stacked from the top so the score stays with the verdict it
// supports (any room the counts leave falls below them).
const READINESS =
  "grid min-w-0 content-start gap-x-6 gap-y-5 @min-[40rem]/glance:grid-cols-2 @min-[60rem]/glance:grid-cols-1 @min-[60rem]/glance:gap-y-6";

type GlanceProps = {
  caseId: string;
  r: Readiness;
  sections: string[] | undefined;
  progress: CaseProgress | undefined;
  canOpen: CanOpen | undefined;
  filter: Filter;
  onFilter: (f: Filter) => void;
  onJump: (itemId: string) => void;
  /** A note over the card, such as that a later read failed. */
  notice?: ReactNode;
};

/** The Overview's hero card. */
export function Glance({
  caseId,
  r,
  sections,
  progress,
  canOpen,
  filter,
  onFilter,
  onJump,
  notice,
}: GlanceProps) {
  const v = verdictOf(r);
  const live = useLiveVerdict(r, v);
  return (
    <section
      className={SHELL}
      data-testid="journey-verdict"
      data-state={v}
      aria-labelledby="journey-verdict-title"
    >
      {notice}
      <div className={BODY}>
        <div className={READINESS} data-testid="journey-readiness">
          {/* Where the verdict and the score share a row, the provisional strip sits under the
              score (whose striped fill it explains), beside the verdict rather than below it. */}
          <div className="min-w-0 @min-[40rem]/glance:contents @min-[60rem]/glance:block">
            <VerdictRow
              r={r}
              v={v}
              progress={progress}
              caseId={caseId}
              className={cn(
                "@min-[40rem]/glance:row-start-1",
                r.provisional && "@min-[40rem]/glance:row-span-2",
              )}
            />
            {r.provisional && (
              <ProvisionalStrip className="mt-3 @min-[40rem]/glance:col-start-2 @min-[40rem]/glance:row-start-2 @min-[40rem]/glance:-mt-2 @min-[60rem]/glance:mt-3" />
            )}
          </div>
          {/* Document readiness first: satisfied of all, the two halves, why the rest are not.
              The weighted score the review gate uses follows, as the gate's own measure. */}
          <div
            className="@min-[40rem]/glance:col-span-2 @min-[60rem]/glance:col-span-1"
            data-testid="journey-summary"
          >
            <DocumentReadiness items={r.items} filter={filter} onFilter={onFilter} />
          </div>
          <ReadinessMeter
            r={r}
            className="border-t border-border pt-4 @min-[40rem]/glance:col-span-2 @min-[60rem]/glance:col-span-1"
          />
        </div>

        {/* Every document named under its section, with a tick or a cross. */}
        <div className="min-w-0 @min-[60rem]/glance:border-l @min-[60rem]/glance:border-border @min-[60rem]/glance:pl-8">
          <DocumentStatusList items={r.items} sections={sections} onJump={onJump} />
        </div>
      </div>
      <GlanceRail caseId={caseId} progress={progress} canOpen={canOpen} />
      <p className="sr-only" aria-live="polite" data-testid="journey-live">
        {live}
      </p>
    </section>
  );
}

/** Empty on mount; once a later read of the checklist moves the score or the verdict, it says
 * the new ones. */
function useLiveVerdict(r: Readiness, v: Verdict): string {
  const [live, setLive] = useState("");
  const last = useRef({ score: r.score_pct, verdict: v });
  useEffect(() => {
    if (last.current.score === r.score_pct && last.current.verdict === v) return;
    last.current = { score: r.score_pct, verdict: v };
    setLive(
      t("journey.live", { score: scoreText(r.score_pct, r.gate_pct), verdict: verdictTitle(v) }),
    );
  }, [r.score_pct, r.gate_pct, v]);
  return live;
}

function ProvisionalLozenge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "rounded-full border border-info/40 bg-info-soft px-2 py-px text-[10.5px] font-semibold uppercase leading-4 tracking-wide text-info",
        className,
      )}
    >
      {t("checklist.provisional")}
    </span>
  );
}

function ProvisionalStrip({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        "flex items-start gap-2 rounded-md border border-info/30 bg-info-soft px-3 py-2 text-[12px] leading-5 text-foreground",
        className,
      )}
      data-testid="journey-provisional"
    >
      <Info className="mt-0.5 size-3.5 shrink-0 text-info" aria-hidden />
      {t("checklist.provisionalHelp")}
    </p>
  );
}

/** The verdict, and under it the conditions of the gate, each met or not. */
function VerdictRow({
  r,
  v,
  progress,
  caseId,
  className,
}: {
  r: Readiness;
  v: Verdict;
  progress: CaseProgress | undefined;
  caseId: string;
  className?: string;
}) {
  const Icon = VERDICT[v].icon;
  const gate = progress?.gate;
  return (
    <div className={cn("flex min-w-0 items-start gap-3", className)}>
      <span
        aria-hidden
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-md @min-[40rem]/glance:size-9",
          VERDICT[v].tile,
        )}
      >
        <Icon className="size-[18px] @min-[40rem]/glance:size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <h2
          id="journey-verdict-title"
          className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[16px] font-semibold leading-[22px] tracking-tight text-foreground @min-[40rem]/glance:text-[18px] @min-[40rem]/glance:leading-6"
        >
          {verdictTitle(v)}
          {r.provisional && <ProvisionalLozenge />}
          {gate?.open && (
            <Chip tone="positive" className="tracking-normal">
              <ShieldCheck className="size-3" aria-hidden />
              {t("assessment.gateTitleOpen")}
            </Chip>
          )}
        </h2>
        <ul
          className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1"
          aria-label={t("journey.verdict.conditions")}
          data-testid="journey-conditions"
        >
          <Condition met={r.score_pct >= r.gate_pct} v={v}>
            {t("readiness.reviewGate")} ·{" "}
            {r.score_pct >= r.gate_pct ? t("readiness.met") : toGoText(pointsToGo(r))}
          </Condition>
          <Condition met={r.blocking_open === 0} v={v}>
            {r.blocking_open === 0
              ? t("console.nothingBlocking")
              : `${t("assessment.tile.blocking")} · ${r.blocking_open} ${t("assessment.tile.blockingOpen")}`}
          </Condition>
          {gate && (
            <Condition met={gate.open_exceptions === 0} v={v}>
              {gate.open_exceptions === 0 ? (
                t("assessment.condition.openExceptionsClear")
              ) : (
                <Link
                  to="/appraisals/$caseId/documents"
                  params={{ caseId }}
                  className="rounded-sm text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                >
                  {t("assessment.condition.openExceptions", { n: gate.open_exceptions })}
                </Link>
              )}
            </Condition>
          )}
        </ul>
      </div>
    </div>
  );
}

function Condition({ met, v, children }: { met: boolean; v: Verdict; children: ReactNode }) {
  const Glyph = met ? Check : X;
  return (
    <li
      className="inline-flex items-center gap-1.5 text-[12.5px] leading-5 text-foreground"
      data-met={met}
    >
      <span
        aria-hidden
        className={cn(
          "grid size-4 shrink-0 place-items-center rounded-full",
          met
            ? "bg-positive-soft text-positive"
            : v === "blocked"
              ? "bg-critical-soft text-destructive"
              : "bg-flag-soft text-flag-foreground",
        )}
      >
        <Glyph className="size-3" strokeWidth={2.5} />
      </span>
      <span className="sr-only">{t(met ? "readiness.met" : "readiness.notMet")}: </span>
      <span>{children}</span>
    </li>
  );
}

/** The weighted score against the gate: the number, and a meter with the gate marked on it. */
function ReadinessMeter({ r, className }: { r: Readiness; className?: string }) {
  const [help, setHelp] = useState(false);
  const score = r.score_pct;
  const gate = r.gate_pct;
  const met = score >= gate;
  const shown = useShownScore(score);
  const text = scoreText(score, gate);
  return (
    <div className={cn("min-w-0", className)}>
      <div className="grid grid-cols-[auto_minmax(0,1fr)] items-end gap-x-5">
        <div>
          <p
            className="tabular text-[22px] font-semibold leading-none tracking-tight text-foreground"
            data-testid="journey-score"
          >
            {text}
            <span className="ml-0.5 text-[14px] font-medium text-muted-foreground">%</span>
          </p>
          <p className="mt-1.5 flex items-center gap-1">
            <span id="journey-score-label" className="field-label">
              {t("readiness.score")}
            </span>
            <button
              type="button"
              aria-expanded={help}
              aria-controls="journey-score-help"
              aria-label={t("journey.scoreHelpToggle")}
              onClick={() => setHelp((h) => !h)}
              // 24px to press, laid out as 16px so the label row keeps its height.
              className="-m-1 grid size-6 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
            >
              <Info className="size-3" />
            </button>
          </p>
        </div>
        <div
          role="meter"
          aria-labelledby="journey-score-label"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={score}
          aria-valuetext={
            met
              ? t("journey.meterMet", { score: text, gate: formatPoints(gate) })
              : t("journey.meter", {
                  score: text,
                  gate: formatPoints(gate),
                  toGo: toGoText(pointsToGo(r)),
                })
          }
          className="relative pb-1.5 pt-5"
          data-testid="journey-meter"
        >
          <span
            aria-hidden
            className={cn(
              "tabular absolute top-0 whitespace-nowrap text-[11px] font-medium text-foreground",
              gate > 70 ? "-translate-x-full" : gate < 30 ? "" : "-translate-x-1/2",
            )}
            style={{ left: `${gate}%` }}
          >
            {t("readiness.reviewGate")} {formatPoints(gate)}%
          </span>
          {/* In forced colours (high contrast) a background is dropped, so the track, the fill
              and the gate mark keep system colours of their own there. */}
          <div className="relative h-2.5 rounded-full bg-muted forced-colors:border forced-colors:border-[CanvasText] forced-colors:bg-[Canvas] forced-colors:forced-color-adjust-none">
            <div
              className={cn(
                "absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out motion-reduce:transition-none forced-colors:bg-[Highlight]",
                scoreTone(score, gate, r.blocking_open),
                r.provisional && "pattern-stripes",
              )}
              style={{ width: `${Math.max(0, Math.min(100, shown))}%` }}
              data-testid="journey-meter-fill"
            />
            <span
              aria-hidden
              className="absolute -inset-y-1 w-0.5 rounded-full bg-foreground forced-colors:bg-[CanvasText]"
              style={{ left: `calc(${gate}% - 1px)` }}
            />
          </div>
        </div>
      </div>
      <p
        id="journey-score-help"
        hidden={!help}
        className="mt-2 text-[11.5px] leading-5 text-muted-foreground"
      >
        {t("readiness.scoreHelp")}
      </p>
    </div>
  );
}

/** The score the meter shows: from nothing to the score once the card is painted, then from
 * each score to the next, so the effect of an upload is seen. At once under reduced motion. */
function useShownScore(score: number): number {
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? score : 0));
  useEffect(() => {
    const frame = requestAnimationFrame(() => setShown(score));
    return () => cancelAnimationFrame(frame);
  }, [score]);
  return shown;
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

/** Document readiness while the checklist is read: the headline, the bar, the two halves and the
 * breakdown, each at its own height. */
function ReadinessSkeleton() {
  return (
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
  );
}

/** Every document under its section while the checklist is read: four sections of rows. */
function StatusSkeleton() {
  return (
    <div className="min-w-0">
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
  );
}

/** The hero's shape while the checklist is read, laid out as the hero is at every width (with
 * what blocks the case, the common case before a file has come in), so nothing jumps when it
 * arrives. */
export function GlanceSkeleton({
  caseId,
  progress,
  canOpen,
}: {
  caseId: string;
  progress: CaseProgress | undefined;
  canOpen: CanOpen | undefined;
}) {
  return (
    <section className={SHELL} aria-busy="true" data-testid="journey-verdict" data-state="loading">
      <p className="sr-only">{t("state.loading")}</p>
      <div className={BODY} aria-hidden>
        <div className={READINESS}>
          <div className="flex min-w-0 items-start gap-3 @min-[40rem]/glance:row-start-1">
            <Pulse className="size-8 shrink-0 rounded-md bg-muted @min-[40rem]/glance:size-9" />
            <div className="min-w-0 flex-1">
              <Line className="h-[22px] @min-[40rem]/glance:h-6" bar="h-4 w-2/3" />
              <Line className="mt-1.5 h-5" bar="h-3 w-3/4" />
            </div>
          </div>
          <div className="@min-[40rem]/glance:col-span-2 @min-[60rem]/glance:col-span-1">
            <ReadinessSkeleton />
          </div>
          <div className="border-t border-border pt-4 @min-[40rem]/glance:col-span-2 @min-[60rem]/glance:col-span-1">
            <Pulse className="h-[22px] w-16 rounded bg-muted" />
            <Line className="mt-1.5 h-[17px]" bar="h-2.5 w-24" />
          </div>
        </div>
        <div className="min-w-0 @min-[60rem]/glance:border-l @min-[60rem]/glance:border-border @min-[60rem]/glance:pl-8">
          <StatusSkeleton />
        </div>
      </div>
      <GlanceRail caseId={caseId} progress={progress} canOpen={canOpen} />
    </section>
  );
}

/** The hero when the checklist could not be read, or there is none yet: a neutral line, what
 * it means, and the rail (what to do next still holds). */
export function GlanceNotice({
  state,
  caseId,
  progress,
  canOpen,
  onRetry,
}: {
  state: "error" | "empty";
  caseId: string;
  progress: CaseProgress | undefined;
  canOpen: CanOpen | undefined;
  onRetry: () => void;
}) {
  return (
    <section
      className={SHELL}
      data-testid="journey-verdict"
      data-state={state}
      aria-labelledby="journey-verdict-title"
    >
      <div className="p-4 @min-[40rem]/glance:p-5">
        <NoticeRow state={state} onRetry={onRetry} />
      </div>
      <GlanceRail caseId={caseId} progress={progress} canOpen={canOpen} />
    </section>
  );
}

function NoticeRow({ state, onRetry }: { state: "error" | "empty"; onRetry: () => void }) {
  return (
    <div className="flex items-start gap-3">
      <span
        aria-hidden
        className="grid size-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground @min-[40rem]/glance:size-9"
      >
        <CircleDashed className="size-[18px] @min-[40rem]/glance:size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <h2
          id="journey-verdict-title"
          className="text-[16px] font-semibold leading-[22px] tracking-tight text-foreground @min-[40rem]/glance:text-[18px] @min-[40rem]/glance:leading-6"
        >
          {state === "error" ? t("caseHeader.readinessUnavailable") : t("checklist.emptyTitle")}
        </h2>
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
