import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import type { Spread } from "@/api/types";
import { t } from "@/config/terminology";
import { crore, lastChange, rowByKey } from "@/domain/spread";
import { cn } from "@/lib/utils";

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
