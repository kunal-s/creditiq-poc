import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleSlash,
  Clock,
  HelpCircle,
  FileText,
  Info,
  Layers,
  Maximize2,
  MapPin,
  RotateCw,
  ScanLine,
  Search,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import type { FileRecord, IntegrityFinding, LogicalDocument } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import {
  KIND_TONE,
  PRINTED_ON_PAGE,
  STATUS_TONE,
  checkKind,
  factRead,
  factRows,
  humanTimes,
  isNote,
  isWholePage,
  originOf,
  stateOf,
  standsOut,
  type CheckKind,
  type FactRow,
  type Origin,
} from "@/domain/integrity";
import { HumanReview, IntegritySummary, StateChip } from "./IntegritySummary";
import { t, tOr } from "@/config/terminology";
import { cn } from "@/lib/utils";

/** F-07A: what a file's own bytes said about its history, checked before anything
 * was read from it. Every check is listed — passed, not applicable, could not be
 * checked, or standing out — so a reader sees what was looked at, not only what
 * was found. Indicators for a person, never a verdict. */

type Status = IntegrityFinding["status"];

export function StatusIcon({ status, note }: { status: Status; note: boolean }) {
  const cls = cn(
    "mt-0.5 h-3.5 w-3.5 shrink-0",
    note ? "text-muted-foreground" : STATUS_TONE[status],
  );
  if (note) return <Info className={cls} />;
  if (status === "pass") return <CheckCircle2 className={cls} />;
  if (status === "warning") return <TriangleAlert className={cls} />;
  if (status === "review_required") return <ShieldAlert className={cls} />;
  if (status === "not_applicable") return <CircleSlash className={cls} />;
  return <HelpCircle className={cls} />;
}

/** The visible way into a check's records: "Trace", or "Hide" once open. */
export function TraceButton({
  selected,
  onClick,
}: {
  selected: boolean;
  onClick: (() => void) | undefined;
}) {
  if (!onClick) return null;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      data-testid="integrity-trace"
      className={cn(
        "ml-auto inline-flex shrink-0 items-center gap-1 self-start rounded border px-1.5 py-0.5 text-[10.5px] font-medium",
        selected
          ? "border-primary/40 bg-primary/10 text-primary"
          : "border-border text-muted-foreground hover:border-primary/40 hover:text-primary",
      )}
    >
      <Search className="h-3 w-3" />
      {t(selected ? "fileIntegrity.untrace" : "fileIntegrity.trace")}
    </button>
  );
}

/** The file row's chip: the integrity status in a word, and the toggle for the checks. A long
 * status wraps inside its column rather than running into the next one. */
export function IntegrityChip({
  file,
  open,
  onToggle,
}: {
  file: FileRecord;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      title={t(open ? "fileIntegrity.hide" : "fileIntegrity.show")}
      data-testid="integrity-chip"
      data-state={stateOf(file)}
      className="max-w-full text-left"
    >
      <StateChip
        file={file}
        className="max-w-full cursor-pointer hover:opacity-80 [&>svg]:shrink-0"
      />
    </button>
  );
}

/** The records a check read, as lines of the file's facts: "where in the file" its answer came from. */
export function WhereInFile({ rows }: { rows: FactRow[] }) {
  if (!rows.length) return null;
  return (
    <div
      className="mt-1.5 rounded border border-primary/20 bg-background px-2 py-1.5"
      data-testid="integrity-where"
    >
      <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
        {t("fileIntegrity.where")}
      </p>
      <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-[11px]">
        {rows.map((r, i) => (
          <div key={i} className="contents">
            <dt className="text-muted-foreground">
              {t(`fileIntegrity.facts.group.${r.group}`)} · {r.label}
            </dt>
            <dd className="break-all font-mono text-[10.5px] text-foreground">{r.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Everything the integrity stage read from the file, grouped, with the lines the
 * selected check read highlighted. */
export function FileFacts({
  rows,
  highlight,
  open,
  onToggle,
}: {
  rows: FactRow[];
  highlight: readonly string[];
  open: boolean;
  onToggle: () => void;
}) {
  const groups = [...new Set(rows.map((r) => r.group))];
  // Identifiers and hashes read best in a fixed-width face; everything else as text.
  const mono = (r: FactRow) => r.group === "id" || /^[0-9a-f]{16,}$/i.test(r.value);
  return (
    <div data-testid="integrity-facts">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex items-center gap-1 text-[12.5px] font-semibold text-foreground hover:text-primary"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        {t("fileIntegrity.facts.title")}
      </button>
      {open && (
        <div className="mt-2 gap-3 sm:columns-2 xl:columns-3">
          {groups.map((g) => (
            <section
              key={g}
              className="mb-3 break-inside-avoid rounded-md border border-border bg-background"
            >
              <p className="border-b border-border bg-muted/40 px-2.5 py-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t(`fileIntegrity.facts.group.${g}`)}
              </p>
              <dl className="divide-y divide-border/60 text-[11.5px]">
                {rows
                  .filter((r) => r.group === g)
                  .map((r, i) => {
                    const lit = factRead(r.key, highlight);
                    return (
                      <div
                        key={i}
                        data-fact={r.key}
                        data-highlighted={lit || undefined}
                        className={cn(
                          "grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-x-3 px-2.5 py-1.5",
                          lit && "bg-primary/10",
                        )}
                      >
                        <dt className="text-muted-foreground">{r.label}</dt>
                        <dd className="min-w-0 text-foreground">
                          <span
                            className={cn(
                              "break-words",
                              mono(r) && "break-all font-mono text-[10.5px]",
                            )}
                          >
                            {r.value}
                          </span>
                          {r.note && (
                            <span className="block break-all font-mono text-[10px] text-muted-foreground">
                              {r.note}
                            </span>
                          )}
                        </dd>
                      </div>
                    );
                  })}
              </dl>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

/** A file's integrity on the Files page: what the checks came to and what a person
 * concluded. Every check, its records and its marks are in the detailed evidence. */
export function IntegrityPanel({
  caseId,
  file,
  documents,
  depth,
}: {
  caseId: string;
  file: FileRecord;
  documents: LogicalDocument[];
  depth: number;
}) {
  const viewer = useDocViewer();
  // The logical document a page belongs to is what the viewer opens.
  const documentFor = (page: number) =>
    documents.find((d) => d.page_from <= page && page <= d.page_to) ?? documents[0];
  return (
    <div
      className="mx-4 mb-2.5 grid gap-2 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]"
      style={{ marginLeft: 16 + depth * 14 + 20 }}
      data-testid="integrity-panel"
    >
      <IntegritySummary
        caseId={caseId}
        file={file}
        compact
        onShow={(f) => {
          const e = (f.evidence ?? []).find((x) => x.rect);
          const doc = e ? documentFor(e.page) : undefined;
          if (e && doc)
            viewer.open({
              caseId,
              documentId: doc.id,
              page: e.page,
              bbox: e.rect as [number, number, number, number],
            });
        }}
      />
      <HumanReview caseId={caseId} file={file} />
    </div>
  );
}
