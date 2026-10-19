import { Fragment } from "react";
import { Eye, X } from "lucide-react";
import type { EvidenceRow, SourceColumn } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

type Cell = EvidenceRow["cells"][number];

function cellText(cell: Cell): string {
  if (cell === null) return "";
  return typeof cell === "number"
    ? cell.toLocaleString("en-IN", { maximumFractionDigits: 2 })
    : cell;
}

/** Short cells (a month, a date, an account, a total's label) stay on one line, so on a narrow
 * screen the table scrolls in its box rather than breaking them word by word; a long token with
 * no spaces may break anywhere; prose wraps between words. */
function wrapClass(cell: Cell): string {
  if (typeof cell === "number") return "whitespace-nowrap text-right tabular";
  if (typeof cell !== "string" || cell.length <= 32) return "whitespace-nowrap";
  return /\s/.test(cell) ? "break-words" : "break-all";
}

/** The rows extracted behind one column's headline value, each opening the page it was read
 * from. Totals are bold; credits left out of the count follow as indented lines. */
export function EvidencePanel({
  caseId,
  column,
  onClose,
}: {
  caseId: string;
  column: SourceColumn;
  onClose: () => void;
}) {
  const viewer = useDocViewer();
  const headings = column.row_columns ?? [];
  const rows = column.rows ?? [];
  const width = Math.max(headings.length, ...rows.map((r) => r.cells.length), 1);
  // A column is numeric when any row holds a number in it: its heading aligns right.
  const numeric = Array.from({ length: width }, (_, j) =>
    rows.some((r) => r.kind !== "excluded" && typeof r.cells[j] === "number"),
  );
  const firstExcluded = rows.findIndex((r) => r.kind === "excluded");
  const open = (row: EvidenceRow) => {
    const e = row.evidence?.[0];
    if (e) viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null });
  };
  return (
    <div
      className="border-b border-border bg-surface px-4 py-3"
      data-testid="xv-evidence-panel"
      data-column={column.key}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 break-words text-[12px] font-semibold text-foreground">
          {column.label}
          {column.coverage && (
            <span className="font-normal text-muted-foreground"> · {column.coverage}</span>
          )}
        </p>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex shrink-0 items-center gap-1 text-[11.5px] font-medium text-muted-foreground hover:text-foreground"
        >
          <X className="h-3 w-3" aria-hidden /> {t("crossVerification.evidence.close")}
        </button>
      </div>
      {/* Positioned, so the visually hidden heading scrolls with the table instead of widening
          the page. */}
      <div className="relative mt-2 overflow-x-auto rounded border border-border bg-surface-muted">
        <table className="w-full border-collapse font-mono text-[11.5px] leading-relaxed text-foreground/85">
          {headings.length > 0 && (
            <thead>
              <tr className="border-b border-border text-left font-sans text-[11px] text-muted-foreground">
                {Array.from({ length: width }, (_, j) => (
                  <th key={j} className={cn("px-3 py-1.5 font-medium", numeric[j] && "text-right")}>
                    {headings[j] ?? ""}
                  </th>
                ))}
                <th className="px-2 py-1.5">
                  <span className="sr-only">{t("crossVerification.evidence.pageLabel")}</span>
                </th>
              </tr>
            </thead>
          )}
          <tbody>
            {rows.map((row, i) => (
              <Fragment key={i}>
                {i === firstExcluded && (
                  <tr className="border-t border-border">
                    <td colSpan={width + 1} className="px-3 pb-0.5 pt-2 font-sans">
                      <span className="field-label">
                        {t("crossVerification.evidence.excluded")}
                      </span>
                    </td>
                  </tr>
                )}
                <RowLine row={row} width={width} onOpen={() => open(row)} />
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RowLine({ row, width, onOpen }: { row: EvidenceRow; width: number; onOpen: () => void }) {
  const evidence = row.evidence?.[0];
  // An excluded credit is one indented line, date, account and description spanning the columns
  // before the last, so the amount stays under the last one and a long narration never widens
  // a column of its own.
  const excluded = row.kind === "excluded" && row.cells.length >= 2;
  const cells = excluded ? row.cells.slice(-1) : row.cells;
  const lead = excluded ? row.cells.slice(0, -1).filter((c) => c !== null && c !== "") : [];
  const filled = cells.length + (excluded ? width - 1 : 0);
  return (
    <tr
      onClick={evidence ? onOpen : undefined}
      className={cn(
        "border-t border-border/70 align-top",
        evidence && "cursor-pointer hover:bg-surface",
        row.kind === "total" && "font-semibold text-foreground",
        row.kind === "excluded" && "text-muted-foreground",
      )}
      data-testid="xv-evidence-row"
      data-kind={row.kind}
    >
      {excluded && (
        <td colSpan={width > 2 ? width - 1 : undefined} className="break-words py-1 pl-6 pr-3">
          {lead.map((cell, j) =>
            j < lead.length - 1 ? (
              <span key={j} className="mr-4 whitespace-nowrap">
                {cellText(cell)}
              </span>
            ) : (
              <span key={j}>{cellText(cell)}</span>
            ),
          )}
        </td>
      )}
      {cells.map((cell, j) => (
        <td key={j} className={cn("px-3 py-1", wrapClass(cell))}>
          {cellText(cell)}
        </td>
      ))}
      {Array.from({ length: Math.max(0, width - filled) }, (_, j) => (
        <td key={`pad-${j}`} className="px-3 py-1" />
      ))}
      <td className="whitespace-nowrap px-2 py-1 text-right">
        {evidence && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onOpen();
            }}
            title={t("crossVerification.evidence.openPage", { page: evidence.page })}
            aria-label={t("crossVerification.evidence.openPage", { page: evidence.page })}
            className="inline-flex items-center rounded border border-border bg-surface p-1 text-primary hover:bg-muted"
            data-testid="xv-evidence-page"
            data-page={evidence.page}
          >
            <Eye className="h-3.5 w-3.5" aria-hidden />
          </button>
        )}
      </td>
    </tr>
  );
}
