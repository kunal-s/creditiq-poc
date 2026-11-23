import { Link } from "@tanstack/react-router";
import { Eye, FileText, Info, PencilLine } from "lucide-react";
import { useState } from "react";
import type { CellInput, CellSource, CellWorking } from "@/api/types";
import { Chip, type Tone } from "@/components/common/Panel";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatDate } from "@/domain/cases";
import { useCan } from "@/domain/session";
import { inRupees, printedAmount } from "@/domain/statementEdits";
import { cn } from "@/lib/utils";

const STATE_TONE: Record<CellWorking["state"], Tone> = {
  printed: "positive",
  nil: "muted",
  not_printed: "muted",
  edited: "flag",
  derived: "info",
  ratio: "info",
  missing: "critical",
};

// How one statement figure was arrived at, read-only: a figure is changed on the Extractions tab,
// where the Credit Manager checks each change, and everything worked from it then follows.
//
// Test ids:
//   figure-working            the whole working (data-state on figure-source)
//   figure-source             where a figure was read: figure-source-file, figure-source-line,
//                             figure-source-changed, figure-source-open, figure-source-change
//   figure-calculation        a sum or a ratio: its formula and figure-input each (data-state),
//                             figure-input-info the (i) that opens an input's source,
//                             figure-input-open the eye that opens its page
//   figure-edit-record        an edit made directly on the statement line before (read-only)
//   figure-change-hint        where a figure is changed

/** How one statement figure was arrived at: where it was read and in what unit, whether the statement
 * printed it or left it as nil, and for a sum or a ratio the figures it is worked from, each of which opens
 * its own source with the (i) beside it. Nothing is edited here. */
export function FigureWorking({ caseId, working }: { caseId: string; working: CellWorking }) {
  const own = working.state !== "derived" && working.state !== "ratio";
  return (
    <div className="space-y-2.5" data-testid="figure-working">
      <Chip tone={STATE_TONE[working.state]}>{t(`spreadPage.working.state.${working.state}`)}</Chip>
      {own && working.source && <FigureSource caseId={caseId} source={working.source} />}
      {working.edit && <EditRecord edit={working.edit} />}
      {working.formula && (
        <div className="space-y-1" data-testid="figure-calculation">
          <p className="text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
            {t("spreadPage.working.inputs")}
          </p>
          <p className="text-[12px] text-foreground">{working.formula}</p>
          {working.substituted && (
            <p className="tabular text-[12px] text-muted-foreground">= {working.substituted}</p>
          )}
          <ul className="divide-y divide-border rounded border border-border">
            {(working.inputs ?? []).map((input) => (
              <InputRow key={input.key} caseId={caseId} input={input} />
            ))}
          </ul>
        </div>
      )}
      {own && (
        <p
          className="flex items-start gap-1.5 text-[11.5px] leading-snug text-muted-foreground"
          data-testid="figure-change-hint"
        >
          <PencilLine className="mt-0.5 size-3 shrink-0" aria-hidden />
          <span>{t("spreadPage.working.changeHint")}</span>
        </p>
      )}
    </div>
  );
}

/** Where a statement figure was read: the file and page, the row and the line as printed, the unit, an
 * approved change if one is in force, and the ways to the page and to the value on the Extractions tab. */
export function FigureSource({ caseId, source }: { caseId: string; source: CellSource }) {
  const viewer = useDocViewer();
  const canMake = useCan("manual.make");
  const unit = source.unit_label ?? null;
  const file = source.file_name ?? source.document;
  return (
    <div className="space-y-1.5" data-testid="figure-source">
      <p
        className="flex items-start gap-1.5 text-[12px] font-medium text-foreground"
        data-testid="figure-source-file"
      >
        <FileText className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
        <span className="min-w-0 break-words">
          {source.page != null
            ? t("spreadPage.working.fileAt", { file, page: source.page })
            : t("spreadPage.working.file", { file })}
        </span>
      </p>
      {source.row_label && (
        <p className="text-[12px] text-muted-foreground">
          {t("spreadPage.working.row", { label: source.row_label })}
        </p>
      )}
      {source.line && (
        <div className="rounded border border-border bg-surface-muted/50 px-2.5 py-1.5">
          <p className="field-label">{t("spreadPage.working.line")}</p>
          <p
            className="tabular break-words text-[12px] text-foreground"
            data-testid="figure-source-line"
          >
            {source.line}
          </p>
        </div>
      )}
      {source.printed != null && source.printed !== "" && !source.line && (
        <p className="text-[12px] text-muted-foreground">
          {t("spreadPage.working.printed", { value: source.printed })}
        </p>
      )}
      {unit && source.printed_value != null && (
        <p className="text-[12px] text-muted-foreground">
          {t("spreadPage.working.unit", {
            unit,
            printed: printedAmount(source.printed_value),
            rupees: inRupees(source.printed_value * source.scale),
          })}
        </p>
      )}
      {source.changed && (
        <p
          className="rounded border border-flag/35 bg-flag-soft px-2.5 py-1.5 text-[12px] text-flag-foreground"
          data-testid="figure-source-changed"
        >
          {source.document_value != null
            ? t("spreadPage.working.changed", { value: printedAmount(source.document_value) })
            : t("spreadPage.working.changedNoValue")}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {source.page != null && (
          <button
            type="button"
            onClick={() =>
              viewer.open({
                caseId,
                documentId: source.document_id,
                page: source.page!,
                bbox: source.bbox ?? null,
              })
            }
            className="inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
            data-testid="figure-source-open"
          >
            <Eye className="size-3.5" aria-hidden />
            {t("spreadPage.working.open")}
          </button>
        )}
        <Link
          to="/appraisals/$caseId/extraction"
          params={{ caseId }}
          search={source.field_id ? { field: source.field_id } : {}}
          className="inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
          data-testid="figure-source-change"
        >
          <PencilLine className="size-3.5" aria-hidden />
          {t(canMake ? "spreadPage.working.change" : "spreadPage.working.see")}
        </Link>
      </div>
    </div>
  );
}

/** An edit made directly on the statement line before figures were changed on the Extractions tab only:
 * still in force, shown as it was made. */
function EditRecord({ edit }: { edit: NonNullable<CellWorking["edit"]> }) {
  return (
    <div
      className="space-y-0.5 rounded border border-flag/35 bg-flag-soft px-3 py-2 text-[12px] text-flag-foreground"
      data-testid="figure-edit-record"
    >
      <p className="font-medium">
        {t("spreadPage.working.editedBy", {
          name: edit.edited_by,
          date: formatDate(edit.edited_at),
        })}
      </p>
      <p>{t("spreadPage.working.reason", { reason: edit.reason })}</p>
      <p>
        {edit.original === null || edit.original === undefined
          ? t("spreadPage.working.originalNone")
          : t("spreadPage.working.original", { value: printedAmount(edit.original) })}
      </p>
    </div>
  );
}

/** One figure a sum or a ratio is worked from: its value, how it came about, and the (i) that opens where
 * it was read; a figure that is itself a sum lists the figures it adds beneath it. */
function InputRow({
  caseId,
  input,
  depth = 0,
}: {
  caseId: string;
  input: CellInput;
  depth?: number;
}) {
  const [open, setOpen] = useState(false);
  const viewer = useDocViewer();
  const pad = { paddingLeft: `${0.625 + depth * 0.9}rem` };
  const page = input.source?.page ?? null;
  return (
    <li data-testid="figure-input" data-state={input.state}>
      <div className="px-2.5 py-1.5 text-[12px]" style={pad}>
        <div className="flex items-baseline gap-2">
          <span className="min-w-0 flex-1 break-words text-foreground">
            {input.sign < 0 ? "− " : ""}
            {input.label}
          </span>
          <span className="tabular shrink-0 text-foreground">
            {input.value === null || input.value === undefined ? "—" : inRupees(input.value)}
          </span>
          {input.source && page != null && (
            <button
              type="button"
              onClick={() =>
                viewer.open({
                  caseId,
                  documentId: input.source!.document_id,
                  page,
                  bbox: input.source!.bbox ?? null,
                })
              }
              aria-label={t("spreadPage.working.openInput", { label: input.label, page })}
              title={t("spreadPage.working.openInput", { label: input.label, page })}
              className="shrink-0 self-center text-muted-foreground transition-colors hover:text-primary"
              data-testid="figure-input-open"
            >
              <Eye className="size-3.5" aria-hidden />
            </button>
          )}
          {input.source && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              aria-label={t(
                open ? "spreadPage.working.hideSource" : "spreadPage.working.showSource",
                { label: input.label },
              )}
              title={t("spreadPage.working.showSource", { label: input.label })}
              className={cn(
                "shrink-0 self-center text-muted-foreground transition-colors hover:text-primary",
                open && "text-primary",
              )}
              data-testid="figure-input-info"
            >
              <Info className="size-3.5" aria-hidden />
            </button>
          )}
        </div>
        {/* How the figure came about, under its name, when it is not simply printed. */}
        {input.state !== "printed" && (
          <p
            className={cn(
              "text-[10.5px] leading-snug",
              input.state === "edited"
                ? "font-semibold text-flag-foreground"
                : "text-muted-foreground",
            )}
            data-testid="figure-input-state"
          >
            {t(`spreadPage.working.state.${input.state}`)}
          </p>
        )}
        {input.state === "printed" && input.source?.changed && (
          <p
            className="text-[10.5px] font-semibold leading-snug text-flag-foreground"
            data-testid="figure-input-state"
          >
            {t("spreadPage.working.changedNoValue")}
          </p>
        )}
      </div>
      {open && input.source && (
        <div className="px-2.5 pb-2" style={pad} data-testid="figure-input-source">
          <FigureSource caseId={caseId} source={input.source} />
        </div>
      )}
      {input.edit && (
        <p className="px-2.5 pb-1.5 text-[11px] text-flag-foreground" style={pad}>
          {t("spreadPage.working.editedBy", {
            name: input.edit.edited_by,
            date: formatDate(input.edit.edited_at),
          })}
          {". "}
          {t("spreadPage.working.reason", { reason: input.edit.reason })}
        </p>
      )}
      {(input.parts ?? []).length > 0 && (
        <ul>
          {(input.parts ?? []).map((p) => (
            <InputRow key={p.key} caseId={caseId} input={p} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}
