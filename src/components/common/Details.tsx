import type { ReactNode } from "react";
import { t } from "@/config/terminology";

/** Technical evidence behind a result, closed until asked for. Every screen
 * shows the plain result first; how it was reached sits here. */
export function Details({
  children,
  title,
  testId,
}: {
  children: ReactNode;
  title?: string;
  testId?: string;
}) {
  return (
    <details className="group rounded border border-border bg-surface" data-testid={testId}>
      <summary className="cursor-pointer select-none px-3 py-1.5 text-[12px] font-medium text-muted-foreground hover:text-foreground">
        {title ?? t("details.title")}
      </summary>
      <div className="space-y-3 border-t border-border px-3 py-3">{children}</div>
    </details>
  );
}
