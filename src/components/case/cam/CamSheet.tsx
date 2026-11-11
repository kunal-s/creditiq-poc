import { Link } from "@tanstack/react-router";
import { FunctionSquare, Loader2 } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import type { Cam, Evidence } from "@/api/types";
import { api } from "@/api/client";
import { Citations, SummaryItem } from "@/components/case/Outputs";
import { t } from "@/config/terminology";
import {
  columnLetter,
  withParagraph,
  type Sheet,
  type SheetCell,
  type SheetRow,
} from "@/domain/camSheet";
import { useCamChange } from "@/domain/findings";
import { camSectionAnchor, formatDay } from "@/domain/outputs";
import { cn } from "@/lib/utils";

// The memo a section at a time, as a spreadsheet (F-23): its rows numbered and its columns lettered,
// the cell in hand outlined with its address and contents above, the sections as tabs at the foot.
// A paragraph is changed in place and kept as the section in a person's words; a figure is changed in
// place and kept as an override, with the reason asked for under the cell. Both go to the engine,
// which keeps who and when; nothing is held on the page alone, so another tab, a reload or another
// person sees the same, and so do the downloads.
//
// Test ids:
//   cam-sheet                the grid (data-section): cam-sheet-brand at its head, cam-sheet-namebox
//                            and cam-sheet-formula (the cell in hand), cam-sheet-cell each cell
//                            (data-ref "B4", data-editable, data-overridden), cam-sheet-editor while
//                            a cell is changed, cam-sheet-reason (cam-sheet-reason-input,
//                            cam-sheet-reason-save, cam-sheet-reason-cancel) for a figure,
//                            cam-sheet-error; cam-sheet-tab each section's tab (data-section,
//                            aria-selected)

const ROW_HEAD = 44;
const HEAD_HEIGHT = 24;
const MIN_WIDTH = 92;
const MAX_WIDTH = 420;

// The bank's logo, where the file has been put in place (the workbook's sheets carry the same file).
const LOGO = Object.values(
  import.meta.glob<string>("/src/assets/brand/logo.png", {
    eager: true,
    query: "?url",
    import: "default",
  }),
)[0];

type Editable = "words" | "figure" | false;

/** One cell as the grid lays it out: where it starts, how many columns it spans, what it shows. */
type GridCell = {
  col: number;
  span: number;
  editable: Editable;
  /** What the contents bar shows and an edit starts from. */
  text: string;
  cell?: SheetCell;
  paragraph?: number;
  render: () => ReactNode;
  className?: string;
  testId?: string;
};

type Pos = { r: number; i: number };

function width(chars: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(chars * 7.1 + 26)));
}

/** Each column's width from what it holds, as a spreadsheet sized to its content. */
function columnWidths(sheet: Sheet): number[] {
  const chars = Array.from({ length: sheet.columns }, () => 6);
  for (const row of sheet.rows) {
    if (row.kind === "head")
      row.cells.forEach((c, i) => (chars[i] = Math.max(chars[i]!, c.length)));
    if (row.kind === "cells") {
      row.cells.forEach((c, i) => {
        const cited = c.citations.length > 0 && !row.facts ? 9 : 0;
        chars[i] = Math.max(chars[i]!, Math.min(c.text.length, 58) + cited);
      });
      if (row.facts) chars[2] = Math.max(chars[2]!, 14);
    }
  }
  return chars.map(width);
}

export function CamSheet({
  caseId,
  m,
  sheet,
  sheets,
  onSelect,
  canEdit,
}: {
  caseId: string;
  m: Cam;
  sheet: Sheet;
  sheets: Sheet[];
  onSelect: (id: string) => void;
  canEdit: boolean;
}) {
  const id = useId();
  const gridRef = useRef<HTMLDivElement>(null);
  const widths = useMemo(() => columnWidths(sheet), [sheet]);
  const layout = useMemo(
    () => sheet.rows.map((row) => layoutRow(caseId, m, sheet, row, canEdit)),
    [caseId, m, sheet, canEdit],
  );
  // A sheet opens at its first cell, top left, as a spreadsheet does.
  const first = useMemo(
    () => ({
      r: Math.max(
        0,
        layout.findIndex((cells) => cells.length > 0),
      ),
      i: 0,
    }),
    [layout],
  );
  const [active, setActive] = useState<Pos>(first);
  const [editing, setEditing] = useState<{ pos: Pos; value: string } | null>(null);
  const [reason, setReason] = useState<{ pos: Pos; value: string; reason: string } | null>(null);

  const words = useCamChange(caseId, (paragraphs: string[]) =>
    api.camWords(caseId, sheet.id, { paragraphs, source: "person" }),
  );
  const override = useCamChange(
    caseId,
    (body: { figure: string; original: string; value: string; reason: string }) =>
      api.camOverride(caseId, sheet.id, body),
  );
  const saving = words.isPending || override.isPending;
  const error = words.error ?? override.error;

  const at = (p: Pos): GridCell | undefined => layout[p.r]?.[p.i];
  const current = at(active);
  const refOf = (p: Pos) => {
    const c = at(p);
    if (!c) return "";
    const start = `${columnLetter(c.col)}${p.r + 1}`;
    return c.span > 1 ? `${start}:${columnLetter(c.col + c.span - 1)}${p.r + 1}` : start;
  };
  const cellId = (p: Pos) => `${id}-r${p.r}-c${p.i}`;

  // The width the grid shows, so a paragraph wraps within it rather than across every column.
  const [visible, setVisible] = useState(0);
  useEffect(() => {
    const box = gridRef.current;
    if (!box) return;
    const observer = new ResizeObserver(() => setVisible(box.clientWidth));
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  // The cell in hand kept in view inside the grid only: the page itself never moves. Not on arrival.
  const moved = useRef(false);
  useEffect(() => {
    if (!moved.current) {
      moved.current = true;
      return;
    }
    const box = gridRef.current;
    const el = document.getElementById(cellId(active));
    if (!box || !el) return;
    const b = box.getBoundingClientRect();
    const e = el.getBoundingClientRect();
    const top = b.top + HEAD_HEIGHT;
    const left = b.left + ROW_HEAD;
    if (e.top < top) box.scrollTop -= top - e.top;
    else if (e.bottom > b.bottom) box.scrollTop += e.bottom - b.bottom;
    if (e.left < left) box.scrollLeft -= left - e.left;
    else if (e.right > b.right && e.width < b.width - ROW_HEAD) box.scrollLeft += e.right - b.right;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  const focusGrid = () => window.setTimeout(() => gridRef.current?.focus(), 0);

  /** The cell in the row reached, under the column the move started from. */
  const move = useCallback(
    (dr: number, di: number) => {
      setActive((p) => {
        if (di !== 0) {
          const row = layout[p.r] ?? [];
          return { r: p.r, i: Math.min(row.length - 1, Math.max(0, p.i + di)) };
        }
        const col = layout[p.r]?.[p.i]?.col ?? 0;
        let r = p.r + dr;
        while (r >= 0 && r < layout.length && (layout[r]?.length ?? 0) === 0) r += dr;
        if (r < 0 || r >= layout.length) return p;
        const row = layout[r]!;
        const i = row.findIndex((c) => col >= c.col && col < c.col + c.span);
        return { r, i: i >= 0 ? i : row.length - 1 };
      });
    },
    [layout],
  );

  const begin = (pos: Pos, value?: string) => {
    const c = at(pos);
    if (!c?.editable || saving) return;
    setActive(pos);
    setReason(null);
    setEditing({ pos, value: value ?? c.text });
  };

  const commit = (value: string, then?: () => void) => {
    if (!editing) return;
    const pos = editing.pos;
    const c = at(pos);
    setEditing(null);
    if (!c || value.trim() === c.text.trim()) {
      focusGrid();
      then?.();
      return;
    }
    if (c.editable === "words") {
      words.mutate(withParagraph(sheet.paragraphs, c.paragraph ?? 0, value), {
        onSettled: focusGrid,
      });
      then?.();
    } else if (c.editable === "figure") {
      // A figure is kept with why it was changed: asked for under the cell before anything is sent.
      setReason({ pos, value: value.trim(), reason: "" });
    }
  };

  const saveReason = () => {
    if (!reason) return;
    const c = at(reason.pos);
    if (!c?.cell?.figure || reason.reason.trim().length < 3) return;
    override.mutate(
      {
        figure: c.cell.figure,
        original: c.cell.override?.original ?? c.cell.drafted,
        value: reason.value,
        reason: reason.reason.trim(),
      },
      {
        onSuccess: () => {
          setReason(null);
          focusGrid();
        },
      },
    );
  };

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (editing || reason) return;
    const keys: Record<string, () => void> = {
      ArrowUp: () => move(-1, 0),
      ArrowDown: () => move(1, 0),
      ArrowLeft: () => move(0, -1),
      ArrowRight: () => move(0, 1),
      Tab: () => move(0, e.shiftKey ? -1 : 1),
      Home: () => setActive((p) => ({ r: p.r, i: 0 })),
      End: () => setActive((p) => ({ r: p.r, i: Math.max(0, (layout[p.r]?.length ?? 1) - 1) })),
      Enter: () => begin(active),
      F2: () => begin(active),
    };
    const run = keys[e.key];
    if (run) {
      if (
        e.key === "Tab" &&
        ((e.shiftKey && active.i === 0) ||
          (!e.shiftKey && active.i >= (layout[active.r]?.length ?? 1) - 1))
      )
        return; // out of the grid, as Tab does at either end
      e.preventDefault();
      run();
      return;
    }
    // Typing into a cell starts changing it with what was typed, as a spreadsheet does.
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey && current?.editable) {
      e.preventDefault();
      begin(active, e.key);
    }
  };

  const hint = !current
    ? ""
    : current.editable
      ? t("outputs.sheet.canEdit")
      : canEdit
        ? t("outputs.sheet.readOnly")
        : t("outputs.sheet.readOnlyRole");

  return (
    <div
      className="min-w-0 overflow-hidden rounded border border-border bg-surface"
      data-testid="cam-sheet"
      data-section={sheet.id}
    >
      {/* The head of the sheet, as the workbook's: the bank's mark and the memo it belongs to. */}
      <div
        className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-surface px-3 py-2"
        data-testid="cam-sheet-brand"
      >
        {LOGO ? (
          <img src={LOGO} alt={t("tenant.bank.name")} className="h-7 w-auto" />
        ) : (
          <span className="text-[12.5px] font-semibold text-primary">
            {t("tenant.bank.name")}
            <span className="font-normal text-muted-foreground"> · {t("tenant.bank.unit")}</span>
          </span>
        )}
        <span className="text-[12px] text-muted-foreground">
          {m.title} · {m.borrower}
        </span>
      </div>

      {/* The cell in hand: its address and what it holds. */}
      <div className="flex min-w-0 items-stretch border-b border-border text-[12px]">
        <span
          className="tabular flex w-24 shrink-0 items-center border-r border-border bg-surface-muted/60 px-2 font-medium text-foreground"
          aria-label={t("outputs.sheet.nameBox")}
          data-testid="cam-sheet-namebox"
        >
          {refOf(active)}
        </span>
        <FunctionSquare
          className="mx-2 my-auto size-4 shrink-0 text-muted-foreground"
          aria-hidden
        />
        <span
          className="min-w-0 flex-1 truncate py-1.5 pr-3 text-foreground"
          data-testid="cam-sheet-formula"
          title={current?.text}
        >
          {current?.text}
        </span>
        <span className="hidden shrink-0 items-center border-l border-border px-3 text-[11px] text-muted-foreground md:flex">
          {hint}
        </span>
      </div>

      <div
        ref={gridRef}
        role="grid"
        tabIndex={0}
        aria-label={t("outputs.sheet.label", { title: sheet.title })}
        aria-rowcount={sheet.rows.length + 1}
        aria-colcount={sheet.columns + 1}
        aria-activedescendant={current ? cellId(active) : undefined}
        onKeyDown={onKey}
        className="relative max-h-[70vh] overflow-auto outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <table
          className="border-separate border-spacing-0 text-[12.5px]"
          style={{ width: ROW_HEAD + widths.reduce((a, b) => a + b, 0) }}
        >
          <colgroup>
            <col style={{ width: ROW_HEAD }} />
            {widths.map((w, i) => (
              <col key={i} style={{ width: w }} />
            ))}
          </colgroup>
          <thead>
            <tr role="row">
              <th className={cn(HEAD, "left-0 z-30")} aria-hidden />
              {widths.map((_, i) => (
                <th
                  key={i}
                  role="columnheader"
                  className={cn(
                    HEAD,
                    "z-20",
                    current &&
                      i >= current.col &&
                      i < current.col + current.span &&
                      "bg-accent text-foreground",
                  )}
                >
                  {columnLetter(i)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody
            data-testid={
              sheet.kind === "summary"
                ? "cam-summary"
                : sheet.kind === "recommendation"
                  ? "cam-recommendation"
                  : undefined
            }
          >
            {sheet.rows.length === 0 && (
              <tr role="row">
                <th className={ROW_NUMBER} role="rowheader">
                  1
                </th>
                <td
                  colSpan={sheet.columns}
                  className="border-b border-r border-border/70 px-2 py-2 italic text-muted-foreground"
                >
                  {t("outputs.sheet.noRows")}
                </td>
              </tr>
            )}
            {sheet.rows.map((row, r) => {
              const cells = layout[r] ?? [];
              const rowCurrent = active.r === r;
              const filler = sheet.columns - cells.reduce((n, c) => Math.max(n, c.col + c.span), 0);
              return (
                <tr
                  key={r}
                  role="row"
                  aria-rowindex={r + 2}
                  className={cn(row.kind === "gap" && "h-3")}
                  data-testid={
                    row.kind === "cells" && !row.facts && !row.label ? "cam-table-row" : undefined
                  }
                >
                  <th
                    role="rowheader"
                    className={cn(ROW_NUMBER, rowCurrent && "bg-accent text-foreground")}
                  >
                    {r + 1}
                  </th>
                  {row.kind === "gap" ? (
                    <td colSpan={sheet.columns} className="border-b border-r border-border/40" />
                  ) : (
                    <>
                      {cells.map((c, i) => {
                        const pos = { r, i };
                        const isActive = active.r === r && active.i === i;
                        const isEditing = editing?.pos.r === r && editing.pos.i === i;
                        const asking = reason?.pos.r === r && reason.pos.i === i;
                        const zebra = row.kind === "cells" && row.zebra;
                        return (
                          <td
                            key={i}
                            id={cellId(pos)}
                            role="gridcell"
                            colSpan={c.span}
                            aria-colindex={c.col + 2}
                            aria-selected={isActive}
                            aria-readonly={!c.editable}
                            onMouseDown={() => {
                              if (!isEditing) setActive(pos);
                            }}
                            onDoubleClick={() => begin(pos)}
                            className={cn(
                              "relative border-b border-r border-border/70 px-2 py-1.5 align-top",
                              zebra && "bg-surface-muted/50",
                              c.cell?.override && "bg-flag-soft/60",
                              c.className,
                              isActive && "outline outline-2 -outline-offset-2 outline-primary",
                              c.editable && "cursor-cell",
                            )}
                            data-testid={c.testId ?? "cam-sheet-cell"}
                            data-ref={`${columnLetter(c.col)}${r + 1}`}
                            data-editable={c.editable || undefined}
                            data-overridden={c.cell?.override ? "true" : undefined}
                            title={
                              c.cell?.override
                                ? t("outputs.sheet.overridden", {
                                    name: c.cell.override.by_name ?? c.cell.override.by,
                                    date: formatDay(c.cell.override.at.slice(0, 10)),
                                    reason: c.cell.override.reason,
                                    original: c.cell.override.original,
                                  })
                                : undefined
                            }
                          >
                            {c.cell?.override && (
                              <span
                                aria-hidden
                                className="absolute right-0 top-0 size-0 border-l-[7px] border-t-[7px] border-l-transparent border-t-flag"
                              />
                            )}
                            {isEditing ? (
                              <Editor
                                multiline={c.editable === "words"}
                                value={editing.value}
                                onCommit={(v, then) =>
                                  commit(v, then === "next" ? () => move(0, 1) : undefined)
                                }
                                onCancel={() => {
                                  setEditing(null);
                                  focusGrid();
                                }}
                              />
                            ) : c.span > 1 ? (
                              // A merged cell's words wrap within the grid as shown and stay in
                              // view as the columns scroll sideways.
                              <div
                                className="sticky"
                                style={(() => {
                                  const left =
                                    ROW_HEAD +
                                    widths.slice(0, c.col).reduce((a, b) => a + b, 0) +
                                    8;
                                  return {
                                    left,
                                    maxWidth:
                                      visible > 0 ? Math.max(240, visible - left - 16) : undefined,
                                  };
                                })()}
                              >
                                {c.render()}
                              </div>
                            ) : (
                              c.render()
                            )}
                            {asking && (
                              <ReasonPrompt
                                value={reason.reason}
                                saving={override.isPending}
                                onChange={(v) => setReason({ ...reason, reason: v })}
                                onSave={saveReason}
                                onCancel={() => {
                                  setReason(null);
                                  override.reset();
                                  focusGrid();
                                }}
                              />
                            )}
                          </td>
                        );
                      })}
                      {filler > 0 && (
                        <td
                          colSpan={filler}
                          className={cn(
                            "border-b border-r border-border/40",
                            row.kind === "cells" && row.zebra && "bg-surface-muted/50",
                          )}
                        />
                      )}
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {(saving || error) && (
        <p
          className={cn(
            "flex items-center gap-1.5 border-t border-border px-3 py-1.5 text-[12px]",
            error ? "text-critical-text" : "text-muted-foreground",
          )}
          role="status"
          data-testid="cam-sheet-error"
        >
          {saving && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
          {saving
            ? t("outputs.sheet.saving")
            : error instanceof Error
              ? error.message
              : String(error)}
        </p>
      )}

      {/* The sections as a workbook's sheets: one tab each, the one shown raised. */}
      <div
        role="tablist"
        aria-label={t("outputs.sheet.tabs")}
        className="flex overflow-x-auto border-t border-border bg-surface-muted/70 px-1"
      >
        {sheets.map((s) => {
          const selected = s.id === sheet.id;
          return (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onSelect(s.id)}
              className={cn(
                "-mt-px shrink-0 whitespace-nowrap border-x border-b-2 px-3 py-1.5 text-[12px] transition-colors",
                selected
                  ? "border-x-border border-b-primary bg-surface font-semibold text-foreground"
                  : "border-x-transparent border-b-transparent text-muted-foreground hover:bg-surface hover:text-foreground",
              )}
              data-testid="cam-sheet-tab"
              data-section={s.id}
            >
              {s.number}. {s.title}
              {s.review.state !== "machine" && (
                <span className="ml-1 text-primary" aria-hidden>
                  •
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

const HEAD =
  "sticky top-0 h-6 border-b border-r border-border bg-surface-muted px-1 text-center text-[11px] font-medium text-muted-foreground";
const ROW_NUMBER =
  "sticky left-0 z-10 border-b border-r border-border bg-surface-muted px-1 text-center align-top text-[11px] font-medium tabular-nums text-muted-foreground";

function Cited({
  caseId,
  text,
  citations,
}: {
  caseId: string;
  text: string;
  citations: Evidence[];
}) {
  return (
    <span className="whitespace-pre-wrap break-words">
      {text}
      <Citations caseId={caseId} evidence={citations} />
    </span>
  );
}

/** A row of the memo as the grid's cells. */
function layoutRow(
  caseId: string,
  m: Cam,
  sheet: Sheet,
  row: SheetRow,
  canEdit: boolean,
): GridCell[] {
  const all = sheet.columns;
  const whole = (cell: Omit<GridCell, "col" | "span">): GridCell[] => [
    { col: 0, span: all, ...cell },
  ];
  switch (row.kind) {
    case "gap":
      return [];
    case "subheading":
      return whole({
        editable: false,
        text: row.text,
        className: "bg-surface pt-3 text-[12.5px] font-semibold text-primary",
        testId: "cam-subheading",
        render: () => (
          <span
            id={row.part ? camSectionAnchor(row.part) : undefined}
            className="scroll-mt-24"
            data-part={row.part}
          >
            {row.text}
          </span>
        ),
      });
    case "note":
      return whole({
        editable: false,
        text: row.text,
        className: "italic text-muted-foreground",
        render: () => (
          <span
            data-testid={
              row.role === "rating"
                ? "cam-rating-note"
                : row.role === "empty"
                  ? "cam-section-empty"
                  : "cam-note"
            }
          >
            {row.text}
          </span>
        ),
      });
    case "paragraph": {
      const empty = !row.text;
      return whole({
        editable: canEdit ? "words" : false,
        text: row.text,
        paragraph: row.index,
        className: "leading-relaxed",
        render: () =>
          empty ? (
            <span className="italic text-muted-foreground">{t("outputs.sheet.writeHere")}</span>
          ) : (
            <span
              data-testid={
                sheet.kind === "recommendation" ? "cam-recommendation-text" : "cam-paragraph"
              }
            >
              <Cited caseId={caseId} text={row.text} citations={row.citations} />
            </span>
          ),
      });
    }
    case "head":
      return row.cells.map((text, col) => ({
        col,
        span: 1,
        editable: false,
        text,
        className: "bg-surface-muted font-semibold text-foreground",
        render: () => text,
      }));
    case "cells":
      if (row.facts) {
        const [label, value] = row.cells as [SheetCell, SheetCell];
        return [
          {
            col: 0,
            span: 1,
            editable: false,
            text: label.text,
            className: "font-medium text-foreground",
            render: () => label.text,
          },
          {
            col: 1,
            span: 1,
            editable: canEdit && value.figure ? "figure" : false,
            text: value.text,
            cell: value,
            render: () => <span className="whitespace-pre-wrap break-words">{value.text}</span>,
          },
          {
            col: 2,
            span: 1,
            editable: false,
            text: "",
            render: () => <Citations caseId={caseId} evidence={value.citations} className="ml-0" />,
          },
        ];
      }
      return row.cells.map((c, col) => ({
        col,
        span: 1,
        editable: canEdit && c.figure ? "figure" : false,
        text: c.text,
        cell: c,
        className: cn(
          c.numeric && "text-right tabular-nums",
          row.label && col === 0 && "font-medium",
        ),
        render: () => <Cited caseId={caseId} text={c.text} citations={c.citations} />,
      }));
    case "group":
      return whole({
        editable: false,
        text: t(`outputs.cam.summary.${row.summaryKind}`, { n: row.count }),
        className: "bg-surface pt-3 text-[12px] font-semibold text-muted-foreground",
        testId: `cam-summary-${row.summaryKind}`,
        render: () =>
          row.count === 0 ? (
            <span data-testid="cam-summary-none">
              {m.run_id
                ? t("outputs.cam.summary.findingNone", { run: m.run_id })
                : t("outputs.cam.summary.findingNoRun")}
            </span>
          ) : (
            <span className="flex flex-wrap items-baseline gap-x-2">
              {t(`outputs.cam.summary.${row.summaryKind}`, { n: row.count })}
              {row.summaryKind === "query" && (
                <Link
                  to="/appraisals/$caseId/completeness"
                  params={{ caseId }}
                  hash="queries"
                  className="font-medium text-primary hover:underline"
                  data-testid="cam-summary-query-list"
                >
                  {t("outputs.cam.summary.queryList")}
                </Link>
              )}
            </span>
          ),
      });
    case "summary":
      return [
        {
          col: 0,
          span: 1,
          editable: false,
          text: String(row.n),
          className: "text-right tabular-nums text-muted-foreground",
          render: () => row.n,
        },
        {
          col: 1,
          span: all - 1,
          editable: false,
          text: row.item.title ?? row.item.text,
          render: () => (
            <ol className="list-none">
              <SummaryItem caseId={caseId} item={row.item} />
            </ol>
          ),
        },
      ];
    case "prompt":
      return whole({
        editable: false,
        text: row.text,
        className: "pt-3 font-semibold",
        testId: "cam-recommendation-prompt",
        render: () => row.text,
      });
    case "box":
      return whole({
        editable: false,
        text: "",
        className: "h-14 italic text-muted-foreground",
        render: () => (
          <span data-testid="cam-recommendation-box">{t("outputs.cam.recommendationEmpty")}</span>
        ),
      });
  }
}

/** A cell being changed: Enter keeps it, Escape leaves it as it was, Tab keeps it and moves on. A
 * paragraph takes Alt+Enter for a new line. */
function Editor({
  value: initial,
  multiline,
  onCommit,
  onCancel,
}: {
  value: string;
  multiline: boolean;
  onCommit: (value: string, then?: "next") => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  const ref = useRef<HTMLTextAreaElement & HTMLInputElement>(null);
  // Kept or left once: a blur after Enter, Escape or Tab is not a second answer.
  const done = useRef(false);
  const finish = (f: () => void) => {
    if (done.current) return;
    done.current = true;
    f();
  };
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, []);
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      finish(onCancel);
    } else if (e.key === "Enter" && !(multiline && e.altKey)) {
      e.preventDefault();
      finish(() => onCommit(value));
    } else if (e.key === "Enter" && multiline && e.altKey) {
      e.preventDefault();
      setValue((v) => `${v}\n`);
    } else if (e.key === "Tab") {
      e.preventDefault();
      finish(() => onCommit(value, "next"));
    }
  };
  const common = {
    ref,
    value,
    onKeyDown,
    onChange: (e: { target: { value: string } }) => setValue(e.target.value),
    onBlur: () => finish(() => onCommit(value)),
    "data-testid": "cam-sheet-editor",
    className:
      "w-full rounded-sm bg-surface px-1 py-0.5 text-[12.5px] text-foreground outline outline-2 outline-primary",
  };
  return multiline ? (
    <textarea
      {...common}
      rows={Math.min(10, Math.max(3, Math.ceil(value.length / 90)))}
      className={cn(common.className, "resize-y leading-relaxed")}
    />
  ) : (
    <input {...common} />
  );
}

/** Why a figure changes, asked for under its cell; kept with the value drafted. */
function ReasonPrompt({
  value,
  saving,
  onChange,
  onSave,
  onCancel,
}: {
  value: string;
  saving: boolean;
  onChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
  const ready = value.trim().length >= 3 && !saving;
  return (
    <div
      className="absolute left-0 top-full z-40 mt-1 w-80 max-w-[80vw] rounded border border-border bg-surface p-3 text-left shadow-lg"
      data-testid="cam-sheet-reason"
      onMouseDown={(e) => e.stopPropagation()}
    >
      <label
        className="block text-[12px] font-medium text-foreground"
        htmlFor="cam-sheet-reason-input"
      >
        {t("outputs.sheet.reason")}
      </label>
      <input
        id="cam-sheet-reason-input"
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && ready) {
            e.preventDefault();
            onSave();
          } else if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
          }
        }}
        placeholder={t("outputs.sheet.reasonPlaceholder")}
        className="mt-1.5 w-full rounded border border-border bg-surface px-2 py-1.5 text-[12.5px] focus:outline-none focus:ring-2 focus:ring-ring"
        data-testid="cam-sheet-reason-input"
      />
      <p className="mt-1 text-[11px] text-muted-foreground">{t("outputs.sheet.reasonNote")}</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={!ready}
          className="inline-flex h-8 items-center gap-1.5 rounded bg-primary px-3 text-[12px] font-medium text-primary-foreground disabled:opacity-50"
          data-testid="cam-sheet-reason-save"
        >
          {saving && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
          {t("outputs.sheet.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-8 rounded border border-border px-3 text-[12px] font-medium"
          data-testid="cam-sheet-reason-cancel"
        >
          {t("outputs.sheet.cancel")}
        </button>
      </div>
    </div>
  );
}
