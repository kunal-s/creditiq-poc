import { Fragment, useState } from "react";
import { ArrowRight, CheckCircle2, ChevronRight, Eye, PencilLine } from "lucide-react";
import type { FieldStatus, FieldValue, LogicalDocument } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { Details } from "@/components/common/Details";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { FieldValueButton } from "@/components/common/FieldValueButton";
import { AverageConfidence } from "@/components/common/ConfidenceChip";
import { GradeChip } from "@/components/documents/chips";
import { FieldStatusCell, PendingChangeRow } from "@/components/review/FigureEdit";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import {
  instanceLabel,
  pageRange,
  useCaseDocuments,
  useCaseFiles,
  useDocumentTypes,
} from "@/domain/documents";
import {
  fieldLabel,
  formatValue,
  effectiveValue,
  groupFields,
  useFields,
  type FieldTable,
} from "@/domain/extraction";
import { usePendingChanges } from "@/domain/figureEdits";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { StackTable } from "@/components/common/StackTable";

/** "awaiting": figures changed by a person and waiting for their check (figureEdits.ts). */
const FILTERS = ["all", "in_review", "awaiting", "missing", "corrected"] as const;

/** The FRD §6 grouping of extracted data, from each document type's group. */
const FIELD_SECTIONS = ["identity", "financials", "tax", "banking", "other"] as const;
type FieldSection = (typeof FIELD_SECTIONS)[number];
const SECTION_OF_GROUP: Record<string, FieldSection> = {
  constitution: "identity",
  registration: "identity",
  kyc: "identity",
  financials: "financials",
  working_capital: "financials",
  tax: "tax",
  banking: "banking",
};

function sectionOf(
  doc: LogicalDocument,
  byId: (id: string) => { group?: string } | undefined,
): FieldSection {
  const group = byId(doc.classification?.types[0] ?? "")?.group;
  return (group && SECTION_OF_GROUP[group]) || "other";
}
type Filter = (typeof FILTERS)[number];

/** The table row a cell belongs to ("<document>:<table>[<row>]"), or null for a plain field. */
function tableRowOf(f: FieldValue): string | null {
  const m = f.field.match(/^(\w+\[\d+\])\./);
  return m ? `${f.document_id}:${m[1]}` : null;
}

/** Extracted fields by document, with confidence and page (F-15, F-16). A figure on a financial
 * statement can be changed by the Credit Analyst and is checked by the Credit Manager. */
export function ExtractedDataSection({ caseId }: { caseId: string }) {
  const fields = useFields(caseId);
  const documents = useCaseDocuments(caseId);
  const pending = usePendingChanges(caseId);
  const checker = useCan("manual.check");
  // The page opens on what needs checking; the reader's own choice of filter wins once made.
  const [chosen, setFilter] = useState<Filter | null>(null);
  const types = useDocumentTypes();

  if (fields.isError || documents.isError) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <ErrorState error={fields.error ?? documents.error} onRetry={() => void fields.refetch()} />
      </div>
    );
  }
  if (!fields.data || !documents.data) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <LoadingBlock />
      </div>
    );
  }
  const all = fields.data;
  const count = (s: FieldStatus) => all.filter((f) => f.status === s).length;
  const awaiting = all.filter((f) => pending.has(f.id)).length;
  // A checker opens on the changes waiting for them; everyone else on what the reading left to check.
  const filter: Filter =
    chosen ??
    (checker && awaiting > 0
      ? "awaiting"
      : count("in_review") > 0
        ? "in_review"
        : awaiting > 0
          ? "awaiting"
          : "all");
  // Nothing to check and nothing chosen: each document is one folded row, opened on request.
  const folded = chosen === null && filter === "all";
  const matches = (f: FieldValue) =>
    filter === "all" ? true : filter === "awaiting" ? pending.has(f.id) : f.status === filter;
  // A table cell that matches brings its whole row, so the row still says what the line is.
  const rowsShown = new Set(all.filter(matches).map(tableRowOf));
  const shown = all.filter(
    (f) => matches(f) || (tableRowOf(f) !== null && rowsShown.has(tableRowOf(f))),
  );
  const filters = FILTERS.filter((f) => f !== "awaiting" || awaiting > 0 || filter === f);
  const groups = documents.data
    .map((doc) => ({ doc, fields: shown.filter((f) => f.document_id === doc.id) }))
    .filter((g) => g.fields.length > 0);

  return (
    <div className="grid gap-4 px-4 py-5 sm:px-6 @min-[49rem]/main:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-4">
        <div className="flex flex-wrap gap-1" role="group" aria-label={t("data.filter")}>
          {filters.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              data-testid={`data-filter-${f}`}
              className={cn(
                "rounded border px-2 py-1 text-[11.5px] transition-colors",
                filter === f
                  ? "border-primary/50 bg-primary/10 font-medium text-primary"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
            >
              {f === "all"
                ? t("data.filterAll")
                : f === "awaiting"
                  ? `${t("figureEdit.filter")} · ${awaiting}`
                  : t(`fieldStatus.${f}`)}
            </button>
          ))}
        </div>
        {folded && all.length > 0 && (
          <p
            className="flex items-center gap-2 rounded border border-border bg-surface px-4 py-2.5 text-[12.5px] text-foreground"
            data-testid="data-nothing-to-check"
          >
            <CheckCircle2 className="size-4 shrink-0 text-positive" aria-hidden />
            {t("data.nothingToCheck")}
          </p>
        )}
        {all.length === 0 ? (
          <Panel title={t("page.data.title")}>
            <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
              {t("data.none")}
            </p>
          </Panel>
        ) : groups.length === 0 ? (
          <Panel title={t("page.data.title")}>
            <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
              {t("data.noneMatch")}
            </p>
          </Panel>
        ) : (
          FIELD_SECTIONS.map((section) => {
            const members = groups.filter((g) => sectionOf(g.doc, types.byId) === section);
            if (members.length === 0) return null;
            return (
              <section key={section} className="space-y-3" data-testid={`field-section-${section}`}>
                <h3 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t(`fieldSection.${section}`)}
                </h3>
                {members.map((g) => (
                  <DocumentFields
                    key={`${g.doc.id}-${folded ? "folded" : filter}`}
                    caseId={caseId}
                    doc={g.doc}
                    fields={g.fields}
                    folded={folded}
                    filtered={filter !== "all"}
                    editable={section === "financials"}
                  />
                ))}
              </section>
            );
          })
        )}
      </div>

      <div className="order-first min-w-0 space-y-3 @min-[49rem]/main:order-none">
        <Panel title={t("data.summary")} testId="data-summary">
          <div className="grid grid-cols-2 divide-x divide-border border-b border-border">
            <div className="px-4 py-3">
              <p className="text-[22px] font-semibold tabular-nums text-foreground">{all.length}</p>
              <p className="text-[11.5px] text-muted-foreground">{t("data.fields")}</p>
            </div>
            <div className="px-4 py-3">
              <p className="text-[22px] font-semibold tabular-nums text-flag-foreground">
                {count("in_review")}
              </p>
              <p className="text-[11.5px] text-muted-foreground">{t("fieldStatus.in_review")}</p>
            </div>
          </div>
          <dl className="divide-y divide-border text-[12.5px]">
            {(["accepted", "corrected", "missing", "rejected"] as const).map((s) => (
              <div key={s} className="flex justify-between gap-3 px-4 py-2">
                <dt className="text-muted-foreground">{t(`fieldStatus.${s}`)}</dt>
                <dd className="tabular-nums">{count(s)}</dd>
              </div>
            ))}
            {awaiting > 0 && (
              <div className="flex justify-between gap-3 px-4 py-2" data-testid="data-awaiting">
                <dt className="text-muted-foreground">{t("figureEdit.summaryAwaiting")}</dt>
                <dd className="tabular-nums text-flag-foreground">{awaiting}</dd>
              </div>
            )}
          </dl>
          {awaiting > 0 && filter !== "awaiting" && (
            <div className="border-t border-border px-4 py-3">
              <button
                type="button"
                onClick={() => setFilter("awaiting")}
                className="flex h-8 w-full items-center justify-center gap-1.5 rounded border border-border bg-surface text-[12.5px] font-medium text-foreground hover:bg-muted"
                data-testid="show-awaiting"
              >
                {t("figureEdit.showAwaiting", { n: awaiting })}
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
          {count("in_review") > 0 && filter !== "in_review" && (
            <div className="border-t border-border px-4 py-3">
              <button
                type="button"
                onClick={() => setFilter("in_review")}
                className="flex h-8 w-full items-center justify-center gap-1.5 rounded border border-border bg-surface text-[12.5px] font-medium text-foreground hover:bg-muted"
                data-testid="show-in-review"
              >
                {t("data.showInReview", { n: count("in_review") })}
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function DocumentFields({
  caseId,
  doc,
  fields,
  folded = false,
  filtered = false,
  editable = false,
}: {
  caseId: string;
  doc: LogicalDocument;
  fields: FieldValue[];
  /** Shown as one row (its counts), its fields on request. */
  folded?: boolean;
  /** The page shows one status only: its tables open on what it shows. */
  filtered?: boolean;
  /** A financial statement: its figures can be changed by a maker, for a checker. */
  editable?: boolean;
}) {
  const [open, setOpen] = useState(!folded);
  const types = useDocumentTypes();
  const files = useCaseFiles(caseId);
  const viewer = useDocViewer();
  const pending = usePendingChanges(caseId);
  const canMake = useCan("manual.make");
  const file = files.data?.find((f) => f.id === doc.file_id);
  const { plain: all, tables } = groupFields(fields);
  // Fields the document does not carry are counted, and listed only when asked for.
  const [showMissing, setShowMissing] = useState(false);
  const notFound = all.filter((f) => f.status === "missing");
  // Under the "Not found" filter every field shown is one of them: they are listed.
  const onlyMissing = notFound.length === all.length;
  const plain = showMissing || onlyMissing ? all : all.filter((f) => f.status !== "missing");
  const title = doc.classification?.types.length
    ? doc.classification.types.map(types.name).join(" + ")
    : t("document.unclassified");

  return (
    <Panel
      title={title}
      testId="field-group"
      subtitle={
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <span className="break-all">{file?.original_name}</span>
          <span>· {pageRange(doc)}</span>
          {instanceLabel(doc.instance_key) && <span>· {instanceLabel(doc.instance_key)}</span>}
        </span>
      }
      action={
        <span className="flex flex-wrap items-center gap-2">
          {!open && (
            <span className="text-[11.5px] text-muted-foreground" data-testid="field-group-counts">
              {t("data.groupCounts", { n: all.length - notFound.length, missing: notFound.length })}
            </span>
          )}
          <AverageConfidence fields={fields} />
          {(doc.grade === "C" || doc.grade === "U") && <GradeChip grade={doc.grade} />}
          <button
            type="button"
            onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
            className="inline-flex items-center gap-1 rounded border border-border px-2 py-0.5 text-[11.5px] font-medium text-primary hover:bg-muted"
          >
            <Eye className="h-3 w-3" /> {t("validation.openDocument")}
          </button>
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11.5px] font-medium text-primary hover:bg-muted"
            data-testid="field-group-toggle"
          >
            <ChevronRight
              className={cn("h-3 w-3 transition-transform", open && "rotate-90")}
              aria-hidden
            />
            {open ? t("data.hideFields") : t("data.showFields")}
          </button>
        </span>
      }
    >
      {open && (
        <>
          {/* A financial statement's values, its tables' figures among them, are changed here. */}
          {editable && canMake && (
            <p
              className="flex items-center gap-1.5 border-b border-border px-4 py-2 text-[12px] text-muted-foreground"
              data-testid="figure-edit-hint"
            >
              <PencilLine className="size-3 shrink-0" aria-hidden />
              {t("figureEdit.hint")}
            </p>
          )}
          {plain.length > 0 && (
            <div className="overflow-x-auto">
              <StackTable className="field-cards w-full min-w-[480px] table-fixed text-[12.5px]">
                <thead>
                  {/* Fixed widths: the columns line up from one document's table to the next. */}
                  <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
                    <th className="w-[32%] px-4 py-2 font-medium">{t("data.col.field")}</th>
                    <th className="w-[40%] px-3 py-2 font-medium">{t("data.col.value")}</th>
                    <th className="px-4 py-2 font-medium">{t("data.col.status")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {plain.map((f) => {
                    // A change awaiting its check reads across the row's width, just below it.
                    const change = pending.get(f.id);
                    return (
                      <Fragment key={f.id}>
                        <tr
                          className={cn("align-top", change && "border-b-0")}
                          data-testid="field-row"
                        >
                          <td className="px-4 py-2 text-muted-foreground">{fieldLabel(f.field)}</td>
                          <td className="px-3 py-2">
                            <FieldValueButton caseId={caseId} field={f} />
                          </td>
                          <td className="px-4 py-2">
                            <FieldStatusCell field={f} editable={editable} changeBelow />
                          </td>
                        </tr>
                        {change && (
                          <tr data-testid="figure-edit-row">
                            <td colSpan={3} className="px-4 pb-3 pt-0">
                              <PendingChangeRow item={change} field={f} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </StackTable>
            </div>
          )}
          {notFound.length > 0 && !onlyMissing && (
            <button
              type="button"
              aria-expanded={showMissing}
              onClick={() => setShowMissing((v) => !v)}
              className="flex w-full items-center gap-1.5 border-t border-border px-4 py-2 text-left text-[12px] text-muted-foreground hover:bg-surface-muted hover:text-foreground"
              data-testid="field-missing-toggle"
            >
              <ChevronRight
                className={cn("h-3 w-3 transition-transform", showMissing && "rotate-90")}
                aria-hidden
              />
              {showMissing
                ? t("data.hideNotFound")
                : t("data.showNotFound", { n: notFound.length })}
            </button>
          )}
          {tables.map((table) => (
            <FieldTableView
              key={table.name}
              caseId={caseId}
              table={table}
              editable={editable}
              filtered={filtered}
            />
          ))}
          <div className="border-t border-border px-4 py-3">
            <Details testId="field-details">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-left text-[10.5px] uppercase tracking-wide text-muted-foreground">
                    <th className="py-1 pr-3 font-medium">{t("data.col.field")}</th>
                    <th className="py-1 pr-3 font-medium">{t("data.readBy")}</th>
                    <th className="py-1 font-medium">{t("data.asPrinted")}</th>
                  </tr>
                </thead>
                <tbody>
                  {fields.map((f) => (
                    <tr key={f.id} className="border-t border-border align-top">
                      <td className="py-1 pr-3 text-muted-foreground">{fieldLabel(f.field)}</td>
                      <td className="py-1 pr-3">{t(`fieldMethod.${f.method}`)}</td>
                      <td className="py-1" data-testid="as-printed">
                        {f.raw && f.status !== "missing" && f.raw !== formatValue(effectiveValue(f))
                          ? f.raw
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Details>
          </div>
        </>
      )}
    </Panel>
  );
}

/** A table read from a document: one row per table row, one column per column,
 * every cell still opens its source page and carries its own confidence and
 * decision (F-16.1, F-17). */
function FieldTableView({
  caseId,
  table,
  editable,
  filtered,
}: {
  caseId: string;
  table: FieldTable;
  editable: boolean;
  filtered: boolean;
}) {
  const pending = usePendingChanges(caseId);
  const needs = table.rows.some((r) =>
    Object.values(r.cells).some((f) => f && (f.status === "in_review" || pending.has(f.id))),
  );
  // A financial statement's tables are its figures: they open with the document.
  const [open, setOpen] = useState(needs || filtered || editable);
  return (
    <div
      className="overflow-x-auto border-t border-border first:border-t-0"
      data-testid="field-table"
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-4 py-2.5 text-left text-[12px] font-semibold text-muted-foreground hover:bg-surface-muted hover:text-foreground"
        data-testid="field-table-toggle"
      >
        <ChevronRight
          className={cn("h-3 w-3 transition-transform", open && "rotate-90")}
          aria-hidden
        />
        {t("data.tableToggle", { title: table.title, n: table.rows.length })}
      </button>
      {open && (
        <table className="mt-1 w-full text-[12.5px]">
          <thead>
            <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
              <th className="px-4 py-2 font-medium">{t("data.col.row")}</th>
              {table.columns.map((c) => (
                <th key={c.key} className="px-3 py-2 font-medium">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {table.rows.map((row) => (
              <tr key={row.index} className="align-top" data-testid="field-table-row">
                <td className="tabular px-4 py-2 text-muted-foreground">{row.index + 1}</td>
                {table.columns.map((c) => {
                  const f = row.cells[c.key];
                  return (
                    <td
                      key={c.key}
                      className={cn(
                        "px-3 py-2",
                        f && (f.status === "in_review" || pending.has(f.id)) && "bg-flag-soft",
                      )}
                    >
                      {f ? (
                        // The pencil sits beside the figure; a status and a waiting change
                        // wrap below it.
                        <div className="flex flex-wrap items-center gap-x-1 gap-y-1">
                          <FieldValueButton caseId={caseId} field={f} />
                          <FieldStatusCell field={f} editable={editable} quiet />
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
