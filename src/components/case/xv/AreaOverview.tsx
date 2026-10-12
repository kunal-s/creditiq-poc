import { useId } from "react";
import type { CrossVerificationView, Finding, XvArea, XvFact, XvHighlight } from "@/api/types";
import { t } from "@/config/terminology";
import {
  areaHighlights,
  areaSectionId,
  areasOf,
  factValue,
  findingTitle,
  isIdentifier,
  itemById,
  severityBreakdown,
} from "@/domain/crossVerification";
import { cn } from "@/lib/utils";
import { AREA_STATUS, highlightMark } from "./styles";

/** One card per area the engine checked, in its order: where the area stands, its open
 * discrepancies by severity, the one of greatest credit impact, and the key figures the engine
 * picked for it. A card opens its section; a key figure opens its finding. */
export function AreaOverview({
  view,
  onOpen,
  onOpenFinding,
}: {
  view: CrossVerificationView;
  onOpen: (area: XvArea["area"]) => void;
  onOpenFinding: (findingId: string) => void;
}) {
  const areas = areasOf(view);
  if (areas.length === 0) return null;
  return (
    // Four in a row where the board is wide, two by two below that, one column on a phone: sized
    // to the board's own width, which the side menus narrow. Each card spans four rows of the
    // grid (its area, its counts, its top finding, its key figures) and lays its parts on them,
    // so a row of cards keeps each part level and every card the same height.
    <section className="@container" aria-label={t("crossVerification.overview.label")}>
      <div
        className="grid gap-3 @min-[30rem]:grid-cols-2 @min-[56rem]:grid-cols-4"
        data-testid="xv-overview"
      >
        {areas.map((area) => (
          <AreaCard
            key={area.area}
            area={area}
            top={itemById(view, area.top_finding_id)?.finding}
            decided={(id) => itemById(view, id)?.adjudicated ?? false}
            onOpen={() => onOpen(area.area)}
            onOpenFinding={onOpenFinding}
          />
        ))}
      </div>
    </section>
  );
}

function AreaCard({
  area,
  top,
  decided,
  onOpen,
  onOpenFinding,
}: {
  area: XvArea;
  top: Finding | undefined;
  /** Whether the discrepancy of this finding is accepted or dismissed. */
  decided: (findingId: string) => boolean;
  onOpen: () => void;
  onOpenFinding: (findingId: string) => void;
}) {
  const id = useId();
  const status = AREA_STATUS[area.status];
  const Icon = status.icon;
  const breakdown = severityBreakdown(area);
  const lines = areaHighlights(area);
  // The open discrepancy of greatest credit impact; once every one is decided, or when there is
  // none, the card says so.
  const caption =
    area.open > 0
      ? top && findingTitle(top)
      : area.discrepancies > 0
        ? t("crossVerification.areaCard.allDecided")
        : t("crossVerification.areaCard.noDiscrepancy");
  const others = [
    t("crossVerification.count.incomplete", { n: area.incomplete }),
    t("crossVerification.count.passed", { n: area.passed }),
    ...(area.not_applicable > 0
      ? [t("crossVerification.count.notApplicable", { n: area.not_applicable })]
      : []),
  ];
  return (
    <div
      className={cn(
        "relative row-span-4 grid min-w-0 grid-rows-subgrid gap-y-0 rounded border border-t-[3px] border-border bg-surface",
        status.bar,
      )}
      data-testid={`xv-area-card-${area.area}`}
      data-status={area.status}
    >
      <div className="min-w-0 px-3 pt-3">
        <div className="flex w-full items-start justify-between gap-2">
          <div className="flex min-w-0 items-start gap-1.5">
            <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", status.text)} aria-hidden />
            {/* Opens the area's section; its surface covers the whole card, all but the key
                figures, which open their own findings. */}
            <button
              type="button"
              onClick={onOpen}
              aria-controls={areaSectionId(area.area)}
              aria-describedby={`${id}-counts${caption ? ` ${id}-top` : ""}`}
              className="min-w-0 break-words text-left text-[13.5px] font-semibold leading-snug text-foreground after:absolute after:inset-0 after:rounded-sm after:transition-colors hover:after:bg-foreground/[0.03] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
              data-testid="xv-area-open-section"
            >
              {t(`crossVerification.area.${area.area}.title`)}{" "}
              <span className="sr-only">({t(`crossVerification.status.${area.status}`)})</span>
            </button>
          </div>
          {area.blocking_open > 0 && (
            <span
              className="shrink-0 rounded bg-destructive px-1.5 py-0.5 text-[10px] font-medium text-destructive-foreground"
              data-testid="xv-area-blocking"
            >
              {t("crossVerification.areaCard.blocking")}
            </span>
          )}
        </div>
        <p className="mt-0.5 break-words text-[11.5px] leading-snug text-muted-foreground">
          {t(`crossVerification.area.${area.area}.purpose`)}
        </p>
      </div>

      <div id={`${id}-counts`} className="min-w-0 px-3 pt-3">
        <p className="flex flex-wrap items-baseline gap-x-1.5">
          <span
            className={cn(
              "tabular text-[26px] font-semibold leading-none",
              area.open > 0 ? "text-foreground" : "text-muted-foreground",
            )}
            data-testid="xv-area-open"
          >
            {area.open}
          </span>{" "}
          <span className="text-[12px] text-muted-foreground">
            {area.open === 1
              ? t("crossVerification.areaCard.openOne")
              : t("crossVerification.areaCard.openMany")}
          </span>
        </p>
        {breakdown && (
          <p
            className="mt-1 text-[12px] font-medium text-foreground"
            data-testid="xv-area-severity"
          >
            {breakdown}
          </p>
        )}
        {area.discrepancies > 0 && (
          <p
            className="tabular mt-1 text-[11.5px] text-muted-foreground"
            data-testid="xv-area-decided"
          >
            {t("crossVerification.areaCard.decided", {
              adjudicated: area.adjudicated,
              total: area.discrepancies,
            })}
          </p>
        )}
        <p
          className="tabular mt-1 break-words text-[11.5px] text-muted-foreground"
          data-testid="xv-area-others"
        >
          {others.join(" · ")}
        </p>
      </div>

      <div className="min-w-0 px-3 pt-3">
        {caption && (
          <p
            id={`${id}-top`}
            className={cn(
              "break-words border-t border-border pt-2 text-[12px] leading-snug",
              area.open > 0 ? "font-medium text-foreground" : "text-muted-foreground",
            )}
            data-testid="xv-area-top"
          >
            {caption}
          </p>
        )}
      </div>

      <div className="min-w-0 px-3 pb-2.5 pt-2">
        {lines.length > 0 && (
          <ul
            className="relative z-10 space-y-0.5 border-t border-border pt-1.5"
            aria-label={t("crossVerification.areaCard.keyFigures")}
            data-testid="xv-area-highlights"
          >
            {/* Each line's mark sits in the card's margin, its text in line with the caption. */}
            {lines.map((line, i) => (
              <li key={`${line.finding_id}-${i}`} className="-ml-2 -mr-1">
                <KeyFigure
                  line={line}
                  decided={line.outcome === "fail" && decided(line.finding_id)}
                  onOpen={() => onOpenFinding(line.finding_id)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** A key figure, as the engine wrote it: what is compared, the figures side by side, and a short
 * note. It opens its finding: a discrepancy's card, or the row of a check that could not run or
 * passed. Marked by where its finding stands. */
function KeyFigure({
  line,
  decided,
  onOpen,
}: {
  line: XvHighlight;
  decided: boolean;
  onOpen: () => void;
}) {
  const facts = line.facts ?? [];
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "block w-full min-w-0 rounded-sm border-l-2 py-1 pl-1.5 pr-1 text-left transition-colors hover:bg-foreground/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        highlightMark(line.outcome, decided),
      )}
      data-testid="xv-area-highlight"
      data-rule={line.rule_id}
      data-outcome={line.outcome}
      data-finding={line.finding_id}
    >
      <span
        className="block break-words text-[10.5px] font-semibold uppercase leading-snug tracking-wide text-muted-foreground"
        data-testid="xv-highlight-label"
      >
        {line.label}
      </span>
      {facts.map((fact, i) => (
        <Fact key={i} fact={fact} />
      ))}
      {line.note && (
        <span
          className="mt-0.5 block break-words text-[11.5px] leading-snug text-muted-foreground"
          data-testid="xv-highlight-note"
        >
          {line.note}
        </span>
      )}
    </button>
  );
}

/** One figure: its value as its unit reads (an identifier in monospace, so its characters can be
 * compared; an amount larger, so the turnover figures stand out; a long name kept to two lines, in
 * full on hover), red where it differs, and its source beside it, or under it where the card is
 * narrow. */
function Fact({ fact }: { fact: XvFact }) {
  const value = factValue(fact);
  const identifier = isIdentifier(fact);
  const amount = fact.unit === "inr";
  return (
    <span
      className="mt-0.5 flex min-w-0 flex-wrap items-baseline gap-x-1.5"
      data-testid="xv-highlight-fact"
      data-differs={fact.differs ? "true" : "false"}
    >
      <span
        className={cn(
          "min-w-0 font-semibold leading-snug",
          identifier
            ? "break-all font-mono text-[12px]"
            : amount
              ? "tabular text-[15px] leading-tight"
              : "tabular line-clamp-2 break-words text-[12.5px]",
          fact.differs ? "text-destructive" : "text-foreground",
        )}
        title={identifier ? undefined : value}
        data-testid="xv-highlight-value"
      >
        {value}
      </span>
      {fact.differs && <span className="sr-only">{t("crossVerification.column.differs")}</span>}
      <span className="min-w-0 break-words text-[11px] leading-snug text-muted-foreground">
        {fact.label}
      </span>
    </span>
  );
}
