import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  CircleCheckBig,
  CircleDashed,
  Clock,
  Info,
  ListTodo,
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
  blockers,
  countItems,
  formatPoints,
  passes,
  pointsToGo,
  scoreText,
  sectionGroups,
  toGoText,
  verdictOf,
  type Filter,
  type Verdict,
} from "@/domain/checklist";
import { cn } from "@/lib/utils";
import { CountList, type Count } from "./CountList";
import { GlanceRail, type CanOpen } from "./GlanceRail";
import { CELL, CELL_ICON, ICON, ICON_TONE } from "./status";
import { prefersReducedMotion } from "./useJump";

// The readiness glance: the answer to "can this case go to credit review?" in one read. The
// verdict and the gate conditions, the weighted score against the gate, what blocks it by name,
// then the requirements counted by status (each count also a filter for the list below), and
// the requirements by section. On the Overview a rail under it says what to do next and what to
// ask the customer.

const VERDICT: Record<Verdict, { icon: LucideIcon; tile: string; text: string; rule: string }> = {
  blocked: {
    icon: OctagonX,
    tile: "bg-critical-soft text-destructive",
    text: "text-destructive",
    rule: "bg-destructive",
  },
  belowGate: {
    icon: AlertTriangle,
    tile: "bg-flag-soft text-flag-foreground",
    text: "text-flag-foreground",
    rule: "bg-flag",
  },
  gateMet: {
    icon: CircleCheckBig,
    tile: "bg-positive-soft text-positive",
    text: "text-positive",
    rule: "bg-positive",
  },
  ready: {
    icon: ShieldCheck,
    tile: "bg-positive-soft text-positive",
    text: "text-positive",
    rule: "bg-positive",
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
      <div aria-hidden className={cn("h-[3px]", VERDICT[v].rule)} />
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
          <ReadinessMeter
            r={r}
            className="@min-[40rem]/glance:col-start-2 @min-[40rem]/glance:row-start-1 @min-[60rem]/glance:col-start-auto @min-[60rem]/glance:row-start-auto"
          />
          <BlockedBy
            r={r}
            sections={sections}
            onJump={onJump}
            onFilter={onFilter}
            className="@min-[40rem]/glance:col-span-2 @min-[60rem]/glance:col-span-1"
          />
        </div>

        <div
          className="min-w-0 @min-[60rem]/glance:border-l @min-[60rem]/glance:border-border @min-[60rem]/glance:pl-8"
          data-testid="journey-summary"
        >
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="field-label">{t("journey.requirements", { n: r.items.length })}</h3>
            {filter !== "all" && <ShowAll n={r.items.length} onFilter={onFilter} />}
          </div>
          <StatusTiles
            items={r.items}
            filter={filter}
            onFilter={onFilter}
            className="mt-2 grid-cols-2 @min-[40rem]/glance:grid-cols-4 @min-[60rem]/glance:grid-cols-2 @min-[84rem]/glance:grid-cols-4"
          />
          {/* Only beside the readiness column: while the card is one column it would push what
              to do next below the screen, and every row names its section. */}
          <div className="mt-4 hidden @min-[60rem]/glance:block">
            <h3 className="field-label">{t("journey.bySection")}</h3>
            <SectionMap items={r.items} sections={sections} onJump={onJump} />
          </div>
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
            className="tabular text-[30px] font-semibold leading-none tracking-tight text-foreground @min-[40rem]/glance:text-[36px]"
            data-testid="journey-score"
          >
            {text}
            <span className="ml-0.5 text-[18px] font-medium text-muted-foreground @min-[40rem]/glance:text-[20px]">
              %
            </span>
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

const MAX_BLOCKERS = 4;

/** What stops the case, by name; each opens its row. */
function BlockedBy({
  r,
  sections,
  onJump,
  onFilter,
  className,
}: {
  r: Readiness;
  sections: string[] | undefined;
  onJump: (itemId: string) => void;
  onFilter: (f: Filter) => void;
  className?: string;
}) {
  const list = blockers(r.items, sections);
  if (list.length === 0) return null;
  return (
    <div className={cn("min-w-0", className)}>
      <p className="field-label">{t("journey.blockedBy")}</p>
      <ul className="mt-1.5 flex flex-wrap gap-1.5">
        {list.slice(0, MAX_BLOCKERS).map((item) => {
          const Icon = ICON[item.status];
          return (
            <li key={item.item_id} className="min-w-0 max-w-full">
              <a
                href={`#req-${item.item_id}`}
                onClick={(e) => {
                  e.preventDefault();
                  onJump(item.item_id);
                }}
                className="inline-flex h-8 max-w-full items-center gap-1.5 rounded-full border border-destructive/35 bg-surface pl-2 pr-3 text-[12.5px] font-medium text-foreground transition-colors hover:border-destructive/60 hover:bg-critical-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                data-testid="journey-blocker"
                data-item={item.item_id}
              >
                <Icon className={cn("size-3.5 shrink-0", ICON_TONE[item.status])} aria-hidden />
                <span className="truncate">{item.name}</span>{" "}
                <span className="shrink-0 font-normal text-muted-foreground">
                  · {t(`docStatus.${item.status}`)}
                </span>
              </a>
            </li>
          );
        })}
        {list.length > MAX_BLOCKERS && (
          <li>
            <button
              type="button"
              onClick={() => onFilter("blocking")}
              className="h-8 rounded-sm px-1 text-[12px] font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              {t("page.overview.more", { n: list.length - MAX_BLOCKERS })}
            </button>
          </li>
        )}
      </ul>
    </div>
  );
}

function ShowAll({ n, onFilter }: { n: number; onFilter: (f: Filter) => void }) {
  return (
    <button
      type="button"
      onClick={() => onFilter("all")}
      className="rounded-sm text-[12px] font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      data-testid="journey-filter-all"
    >
      {t("journey.showAll", { n })}
    </button>
  );
}

type TileKey = Exclude<Filter, "all">;

type Tile = {
  key: TileKey;
  glyph: LucideIcon;
  glyphTone: string;
  label: string;
  n: number;
  tone: string;
  /** What the number means: a phrase, or counts by status. */
  note: string | Count[];
  finished: boolean;
};

/** The requirements counted by status. Each tile is also the filter for the list. */
export function StatusTiles({
  items,
  filter,
  onFilter,
  className,
}: {
  items: ChecklistItemState[];
  filter: Filter;
  onFilter: (f: Filter) => void;
  className: string;
}) {
  const c = countItems(items);
  const blocking = items.filter((i) => passes(i, "blocking")).length;
  const todo = c.missing + c.insufficient;
  const done = c.satisfied + c.waived;
  const tiles: Tile[] = [
    blocking === 0
      ? {
          key: "blocking",
          glyph: CheckCircle2,
          glyphTone: "text-positive",
          label: t("console.kpi.blocking"),
          n: 0,
          tone: "text-positive",
          note: t("journey.tile.nothingBlocking"),
          finished: true,
        }
      : {
          key: "blocking",
          glyph: OctagonX,
          glyphTone: "text-destructive",
          label: t("console.kpi.blocking"),
          n: blocking,
          tone: "text-destructive",
          note: t("console.kpi.blockingNote"),
          finished: false,
        },
    todo === 0
      ? {
          key: "todo",
          glyph: CheckCircle2,
          glyphTone: "text-positive",
          label: t("console.outstanding"),
          n: 0,
          tone: "text-positive",
          note: t("journey.tile.nothingOutstanding"),
          finished: true,
        }
      : {
          key: "todo",
          glyph: ListTodo,
          glyphTone: "text-foreground",
          label: t("console.outstanding"),
          n: todo,
          tone: "text-foreground",
          note: [
            { key: "missing", label: t("docStatus.missing"), n: c.missing },
            { key: "insufficient", label: t("docStatus.insufficient"), n: c.insufficient },
          ],
          finished: false,
        },
    {
      key: "in_review",
      glyph: Clock,
      glyphTone: "text-info",
      label: t("docStatus.in_review"),
      n: c.in_review,
      tone: c.in_review > 0 ? "text-info" : "text-muted-foreground",
      note: t("console.kpi.inReviewNote"),
      finished: false,
    },
    {
      key: "satisfied",
      glyph: CheckCircle2,
      glyphTone: "text-positive",
      label: t("docStatus.satisfied"),
      n: done,
      // Nothing done yet is not a success.
      tone: done > 0 ? "text-positive" : "text-muted-foreground",
      note:
        t("journey.tile.ofTotal", { n: items.length }) +
        (c.waived > 0 ? ` · ${t("journey.tile.waived", { n: c.waived })}` : ""),
      finished: items.length > 0 && done === items.length,
    },
  ];

  const press = (key: TileKey, keyboard: boolean) => {
    onFilter(filter === key ? "all" : key);
    // From a pointer, bring the list into view when it starts below the screen. From the
    // keyboard the screen stays with the focused tile; the list's new count is announced.
    if (keyboard) return;
    const list = document.getElementById("journey-list");
    if (list && list.getBoundingClientRect().top > window.innerHeight - 80)
      list.scrollIntoView({ block: "start", behavior: prefersReducedMotion() ? "auto" : "smooth" });
  };

  return (
    <div role="group" aria-label={t("journey.filterLabel")} className={cn("grid gap-2", className)}>
      {tiles.map((tile) => {
        const Glyph = tile.glyph;
        return (
          <button
            key={tile.key}
            type="button"
            aria-pressed={filter === tile.key}
            // A click from the keyboard has no pointer presses (detail 0).
            onClick={(e) => press(tile.key, e.detail === 0)}
            className={cn(
              "@container/tile relative flex min-h-[64px] min-w-0 flex-col justify-start gap-1 rounded-md border border-border bg-surface px-2.5 py-2.5 text-left transition-[border-color,background-color,box-shadow] hover:border-primary/40 hover:bg-surface-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring aria-pressed:border-primary aria-pressed:bg-accent/40 aria-pressed:shadow-[inset_0_0_0_1px_var(--color-primary)]",
              tile.finished && "border-positive/30",
            )}
            data-testid={`journey-filter-${tile.key}`}
          >
            <span className="field-label flex items-start gap-1.5 leading-[14px] @max-[21rem]/glance:min-h-7">
              <Glyph className={cn("size-3.5 shrink-0", tile.glyphTone)} aria-hidden />
              <span className="min-w-0">{tile.label}</span>
            </span>{" "}
            {/* Every tile in a row is built the same: in a narrow tile the note takes a line of
                its own under the number, in a wide one it follows the number. */}
            <span className="flex min-w-0 flex-col gap-1 @min-[12rem]/tile:flex-row @min-[12rem]/tile:items-baseline @min-[12rem]/tile:gap-2">
              <span
                className={cn(
                  "tabular text-[22px] font-semibold leading-none @min-[40rem]/glance:text-[24px]",
                  tile.tone,
                )}
              >
                {tile.n}
              </span>{" "}
              <TileNote note={tile.note} />
            </span>
          </button>
        );
      })}
    </div>
  );
}

const NOTE =
  "min-w-0 text-[11px] leading-[14px] text-muted-foreground @min-[12rem]/tile:text-[11.5px]";

/** A phrase wraps to a second line where the tile is narrow (on a phone, or four across beside
 * the assistant), so its qualifier is read in full without a pointer; counts wrap between two
 * counts if they must, never inside one. */
function TileNote({ note }: { note: string | Count[] }) {
  return typeof note === "string" ? (
    <span className={cn(NOTE, "line-clamp-2 break-words")} title={note}>
      {note}
    </span>
  ) : (
    <CountList counts={note} className={NOTE} />
  );
}

/** Up to this many sections, the map beside the readiness column sizes each by its name. */
const SIZED_SECTIONS = 5;

/** Every requirement as a cell, grouped by section; a cell opens its row. Decorative for a
 * screen reader, which hears one sentence a section instead. Each group's cells, name and count
 * share rows with its neighbours', so the counts line up however the names run. */
function SectionMap({
  items,
  sections,
  onJump,
  wide,
}: {
  items: ChecklistItemState[];
  sections: string[] | undefined;
  onJump: (itemId: string) => void;
  /** Across the full width of the panel (on Files), where the names fit on one line. */
  wide?: boolean;
}) {
  const groups = sectionGroups(items, sections);
  // Beside the readiness column the sections share one row, each as wide as its name needs (a
  // short name leaves the room to the long ones), so a name is cut only when the row has no
  // room left for it; its full name is then on hover, in the sentence a screen reader hears,
  // and on every row. With more sections than that, or across the full width (where the counts
  // run four across, and on Files), they sit in equal columns from the left, the names on up to
  // two lines.
  const sized = !wide && groups.length <= SIZED_SECTIONS;
  return (
    <ul
      aria-label={t("journey.sectionMap")}
      style={sized ? ({ "--sections": groups.length } as CSSProperties) : undefined}
      className={cn(
        "mt-2 -mb-3 grid gap-x-4",
        wide
          ? "grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))]"
          : sized
            ? "grid-cols-[repeat(var(--sections),minmax(0,auto))] @min-[84rem]/glance:grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))]"
            : "grid-cols-[repeat(auto-fit,minmax(5.75rem,1fr))] @min-[84rem]/glance:grid-cols-[repeat(auto-fill,minmax(8.5rem,1fr))]",
      )}
    >
      {groups.map(({ section, cells, satisfied, counts }) => {
        const of = t("console.satisfiedOf", { x: satisfied, y: cells.length });
        const others = (["insufficient", "missing", "in_review", "waived"] as const)
          .filter((s) => counts[s] > 0)
          .map((s) => ` · ${t(`docStatus.${s}`)} ${counts[s]}`)
          .join("");
        return (
          <li
            key={section}
            className={cn(
              "relative row-span-3 grid min-w-0 grid-rows-subgrid pb-3",
              !sized && cells.length > 4 && "col-span-2",
            )}
            data-testid="journey-section"
          >
            <div
              aria-hidden
              className="flex flex-wrap content-start gap-1"
              onClick={(e) => {
                const id = (e.target as HTMLElement).closest<HTMLElement>("[data-item]")?.dataset[
                  "item"
                ];
                if (id) onJump(id);
              }}
            >
              {cells.map((item) => {
                const Glyph = CELL_ICON[item.status];
                return (
                  <span
                    key={item.item_id}
                    title={`${item.name} · ${t(`docStatus.${item.status}`)}`}
                    className={cn(
                      "grid size-5 cursor-pointer place-items-center rounded-[4px] transition-transform hover:scale-110 motion-reduce:hover:scale-100",
                      CELL[item.status],
                    )}
                    data-testid="journey-cell"
                    data-item={item.item_id}
                    data-status={item.status}
                  >
                    <Glyph className="size-3" strokeWidth={2.5} />
                  </span>
                );
              })}
            </div>
            <p
              aria-hidden
              title={sized ? section : undefined}
              className={cn(
                "mt-1.5 text-[11.5px] font-medium leading-tight text-foreground",
                sized ? "truncate" : "line-clamp-2",
              )}
            >
              {section}
            </p>
            <p aria-hidden className="tabular text-[11px] text-muted-foreground">
              {of}
            </p>
            <span className="sr-only">
              {section}: {of}
              {others}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** The summary at the head of the checklist on the Files step: the verdict in a line, the
 * requirements counted by status (the filters) and by section. No score: the case header has
 * it. */
export function GlanceCompact({
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
  const v = verdictOf(r);
  const Icon = VERDICT[v].icon;
  const met = r.score_pct >= r.gate_pct;
  return (
    <div
      className="@container/glance relative space-y-3 border-b border-border px-4 py-3"
      data-testid="journey-summary"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        {/* One line of text after the icon, so where it wraps it wraps as a sentence. */}
        <p className="flex min-w-0 items-start gap-2">
          <Icon className={cn("mt-0.5 size-4 shrink-0", VERDICT[v].text)} aria-hidden />
          <span className="min-w-0 text-[12.5px] leading-5 text-muted-foreground">
            <span className="text-[13.5px] font-semibold text-foreground">{verdictTitle(v)}</span>
            {r.provisional && (
              <>
                {" "}
                <ProvisionalLozenge className="ml-1 inline-block align-[1px]" />
              </>
            )}
            {" · "}
            {met
              ? t("console.gateMet")
              : t("console.belowGate", { gate: formatPoints(r.gate_pct) })}
            {" · "}
            {r.blocking_open
              ? t("console.blocking", { n: r.blocking_open })
              : t("console.nothingBlocking")}
          </span>
        </p>
        {filter !== "all" && <ShowAll n={r.items.length} onFilter={onFilter} />}
      </div>
      {r.provisional && <ProvisionalStrip />}
      <StatusTiles
        items={r.items}
        filter={filter}
        onFilter={onFilter}
        className="grid-cols-2 @min-[40rem]/glance:grid-cols-4"
      />
      <div className="hidden @min-[40rem]/glance:block">
        <h3 className="field-label">{t("journey.bySection")}</h3>
        <SectionMap items={r.items} sections={sections} onJump={onJump} wide />
      </div>
    </div>
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

const TILE_SKELETON = Array.from({ length: 4 }, (_, i) => i);

/** The status tiles' placeholders, built as the tiles are (label, number, note, laid out by the
 * tile's own width), so they take the tiles' height at every width. */
function TilesSkeleton({ className }: { className: string }) {
  return (
    <div className={cn("grid gap-2", className)}>
      {TILE_SKELETON.map((i) => (
        <div
          key={i}
          className="@container/tile flex min-h-[64px] min-w-0 flex-col gap-1 rounded-md border border-border px-2.5 py-2.5"
        >
          <Line className="h-[14px] @max-[21rem]/glance:min-h-7" bar="h-2.5 w-20 max-w-full" />
          <div className="flex min-w-0 flex-col gap-1 @min-[12rem]/tile:flex-row @min-[12rem]/tile:items-center @min-[12rem]/tile:gap-2">
            <Pulse className="h-[22px] w-6 shrink-0 rounded bg-muted @min-[40rem]/glance:h-6" />
            <Line className="h-[14px] min-w-0 flex-1" bar="h-2.5 w-24 max-w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** The section map's placeholders: a group's cells, its name and its count. */
function SectionMapSkeleton() {
  return (
    <div className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(5.75rem,1fr))] gap-x-4">
      {TILE_SKELETON.map((i) => (
        <div key={i} className="min-w-0">
          <div className="flex gap-1">
            {[0, 1, 2].map((c) => (
              <Pulse key={c} className="size-5 rounded-[4px] bg-muted" />
            ))}
          </div>
          <Line className="mt-1.5 h-[14px]" bar="h-2.5 w-4/5" />
          <Line className="h-[17px]" bar="h-2 w-1/2" />
        </div>
      ))}
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
      <div aria-hidden className="h-[3px] bg-border" />
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
          <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] items-end gap-x-5 @min-[40rem]/glance:col-start-2 @min-[40rem]/glance:row-start-1 @min-[60rem]/glance:col-start-auto @min-[60rem]/glance:row-start-auto">
            <div>
              <Pulse className="h-[30px] w-20 rounded bg-muted @min-[40rem]/glance:h-9" />
              <Line className="mt-1.5 h-[17px]" bar="h-2.5 w-24" />
            </div>
            <div className="pb-1.5 pt-5">
              <Pulse className="h-2.5 rounded-full bg-muted" />
            </div>
          </div>
          <div className="min-w-0 @min-[40rem]/glance:col-span-2 @min-[60rem]/glance:col-span-1">
            <Line className="h-[17px]" bar="h-2.5 w-20" />
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <Pulse className="h-8 w-40 max-w-full rounded-full bg-muted/60" />
              <Pulse className="h-8 w-44 max-w-full rounded-full bg-muted/60" />
            </div>
          </div>
        </div>
        <div className="min-w-0 @min-[60rem]/glance:border-l @min-[60rem]/glance:border-border @min-[60rem]/glance:pl-8">
          <Line className="h-[17px]" bar="h-2.5 w-32" />
          <TilesSkeleton className="mt-2 grid-cols-2 @min-[40rem]/glance:grid-cols-4 @min-[60rem]/glance:grid-cols-2 @min-[84rem]/glance:grid-cols-4" />
          <div className="mt-4 hidden @min-[60rem]/glance:block">
            <Line className="h-[17px]" bar="h-2.5 w-24" />
            <SectionMapSkeleton />
          </div>
        </div>
      </div>
      <GlanceRail caseId={caseId} progress={progress} canOpen={canOpen} />
    </section>
  );
}

/** The Files step's summary while the checklist is read: the verdict line, the tiles and, where
 * there is room, the sections. */
export function GlanceCompactSkeleton() {
  return (
    <div
      className="@container/glance relative space-y-3 border-b border-border px-4 py-3"
      aria-busy="true"
      data-testid="journey-summary"
      data-state="loading"
    >
      <p className="sr-only">{t("state.loading")}</p>
      <div aria-hidden className="space-y-3">
        <Line className="h-5" bar="h-4 w-2/3" />
        <TilesSkeleton className="grid-cols-2 @min-[40rem]/glance:grid-cols-4" />
        <div className="hidden @min-[40rem]/glance:block">
          <Line className="h-[17px]" bar="h-2.5 w-24" />
          <SectionMapSkeleton />
        </div>
      </div>
    </div>
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
      <div aria-hidden className="h-[3px] bg-border" />
      <div className="p-4 @min-[40rem]/glance:p-5">
        <NoticeRow state={state} onRetry={onRetry} />
      </div>
      <GlanceRail caseId={caseId} progress={progress} canOpen={canOpen} />
    </section>
  );
}

/** The same notice as one row at the head of the checklist on the Files step. */
export function GlanceCompactNotice({
  state,
  onRetry,
}: {
  state: "error" | "empty";
  onRetry: () => void;
}) {
  return (
    <div className="px-4 py-4" data-testid="journey-summary" data-state={state}>
      <NoticeRow state={state} onRetry={onRetry} compact />
    </div>
  );
}

function NoticeRow({
  state,
  onRetry,
  compact,
}: {
  state: "error" | "empty";
  onRetry: () => void;
  compact?: boolean;
}) {
  const Title = compact ? "p" : "h2";
  return (
    <div className="flex items-start gap-3">
      <span
        aria-hidden
        className="grid size-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground @min-[40rem]/glance:size-9"
      >
        <CircleDashed className="size-[18px] @min-[40rem]/glance:size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <Title
          id={compact ? undefined : "journey-verdict-title"}
          className={cn(
            "font-semibold tracking-tight text-foreground",
            compact
              ? "text-[13.5px] leading-5"
              : "text-[16px] leading-[22px] @min-[40rem]/glance:text-[18px] @min-[40rem]/glance:leading-6",
          )}
        >
          {state === "error" ? t("caseHeader.readinessUnavailable") : t("checklist.emptyTitle")}
        </Title>
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
