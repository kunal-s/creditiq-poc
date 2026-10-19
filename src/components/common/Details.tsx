import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { t } from "@/config/terminology";

/** Technical evidence behind a result, closed until asked for. Every screen
 * shows the plain result first; how it was reached sits here. */
export function Details({
  children,
  title,
  testId,
  open,
  variant = "box",
}: {
  children: ReactNode;
  title?: string;
  testId?: string;
  /** Open at first, for detail the result rests on (a failed check's lines). */
  open?: boolean;
  /** "inline": a small link at the end of a line, for a dense list; it takes the full width of
   * its line once open. */
  variant?: "box" | "inline";
}) {
  if (variant === "inline")
    return (
      <details className="group open:basis-full" data-testid={testId} open={open}>
        <summary className="inline-flex cursor-pointer list-none select-none items-center gap-0.5 text-[11.5px] font-medium text-primary hover:underline [&::-webkit-details-marker]:hidden">
          <ChevronRight
            className="h-3.5 w-3.5 transition-transform group-open:rotate-90"
            aria-hidden
          />
          {title ?? t("details.title")}
        </summary>
        <div className="mt-1.5 space-y-3 rounded border border-border bg-surface px-3 py-3">
          {children}
        </div>
      </details>
    );
  return (
    <details
      className="group rounded border border-border bg-surface"
      data-testid={testId}
      open={open}
    >
      <summary className="cursor-pointer select-none px-3 py-1.5 text-[12px] font-medium text-muted-foreground hover:text-foreground">
        {title ?? t("details.title")}
      </summary>
      <div className="space-y-3 border-t border-border px-3 py-3">{children}</div>
    </details>
  );
}
