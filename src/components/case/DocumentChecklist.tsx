import { Link } from "@tanstack/react-router";
import { useCallback, useLayoutEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  CircleDashed,
  Copy,
  FileText,
  Loader2,
  Upload,
  X,
} from "lucide-react";
import type {
  CaseProgress,
  ChecklistItemState,
  FileRecord,
  LogicalDocument,
  QueryItem,
  Readiness,
} from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { LoadingBlock } from "@/components/common/States";
import { StageTrack } from "@/components/documents/StageTrack";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import {
  bandOf,
  isOpen,
  passes,
  readyForCredit,
  scoreText,
  sortInBand,
  useChecklist,
  useQueryList,
  useTaxonomy,
  type Band,
  type Filter,
} from "@/domain/checklist";
import { ACCEPT, pageRange, useCaseRegister, useDocumentTypes } from "@/domain/documents";
import { integrityNeedsPerson, stateOf } from "@/domain/integrity";
import { readinessWait, type ReadinessWait } from "@/domain/progress";
import { cn } from "@/lib/utils";
import { Glance, GlanceNotice, GlanceSkeleton } from "./checklist/Glance";
import type { CanOpen } from "./checklist/GlanceRail";
import { BAND, filterLabel, ICON, ICON_TONE, TONE, type BandKey } from "./checklist/status";
import { CopyLabel } from "./checklist/CopyLabel";
import { useCopy } from "./checklist/useCopy";
import { useFileDrag } from "./checklist/useFileDrag";
import { useJump } from "./checklist/useJump";
import { useRowUploads, type Outcome, type Pin, type RowUploads } from "./checklist/useRowUploads";

// What this appraisal needs, what has come in for each, what is wrong or missing, what to ask the
// customer, and an upload on the spot, after the readiness glance on the Overview. Requirements are grouped by what they do to the
// case: what blocks it, what is asked but does not block, what waits for a person, and what is
// done. The content of a file decides where it counts, so a file sent from a row is read and
// lands where it belongs; the row keeps its place and says what became of the file.

export function DocumentChecklist({
  caseId,
  progress,
  canOpen,
}: {
  caseId: string;
  progress?: CaseProgress;
  canOpen?: CanOpen;
}) {
  const checklist = useChecklist(caseId);
  const r = checklist.data;
  const retry = () => void checklist.refetch();

  // A failed read with an earlier one at hand keeps the earlier one on screen (and every
  // outcome, pin and filter with it), with a note and a retry; only a first read that fails
  // replaces the checklist.
  if (!r || r.items.length === 0) {
    const state = !r ? (checklist.isError ? "error" : "loading") : "empty";
    if (state === "loading")
      return (
        <>
          <GlanceSkeleton caseId={caseId} progress={progress} canOpen={canOpen} />
          <Panel title={t("journey.title")} testId="document-checklist">
            <LoadingBlock rows={4} className="border-0" />
          </Panel>
        </>
      );
    return (
      <GlanceNotice
        state={state}
        caseId={caseId}
        progress={progress}
        canOpen={canOpen}
        onRetry={retry}
      />
    );
  }

  return (
    <Journey
      caseId={caseId}
      r={r}
      progress={progress}
      canOpen={canOpen}
      stale={checklist.isError ? retry : undefined}
    />
  );
}

/** The last read is shown because a later one failed. */
function StaleNotice({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-flag-soft px-4 py-2 text-[12px] leading-5 text-flag-foreground"
      data-testid="journey-stale"
    >
      <AlertTriangle className="size-3.5 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1">{t("journey.stale")}</span>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex h-7 items-center rounded border border-flag/40 bg-surface px-2.5 text-[12px] font-medium text-foreground hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        {t("action.retry")}
      </button>
    </div>
  );
}

/** Rows in their bands, with what each row needs drawn from the case. */
function Journey({
  caseId,
  r,
  progress,
  canOpen,
  stale,
}: {
  caseId: string;
  r: Readiness;
  progress: CaseProgress | undefined;
  canOpen: CanOpen | undefined;
  /** Set when the latest read failed: retries it. */
  stale: (() => void) | undefined;
}) {
  const taxonomy = useTaxonomy();
  const sections = taxonomy.data?.sections;
  const { files, documents } = useCaseRegister(caseId);
  const queries = useQueryList(caseId);
  const uploads = useRowUploads(caseId);
  const dragging = useFileDrag();
  const [filter, setFilterState] = useState<Filter>("all");
  // The done band: open whenever nothing is open; else as last toggled.
  const [doneToggle, setDoneToggle] = useState<boolean | null>(null);
  // What came in that no requirement asks for starts closed, under its count.
  const [unmatchedOpen, setUnmatchedOpen] = useState(false);
  const anyOpen = r.items.some(isOpen);
  const doneOpen = doneToggle ?? !anyOpen;

  const docs = documents.data ?? [];
  const fileList = files.data ?? [];
  const attention = fileList.filter(integrityNeedsPerson).length;
  // In the full list a row sent a file keeps its band, so its outcome is read where the file
  // was dropped. Every count, and every filter, goes by where each requirement stands now: a
  // tile's number is always the number of rows it shows.
  const pinned = filter === "all" ? uploads.pinned : NO_PINS;
  const bandFor = useCallback(
    (item: ChecklistItemState): Band => pinned[item.item_id]?.band ?? bandOf(item),
    [pinned],
  );
  const shows = useCallback((item: ChecklistItemState, f: Filter) => passes(item, f), []);

  const setFilter = useCallback((f: Filter) => {
    setFilterState(f);
    if (f === "satisfied") setDoneToggle(true);
  }, []);

  const byId = (id: string) => r.items.find((i) => i.item_id === id);
  const { jump, flash } = useJump({
    hidden: (id) => {
      const item = byId(id);
      return item !== undefined && !shows(item, filter);
    },
    inDone: (id) => {
      const item = byId(id);
      return item !== undefined && bandFor(item) === "done";
    },
    showAll: () => setFilterState("all"),
    openDone: () => setDoneToggle(true),
  });

  // A requirement's requests: by its id, or "id:code" for each thing wrong with what came in.
  const askFor = (id: string) =>
    (queries.data ?? []).filter(
      (q: QueryItem) =>
        q.source_kind === "checklist" &&
        !q.resolved &&
        (q.source_ref === id || q.source_ref.startsWith(`${id}:`)),
    );
  const docsFor = (item: ChecklistItemState) =>
    docs.filter((d) => (item.document_ids ?? []).includes(d.id));

  const shown = r.items.filter((i) => shows(i, filter));
  const inBand = (band: Band) =>
    sortInBand(
      shown.filter((i) => bandFor(i) === band),
      sections,
      (i) => pinned[i.item_id]?.status ?? i.status,
    );
  const used = new Set(r.items.flatMap((i) => i.document_ids ?? []));
  const unmatched = docs.filter((d) => !used.has(d.id) && d.status !== "duplicate");
  const done = inBand("done");
  // The done band counts and names what is satisfied or waived now, as the tiles do (the
  // blocking band counts by the same rule); a row kept above, where its file was sent, is said
  // to be there.
  const doneNow = sortInBand(
    shown.filter((i) => bandOf(i) === "done"),
    sections,
    (i) => i.status,
  );

  const row = (item: ChecklistItemState, band: Band) => (
    <Requirement
      key={item.item_id}
      caseId={caseId}
      item={item}
      band={band}
      docs={docsFor(item)}
      files={fileList}
      ask={askFor(item.item_id)}
      uploads={uploads}
      dragging={dragging}
      flash={flash === item.item_id}
      onJump={jump}
      compact
    />
  );

  const filesLine = (
    <>
      {t("journey.files", { n: fileList.length })}
      {attention > 0 && (
        <span className="text-flag-foreground">
          {" · "}
          {t("journey.filesAttention", { n: attention })}
        </span>
      )}
    </>
  );

  const list = (
    <Panel
      id="journey-list"
      className="relative scroll-mt-4"
      title={t("journey.title")}
      subtitle={t(uploads.can ? "journey.subtitle" : "journey.subtitleRead", {
        n: r.items.length,
      })}
      testId="document-checklist"
      action={
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          {/* Says what a filter left in the list; empty until one is chosen. */}
          <span className="sr-only" aria-live="polite" data-testid="journey-showing-live">
            {filter === "all"
              ? ""
              : t("journey.showingLive", { filter: filterLabel(filter), n: shown.length })}
          </span>
          {filter !== "all" && (
            <span
              className="inline-flex h-7 items-center gap-1.5 rounded-full border border-primary/40 bg-accent/40 pl-2.5 pr-1 text-[12px] font-medium text-foreground"
              data-testid="journey-showing"
            >
              {t("journey.showing", { filter: filterLabel(filter) })}
              <button
                type="button"
                aria-label={t("journey.clearFilter")}
                onClick={() => setFilter("all")}
                className="grid size-5 place-items-center rounded-full hover:bg-primary/10 focus-visible:outline-2 focus-visible:outline-ring"
                data-testid="journey-filter-clear"
              >
                <X className="size-3" aria-hidden />
              </button>
            </span>
          )}
          <Link
            to="/appraisals/$caseId/documents"
            params={{ caseId }}
            className="rounded-sm text-[12px] text-muted-foreground hover:text-foreground hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            {filesLine}
          </Link>
        </div>
      }
    >
      <div className="divide-y divide-border">
        {shown.length === 0 && (
          <p className="px-4 py-6 text-center text-[12.5px] text-muted-foreground">
            {t("journey.filterEmpty")}
          </p>
        )}
        {(["blocking", "nonblocking", "inreview"] as const).map((band) => {
          const rows = inBand(band);
          // The rows that still belong here; the rest are kept in place for their outcome.
          const live = rows.filter((i) => bandOf(i) === band).length;
          if (rows.length === 0) {
            return band === "blocking" && filter === "all" ? (
              <ClearLine key={band} testId="journey-band-blocking" text={CLEAR[band]} />
            ) : null;
          }
          return (
            <section
              key={band}
              aria-labelledby={`journey-band-${band}-title`}
              data-testid={`journey-band-${band}`}
              data-clear={live === 0 || undefined}
            >
              {live === 0 ? (
                <ClearLine id={`journey-band-${band}-title`} text={CLEAR[band]} />
              ) : (
                <BandHeader
                  band={band}
                  id={`journey-band-${band}-title`}
                  title={
                    band === "blocking"
                      ? t("readiness.blocking")
                      : band === "nonblocking"
                        ? t("readiness.nonBlocking")
                        : t("docStatus.in_review")
                  }
                  n={live}
                  help={
                    band === "blocking"
                      ? t("readiness.blockingHelp")
                      : band === "nonblocking"
                        ? t("readiness.nonBlockingHelp")
                        : t("journey.band.inReviewHelp")
                  }
                />
              )}
              <ul className="divide-y divide-border">{rows.map((item) => row(item, band))}</ul>
            </section>
          );
        })}

        {filter === "all" && unmatched.length > 0 && (
          <section aria-labelledby="journey-unmatched-title" data-testid="journey-unmatched">
            <button
              type="button"
              aria-expanded={unmatchedOpen}
              onClick={() => setUnmatchedOpen((v) => !v)}
              className="group block w-full text-left"
              data-testid="journey-unmatched-toggle"
            >
              <BandHeader
                band="unmatched"
                id="journey-unmatched-title"
                title={t("journey.unmatched")}
                n={unmatched.length}
                help={t("journey.unmatchedHelp")}
              />
            </button>
            <ul hidden={!unmatchedOpen} className="flex flex-wrap gap-1.5 px-4 py-3">
              {unmatched.slice(0, 12).map((d) => (
                <li key={d.id} className="min-w-0 max-w-full">
                  <DocPill caseId={caseId} doc={d} files={fileList} />
                </li>
              ))}
            </ul>
          </section>
        )}

        {doneNow.length > 0 && (
          <DoneBand
            caseId={caseId}
            items={done}
            now={doneNow}
            open={doneOpen}
            onToggle={() => setDoneToggle(!doneOpen)}
            docsFor={docsFor}
            files={fileList}
            flash={flash}
          />
        )}
      </div>
    </Panel>
  );

  return (
    <>
      <OverviewStatus r={r} wait={readinessWait(progress, r)} caseId={caseId} />
      {stale && <StaleNotice onRetry={stale} />}
      {list}
    </>
  );
}

const NO_PINS: Record<string, Pin> = {};

const CLEAR: Record<Exclude<Band, "done">, string> = {
  blocking: t("readiness.noBlocking"),
  nonblocking: t("journey.band.clearNonblocking"),
  inreview: t("journey.band.clearInReview"),
};

/** A band with nothing left in it: said in green. */
function ClearLine({ text, id, testId }: { text: string; id?: string; testId?: string }) {
  return (
    <div
      className="flex items-center gap-2 border-l-[3px] border-l-positive px-4 py-2.5 text-[12.5px] font-medium text-positive"
      data-testid={testId}
      data-clear={testId ? true : undefined}
    >
      <CheckCircle2 className="size-3.5 shrink-0" aria-hidden />
      {id ? (
        <h3 id={id} className="text-[12.5px] font-medium">
          {text}
        </h3>
      ) : (
        text
      )}
    </div>
  );
}

function BandHeader({
  band,
  id,
  title,
  n,
  help,
}: {
  band: BandKey;
  id: string;
  title: string;
  /** The count, as a pill after the title. */
  n?: number;
  help: string;
}) {
  const Glyph = BAND[band].glyph;
  // The glyph keeps a column of its own, so a title that wraps wraps beside it.
  return (
    <div
      className={cn(
        "flex items-start gap-x-2 border-b border-l-[3px] border-border bg-surface-muted/40 px-4 py-2",
        BAND[band].rule,
      )}
    >
      <Glyph className={cn("mt-px size-3.5 shrink-0", BAND[band].tone)} aria-hidden />
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-0.5">
        <h3
          id={id}
          className="min-w-0 text-[11.5px] font-semibold uppercase leading-4 tracking-wide text-foreground"
        >
          {title}
        </h3>
        {n !== undefined && (
          <span
            className={cn(
              "tabular rounded-full px-1.5 text-[10.5px] font-semibold leading-4",
              BAND[band].pill,
            )}
          >
            {n}
          </span>
        )}
        <p className="basis-full text-[11.5px] leading-4 text-muted-foreground sm:basis-auto">
          {help}
        </p>
      </div>
    </div>
  );
}

function StatusChip({ status }: { status: ChecklistItemState["status"] }) {
  const Icon = ICON[status];
  return (
    <Chip tone={TONE[status]} className="gap-1 whitespace-nowrap">
      <Icon className="size-3" aria-hidden />
      {t(`docStatus.${status}`)}
    </Chip>
  );
}

/** "Unsigned: the copy…": what is wrong in bold, then the detail. */
function Deficiency({ text }: { text: string }) {
  const at = text.indexOf(": ");
  if (at < 0) return <>{text}</>;
  return (
    <>
      <span className="font-semibold">{text.slice(0, at + 1)}</span>
      {text.slice(at + 1)}
    </>
  );
}

const DEFICIENCY_TONE: Partial<Record<ChecklistItemState["status"], string>> = {
  missing: "text-destructive",
  insufficient: "text-flag-foreground",
  in_review: "text-info",
};

/** One requirement still open: where it stands, what is on file and what is wrong with it, what
 * to ask the customer, what became of files sent from here, and why it is needed on demand.
 * Files dropped on the row are uploaded from it. */
function Requirement({
  caseId,
  item,
  band,
  docs,
  files,
  ask,
  uploads,
  dragging,
  flash,
  onJump,
  compact = false,
}: {
  caseId: string;
  item: ChecklistItemState;
  /** The band the row is shown in (it keeps the one it had when a file was sent from it). */
  band: Band;
  docs: LogicalDocument[];
  files: FileRecord[];
  ask: QueryItem[];
  uploads: RowUploads;
  dragging: boolean;
  flash: boolean;
  onJump: (itemId: string) => void;
  /** One line (name, one detail, status), the rest opened on demand: the Overview. */
  compact?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [allDocs, setAllDocs] = useState(false);
  const detail = !compact || expanded;
  const Icon = ICON[item.status];
  const id = item.item_id;
  const open = item.status === "missing" || item.status === "insufficient";
  const droppable = open && uploads.can;
  const pending = uploads.pendingFor(id);
  const outcomes = uploads.outcomesFor(id);
  const input = useRef<HTMLInputElement>(null);
  const name = useRef<HTMLParagraphElement>(null);
  const uploadFocused = useRef(false);
  const [why, setWhy] = useState(false);
  const [over, setOver] = useState(false);
  const send = (list: File[]) => void uploads.send(item, band, list);

  // When the row stops taking files (it is satisfied, or in review) while its Upload button has
  // the focus, the focus moves to the row's name rather than being lost with the button.
  const wasDroppable = useRef(droppable);
  useLayoutEffect(() => {
    if (wasDroppable.current && !droppable && uploadFocused.current) {
      uploadFocused.current = false;
      const active = document.activeElement;
      if (!active || active === document.body) name.current?.focus({ preventScroll: true });
    }
    wasDroppable.current = droppable;
  }, [droppable]);

  return (
    <li
      id={`req-${id}`}
      className={cn(
        "relative grid scroll-mt-24 gap-x-3 gap-y-2 border-l-[3px] px-4 transition-colors duration-700 motion-reduce:transition-none",
        // Red while the requirement still blocks the case, wherever the row is kept.
        compact
          ? "grid-cols-[16px_minmax(0,1fr)_auto] py-2.5"
          : "grid-cols-[16px_minmax(0,1fr)] py-3 sm:grid-cols-[16px_minmax(0,1fr)_auto]",
        bandOf(item) === "blocking" ? "border-l-destructive" : "border-l-transparent",
        flash && "bg-accent/70 duration-0",
        dragging &&
          droppable &&
          !over &&
          "outline-1 -outline-offset-4 outline-dashed outline-info/50",
        over && "bg-info-soft outline-2 -outline-offset-4 outline-dashed outline-info",
      )}
      data-testid="journey-item"
      data-item={id}
      data-status={item.status}
      data-blocking={item.blocking}
      data-band={band}
      onDragOver={
        droppable
          ? (e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "copy";
              setOver(true);
            }
          : undefined
      }
      onDragLeave={
        droppable
          ? (e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false);
            }
          : undefined
      }
      onDrop={
        droppable
          ? (e) => {
              e.preventDefault();
              setOver(false);
              send(Array.from(e.dataTransfer.files));
            }
          : undefined
      }
    >
      <Icon
        className={cn(compact ? "mt-0.5" : "mt-5", "size-4", ICON_TONE[item.status])}
        aria-hidden
      />

      <div className="flex min-w-0 flex-col gap-1.5">
        {compact && (
          <CompactLine
            item={item}
            docs={docs.length}
            expanded={expanded}
            onToggle={() => setExpanded((v) => !v)}
          />
        )}
        {/* On a phone the section wraps beside the status, never cut off. */}
        <div className={cn("flex items-start gap-2", compact && "hidden")}>
          <span className="min-w-0 text-[10.5px] font-medium uppercase leading-4 tracking-wide text-muted-foreground">
            {item.section}
          </span>
          <span className="ml-auto shrink-0 sm:hidden">
            <StatusChip status={item.status} />
          </span>
        </div>
        <p
          ref={name}
          id={`req-${id}-name`}
          tabIndex={-1}
          className={cn(
            "rounded-sm text-[13.5px] font-medium leading-snug text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
            compact && "sr-only",
          )}
        >
          {item.name}
        </p>

        {detail && docs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {(allDocs ? docs : docs.slice(0, SHOWN_DOCS)).map((d) => (
              <DocPill key={d.id} caseId={caseId} doc={d} files={files} />
            ))}
            {docs.length > SHOWN_DOCS && (
              <button
                type="button"
                onClick={() => setAllDocs((v) => !v)}
                className="rounded px-1.5 py-0.5 text-[11.5px] font-medium text-primary hover:underline"
                data-testid="journey-docs-more"
              >
                {allDocs
                  ? t("journey.fewerDocs")
                  : t("journey.moreDocs", { n: docs.length - SHOWN_DOCS })}
              </button>
            )}
          </div>
        )}

        {!detail ? null : item.deficiency && item.status !== "satisfied" ? (
          <p
            className={cn(
              "text-[12.5px] leading-5",
              DEFICIENCY_TONE[item.status] ?? "text-muted-foreground",
            )}
          >
            <Deficiency text={item.deficiency} />
          </p>
        ) : item.status === "missing" && docs.length === 0 ? (
          <p className="text-[12.5px] text-muted-foreground">{t("journey.notReceived")}</p>
        ) : item.status === "in_review" ? (
          <p className="text-[12.5px] text-info">{t("journey.waitingPerson")}</p>
        ) : null}

        {detail && open && ask.map((q) => <AskBlock key={q.id} text={q.text} />)}

        {/* In place before the first file is sent, so its first outcome is announced. */}
        {detail && (droppable || outcomes.length > 0) && (
          <Outcomes outcomes={outcomes} itemId={id} onJump={onJump} />
        )}

        {detail && item.why && (
          <div className="pt-0.5">
            <button
              type="button"
              aria-expanded={why}
              aria-controls={`req-${id}-why`}
              onClick={() => setWhy((v) => !v)}
              className="group inline-flex items-center gap-1 rounded-sm text-[11.5px] font-medium text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              data-testid="journey-why"
            >
              <ChevronRight
                className="size-3 transition-transform group-aria-expanded:rotate-90 motion-reduce:transition-none"
                aria-hidden
              />
              {t("journey.why")}
            </button>
            <div
              id={`req-${id}-why`}
              hidden={!why}
              className="mt-1.5 rounded border border-border bg-surface px-3 py-2 text-[12px] leading-5 text-muted-foreground"
              data-testid="journey-why-text"
            >
              {item.why}
              {item.basis && (
                <span className="mt-1 block">
                  <span className="field-label">{t("checklist.basis")}</span> {item.basis}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      <div
        className={cn(
          "flex items-center gap-2 sm:flex-col sm:items-end",
          compact ? "col-start-3 row-start-1" : "col-start-2 sm:col-start-3 sm:row-start-1",
        )}
      >
        <span className={compact ? "inline-flex" : "hidden sm:inline-flex"}>
          <StatusChip status={item.status} />
        </span>
        {droppable && detail && (
          <>
            <input
              ref={input}
              type="file"
              multiple
              accept={ACCEPT}
              className="hidden"
              data-testid="journey-upload-input"
              onChange={(e) => {
                send(Array.from(e.target.files ?? []));
                e.target.value = "";
              }}
            />
            {/* Not disabled while it uploads (that would drop the focus), only marked so. */}
            <button
              type="button"
              onClick={() => {
                if (!pending) input.current?.click();
              }}
              onFocus={() => (uploadFocused.current = true)}
              onBlur={(e) => {
                // Removing the focused button blurs it with nowhere to go: that is kept as
                // focused, so the focus can be handed to the row's name.
                if (e.relatedTarget) uploadFocused.current = false;
              }}
              aria-disabled={pending || undefined}
              aria-label={t(pending ? "journey.uploadingFor" : "journey.uploadFor", {
                name: item.name,
              })}
              title={t("journey.uploadHelp")}
              className="inline-flex h-10 items-center gap-1.5 rounded border border-primary/40 bg-surface px-3 text-[12px] font-medium text-primary hover:bg-primary/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring aria-disabled:cursor-default aria-disabled:opacity-50 sm:h-8"
              data-testid="journey-upload"
              data-item={id}
            >
              {pending ? (
                <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
              ) : (
                <Upload className="size-3.5" aria-hidden />
              )}
              <span>{pending ? t("journey.uploading") : t("journey.upload")}</span>
            </button>
          </>
        )}
      </div>

      {over && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <span className="rounded-full bg-surface px-3 py-1 text-[12px] font-semibold text-info shadow-sm">
            {t("journey.dropHere", { name: item.name })}
          </span>
        </div>
      )}
    </li>
  );
}

/** A compact row's one line: the name (a toggle), its section and one detail. */
function CompactLine({
  item,
  docs,
  expanded,
  onToggle,
}: {
  item: ChecklistItemState;
  docs: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const detail =
    item.deficiency && item.status !== "satisfied"
      ? item.deficiency
      : item.status === "in_review"
        ? t("journey.waitingPerson")
        : docs === 0
          ? t("journey.notReceived")
          : docs === 1
            ? t("journey.oneDocument")
            : t("journey.documents", { n: docs });
  return (
    <button
      type="button"
      aria-expanded={expanded}
      onClick={onToggle}
      className="group flex min-w-0 items-start gap-1.5 rounded-sm text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      data-testid="journey-item-toggle"
    >
      <ChevronRight
        className="mt-1 size-3 shrink-0 text-muted-foreground transition-transform group-aria-expanded:rotate-90 motion-reduce:transition-none"
        aria-hidden
      />
      <span className="min-w-0">
        <span className="block text-[13px] font-medium leading-snug text-foreground">
          {item.name}
        </span>
        <span
          className={cn(
            "block text-[12px] leading-5",
            item.status === "satisfied" || item.status === "waived"
              ? "text-muted-foreground"
              : (DEFICIENCY_TONE[item.status] ?? "text-muted-foreground"),
          )}
          data-testid="journey-item-detail"
        >
          {item.section} · {detail}
        </span>
      </span>
    </button>
  );
}

/** How many of a requirement's documents its row names before "n more". */
const SHOWN_DOCS = 6;

const FILTERS: Filter[] = ["all", "todo", "blocking", "in_review", "satisfied"];

/** The Files step's summary: the requirements counted by status, each count a filter. */
function FilterRow({
  r,
  filter,
  onFilter,
}: {
  r: Readiness;
  filter: Filter;
  onFilter: (f: Filter) => void;
}) {
  return (
    <div
      className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2.5"
      role="group"
      aria-label={t("journey.filterLabel")}
      data-testid="journey-summary"
    >
      {r.provisional && (
        <span
          className="mr-1 rounded border border-flag/40 bg-flag-soft px-2 py-0.5 text-[12px] text-flag-foreground"
          title={t("checklist.provisionalHelp")}
          data-testid="journey-provisional"
        >
          {t("checklist.provisional")}
        </span>
      )}
      {FILTERS.map((f) => {
        const n = r.items.filter((i) => passes(i, f)).length;
        if (f !== "all" && n === 0) return null;
        const on = filter === f;
        return (
          <button
            key={f}
            type="button"
            aria-pressed={on}
            onClick={() => onFilter(on && f !== "all" ? "all" : f)}
            className={cn(
              "rounded border px-2 py-0.5 text-[12px] transition-colors",
              on
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-surface text-foreground hover:bg-muted",
            )}
            data-testid={`journey-filter-${f}`}
          >
            {f === "all" ? t("journey.filterAll") : filterLabel(f)} {n}
          </button>
        );
      })}
    </div>
  );
}

/** The Overview's opening line: whether the case can go to credit review, and why not. */
function OverviewStatus({
  r,
  wait,
  caseId,
}: {
  r: Readiness;
  wait: ReadinessWait;
  caseId: string;
}) {
  // Before the documents are in and read, the score and blocking count would only say "nothing
  // received yet": say what readiness waits on instead.
  if (wait) {
    const text =
      wait.kind === "documents"
        ? t("overviewStatus.waitingDocuments")
        : wait.total > 0
          ? t("overviewStatus.reading", { done: wait.done, total: wait.total })
          : t("overviewStatus.readingStarted");
    const Icon = wait.kind === "documents" ? Clock : Loader2;
    return (
      <section
        className="flex flex-wrap items-start gap-2.5 rounded border border-border bg-surface-muted px-4 py-3 text-[13px] text-foreground"
        data-testid="journey-verdict"
        data-state={`waiting-${wait.kind}`}
        role="status"
      >
        <Icon
          className={cn(
            "mt-0.5 size-4 shrink-0 text-muted-foreground",
            wait.kind === "reading" && "animate-spin",
          )}
          aria-hidden
        />
        <p className="min-w-0 flex-1 font-medium">{text}</p>
        {wait.kind === "documents" && (
          <Link
            to="/appraisals/$caseId/documents"
            params={{ caseId }}
            className="text-[12.5px] font-medium text-primary hover:underline"
            data-testid="verdict-upload"
          >
            {t("overviewStatus.uploadDocuments")}
          </Link>
        )}
      </section>
    );
  }
  const ready = readyForCredit(r);
  const score = scoreText(r.score_pct, r.gate_pct);
  const gate = Math.round(r.gate_pct);
  const text = ready
    ? t("overviewStatus.ready", { score, gate })
    : r.blocking_open > 0
      ? t("overviewStatus.notReady", { score, gate, n: r.blocking_open })
      : t("overviewStatus.notReadyScore", { score, gate });
  const Icon = ready ? CheckCircle2 : AlertTriangle;
  return (
    <section
      className={cn(
        "flex items-start gap-2.5 rounded border px-4 py-3 text-[13px]",
        ready
          ? "border-positive/30 bg-positive-soft text-positive"
          : "border-destructive/30 bg-destructive/5 text-destructive",
      )}
      data-testid="journey-verdict"
      data-state={ready ? "ready" : "not_ready"}
      role="status"
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p className="font-medium">{text}</p>
    </section>
  );
}

/** What to ask the customer for this requirement, as the query list words it, with a copy. */
function AskBlock({ text }: { text: string }) {
  const { copied, copy } = useCopy();
  return (
    <div className="rounded-md border-l-2 border-primary/50 bg-surface-muted/60 px-3 py-2">
      <p className="text-[12.5px] leading-5 text-foreground">
        <span className="field-label mb-0.5 block">{t("journey.ask")}</span>
        <span>{text}</span>
      </p>
      <button
        type="button"
        aria-label={t("journey.copy")}
        onClick={() => void copy("ask", text)}
        className="mt-1.5 inline-flex h-8 items-center rounded border border-border bg-surface px-2 text-[11.5px] font-medium text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:h-7"
      >
        <CopyLabel
          icon={Copy}
          label={t("queries.copyText")}
          copied={copied !== null}
          iconClass="size-3"
        />
      </button>
      <span className="sr-only" aria-live="polite">
        {copied ? t("journey.copied") : ""}
      </span>
    </div>
  );
}

/** What became of each file sent from the row. */
function Outcomes({
  outcomes,
  itemId,
  onJump,
}: {
  outcomes: Outcome[];
  itemId: string;
  onJump: (itemId: string) => void;
}) {
  return (
    // Out of the flow while empty, so it takes no room before the first file is sent.
    <ul className="space-y-1 empty:absolute" aria-live="polite" data-testid="journey-received">
      {outcomes.map((o) => {
        const elsewhere = o.state === "counted" && !o.counts.includes(itemId) ? o.counts[0] : null;
        return (
          <li
            key={o.id}
            className={cn(
              "flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11.5px]",
              o.state === "reading" && "text-info",
              o.state === "counted" && "text-positive",
              (o.state === "unidentified" || o.state === "unasked") && "text-flag-foreground",
              o.state === "turnedAway" && "text-destructive",
            )}
            data-testid="journey-outcome"
            data-state={o.state}
          >
            {o.state === "reading" ? (
              <CircleDashed
                className="size-3 shrink-0 animate-spin motion-reduce:animate-none"
                aria-hidden
              />
            ) : o.state === "counted" ? (
              <CheckCircle2 className="size-3 shrink-0" aria-hidden />
            ) : (
              <AlertTriangle className="size-3 shrink-0" aria-hidden />
            )}
            <span className="min-w-0">
              <span className="font-medium">{o.name}</span>
              {": "}
              {o.state === "reading"
                ? t("journey.outcome.reading")
                : o.state === "unidentified"
                  ? t("journey.outcome.unidentified")
                  : o.state === "turnedAway"
                    ? t("journey.outcome.turnedAway", { reason: o.text })
                    : o.text}
            </span>
            {o.state === "reading" && <StageTrack doc={o.doc} />}
            {elsewhere && (
              <button
                type="button"
                onClick={() => onJump(elsewhere)}
                className="rounded-sm font-medium underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                {t("journey.jumpTo")}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Satisfied and waived: one line with their names on the Overview, the rows when opened. */
function DoneBand({
  caseId,
  items,
  now,
  open,
  onToggle,
  docsFor,
  files,
  flash,
}: {
  caseId: string;
  /** The rows in the band. */
  items: ChecklistItemState[];
  /** Every requirement satisfied or waived now, with any kept above where its file was sent. */
  now: ChecklistItemState[];
  open: boolean;
  onToggle: () => void;
  docsFor: (item: ChecklistItemState) => LogicalDocument[];
  files: FileRecord[];
  flash: string | null;
}) {
  const flaggedOn = (item: ChecklistItemState) =>
    docsFor(item).some((d) => {
      const file = files.find((f) => f.id === d.file_id);
      return file ? integrityNeedsPerson(file) : false;
    });
  const flagged = now.filter(flaggedOn).length;
  const above = now.length - items.length;
  return (
    <section aria-labelledby="journey-band-done-title" data-testid="journey-band-done">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="journey-done-rows"
        onClick={onToggle}
        className="group relative flex w-full items-start gap-2 border-l-[3px] border-l-positive bg-surface px-4 py-2.5 text-left hover:bg-surface-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
        data-testid="journey-done-toggle"
      >
        <CheckCircle2 className="mt-px size-3.5 shrink-0 text-positive" aria-hidden />
        {/* On a narrow screen the names and the flag drop under the title, never past the edge. */}
        <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          <span
            id="journey-band-done-title"
            className="text-[11.5px] font-semibold uppercase leading-4 tracking-wide text-foreground"
          >
            {t("journey.band.done")}
          </span>
          <span
            className="tabular rounded-full bg-positive-soft px-1.5 text-[10.5px] font-semibold leading-4 text-positive"
            data-testid="journey-done-count"
          >
            {now.length}
          </span>
          {!open && (
            <span className="min-w-0 flex-1 basis-40 truncate text-[12px] leading-4 text-muted-foreground">
              {now.map((i) => i.name).join(" · ")}
            </span>
          )}
          {flagged > 0 && (
            <span className="inline-flex min-w-0 items-center gap-1 text-[11.5px] font-medium leading-4 text-flag-foreground">
              <AlertTriangle className="size-3 shrink-0" aria-hidden />
              {t("journey.band.doneFlagged", { n: flagged })}
            </span>
          )}
        </span>
        <span className="sr-only">
          {t(open ? "documents.section.hide" : "documents.section.show")}
        </span>
        <ChevronDown
          className="mt-px size-3.5 shrink-0 text-muted-foreground transition-transform group-aria-expanded:rotate-180 motion-reduce:transition-none"
          aria-hidden
        />
      </button>
      <ul
        id="journey-done-rows"
        hidden={!open}
        className="divide-y divide-border border-t border-border"
      >
        {open &&
          items.map((item) => (
            <DoneRow
              key={item.item_id}
              caseId={caseId}
              item={item}
              docs={docsFor(item)}
              files={files}
              flash={flash === item.item_id}
            />
          ))}
        {open && above > 0 && (
          <li
            className="px-4 py-2 text-[12px] text-muted-foreground"
            data-testid="journey-done-above"
          >
            {t("journey.band.doneAbove", {
              names: now
                .filter((i) => !items.includes(i))
                .map((i) => i.name)
                .join(" · "),
            })}
          </li>
        )}
      </ul>
    </section>
  );
}

function DoneRow({
  caseId,
  item,
  docs,
  files,
  flash,
}: {
  caseId: string;
  item: ChecklistItemState;
  docs: LogicalDocument[];
  files: FileRecord[];
  flash: boolean;
}) {
  const Icon = ICON[item.status];
  return (
    <li
      id={`req-${item.item_id}`}
      className={cn(
        // On a phone the documents take a line of their own under the name, so a file's tag
        // never squeezes its name away; from sm they follow the section on the same line.
        "grid scroll-mt-24 grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 px-4 py-2 transition-colors duration-700 motion-reduce:transition-none sm:grid-cols-[16px_auto_minmax(0,1fr)_auto]",
        flash && "bg-accent/70 duration-0",
      )}
      data-testid="journey-item"
      data-item={item.item_id}
      data-status={item.status}
      data-blocking={item.blocking}
      data-band="done"
    >
      <Icon className={cn("row-start-1 size-4", ICON_TONE[item.status])} aria-hidden />
      <div className="col-start-2 row-start-1 flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <p
          id={`req-${item.item_id}-name`}
          tabIndex={-1}
          className="rounded-sm text-[13px] font-medium text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          {item.name}
        </p>
        <span className="text-[11px] text-muted-foreground">{item.section}</span>
      </div>
      {docs.length > 0 && (
        <div className="col-start-2 col-end-4 row-start-2 flex min-w-0 flex-wrap gap-1.5 sm:col-start-3 sm:col-end-4 sm:row-start-1">
          {docs.map((d) => (
            <DocPill key={d.id} caseId={caseId} doc={d} files={files} />
          ))}
        </div>
      )}
      <span className="col-start-3 row-start-1 justify-self-end sm:col-start-4">
        <StatusChip status={item.status} />
      </span>
    </li>
  );
}

/** A document on file: its type and pages, opening its first page; flagged, with its file's
 * integrity state, when the file's checks want a person. */
function DocPill({
  caseId,
  doc,
  files,
}: {
  caseId: string;
  doc: LogicalDocument;
  files: FileRecord[];
}) {
  const viewer = useDocViewer();
  const types = useDocumentTypes();
  const file = files.find((f) => f.id === doc.file_id);
  const flagged = file ? integrityNeedsPerson(file) : false;
  const type = (doc.classification?.types ?? []).map(types.name).join(" + ");
  return (
    <button
      type="button"
      onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
      title={file?.original_name}
      className={cn(
        "inline-flex h-6 max-w-full items-center gap-1 rounded border px-1.5 text-left text-[11.5px] transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
        flagged ? "border-flag/40 bg-flag-soft text-flag-foreground" : "border-border bg-surface",
      )}
      data-testid="journey-doc"
      data-flagged={flagged}
    >
      {flagged ? (
        <AlertTriangle className="size-3 shrink-0" aria-hidden />
      ) : (
        <FileText className="size-3 shrink-0 text-muted-foreground" aria-hidden />
      )}
      <span className="min-w-0 truncate">
        {type || t("document.unclassified")}
        <span className="text-muted-foreground">
          {" · "}
          {file?.original_name ?? ""} {pageRange(doc)}
        </span>
      </span>
      {flagged && file && (
        <span className="shrink-0 rounded-sm bg-flag/15 px-1 text-[10px] font-semibold uppercase tracking-wide">
          {t(`documents.table.integrityState.${stateOf(file)}`)}
        </span>
      )}
    </button>
  );
}
