import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** A titled block of the Banking view, with the title and its one-line caption on the same line so the header takes
 * as little height as the other tabs' captions do. */
export function Block({
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
      className={cn("min-w-0 rounded border border-border bg-surface", className)}
      data-testid={testId}
    >
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 px-4 py-2">
        <h3 className="text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </h3>
        {subtitle && <p className="text-[12px] text-muted-foreground">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}
