import { Link } from "@tanstack/react-router";
import { Fragment, createContext, useContext, useState } from "react";
import { ChevronRight, Download, Eye, Files, Loader2, Lock } from "lucide-react";
import type {
  Cam,
  CamBlock,
  CamFact,
  CamSection,
  CamSignOff,
  CamSummaryItem,
  CamSummaryKind,
  CamTable,
  CamText,
  Evidence,
  OutputKind,
  OutputSource,
  PdArea,
  PdNote,
  PdPerson,
  PdQuestion,
  Spread,
  SpreadCell,
  SpreadRow,
} from "@/api/types";
import { SEVERITY_TONE } from "@/components/case/xv/styles";
import { Chip, Panel, type Tone } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { evidenceRequest, useDocViewer } from "@/components/docviewer/DocViewer";
import { t, tOr } from "@/config/terminology";
import { useAnchor } from "@/domain/anchor";
import { formatInr } from "@/domain/cases";
import { useCam, usePdNote, useSpread } from "@/domain/findings";
import {
  OUTPUT_FORMATS,
  camSectionAnchor,
  citationRuns,
  configLabel,
  formatDay,
  leadingFigure,
  observationSection,
  pageRuns,
  sourcesById,
  unbrokenParts,
  uniqueEvidence,
  useOutputDownload,
  type SourcePages,
} from "@/domain/outputs";
import { cn } from "@/lib/utils";

// The Outputs tab's three views (FRD §6): the spread (F-22, interim layout),
// the draft CAM (F-23) and the PD question note (F-24). Every figure and
// statement opens the page it rests on; the memo and the note number the
// documents they cite as their Word and PDF downloads do, and download in
// both formats.
//
// Test ids (data-testid):
//   cam                  the memo: cam-header (cam-title, cam-borrower, cam-meta with
//                        cam-config, whose title is the full version, cam-template-note) with
//                        cam-downloads (cam-download-docx, cam-download-pdf); a cam-section per
//                        section (data-section; its id, cam-section-<id>, the anchor the note's
//                        observations open) headed cam-section-title, holding
//                        cam-section-empty or its blocks: cam-paragraph, cam-facts (a cam-fact
//                        each, data-label), cam-table (data-stacks="true" when its rows read as
//                        cards in a narrow box; cam-table-title, a cam-table-row each with its
//                        figures data-numeric and, when it stacks, each cell's data-label,
//                        cam-table-note), cam-subheading and cam-note; cam-summary, a
//                        cam-summary-<kind> per kind (finding, incomplete, deviation,
//                        unassessed, query; cam-summary-finding always, with cam-summary-none
//                        when the run found nothing) with a cam-summary-item each (data-kind,
//                        data-ref: cam-summary-ref, cam-summary-status, blocks-submission,
//                        cam-summary-request), the open queries under a cam-summary-group title
//                        each, and cam-summary-query-list; cam-recommendation, a
//                        cam-recommendation-prompt each with its empty cam-recommendation-box,
//                        then cam-sign-off (a cam-sign-off-role each)
//   pd-note              the note: pd-header (pd-title, pd-subtitle, pd-facts with a pd-fact
//                        each, data-label) with pd-downloads (pd-download-docx,
//                        pd-download-pdf); pd-people (a pd-person each); pd-record (a
//                        pd-record-field each, left blank); a pd-topic per topic (data-area)
//                        headed pd-topic-title, with a pd-question each (data-question,
//                        data-rule, data-source): pd-question-number, pd-question-text,
//                        pd-question-context, pd-question-source, pd-question-link (an
//                        observation's opens the CAM view at the section its key names),
//                        pd-question-status, and pd-question-also with a pd-also each
//                        (data-ref: pd-also-link, pd-also-status); pd-no-questions
//                        instead when there are none; pd-documents (a pd-document each);
//                        pd-sign-off (a pd-sign-off-role each)
//   output-sources       either one's numbered sources: an output-source row each (data-number,
//                        data-document) whose output-source-open opens its first cited page
//   citation             a document a statement rests on, opening its first cited page
//                        (data-source: its source's number; data-pages); citation-range three
//                        or more sources in a row cited at the same pages (data-first,
//                        data-last, aria-expanded), which opens into a citation each;
//                        citation-more the rest of the pages where documents are not numbered

/** The numbered sources of the memo or the note on screen, by document id. */
export const SourcesContext = createContext<ReadonlyMap<string, OutputSource> | null>(null);

const chip =
  "inline-flex shrink-0 items-center gap-0.5 whitespace-nowrap rounded border border-border px-1 text-[10.5px] font-medium text-primary hover:bg-muted";

/** The pages a statement rests on. In the memo and the note they are marked as the downloads mark
 * them: by source number, a source's pages together ("6 pp.3, 5"), and three or more sources in a
 * row cited at the same pages as one run ("13-23 p.1") that opens into its sources. Each source
 * opens its first cited page. */
function Citations({
  caseId,
  evidence,
  className,
}: {
  caseId: string;
  evidence: Evidence[];
  className?: string;
}) {
  const sources = useContext(SourcesContext);
  if (evidence.length === 0) return null;
  return (
    <span className={cn("ml-1 inline-flex flex-wrap gap-0.5 align-baseline", className)}>
      {sources ? (
        <NumberedCitations caseId={caseId} evidence={evidence} sources={sources} />
      ) : (
        <PageCitations caseId={caseId} evidence={uniqueEvidence(evidence)} />
      )}
    </span>
  );
}

/** "p.4", "pp.3-5": a source's pages, as the downloads print them. */
function pagesAt(pages: number[]): string {
  const text = pageRuns(pages);
  return pages.length === 1
    ? t("outputs.citation.onePage", { pages: text })
    : t("outputs.citation.manyPages", { pages: text });
}

function NumberedCitations({
  caseId,
  evidence,
  sources,
}: {
  caseId: string;
  evidence: Evidence[];
  sources: ReadonlyMap<string, OutputSource>;
}) {
  const [open, setOpen] = useState<ReadonlySet<number>>(() => new Set());
  const toggle = (first: number) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(first)) next.delete(first);
      else next.add(first);
      return next;
    });
  const { runs, unlisted } = citationRuns(evidence, sources);
  return (
    <>
      {runs.map((run) => {
        const first = run[0];
        const last = run[run.length - 1];
        if (!first || !last) return null;
        if (run.length === 1)
          return (
            <SourceChip key={first.source.number} caseId={caseId} cited={first} all={evidence} />
          );
        const expanded = open.has(first.source.number);
        const span = {
          first: first.source.number,
          last: last.source.number,
          at: pagesAt(first.pages),
        };
        return (
          <Fragment key={first.source.number}>
            <button
              type="button"
              onClick={() => toggle(first.source.number)}
              aria-expanded={expanded}
              title={t("outputs.citation.rangeTitle", span)}
              className={chip}
              data-testid="citation-range"
              data-first={span.first}
              data-last={span.last}
            >
              <Files className="h-2.5 w-2.5" />
              {t("outputs.citation.range", span)}
              <ChevronRight
                className={cn("h-2.5 w-2.5 transition-transform", expanded && "rotate-90")}
                aria-hidden
              />
            </button>
            {expanded &&
              run.map((cited) => (
                <SourceChip
                  key={cited.source.number}
                  caseId={caseId}
                  cited={cited}
                  all={evidence}
                />
              ))}
          </Fragment>
        );
      })}
      {unlisted.map((e) => (
        <PageChip key={`${e.document_id}-${e.page}`} caseId={caseId} evidence={e} />
      ))}
    </>
  );
}

/** One numbered source, "5 p.1" or "11 pp.3-5", opening its first cited page with the statement's
 * other pages listed in the viewer. */
function SourceChip({
  caseId,
  cited,
  all,
}: {
  caseId: string;
  cited: SourcePages;
  all: Evidence[];
}) {
  const viewer = useDocViewer();
  const e = cited.evidence[0];
  if (!e) return null;
  const { number: n, label } = cited.source;
  const pages = pageRuns(cited.pages);
  return (
    <button
      type="button"
      onClick={() => {
        const request = evidenceRequest(caseId, all, e);
        if (request) viewer.open(request);
      }}
      title={
        cited.pages.length === 1
          ? t("outputs.citation.title", { n, label, pages })
          : t("outputs.citation.titlePages", { n, label, pages })
      }
      className={chip}
      data-testid="citation"
      data-source={n}
      data-pages={cited.pages.join(",")}
    >
      <Eye className="h-2.5 w-2.5" />
      {t("outputs.citation.source", { n, at: pagesAt(cited.pages) })}
    </button>
  );
}

/** A page of a document that is not numbered. */
function PageChip({ caseId, evidence: e }: { caseId: string; evidence: Evidence }) {
  const viewer = useDocViewer();
  return (
    <button
      type="button"
      onClick={() =>
        viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null })
      }
      title={t("crossVerification.evidence.openPage", { page: e.page })}
      aria-label={t("crossVerification.evidence.openPage", { page: e.page })}
      className={chip}
      data-testid="citation"
      data-page={e.page}
    >
      <Eye className="h-3 w-3" aria-hidden />
    </button>
  );
}

/** Where documents are not numbered, one eye for all the pages a statement rests on: the viewer
 * opens at the first and lists the rest. */
function PageCitations({ caseId, evidence }: { caseId: string; evidence: Evidence[] }) {
  const viewer = useDocViewer();
  const request = evidenceRequest(caseId, evidence);
  if (!request) return null;
  const count = request.set?.length ?? 1;
  const label =
    count > 1
      ? t("viewer.openEvidenceSet", { count })
      : t("crossVerification.evidence.openPage", { page: request.page ?? 1 });
  return (
    <button
      type="button"
      onClick={() => viewer.open(request)}
      title={label}
      aria-label={label}
      className={chip}
      data-testid="citation"
      data-page={request.page}
      data-count={count}
    >
      <Eye className="h-3 w-3" aria-hidden />
      {count > 1 && <span className="tabular">{count}</span>}
    </button>
  );
}

// --- The memo and the note, shared ---

const heading = "text-[14px] font-semibold text-foreground";
const columnHead = "px-2 py-1 font-medium first:pl-0 last:pr-0";
const cell = "px-2 py-1.5 align-top first:pl-0 last:pr-0";

type Stack = {
  table: string;
  head: string;
  body: string;
  row: string;
  cell: string;
  chips: string;
};

/** Where its box is narrower than about 7rem a column, a table of four columns or more reads as
 * one card per row (F-20): each value beside its column's label, the first column as the card's
 * title. Tables of up to three columns fit a phone as they are. Tailwind needs every class
 * written out. */
const STACK: Record<4 | 5 | 6 | 7, Stack> = {
  4: {
    table: "@max-[28rem]:block",
    head: "@max-[28rem]:sr-only",
    body: "@max-[28rem]:block @max-[28rem]:space-y-2",
    row: "@max-[28rem]:block @max-[28rem]:rounded @max-[28rem]:border @max-[28rem]:px-3 @max-[28rem]:py-2",
    cell: "@max-[28rem]:grid @max-[28rem]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] @max-[28rem]:gap-x-3 @max-[28rem]:px-0 @max-[28rem]:py-0.5 @max-[28rem]:text-left @max-[28rem]:before:text-[11px] @max-[28rem]:before:text-muted-foreground @max-[28rem]:before:content-[attr(data-label)] @max-[28rem]:first:block @max-[28rem]:first:pb-1 @max-[28rem]:first:font-semibold @max-[28rem]:first:before:content-none",
    chips: "@max-[28rem]:justify-start",
  },
  5: {
    table: "@max-[35rem]:block",
    head: "@max-[35rem]:sr-only",
    body: "@max-[35rem]:block @max-[35rem]:space-y-2",
    row: "@max-[35rem]:block @max-[35rem]:rounded @max-[35rem]:border @max-[35rem]:px-3 @max-[35rem]:py-2",
    cell: "@max-[35rem]:grid @max-[35rem]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] @max-[35rem]:gap-x-3 @max-[35rem]:px-0 @max-[35rem]:py-0.5 @max-[35rem]:text-left @max-[35rem]:before:text-[11px] @max-[35rem]:before:text-muted-foreground @max-[35rem]:before:content-[attr(data-label)] @max-[35rem]:first:block @max-[35rem]:first:pb-1 @max-[35rem]:first:font-semibold @max-[35rem]:first:before:content-none",
    chips: "@max-[35rem]:justify-start",
  },
  6: {
    table: "@max-[42rem]:block",
    head: "@max-[42rem]:sr-only",
    body: "@max-[42rem]:block @max-[42rem]:space-y-2",
    row: "@max-[42rem]:block @max-[42rem]:rounded @max-[42rem]:border @max-[42rem]:px-3 @max-[42rem]:py-2",
    cell: "@max-[42rem]:grid @max-[42rem]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] @max-[42rem]:gap-x-3 @max-[42rem]:px-0 @max-[42rem]:py-0.5 @max-[42rem]:text-left @max-[42rem]:before:text-[11px] @max-[42rem]:before:text-muted-foreground @max-[42rem]:before:content-[attr(data-label)] @max-[42rem]:first:block @max-[42rem]:first:pb-1 @max-[42rem]:first:font-semibold @max-[42rem]:first:before:content-none",
    chips: "@max-[42rem]:justify-start",
  },
  7: {
    table: "@max-[49rem]:block",
    head: "@max-[49rem]:sr-only",
    body: "@max-[49rem]:block @max-[49rem]:space-y-2",
    row: "@max-[49rem]:block @max-[49rem]:rounded @max-[49rem]:border @max-[49rem]:px-3 @max-[49rem]:py-2",
    cell: "@max-[49rem]:grid @max-[49rem]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] @max-[49rem]:gap-x-3 @max-[49rem]:px-0 @max-[49rem]:py-0.5 @max-[49rem]:text-left @max-[49rem]:before:text-[11px] @max-[49rem]:before:text-muted-foreground @max-[49rem]:before:content-[attr(data-label)] @max-[49rem]:first:block @max-[49rem]:first:pb-1 @max-[49rem]:first:font-semibold @max-[49rem]:first:before:content-none",
    chips: "@max-[49rem]:justify-start",
  },
};

/** How a table of this many columns stacks in a narrow box, if it does. */
function stackOf(columns: number): Stack | null {
  return columns < 4 ? null : STACK[Math.min(columns, 7) as 4 | 5 | 6 | 7];
}

/** Words with the years and references in them (FY 2025-26, XV-000021-03, DOC-01) kept whole. */
function Words({ text }: { text: string }) {
  return (
    <>
      {unbrokenParts(text).map((part, i) =>
        part.unbroken ? (
          <span key={i} className="whitespace-nowrap">
            {part.text}
          </span>
        ) : (
          <Fragment key={i}>{part.text}</Fragment>
        ),
      )}
    </>
  );
}

function Statement({ caseId, text }: { caseId: string; text: CamText }) {
  return (
    <>
      <Words text={text.text} />
      <Citations caseId={caseId} evidence={text.citations ?? []} />
    </>
  );
}

const DOWNLOAD_ID: Record<OutputKind, string> = { cam: "cam", pd_note: "pd" };

/** Download Word and Download PDF: the file is fetched with the session's token and saved. */
export function Downloads({ caseId, output }: { caseId: string; output: OutputKind }) {
  const download = useOutputDownload(caseId, output);
  const id = DOWNLOAD_ID[output];
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid={`${id}-downloads`}>
      {OUTPUT_FORMATS.map((format) => {
        const busy = download.isPending && download.variables === format;
        return (
          <button
            key={format}
            type="button"
            onClick={() => download.mutate(format)}
            disabled={download.isPending}
            aria-busy={busy}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12px] font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed",
              !busy && "disabled:opacity-60",
            )}
            data-testid={`${id}-download-${format}`}
          >
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <Download className="h-3.5 w-3.5" aria-hidden />
            )}
            {busy ? t("outputs.download.preparing") : t(`outputs.download.${format}`)}
          </button>
        );
      })}
    </div>
  );
}

const STATUS_TONE: Record<string, Tone> = {
  accepted_as_valid: "flag",
  accepted: "flag",
  escalated: "info",
  not_valid: "positive",
};

/** A finding's status as the engine gives it (Accepted as valid, Escalated, Open). */
function StatusChip({ status, testId }: { status: string; testId: string }) {
  const key = status.trim().toLowerCase().replace(/\s+/g, "_");
  return (
    <Chip tone={STATUS_TONE[key] ?? "muted"}>
      <span data-testid={testId}>{tOr(`outputs.status.${key}`, status)}</span>
    </Chip>
  );
}

function BlocksSubmission() {
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded bg-destructive px-1.5 py-0.5 text-[10.5px] font-medium text-destructive-foreground"
      data-testid="blocks-submission"
    >
      <Lock className="h-3 w-3" aria-hidden /> {t("crossVerification.card.blocksSubmission")}
    </span>
  );
}

/** The documents cited, numbered as the citations and the downloads number them; each opens its
 * first cited page. */
export function Sources({ caseId, sources }: { caseId: string; sources: OutputSource[] }) {
  const viewer = useDocViewer();
  if (sources.length === 0) return null;
  return (
    <section className="min-w-0" data-testid="output-sources">
      <h3 className={heading}>{t("outputs.sources.title")}</h3>
      <div className="mt-1.5 overflow-x-auto">
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
              <th scope="col" className={cn(columnHead, "w-10 text-right")}>
                {t("outputs.sources.number")}
              </th>
              <th scope="col" className={columnHead}>
                {t("outputs.sources.document")}
              </th>
              <th scope="col" className={columnHead}>
                {t("outputs.sources.file")}
              </th>
              <th scope="col" className={columnHead}>
                {t("outputs.sources.pages")}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sources.map((s) => {
              const first = s.pages[0];
              return (
                <tr
                  key={s.number}
                  data-testid="output-source"
                  data-number={s.number}
                  data-document={s.document_id}
                >
                  <td className={cn(cell, "tabular text-right")}>{s.number}</td>
                  <td className={cell}>
                    <button
                      type="button"
                      onClick={() =>
                        viewer.open({
                          caseId,
                          documentId: s.document_id,
                          ...(first === undefined ? {} : { page: first }),
                        })
                      }
                      className="text-left font-medium text-primary hover:underline"
                      data-testid="output-source-open"
                    >
                      {s.label}
                    </button>
                  </td>
                  <td className={cn(cell, "break-all text-muted-foreground")}>
                    {s.file_name ?? "—"}
                  </td>
                  <td className={cn(cell, "tabular")}>{s.pages.join(", ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// --- CAM ---

function Facts({ caseId, facts }: { caseId: string; facts: CamFact[] }) {
  return (
    <dl
      className="grid gap-x-6 gap-y-2.5 rounded border border-border bg-surface-muted/40 px-3 py-2.5 sm:grid-cols-2"
      data-testid="cam-facts"
    >
      {facts.map((f, i) => (
        <div
          key={`${f.label}-${i}`}
          className="min-w-0"
          data-testid="cam-fact"
          data-label={f.label}
        >
          <dt className="field-label">{f.label}</dt>
          <dd className="mt-0.5 break-words text-[13px]">
            <Statement caseId={caseId} text={f.value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** A figure in a column of figures: its amount kept on one line, the words after it free to wrap,
 * and the pages it rests on on a line of their own, so that the figures align. */
function Figure({ caseId, value, chips }: { caseId: string; value: CamText; chips: string }) {
  const [lead, rest] = leadingFigure(value.text);
  return (
    <>
      <span className="block">
        {lead && <span className="whitespace-nowrap">{lead}</span>}
        <Words text={rest} />
      </span>
      <Citations
        caseId={caseId}
        evidence={value.citations ?? []}
        className={cn("ml-0 mt-0.5 flex justify-end", chips)}
      />
    </>
  );
}

/** A value in a column of words; an identifier or a single word stays on one line. */
function CellText({ caseId, value }: { caseId: string; value: CamText }) {
  const whole = !/\s/.test(value.text) && value.text.length <= 24;
  return (
    <>
      {whole ? (
        <span className="whitespace-nowrap">{value.text}</span>
      ) : (
        <Words text={value.text} />
      )}
      <Citations caseId={caseId} evidence={value.citations ?? []} />
    </>
  );
}

function MemoTable({ caseId, table }: { caseId: string; table: CamTable }) {
  const numeric = new Set(table.numeric ?? []);
  const stack = stackOf(table.columns.length);
  return (
    <figure
      className="min-w-0 @container"
      data-testid="cam-table"
      data-stacks={stack ? "true" : undefined}
    >
      {table.title && (
        <figcaption className="mb-1 text-[12.5px] font-semibold" data-testid="cam-table-title">
          {table.title}
        </figcaption>
      )}
      <div className="overflow-x-auto">
        <table className={cn("w-full text-[12.5px]", stack?.table)}>
          <thead className={stack?.head}>
            <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
              {table.columns.map((c, j) => (
                <th key={j} scope="col" className={cn(columnHead, numeric.has(j) && "text-right")}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className={cn("divide-y divide-border", stack?.body)}>
            {table.rows.map((row, j) => (
              <tr key={j} className={stack?.row} data-testid="cam-table-row">
                {row.map((value, k) => (
                  <td
                    key={k}
                    className={cn(cell, numeric.has(k) && "tabular text-right", stack?.cell)}
                    data-numeric={numeric.has(k) ? "true" : undefined}
                    data-label={stack ? table.columns[k] : undefined}
                  >
                    <div className="min-w-0">
                      {numeric.has(k) ? (
                        <Figure caseId={caseId} value={value} chips={stack?.chips ?? ""} />
                      ) : (
                        <CellText caseId={caseId} value={value} />
                      )}
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.note && (
        <p className="mt-1 text-[11.5px] italic text-muted-foreground" data-testid="cam-table-note">
          <Words text={table.note} />
        </p>
      )}
    </figure>
  );
}

export function Block({ caseId, block }: { caseId: string; block: CamBlock }) {
  if (block.kind === "paragraph" && block.paragraph) {
    return (
      <p className="text-[13px] leading-relaxed" data-testid="cam-paragraph">
        <Statement caseId={caseId} text={block.paragraph} />
      </p>
    );
  }
  if (block.kind === "facts") return <Facts caseId={caseId} facts={block.facts ?? []} />;
  if (block.kind === "table" && block.table) {
    return <MemoTable caseId={caseId} table={block.table} />;
  }
  if (block.kind === "subheading") {
    return (
      <h4 className="pt-1 text-[13px] font-semibold" data-testid="cam-subheading">
        {block.text}
      </h4>
    );
  }
  if (block.kind === "note") {
    return (
      <p className="text-[12px] italic text-muted-foreground" data-testid="cam-note">
        <Words text={block.text ?? ""} />
      </p>
    );
  }
  return null;
}

/** A section's blocks as its parts read them: each part's run of blocks, from its subheading to
 * the next, the person's words and overrides included (they are laid over the section's blocks). */
function partsOf(section: CamSection): { id: string; title: string | null; blocks: CamBlock[] }[] {
  const parts = section.parts ?? [];
  const blocks = section.blocks ?? [];
  if (parts.length <= 1) return [{ id: parts[0]?.id ?? section.id, title: null, blocks }];
  const out: { id: string; title: string | null; blocks: CamBlock[] }[] = [];
  let next = 0;
  for (const block of blocks) {
    if (block.kind === "subheading" && next < parts.length && block.text === parts[next]!.title) {
      out.push({ id: parts[next]!.id, title: block.text ?? null, blocks: [] });
      next += 1;
    } else if (out.length > 0) out[out.length - 1]!.blocks.push(block);
    else out.push({ id: section.id, title: null, blocks: [block] });
  }
  return out;
}

/** A part of a section, under its subheading where the section has several; it keeps its id, the
 * anchor the note's observations open. */
function MemoPart({
  caseId,
  part,
}: {
  caseId: string;
  part: { id: string; title: string | null; blocks: CamBlock[] };
}) {
  const anchor = camSectionAnchor(part.id);
  const ref = useAnchor<HTMLElement>(anchor);
  return (
    <section
      ref={ref}
      id={anchor}
      className="min-w-0 scroll-mt-4 space-y-2.5"
      data-testid="cam-section"
      data-section={part.id}
    >
      {part.title && (
        <h4 className="pt-1 text-[13px] font-semibold" data-testid="cam-subheading">
          {part.title}
        </h4>
      )}
      {part.blocks.map((block, i) => (
        <Block key={i} caseId={caseId} block={block} />
      ))}
    </section>
  );
}

function MemoSection({ caseId, section }: { caseId: string; section: CamSection }) {
  const blocks = section.blocks ?? [];
  const anchor = camSectionAnchor(section.id);
  const ref = useAnchor<HTMLElement>(anchor);
  return (
    <section
      ref={ref}
      id={anchor}
      className="min-w-0 scroll-mt-4"
      data-testid="cam-memo-section"
      data-section={section.id}
    >
      <h3 className={heading} data-testid="cam-section-title">
        {section.number}. {section.title}
      </h3>
      {blocks.length === 0 && section.empty && (
        <p className="mt-1 text-[12.5px] text-muted-foreground" data-testid="cam-section-empty">
          {section.empty}
        </p>
      )}
      <div className="mt-1.5 space-y-2.5">
        {partsOf(section).map((part) => (
          <MemoPart key={part.id} caseId={caseId} part={part} />
        ))}
      </div>
    </section>
  );
}

function CamHeader({ caseId, m }: { caseId: string; m: Cam }) {
  const note = m.template_note || (m.interim_template ? t("outputs.cam.interim") : null);
  return (
    <header className="border-b border-border pb-3" data-testid="cam-header">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <p className="field-label">{t("outputs.cam.eyebrow")}</p>
          <h2 className="text-[18px] font-semibold" data-testid="cam-title">
            {m.title}
          </h2>
          <p className="mt-0.5 break-words text-[13px]" data-testid="cam-borrower">
            {m.borrower} ·{" "}
            <span className="whitespace-nowrap">{t("outputs.header.case", { id: m.case_id })}</span>
          </p>
          <p
            className="tabular mt-0.5 break-words text-[11.5px] text-muted-foreground"
            data-testid="cam-meta"
          >
            {t("outputs.header.asOf", { date: formatDay(m.as_of) })} ·{" "}
            <span title={m.config_version} data-testid="cam-config">
              {t("outputs.header.config", { version: configLabel(m) })}
            </span>
            {m.run_id && (
              <>
                {" · "}
                <span className="whitespace-nowrap">
                  {t("outputs.header.run", { id: m.run_id })}
                </span>
              </>
            )}
          </p>
        </div>
        <Downloads caseId={caseId} output="cam" />
      </div>
      {note && (
        <p
          className="mt-2 rounded border border-info/40 bg-info-soft px-3 py-2 text-[12px] italic text-info"
          data-testid="cam-template-note"
        >
          {note}
        </p>
      )}
    </header>
  );
}

const SUMMARY_KINDS: CamSummaryKind[] = [
  "finding",
  "incomplete",
  "deviation",
  "unassessed",
  "query",
];

/** Where a summary item is decided, opened at the item: the board for a finding or a check that
 * could not be completed (named by its rule, having no XV reference), the policy tab for a norm. */
function SummaryRef({ caseId, item }: { caseId: string; item: CamSummaryItem }) {
  const className =
    "whitespace-nowrap font-mono text-[11.5px] font-medium text-primary hover:underline";
  return item.kind === "finding" || item.kind === "incomplete" ? (
    <Link
      to="/appraisals/$caseId/cross-verification"
      params={{ caseId }}
      search={{ finding: item.ref }}
      className={className}
      data-testid="cam-summary-ref"
    >
      {item.kind === "incomplete" ? (item.rule ?? item.ref) : item.ref}
    </Link>
  ) : (
    <Link
      to="/appraisals/$caseId/policy"
      params={{ caseId }}
      search={{ norm: item.ref }}
      className={className}
      data-testid="cam-summary-ref"
    >
      {item.ref}
    </Link>
  );
}

/** A line of the summary. A finding is a register entry (reference, severity, title cited,
 * status, whether it blocks submission); its explanation is in section 10. A check not completed
 * says why and what would complete it; a norm, its sentence; a query, its text. */
function SummaryItem({ caseId, item }: { caseId: string; item: CamSummaryItem }) {
  const citations = item.citations ?? [];
  const detail = item.kind === "query" || (item.text && item.text !== item.title) ? item.text : "";
  return (
    <li className="pl-1" data-testid="cam-summary-item" data-kind={item.kind} data-ref={item.ref}>
      {item.kind !== "query" && (
        <span className="flex flex-wrap items-center gap-1.5">
          <SummaryRef caseId={caseId} item={item} />
          {item.severity && (
            <Chip tone={SEVERITY_TONE[item.severity]}>{t(`severity.${item.severity}`)}</Chip>
          )}
          {(item.title || !detail) && (
            <span className="font-medium">
              {item.title && <Words text={item.title} />}
              {!detail && <Citations caseId={caseId} evidence={citations} />}
            </span>
          )}
          {item.status && <StatusChip status={item.status} testId="cam-summary-status" />}
          {item.blocking && <BlocksSubmission />}
        </span>
      )}
      {detail && (
        <span className="mt-0.5 block leading-relaxed">
          <Statement caseId={caseId} text={{ text: detail, citations }} />
        </span>
      )}
      {item.request && (
        <span className="mt-0.5 block leading-relaxed" data-testid="cam-summary-request">
          <span className="font-medium">{t("outputs.cam.summary.request")}</span>{" "}
          <Words text={item.request} />
        </span>
      )}
    </li>
  );
}

/** The open queries, grouped as the query list groups them. */
function queryGroups(items: CamSummaryItem[]): { title: string | null; items: CamSummaryItem[] }[] {
  const out: { title: string | null; items: CamSummaryItem[] }[] = [];
  for (const item of items) {
    const title = item.group ? t(`queryGroup.${item.group}`) : (item.title ?? null);
    const last = out[out.length - 1];
    if (last && last.title === title) last.items.push(item);
    else out.push({ title, items: [item] });
  }
  return out;
}

export function Summary({
  caseId,
  m,
  headed = true,
}: {
  caseId: string;
  m: Cam;
  /** Off where the section's card carries the title. */
  headed?: boolean;
}) {
  return (
    <section className="min-w-0" data-testid="cam-summary">
      {headed && (
        <h3 className={heading}>
          {m.summary_number}. {m.summary_title}
        </h3>
      )}
      {SUMMARY_KINDS.map((kind) => {
        const items = m.summary.filter((i) => i.kind === kind);
        if (items.length === 0) {
          // The findings are always accounted for: none found is the run's result (F-25).
          if (kind !== "finding") return null;
          return (
            <p
              key={kind}
              className="mt-2.5 text-[12px] font-semibold text-muted-foreground"
              data-testid="cam-summary-finding"
            >
              <span data-testid="cam-summary-none">
                <Words
                  text={
                    m.run_id
                      ? t("outputs.cam.summary.findingNone", { run: m.run_id })
                      : t("outputs.cam.summary.findingNoRun")
                  }
                />
              </span>
            </p>
          );
        }
        const groups = kind === "query" ? queryGroups(items) : [{ title: null, items }];
        let start = 1;
        return (
          <div key={kind} className="mt-2.5" data-testid={`cam-summary-${kind}`}>
            <p className="flex flex-wrap items-baseline gap-x-2 text-[12px] font-semibold text-muted-foreground">
              {t(`outputs.cam.summary.${kind}`, { n: items.length })}
              {kind === "query" && (
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
            </p>
            {groups.map((group, g) => {
              const first = start;
              start += group.items.length;
              return (
                <div key={g}>
                  {group.title && (
                    <p className="mt-1.5 text-[12px] font-medium" data-testid="cam-summary-group">
                      {group.title}
                    </p>
                  )}
                  <ol start={first} className="mt-1 list-decimal space-y-1.5 pl-5 text-[12.5px]">
                    {group.items.map((item, i) => (
                      <SummaryItem key={`${item.ref}-${i}`} caseId={caseId} item={item} />
                    ))}
                  </ol>
                </div>
              );
            })}
          </div>
        );
      })}
    </section>
  );
}

const SIGN_OFF_FIELDS = ["name", "designation", "signature", "date"] as const;

/** Prepared, recommended, approved (the memo), or whoever holds the discussion (the note): left
 * blank for the people who sign. */
function SignOff({
  roles,
  testId,
}: {
  roles: CamSignOff[];
  testId: "cam-sign-off" | "pd-sign-off";
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-3" data-testid={testId}>
      {roles.map((r) => (
        <div
          key={r.role}
          className="rounded border border-border px-3 py-2.5"
          data-testid={`${testId}-role`}
        >
          <p className="text-[12.5px] font-semibold">{r.role}</p>
          <dl className="mt-2 space-y-2.5 text-[11.5px] text-muted-foreground">
            {SIGN_OFF_FIELDS.map((f) => (
              <div key={f} className="flex items-end gap-2">
                <dt className="w-[5.5rem] shrink-0">{t(`outputs.cam.signOff.${f}`)}</dt>
                <dd className="h-4 min-w-0 flex-1 border-b border-dashed border-border" />
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}

/** Present and empty (F-23.4): the headings credit completes, each with room to write. */
export function Recommendation({ m, headed = true }: { m: Cam; headed?: boolean }) {
  const prompts = m.recommendation_prompts ?? [];
  const boxes = prompts.length > 0 ? prompts : [null];
  const signOff = m.sign_off ?? [];
  return (
    <section className="min-w-0 space-y-3" data-testid="cam-recommendation">
      {headed && (
        <h3 className={heading}>
          {m.recommendation_number}. {m.recommendation_title}
        </h3>
      )}
      {(m.recommendation ?? "")
        .split("\n\n")
        .filter((p) => p.trim())
        .map((p, i) => (
          <p key={i} className="text-[13px] leading-relaxed" data-testid="cam-recommendation-text">
            {p}
          </p>
        ))}
      {boxes.map((prompt, i) => (
        <div key={i} data-testid="cam-recommendation-prompt">
          {prompt && <p className="text-[12.5px] font-medium">{prompt}</p>}
          <div
            className="mt-1 min-h-[3.5rem] rounded border border-dashed border-border px-3 py-2 text-[12.5px] text-muted-foreground"
            data-testid="cam-recommendation-box"
          >
            {t("outputs.cam.recommendationEmpty")}
          </div>
        </div>
      ))}
      {signOff.length > 0 && <SignOff roles={signOff} testId="cam-sign-off" />}
    </section>
  );
}

/** The whole memo, top to bottom, as the downloads lay it out. */
export function CamMemo({ caseId, m }: { caseId: string; m: Cam }) {
  return (
    <SourcesContext.Provider value={sourcesById(m.sources ?? [])}>
      <article
        className="mx-auto max-w-4xl space-y-6 rounded border border-border bg-surface px-4 py-5 sm:px-6"
        data-testid="cam"
      >
        <CamHeader caseId={caseId} m={m} />
        {m.sections.map((s) => (
          <MemoSection key={s.id} caseId={caseId} section={s} />
        ))}
        <Summary caseId={caseId} m={m} />
        <Recommendation m={m} />
        <Sources caseId={caseId} sources={m.sources ?? []} />
      </article>
    </SourcesContext.Provider>
  );
}

export function CamView({ caseId }: { caseId: string }) {
  const cam = useCam(caseId);
  return (
    <QueryView query={cam}>
      {(m) => (
        <SourcesContext.Provider value={sourcesById(m.sources ?? [])}>
          <article
            className="mx-auto max-w-4xl space-y-6 rounded border border-border bg-surface px-4 py-5 sm:px-6"
            data-testid="cam"
          >
            <CamHeader caseId={caseId} m={m} />
            {m.sections.map((s) => (
              <MemoSection key={s.id} caseId={caseId} section={s} />
            ))}
            <Summary caseId={caseId} m={m} />
            <Recommendation m={m} />
            <Sources caseId={caseId} sources={m.sources ?? []} />
          </article>
        </SourcesContext.Provider>
      )}
    </QueryView>
  );
}

// --- PD note ---

function PdHeader({ caseId, n }: { caseId: string; n: PdNote }) {
  const version = configLabel(n);
  // The header facts as the engine composes them; from an engine that sends none, the note's own.
  const facts: CamFact[] =
    (n.header ?? []).length > 0
      ? (n.header ?? [])
      : [
          { label: t("outputs.pd.header.borrower"), value: { text: n.borrower } },
          { label: t("outputs.pd.header.case"), value: { text: n.case_id } },
          { label: t("outputs.pd.header.asOf"), value: { text: formatDay(n.as_of) } },
          { label: t("outputs.pd.header.config"), value: { text: version } },
        ];
  const asked = n.questions.length;
  return (
    <header className="space-y-3 border-b border-border pb-3" data-testid="pd-header">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <p className="field-label">{t("outputs.pd.eyebrow")}</p>
          <h2 className="text-[18px] font-semibold" data-testid="pd-title">
            {n.title}
          </h2>
          {asked > 0 && (
            <p className="mt-0.5 text-[12.5px] text-muted-foreground" data-testid="pd-subtitle">
              {asked === 1
                ? t("outputs.pd.subtitleOne")
                : t("outputs.pd.subtitleMany", { n: asked })}
            </p>
          )}
        </div>
        <Downloads caseId={caseId} output="pd_note" />
      </div>
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="pd-facts">
        {facts.map((f, i) => (
          <div
            key={`${f.label}-${i}`}
            className="min-w-0"
            data-testid="pd-fact"
            data-label={f.label}
          >
            <dt className="field-label">{f.label}</dt>
            {/* The configuration as people know it; the full version on hover. */}
            <dd
              className="mt-0.5 break-words text-[13px]"
              title={f.value.text === version ? n.config_version : undefined}
            >
              <Statement caseId={caseId} text={f.value} />
            </dd>
          </div>
        ))}
      </dl>
    </header>
  );
}

const PERSON_COLUMNS = ["name", "role", "din", "namedIn"] as const;

/** Whom to meet: each person with the documents that name them, cited. */
function People({ caseId, people }: { caseId: string; people: PdPerson[] }) {
  if (people.length === 0) return null;
  const stack = stackOf(PERSON_COLUMNS.length);
  const labels = PERSON_COLUMNS.map((c) => t(`outputs.pd.person.${c}`));
  return (
    <section className="min-w-0 @container" data-testid="pd-people">
      <h3 className={heading}>{t("outputs.pd.people")}</h3>
      <div className="mt-1.5 overflow-x-auto">
        <table className={cn("w-full text-[12.5px]", stack?.table)}>
          <thead className={stack?.head}>
            <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
              {labels.map((label) => (
                <th key={label} scope="col" className={columnHead}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className={cn("divide-y divide-border", stack?.body)}>
            {people.map((p, i) => (
              <tr key={`${p.name}-${i}`} className={stack?.row} data-testid="pd-person">
                <td className={cn(cell, "font-medium", stack?.cell)} data-label={labels[0]}>
                  <div className="min-w-0">{p.name}</div>
                </td>
                <td className={cn(cell, stack?.cell)} data-label={labels[1]}>
                  <div className="min-w-0">{p.role ?? "—"}</div>
                </td>
                <td className={cn(cell, "tabular", stack?.cell)} data-label={labels[2]}>
                  <div className="min-w-0">{p.din ?? "—"}</div>
                </td>
                <td
                  className={cn(cell, "text-muted-foreground", stack?.cell)}
                  data-label={labels[3]}
                >
                  <div className="min-w-0">
                    {(p.sources ?? []).join(", ") || "—"}
                    <Citations caseId={caseId} evidence={p.evidence ?? []} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** The record of the discussion: its date, place and who attended, left blank. */
function RecordFields({ fields }: { fields: string[] }) {
  if (fields.length === 0) return null;
  return (
    <section className="min-w-0" data-testid="pd-record">
      <h3 className={heading}>{t("outputs.pd.record")}</h3>
      <dl className="mt-2 grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {fields.map((f) => (
          <div key={f} className="flex min-w-0 items-end gap-2" data-testid="pd-record-field">
            <dt className="shrink-0 text-[12.5px] text-muted-foreground">{f}</dt>
            <dd className="h-5 min-w-16 flex-1 border-b border-dashed border-border" />
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Where a question's source is decided, opened at it: the board for a finding or a check that
 * could not run, the policy tab for a norm; for an observation, the CAM view at the section that
 * states it, or at its top where no one section does. */
function SourceLink({
  caseId,
  target,
  id,
  label,
  testId,
  section = null,
}: {
  caseId: string;
  target: PdQuestion["target"];
  /** The finding id or the norm id. */
  id: string;
  label: string;
  testId: string;
  /** For an observation: the id of the memo section that states it. */
  section?: string | null;
}) {
  const className = "font-medium text-primary hover:underline";
  if (target === "cam") {
    return (
      <Link
        to="/appraisals/$caseId/outputs"
        params={{ caseId }}
        search={{ view: "cam" }}
        {...(section ? { hash: camSectionAnchor(section) } : {})}
        className={className}
        data-testid={testId}
      >
        <Words text={label} />
      </Link>
    );
  }
  return target === "cross_verification" ? (
    <Link
      to="/appraisals/$caseId/cross-verification"
      params={{ caseId }}
      search={{ finding: id }}
      className={className}
      data-testid={testId}
    >
      <Words text={label} />
    </Link>
  ) : (
    <Link
      to="/appraisals/$caseId/policy"
      params={{ caseId }}
      search={{ norm: id }}
      className={className}
      data-testid={testId}
    >
      <Words text={label} />
    </Link>
  );
}

function Question({ caseId, q }: { caseId: string; q: PdQuestion }) {
  const also = q.also ?? [];
  // An observation's link names the draft CAM (its rule, OBS, means nothing to a reader) and opens
  // it at the section that states it, which the observation's status names ("section 9").
  const observed = q.target === "cam";
  const source = <span data-testid="pd-question-source">{t(`outputs.pd.source.${q.source}`)}</span>;
  return (
    <li
      className="flex gap-3 px-3 py-3"
      data-testid="pd-question"
      data-question={q.id}
      data-rule={q.rule}
      data-source={q.source}
    >
      <span
        className="tabular w-6 shrink-0 text-[13px] font-semibold"
        data-testid="pd-question-number"
      >
        {q.number}.
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-[13.5px] font-semibold leading-snug" data-testid="pd-question-text">
          <Words text={q.question} />
        </p>
        <p
          className="text-[12.5px] leading-relaxed text-muted-foreground"
          data-testid="pd-question-context"
        >
          <span className="font-medium text-foreground">{t("outputs.pd.why")}</span>{" "}
          <Words text={q.context} />
          <Citations caseId={caseId} evidence={q.evidence ?? []} />
        </p>
        <p className="flex flex-wrap items-center gap-2 text-[11.5px] text-muted-foreground">
          <Chip tone={SEVERITY_TONE[q.severity]}>{t(`severity.${q.severity}`)}</Chip>
          {/* An observation is a fact the memo states, not a check's result: marked apart. */}
          {q.source === "observation" ? <Chip tone="info">{source}</Chip> : source}
          <SourceLink
            caseId={caseId}
            target={q.target}
            id={q.ref}
            label={`${observed ? t("outputs.pd.cam") : (q.xv_ref ?? q.rule)} · ${q.title}`}
            testId="pd-question-link"
            section={observed ? observationSection(q.ref) : null}
          />
          {q.status && <StatusChip status={q.status} testId="pd-question-status" />}
        </p>
        {/* The other findings the same question covers, each opened at itself. */}
        {also.length > 0 && (
          <p
            className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-muted-foreground"
            data-testid="pd-question-also"
          >
            <span>{t("outputs.pd.also")}</span>
            {also.map((r) => (
              <span
                key={r.ref}
                className="inline-flex flex-wrap items-center gap-1.5"
                data-testid="pd-also"
                data-ref={r.ref}
              >
                <SourceLink
                  caseId={caseId}
                  target={q.target}
                  id={r.ref}
                  label={`${r.xv_ref ?? r.rule} · ${r.title}`}
                  testId="pd-also-link"
                />
                {r.status && <StatusChip status={r.status} testId="pd-also-status" />}
              </span>
            ))}
          </p>
        )}
      </div>
    </li>
  );
}

type Topic = { area: PdArea | null; title: string | null; questions: PdQuestion[] };

/** The note's topics in order with their questions; any question no topic lists comes last. */
function topicsOf(n: PdNote): Topic[] {
  const byId = new Map(n.questions.map((q) => [q.id, q]));
  const topics: Topic[] = (n.topics ?? [])
    .map((topic) => ({
      area: topic.area,
      title: topic.title,
      questions: topic.question_ids
        .map((id) => byId.get(id))
        .filter((q): q is PdQuestion => q !== undefined),
    }))
    .filter((topic) => topic.questions.length > 0);
  const listed = new Set(topics.flatMap((topic) => topic.questions.map((q) => q.id)));
  const rest = n.questions.filter((q) => !listed.has(q.id));
  if (rest.length > 0) topics.push({ area: null, title: null, questions: rest });
  return topics;
}

function TopicSection({ caseId, topic }: { caseId: string; topic: Topic }) {
  return (
    <section className="min-w-0" data-testid="pd-topic" data-area={topic.area ?? undefined}>
      {topic.title && (
        <h3 className={heading} data-testid="pd-topic-title">
          {topic.title}
        </h3>
      )}
      <ol className="mt-1.5 divide-y divide-border rounded border border-border">
        {topic.questions.map((q) => (
          <Question key={q.id} caseId={caseId} q={q} />
        ))}
      </ol>
    </section>
  );
}

/** Where the topics would be when nothing on file calls for a question; the rest of the note
 * (whom to meet, the record, the documents to collect, the downloads) still stands (F-25). */
function NoQuestions() {
  return (
    <section
      className="min-w-0 rounded border border-dashed border-border px-4 py-3"
      data-testid="pd-no-questions"
    >
      <p className="text-[13px] font-medium">{t("outputs.pd.emptyTitle")}</p>
      <p className="mt-0.5 text-[12.5px] text-muted-foreground">
        {t("outputs.pd.emptyDescription")}
      </p>
    </section>
  );
}

function DocumentsToCollect({ caseId, documents }: { caseId: string; documents: CamText[] }) {
  if (documents.length === 0) return null;
  return (
    <section className="min-w-0" data-testid="pd-documents">
      <h3 className={heading}>{t("outputs.pd.documents")}</h3>
      <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[13px] leading-relaxed">
        {documents.map((d, i) => (
          <li key={i} data-testid="pd-document">
            <Statement caseId={caseId} text={d} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function PdNoteView({ caseId }: { caseId: string }) {
  const note = usePdNote(caseId);
  return (
    <QueryView query={note}>
      {(n) => {
        const topics = topicsOf(n);
        const signOff = n.sign_off ?? [];
        return (
          <SourcesContext.Provider value={sourcesById(n.sources ?? [])}>
            <article
              className="mx-auto max-w-4xl space-y-6 rounded border border-border bg-surface px-4 py-5 sm:px-6"
              data-testid="pd-note"
            >
              <PdHeader caseId={caseId} n={n} />
              <People caseId={caseId} people={n.people ?? []} />
              <RecordFields fields={n.record_fields ?? []} />
              {topics.length === 0 ? (
                <NoQuestions />
              ) : (
                topics.map((topic, i) => (
                  <TopicSection key={topic.area ?? `rest-${i}`} caseId={caseId} topic={topic} />
                ))
              )}
              <DocumentsToCollect caseId={caseId} documents={n.documents_to_collect ?? []} />
              {signOff.length > 0 && <SignOff roles={signOff} testId="pd-sign-off" />}
              <Sources caseId={caseId} sources={n.sources ?? []} />
            </article>
          </SourcesContext.Provider>
        );
      }}
    </QueryView>
  );
}
