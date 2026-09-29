import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** The prototype's titled panel. */
export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
  testId,
}: {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <section
      className={cn("min-w-0 rounded border border-border bg-surface", className)}
      data-testid={testId}
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <div className="min-w-0">
          <h2 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
            {title}
          </h2>
          {subtitle && <p className="mt-0.5 text-[12px] text-muted-foreground">{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

export type Tone = "positive" | "flag" | "critical" | "info" | "muted" | "primary";

export const TONE_CLASS: Record<Tone, string> = {
  positive: "border-positive/30 bg-positive-soft text-positive",
  flag: "border-flag/35 bg-flag-soft text-flag-foreground",
  critical: "border-destructive/30 bg-destructive/10 text-destructive",
  info: "border-info/30 bg-info-soft text-info",
  muted: "border-border bg-surface-muted text-muted-foreground",
  primary: "border-primary/35 bg-primary/10 text-primary",
};

export function Chip({
  tone,
  children,
  className,
  title,
  upper,
}: {
  tone: Tone;
  children: ReactNode;
  className?: string;
  title?: string;
  upper?: boolean;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[10.5px] font-medium",
        upper && "text-[10px] uppercase tracking-wide",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A KPI tile (prototype Readiness console and Validation tab). */
export function Kpi({
  label,
  value,
  note,
  tone,
  testId,
}: {
  label: string;
  value: ReactNode;
  note?: string;
  tone?: "critical" | "positive" | "flag";
  testId?: string;
}) {
  return (
    <div className="min-w-0 rounded border border-border bg-surface px-4 py-3" data-testid={testId}>
      <p className="field-label">{label}</p>
      <p
        className={cn(
          "tabular mt-1 text-[22px] font-semibold leading-none",
          tone === "critical"
            ? "text-destructive"
            : tone === "positive"
              ? "text-positive"
              : tone === "flag"
                ? "text-flag-foreground"
                : "text-foreground",
        )}
      >
        {value}
      </p>
      {note && <p className="mt-1.5 text-[11.5px] text-muted-foreground">{note}</p>}
    </div>
  );
}

/** Readiness bar coloured against the gate. */
export function ScoreBar({
  score,
  gate,
  blocking,
  className,
}: {
  score: number;
  gate: number;
  blocking?: number;
  className?: string;
}) {
  const tone =
    score >= gate && !blocking
      ? "bg-positive"
      : blocking
        ? "bg-destructive"
        : score >= gate * 0.75
          ? "bg-flag"
          : "bg-destructive";
  return (
    <div className={cn("h-1.5 overflow-hidden rounded-full bg-muted", className)}>
      <div
        className={cn("h-full rounded-full transition-all", tone)}
        style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
      />
    </div>
  );
}
