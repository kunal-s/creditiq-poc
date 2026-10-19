import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import type { PolicyAssessment, Spread } from "@/api/types";
import { t } from "@/config/terminology";
import { crore, lastChange, ratioTiles, rowByKey, type RatioTile } from "@/domain/spread";
import { cn } from "@/lib/utils";

type Look = { key: string; value: string; chip: string; dot: string };

/** A tile's colour, by the band the engine placed the ratio in. */
const LOOKS: Record<string, Look> = {
  within: {
    key: "within",
    value: "text-positive",
    chip: "border-positive/30 bg-positive-soft text-positive",
    dot: "bg-positive",
  },
  marginal: {
    key: "marginal",
    value: "text-flag-foreground",
    chip: "border-flag/40 bg-flag-soft text-flag-foreground",
    dot: "bg-flag-foreground",
  },
  outside: {
    key: "outside",
    value: "text-destructive",
    chip: "border-destructive/30 bg-critical-soft text-destructive",
    dot: "bg-destructive",
  },
  cannot: {
    key: "cannot",
    value: "text-muted-foreground",
    chip: "border-flag/40 bg-flag-soft text-flag-foreground",
    dot: "bg-flag",
  },
  noNorm: {
    key: "noNorm",
    value: "text-foreground",
    chip: "border-border bg-surface-muted text-muted-foreground",
    dot: "bg-muted-foreground/60",
  },
};

function lookOf(tile: RatioTile): Look {
  if (!tile.norm) return LOOKS["noNorm"]!;
  if (tile.norm.outcome === "cannot_evaluate") return LOOKS["cannot"]!;
  return LOOKS[tile.norm.band ?? (tile.norm.outcome === "pass" ? "within" : "outside")]!;
}

function figure(tile: RatioTile): { number: string; unit: string } {
  if (tile.value === null) return { number: "—", unit: "" };
  if (tile.unit === "days") return { number: String(Math.round(tile.value)), unit: " days" };
  if (tile.unit === "%") return { number: tile.value.toFixed(1), unit: "%" };
  if (tile.unit === "x") return { number: tile.value.toFixed(2), unit: "x" };
  return { number: tile.value.toFixed(2), unit: tile.unit };
}

/** The ratios against the policy norms (F-20), as tiles: the value, the band the engine placed
 * it in against the configured acceptable and marginal values, and the norm itself. Ratios the
 * policy does not test are shown beside them, without a band. */
export function RatioTiles({ spread, policy }: { spread: Spread; policy: PolicyAssessment }) {
  const tiles = ratioTiles(spread, policy);
  if (tiles.length === 0) return null;
  return (
    <section
      className="min-w-0 rounded border border-border bg-surface"
      data-testid="spread-ratios"
    >
      <header className="px-4 pb-3 pt-3.5">
        <h2 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t("spreadPage.ratios.title")}
        </h2>
        <p className="mt-0.5 text-[12px] text-muted-foreground">
          {t("spreadPage.ratios.subtitle", { period: policy.period ?? "" })}
        </p>
      </header>
      <div className="grid grid-cols-1 gap-px border-t border-border bg-border sm:grid-cols-2 xl:grid-cols-4">
        {tiles.map((tile) => {
          const look = lookOf(tile);
          const { number, unit } = figure(tile);
          const n = tile.norm;
          return (
            <div
              key={tile.key}
              className="min-w-0 bg-surface px-4 py-3.5"
              data-testid="spread-ratio"
              data-ratio={tile.key}
              data-band={look.key}
            >
              <p className="text-[12.5px] text-muted-foreground">{tile.label}</p>
              <p className={cn("mt-2 tabular font-semibold leading-none", look.value)}>
                <span className="text-[26px]">{number}</span>
                <span className="text-[14px]">{unit}</span>
              </p>
              <span
                className={cn(
                  "mt-2.5 inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11.5px] font-medium",
                  look.chip,
                )}
                data-testid="spread-ratio-band"
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", look.dot)} aria-hidden />
                {t(`spreadPage.ratios.${look.key}`)}
              </span>
              <p className="mt-2 break-words text-[11.5px] leading-snug text-muted-foreground">
                {n
                  ? [
                      t("spreadPage.ratios.required", { required: n.required }),
                      n.marginal_text
                        ? t("spreadPage.ratios.marginalAt", { value: n.marginal_text })
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")
                  : t("spreadPage.ratios.noNormNote")}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/** Two notes on how the latest year moved against the one before: turnover, and the
 * working-capital cycle. Each is the change between two spread figures, nothing more. */
export function TrendNotes({ spread }: { spread: Spread }) {
  const turnover = lastChange(rowByKey(spread, "revenue_from_operations"), spread.columns);
  const cycle = lastChange(rowByKey(spread, "wc-cycle"), spread.columns);
  if (!turnover && !cycle) return null;
  return (
    <div className="grid gap-3 lg:grid-cols-2" data-testid="spread-trends">
      {turnover && turnover.pct !== null && (
        <Note
          tone={turnover.delta >= 0 ? "positive" : "flag"}
          icon={turnover.delta >= 0 ? TrendingUp : TrendingDown}
          title={t(
            turnover.delta >= 0 ? "spreadPage.trend.turnoverUp" : "spreadPage.trend.turnoverDown",
            { pct: Math.abs(turnover.pct).toFixed(1), fy: turnover.to },
          )}
          body={t("spreadPage.trend.turnoverBody", {
            before: crore(turnover.before),
            after: crore(turnover.after),
            from: turnover.from,
            to: turnover.to,
          })}
          testId="spread-trend-turnover"
        />
      )}
      {cycle && (
        <Note
          tone={cycle.delta > 0.5 ? "flag" : cycle.delta < -0.5 ? "positive" : "muted"}
          icon={cycle.delta > 0.5 ? TrendingUp : cycle.delta < -0.5 ? TrendingDown : Minus}
          title={t(
            cycle.delta > 0.5
              ? "spreadPage.trend.cycleLonger"
              : cycle.delta < -0.5
                ? "spreadPage.trend.cycleShorter"
                : "spreadPage.trend.cycleSame",
            { n: Math.round(Math.abs(cycle.delta)), fy: cycle.to },
          )}
          body={t("spreadPage.trend.cycleBody", {
            before: Math.round(cycle.before),
            after: Math.round(cycle.after),
            from: cycle.from,
            to: cycle.to,
          })}
          testId="spread-trend-cycle"
        />
      )}
    </div>
  );
}

const NOTE_TONE = {
  positive: "border-positive/30 bg-positive-soft text-positive",
  flag: "border-flag/40 bg-flag-soft text-flag-foreground",
  muted: "border-border bg-surface text-foreground",
} as const;

function Note({
  tone,
  icon: Icon,
  title,
  body,
  testId,
}: {
  tone: keyof typeof NOTE_TONE;
  icon: typeof TrendingUp;
  title: string;
  body: string;
  testId: string;
}) {
  return (
    <div className={cn("rounded border px-4 py-3.5", NOTE_TONE[tone])} data-testid={testId}>
      <p className="flex items-start gap-2 text-[13.5px] font-semibold">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        {title}
      </p>
      <p className="mt-1.5 text-[12.5px] leading-relaxed opacity-90">{body}</p>
    </div>
  );
}
