import { useState } from "react";
import { t } from "@/config/terminology";
import { dayLabel, shortNumber } from "@/domain/modelUsage";
import { cn } from "@/lib/utils";

// A daily bar chart in inline SVG for Model usage: one column per day of the range, its parts stacked
// from the baseline (2px surface gap between them, the top end rounded), three recessive grid lines,
// and a hover readout above the plot (every column is a hit target the width of its day). The figures
// are also in the tables below, so the chart is a picture of them, not their only record.
// Test ids: `${testId}` (the figure), `${testId}-bar` (one per day), `${testId}-readout`.

export type Series = { key: string; label: string; className: string; swatch: string };
export type Column = { day: string; values: number[] };

const W = 640;
const H = 168;
const PAD = { top: 8, right: 8, bottom: 22, left: 40 };
const GAP = 2;

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}

/** A path for a bar whose top corners are rounded by r (the end that carries the value). */
function bar(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.max(0, Math.min(r, w / 2, h));
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

export function DailyBars({
  title,
  series,
  columns,
  format,
  axis = shortNumber,
  testId,
}: {
  title: string;
  series: Series[];
  columns: Column[];
  /** A value as the readout says it (the axis uses a short form). */
  format: (v: number) => string;
  /** A value on the axis (default: the short form, 12k). */
  axis?: (v: number) => string;
  testId: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const totals = columns.map((c) => c.values.reduce((a, b) => a + b, 0));
  const max = niceMax(Math.max(0, ...totals));
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const step = plotW / Math.max(1, columns.length);
  const barW = Math.max(2, Math.min(28, step * 0.62));
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  const ticks = [0, max / 2, max];
  // Label every day while they fit; otherwise every nth, always the first and the last.
  const every = Math.max(1, Math.ceil(columns.length / 10));
  const last = columns.length - 1;
  const shown = hover ?? last;
  const current = columns[shown];

  return (
    <figure className="min-w-0" data-testid={testId}>
      <div
        className="flex min-h-[2.25rem] flex-wrap items-baseline gap-x-4 gap-y-0.5 px-4 pt-3 text-[11.5px]"
        data-testid={`${testId}-readout`}
        aria-live="polite"
      >
        <span className="tabular font-medium text-foreground">
          {current ? dayLabel(current.day) : ""}
        </span>
        {series.map((s, i) => (
          <span key={s.key} className="inline-flex items-center gap-1.5 text-muted-foreground">
            <span className={cn("h-2 w-2 rounded-sm", s.swatch)} aria-hidden />
            {s.label}
            <span className="tabular text-foreground">
              {current ? format(current.values[i] ?? 0) : ""}
            </span>
          </span>
        ))}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="block h-auto w-full"
        role="img"
        aria-label={t("admin.modelUsage.chartLabel", {
          title,
          from: columns[0] ? dayLabel(columns[0].day) : "",
          to: columns[last] ? dayLabel(columns[last].day) : "",
        })}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(v)}
              y2={y(v)}
              className="stroke-border"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 6}
              y={y(v) + 3}
              textAnchor="end"
              className="tabular fill-muted-foreground text-[10px]"
            >
              {axis(v)}
            </text>
          </g>
        ))}
        {columns.map((c, i) => {
          const x0 = PAD.left + i * step + (step - barW) / 2;
          let base = 0;
          const parts = c.values.map((v, k) => {
            const top = base + v;
            const yTop = y(top);
            const h = y(base) - yTop - (base > 0 ? GAP : 0);
            base = top;
            const isTop = c.values.slice(k + 1).every((n) => n <= 0);
            if (v <= 0 || h <= 0) return null;
            return (
              <path
                key={series[k]?.key ?? k}
                d={bar(x0, yTop, barW, h, isTop ? 4 : 0)}
                className={series[k]?.className}
              />
            );
          });
          return (
            <g
              key={c.day}
              data-testid={`${testId}-bar`}
              data-day={c.day}
              onMouseEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              tabIndex={0}
              role="img"
              aria-label={t("admin.modelUsage.barLabel", {
                day: dayLabel(c.day),
                value: series.map((s, k) => `${s.label} ${format(c.values[k] ?? 0)}`).join(", "),
              })}
              className="outline-none"
            >
              <rect
                x={PAD.left + i * step}
                y={PAD.top}
                width={step}
                height={plotH}
                className={cn("fill-transparent", hover === i && "fill-surface-muted")}
              />
              {parts}
              {((i % every === 0 && last - i >= every) || i === last) && (
                <text
                  x={PAD.left + i * step + step / 2}
                  y={H - 6}
                  textAnchor="middle"
                  className="tabular fill-muted-foreground text-[10px]"
                >
                  {dayLabel(c.day)}
                </text>
              )}
            </g>
          );
        })}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={y(0)}
          y2={y(0)}
          className="stroke-muted-foreground/50"
          strokeWidth={1}
        />
      </svg>
    </figure>
  );
}
