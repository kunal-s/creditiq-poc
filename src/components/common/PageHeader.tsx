import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** The head of a working screen, as every screen opens: a kicker naming the appraisal and the
 * step, the title, one sentence saying what the screen is for, and an action row.
 *
 * Exactly one action is filled (`primary`); the rest are quiet, so the analyst can see what to
 * do next without reading the row. Wording comes from the terminology, never from here. */
export function PageHeader({
  kicker,
  title,
  purpose,
  actions,
  className,
}: {
  kicker: string;
  title: string;
  purpose?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn("border-b border-border bg-surface px-4 py-4 sm:px-6", className)}
      data-testid="page-header"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="field-label">{kicker}</p>
          <h1 className="mt-0.5 text-[19px] font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {purpose && (
            <p className="mt-1 max-w-3xl text-[12.5px] text-muted-foreground">{purpose}</p>
          )}
        </div>
      </div>
      {actions && <div className="mt-3 flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** The one filled action of a page header. */
export function PrimaryAction({
  children,
  onClick,
  disabled,
  testId,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  testId?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      className={cn(
        "flex h-9 items-center gap-1.5 rounded px-3.5 text-[13px] font-medium transition-colors",
        disabled
          ? "cursor-not-allowed border border-border text-muted-foreground"
          : "bg-primary text-primary-foreground hover:opacity-90",
      )}
    >
      {children}
    </button>
  );
}

/** A quiet action beside the primary one. */
export function SecondaryAction({
  children,
  onClick,
  testId,
}: {
  children: ReactNode;
  onClick?: () => void;
  testId?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="flex h-9 items-center gap-1.5 rounded border border-border px-3 text-[13px] font-medium text-foreground transition-colors hover:bg-surface-muted"
    >
      {children}
    </button>
  );
}
