import type { CrossVerificationView, XvRun } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

/** One tile: a label, the count, a bar in the severity's colour (grey at zero), and a line saying
 * what the count is. The bar is the only colour, so three tiles read as one scale. */
function Tile({
  label,
  value,
  note,
  bar,
  chip,
  testId,
}: {
  label: string;
  value: string;
  note: string;
  bar?: string | undefined;
  chip?: string | undefined;
  testId: string;
}) {
  return (
    <div
      className="min-w-0 rounded border border-border bg-surface px-3 py-3 sm:px-4"
      data-testid={testId}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
        <p className="field-label">{label}</p>
        {chip && <Chip tone="critical">{chip}</Chip>}
      </div>
      <div className="mt-1.5 flex items-center gap-2.5">
        <span className="text-[26px] font-semibold tabular leading-none text-foreground">
          {value}
        </span>
        {/* At zero the bar is grey: colour only where there is something of that severity. */}
        {bar && (
          <span
            className={cn("h-1.5 w-10 shrink-0 rounded-full", value === "0" ? "bg-border" : bar)}
            aria-hidden
          />
        )}
      </div>
      <p className="mt-2 text-[11.5px] leading-snug text-muted-foreground">{note}</p>
    </div>
  );
}

/** The run that produced the board, for the Adjudicated tile's note. */
function runNote(run: XvRun | null | undefined): string {
  if (!run) return "";
  return t("crossVerification.meta.run", {
    id: run.id,
    rules: run.rules,
    sources: run.sources,
    at: run.at.slice(0, 10),
  });
}

/** The head of the board: open discrepancies by credit impact, then how many of all of them
 * have been decided (F-19.3). Ranked by what the discrepancy costs, not by the area it falls
 * in, so the most serious thing on the case is the first thing read. Counts come from the
 * engine; nothing here recomputes them. */
export function SeverityTiles({ view }: { view: CrossVerificationView }) {
  const c = view.counts;
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4" data-testid="xv-severity-tiles">
      <Tile
        testId="xv-tile-serious"
        label={t("crossVerification.tiles.serious")}
        value={String(c.serious)}
        bar="bg-critical"
        chip={c.blocking_open > 0 ? t("crossVerification.tiles.blocking") : undefined}
        note={c.serious === 0 ? t("crossVerification.tiles.noneSerious") : topNote(view, "serious")}
      />
      <Tile
        testId="xv-tile-moderate"
        label={t("crossVerification.tiles.moderate")}
        value={String(c.moderate)}
        bar="bg-flag"
        note={
          c.moderate === 0 ? t("crossVerification.tiles.noneModerate") : topNote(view, "moderate")
        }
      />
      <Tile
        testId="xv-tile-mild"
        label={t("crossVerification.tiles.mild")}
        value={String(c.mild)}
        bar="bg-info"
        note={c.mild === 0 ? t("crossVerification.tiles.noneMild") : topNote(view, "mild")}
      />
      <Tile
        testId="xv-tile-adjudicated"
        label={t("crossVerification.tiles.adjudicated")}
        value={`${c.adjudicated}`}
        note={
          c.total === 0
            ? t("crossVerification.tiles.noneToDecide")
            : `${t("crossVerification.tiles.outOf", { total: c.total })} · ${runNote(view.run)}`
        }
      />
    </div>
  );
}

/** The greatest open discrepancy of a severity, in the engine's words, for the tile's note. */
function topNote(view: CrossVerificationView, severity: string): string {
  const item = view.items.find(
    (i) => i.finding.outcome === "fail" && i.finding.severity === severity && !i.adjudicated,
  );
  return item?.finding.title ?? "";
}
