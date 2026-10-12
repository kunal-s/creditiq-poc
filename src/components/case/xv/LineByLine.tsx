import { AlertTriangle } from "lucide-react";
import type { FindingDetail } from "@/api/types";
import { formatInr } from "@/domain/cases";
import { cn } from "@/lib/utils";

type Cell = FindingDetail["rows"][number]["cells"][number];

/** An amount in INR; a whole number under 1,000 is a count (months, debits), shown as it is. */
function cellText(cell: Cell): string {
  if (cell === null || cell === "") return "—";
  if (typeof cell !== "number") return cell;
  return Number.isInteger(cell) && Math.abs(cell) < 1000
    ? cell.toLocaleString("en-IN")
    : formatInr(cell);
}

/** The line-by-line comparison behind a finding: months, people, years; the lines that fail
 * the check flagged, and within a line the cells it fails on. */
export function LineByLine({ detail }: { detail: FindingDetail }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12px]" data-testid="xv-detail-table">
        <thead>
          <tr className="text-left text-[11px] text-muted-foreground">
            <th className="px-2 py-1 font-medium" />
            {detail.columns.map((c) => (
              <th key={c} className="px-2 py-1 text-right font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {detail.rows.map((r, i) => (
            <tr
              key={`${r.label}-${i}`}
              className={cn("border-t border-border", r.flagged && "bg-destructive/5")}
              data-flagged={r.flagged ? "true" : "false"}
            >
              <td
                className={cn(
                  "px-2 py-1",
                  r.label.length <= 32 ? "whitespace-nowrap" : "break-words",
                  r.flagged && "font-semibold text-destructive",
                )}
              >
                {r.flagged && <AlertTriangle className="mr-1 inline h-3 w-3" aria-hidden />}
                {r.label}
              </td>
              {r.cells.map((c, j) => (
                <td
                  key={j}
                  className={cn(
                    "tabular px-2 py-1 text-right",
                    // Short values stay on one line; on a phone the table scrolls in its box.
                    typeof c !== "string" || c.length <= 32 ? "whitespace-nowrap" : "break-words",
                    c === "—" && "text-destructive",
                    c === "✓" && "text-positive",
                    // A cell the row is flagged for (a name's middle name missing).
                    r.flagged_cells.includes(j) && "font-semibold text-destructive",
                  )}
                  data-flagged-cell={r.flagged_cells.includes(j) ? "true" : undefined}
                >
                  {cellText(c)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
