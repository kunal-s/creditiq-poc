import { useEffect, useRef, useState } from "react";
import type { IntegrityFigure } from "@/api/types";
import { t, tOr } from "@/config/terminology";
import { KIND_TONE, checkKind, columnOf, humanTimes, type Mark } from "@/domain/integrity";
import { cn } from "@/lib/utils";

/** F-07A: what the integrity checks found, drawn on a page. Laid over a page image
 * (the parent is `relative` and the image's size): each mark a labelled box where a
 * check points, and on request every figure the page checks read. Point at either
 * to see what it says; select a mark to keep its card open. Used by the document
 * viewer and by the integrity view, so both show the same thing. */

const MARK_TONE: Record<Mark["tone"], string> = {
  critical: "border-destructive bg-destructive/10",
  flag: "border-flag bg-flag/15",
  muted: "border-muted-foreground/60 bg-muted-foreground/10",
};

const MARK_TAG: Record<Mark["tone"], string> = {
  critical: "bg-destructive text-white",
  flag: "bg-flag text-white",
  muted: "bg-muted-foreground text-white",
};

type Rect = readonly [number, number, number, number];

function box([x0, y0, x1, y1]: Rect) {
  return {
    left: `${x0 * 100}%`,
    top: `${y0 * 100}%`,
    width: `${Math.max((x1 - x0) * 100, 0.6)}%`,
    height: `${Math.max((y1 - y0) * 100, 0.6)}%`,
  };
}

/** A card under (or, near the foot of the page, over) the thing it describes. */
function Card({ rect, children }: { rect: Rect; children: React.ReactNode }) {
  const [x0, y0, , y1] = rect;
  const below = y1 < 0.72;
  return (
    <div
      role="tooltip"
      data-testid="overlay-card"
      className="pointer-events-none absolute z-20 w-[min(300px,80%)] rounded-md border border-border bg-popover px-2.5 py-2 text-left text-[11px] leading-snug text-popover-foreground shadow-lg"
      style={{
        left: `${Math.min(x0, 0.6) * 100}%`,
        ...(below
          ? { top: `calc(${y1 * 100}% + 6px)` }
          : { bottom: `calc(${(1 - y0) * 100}% + 20px)` }),
      }}
    >
      {children}
    </div>
  );
}

function MarkCard({ mark }: { mark: Mark }) {
  const f = mark.finding;
  const kind = checkKind(f);
  const why = f.method?.["limitations"];
  return (
    <>
      <p className="flex items-baseline justify-between gap-2">
        <span className="font-semibold text-foreground">
          {tOr(`fileIntegrity.check.${f.code}`, f.code)}
        </span>
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {t("fileIntegrity.overlay.page", { page: mark.page })}
        </span>
      </p>
      <p className={cn("text-[10.5px] font-medium", KIND_TONE[kind])}>
        {t(`fileIntegrity.kind.${kind}`)}
      </p>
      <p className="mt-1 text-foreground">{humanTimes(mark.observed)}</p>
      <p className="mt-0.5 text-muted-foreground">
        <span className="font-medium">{t("fileIntegrity.threshold")}:</span>{" "}
        {humanTimes(mark.threshold)}
      </p>
      <p className="mt-1 text-muted-foreground">
        <span className="font-medium">{t("fileIntegrity.overlay.whyFlagged")}:</span>{" "}
        {humanTimes(f.finding)}
      </p>
      {why && (
        <p className="mt-0.5 text-muted-foreground">
          <span className="font-medium">{t("fileIntegrity.overlay.bearInMind")}:</span> {why}
        </p>
      )}
    </>
  );
}

function FigureCard({
  figure,
  figures,
}: {
  figure: IntegrityFigure;
  figures: readonly IntegrityFigure[];
}) {
  const column = columnOf(figure, figures);
  return (
    <>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {t("fileIntegrity.overlay.figure")}
      </p>
      <p className="font-mono text-[12px] text-foreground">{figure.text}</p>
      <p className="mt-0.5 text-foreground">
        {t("fileIntegrity.overlay.setIn", { font: figure.font, size: figure.size })}
      </p>
      <p className="text-muted-foreground">
        {column
          ? t("fileIntegrity.overlay.column", {
              count: column.count,
              font: column.font,
              size: column.size,
            })
          : t("fileIntegrity.overlay.noColumn")}
      </p>
      {column?.apart && (
        <p className="mt-0.5 font-medium text-flag-foreground">
          {t("fileIntegrity.overlay.apart")}
        </p>
      )}
    </>
  );
}

export function IntegrityOverlay({
  marks,
  figures,
  focus,
  onPick,
}: {
  /** The marks on this page. */
  marks: Mark[];
  /** The figures read on this page, when they are shown. */
  figures?: readonly IntegrityFigure[] | undefined;
  /** A mark kept open (its key), as when "Show on page" brought the reader here. */
  focus: string | null;
  onPick?: (mark: Mark) => void;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const focused = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    focused.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focus]);
  const shown = hover ?? focus;
  const markShown = marks.find((m) => m.key === shown);
  const figureShown = shown?.startsWith("fig-") ? figures?.[Number(shown.slice(4))] : undefined;

  return (
    <>
      {figures?.map((f, i) => {
        const apart = columnOf(f, figures)?.apart;
        return (
          <span
            key={`fig-${i}`}
            data-testid="overlay-figure"
            onMouseEnter={() => setHover(`fig-${i}`)}
            onMouseLeave={() => setHover(null)}
            className={cn(
              "absolute z-[5] rounded-[1px] border",
              apart ? "border-flag bg-flag/20" : "border-info/60 bg-info/10 hover:bg-info/25",
            )}
            style={box(f.rect as Rect)}
          />
        );
      })}
      {marks.map((m) => {
        const isFocus = focus === m.key;
        return (
          <button
            key={m.key}
            ref={isFocus ? focused : undefined}
            type="button"
            onClick={() => onPick?.(m)}
            onMouseEnter={() => setHover(m.key)}
            onMouseLeave={() => setHover(null)}
            data-testid="integrity-mark"
            data-code={m.finding.code}
            data-focus={isFocus || undefined}
            aria-label={tOr(`fileIntegrity.mark.${m.finding.code}`, m.finding.code)}
            className={cn(
              "absolute z-10 rounded-[2px] border-[1.5px] border-dashed",
              MARK_TONE[m.tone],
              isFocus && "border-solid ring-4 ring-primary/40",
            )}
            style={box(m.rect)}
          >
            <span
              className={cn(
                "pointer-events-none absolute -top-[17px] left-[-1.5px] whitespace-nowrap rounded-t px-1 py-px text-[10px] font-semibold leading-tight",
                MARK_TAG[m.tone],
              )}
            >
              {tOr(`fileIntegrity.mark.${m.finding.code}`, m.finding.code)}
            </span>
          </button>
        );
      })}
      {markShown && (
        <Card rect={markShown.rect}>
          <MarkCard mark={markShown} />
        </Card>
      )}
      {figureShown && figures && (
        <Card rect={figureShown.rect as Rect}>
          <FigureCard figure={figureShown} figures={figures} />
        </Card>
      )}
    </>
  );
}
