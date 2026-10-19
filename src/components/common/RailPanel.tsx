import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** A panel of the right rail: an uppercase title, an optional subtitle, then its content.
 * Used for the summary beside a working screen (F-20, F-19), so every rail reads the same. */
export function RailPanel({
  title,
  subtitle,
  children,
  className,
  testId,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <section
      className={cn("rounded border border-border bg-surface", className)}
      data-testid={testId}
    >
      <header className="px-4 pt-3">
        <h2 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </h2>
        {subtitle && <p className="mt-0.5 text-[12px] text-muted-foreground">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

/** Two figures side by side at the head of a rail panel: the count and what it counts. */
export function RailStats({
  stats,
}: {
  stats: Array<{ value: ReactNode; label: string; tone?: string }>;
}) {
  return (
    <div className="mt-2 grid grid-cols-2 divide-x divide-border border-y border-border">
      {stats.map((s) => (
        <div key={s.label} className="px-4 py-3" data-testid="rail-stat">
          <p className={cn("text-[22px] font-semibold tabular leading-none", s.tone)}>{s.value}</p>
          <p className="mt-1.5 text-[11.5px] text-muted-foreground">{s.label}</p>
        </div>
      ))}
    </div>
  );
}

/** Key and value rows under a rail panel's stats; the value sits right. */
export function RailRows({ rows }: { rows: Array<{ label: string; value: ReactNode }> }) {
  return (
    <dl className="divide-y divide-border">
      {rows.map((r) => (
        <div key={r.label} className="flex items-baseline justify-between gap-3 px-4 py-2.5">
          <dt className="text-[12px] text-muted-foreground">{r.label}</dt>
          <dd className="text-right text-[12.5px] text-foreground">{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}
