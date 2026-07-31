import { cn } from "@/lib/utils";
import type { Confidence } from "@/data/identity";

const tone: Record<Confidence, string> = {
  high: "border-positive/30 bg-positive-soft text-positive",
  medium: "border-flag/35 bg-flag-soft text-flag-foreground",
  low: "border-destructive/30 bg-destructive/10 text-destructive",
};

const label: Record<Confidence, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

export function ConfidenceChip({ level, className }: { level: Confidence; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10.5px] font-medium",
        tone[level],
        className,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label[level]}
    </span>
  );
}

export function SourceChip({ source }: { source: string }) {
  return (
    <span className="inline-flex items-center rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[10.5px] text-muted-foreground">
      {source}
    </span>
  );
}

export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded border border-border bg-surface", className)}>
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
