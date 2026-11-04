import { useEffect, useRef, type ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

/** A table that, on a phone, shows each row as a stacked card instead of cutting its columns
 * (`table-stack` in styles.css). Each cell is labelled with its column's heading, read from the
 * table's own header, so the heading shows above the value; wide tables stay tables elsewhere. */
export function StackTable({ className, ...props }: ComponentPropsWithoutRef<"table">) {
  const ref = useRef<HTMLTableElement>(null);
  useEffect(() => {
    const table = ref.current;
    if (!table) return;
    const label = () => {
      const heads = Array.from(table.querySelectorAll("thead th")).map(
        (th) => th.textContent?.trim() ?? "",
      );
      for (const row of Array.from(table.querySelectorAll("tbody tr"))) {
        let col = 0;
        for (const cell of Array.from(row.children) as HTMLTableCellElement[]) {
          const head = heads[col];
          // A cell spanning the row (an empty state) says itself; it needs no heading.
          if (head && cell.colSpan === 1) cell.setAttribute("data-label", head);
          col += cell.colSpan || 1;
        }
      }
    };
    label();
    const watch = new MutationObserver(label);
    watch.observe(table, { childList: true, subtree: true });
    return () => watch.disconnect();
  }, []);
  return <table ref={ref} className={cn("table-stack", className)} {...props} />;
}
