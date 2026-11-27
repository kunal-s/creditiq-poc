// Test ids: rows-<section>, row-<section> (data-row = its number), add-<section>,
// remove-row, cell-<field>, cell-source.
import { Plus } from "lucide-react";
import { useId, type ReactNode } from "react";
import type { IntakeField, IntakeSection, Meta } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { t, tOr } from "@/config/terminology";
import {
  addRow,
  cellSource,
  removeRow,
  setCell,
  visibleFields,
  type Draft,
  type Row,
} from "@/domain/intake";
import { FieldEditor } from "./FieldEditor";
import { fieldLabel, rowLabel } from "./labels";

/** A repeating section of the application form (applicants, properties, facility lines, existing
 * loans …): one card per row, its fields in a grid that folds to one column on a phone, with the
 * section's add and remove buttons inside its configured minimum and maximum. A value read from
 * the message or typed at the start carries that source; anything else is the person's. */
export function RepeatingGroup({
  section,
  draft,
  meta,
  onChange,
  rowTitle = (_row, i) => rowLabel(section.id, i + 1),
  fieldProps = () => ({}),
  footer,
}: {
  section: IntakeSection;
  draft: Draft;
  meta: Meta;
  onChange: (draft: Draft) => void;
  rowTitle?: (row: Row, index: number) => string;
  /** Extra props for one field of a row (the names a `parties` field chooses from). */
  fieldProps?: (field: IntakeField, row: Row) => { parties?: string[]; holderLifted?: boolean };
  footer?: ReactNode;
}) {
  const rows = draft.groups[section.id] ?? [];
  const min = section.repeat?.["min"] ?? 0;
  const max = section.repeat?.["max"] ?? 1;
  const fields = visibleFields(section, draft.values);
  const help = tOr(`intake.sectionHelp.${section.id}`, "");
  return (
    <Panel
      title={`${tOr(`intake.section.${section.id}`, section.id)}${min > 0 ? " *" : ""}`}
      subtitle={help || undefined}
      testId={`rows-${section.id}`}
    >
      <div className="space-y-2 px-4 py-3">
        {rows.length === 0 && (
          <p className="text-[12px] text-muted-foreground">
            {tOr(`intake.empty.${section.id}`, t("intake.empty.other"))}
          </p>
        )}
        {rows.length > 0 && (
          <ol className="space-y-2">
            {rows.map((row, i) => {
              const title = rowTitle(row, i);
              return (
                <li
                  key={row.key}
                  data-testid={`row-${section.id}`}
                  data-row={i + 1}
                  className="@container/row rounded border border-border"
                >
                  <div className="flex items-center justify-between gap-2 border-b border-border/70 bg-surface-muted/60 px-3 py-1">
                    <p className="text-[12px] font-semibold text-foreground">{title}</p>
                    {rows.length > min && (
                      <button
                        type="button"
                        data-testid="remove-row"
                        aria-label={t("intake.remove", { row: title })}
                        onClick={() => onChange(removeRow(draft, section.id, row.key))}
                        className="rounded px-1.5 py-0.5 text-[11.5px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        {t("intake.removeShort")}
                      </button>
                    )}
                  </div>
                  <div className="grid gap-x-3 gap-y-2 px-3 py-2 @min-[30rem]/row:grid-cols-2 @min-[52rem]/row:grid-cols-4">
                    {fields.map((field) => (
                      <RowCell
                        key={field.id}
                        field={field}
                        row={row}
                        extra={fieldProps(field, row)}
                        title={title}
                        onChange={(value) =>
                          onChange(setCell(draft, section.id, row.key, field.id, value))
                        }
                      />
                    ))}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
        {footer}
        {rows.length < max && (
          <button
            type="button"
            data-testid={`add-${section.id}`}
            onClick={() => onChange(addRow(meta, draft, section.id))}
            className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-[12px] font-medium text-primary hover:bg-accent"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
            {tOr(`intake.add.${section.id}`, t("intake.add.other"))}
          </button>
        )}
      </div>
    </Panel>
  );
}

function RowCell({
  field,
  row,
  extra,
  title,
  onChange,
}: {
  field: IntakeField;
  row: Row;
  /** The row's name, for each field's accessible name ("Co-applicant 1 – PAN"). */
  title: string;
  extra: { parties?: string[]; holderLifted?: boolean };
  onChange: (value: string) => void;
}) {
  const cell = row.cells[field.id];
  const inputId = useId();
  const kind = (cellSource(cell) ?? "person").split(":")[0];
  return (
    <div className="min-w-0" data-testid={`cell-${field.id}`}>
      <div className="flex min-h-5 flex-wrap items-center justify-between gap-x-1.5">
        <label htmlFor={inputId} className="field-label">
          {fieldLabel(field.id)}
          {field.required && (
            <span className="text-critical-text" aria-hidden>
              {" "}
              *
            </span>
          )}
        </label>
        {kind !== "person" && (
          <Chip tone="muted">
            <span data-testid="cell-source">{tOr(`intake.source.${kind}`, kind ?? "")}</span>
          </Chip>
        )}
      </div>
      <FieldEditor
        field={field}
        value={cell?.value ?? ""}
        onChange={onChange}
        id={inputId}
        label={t("intake.rowField", { row: title, field: fieldLabel(field.id) })}
        {...extra}
      />
    </div>
  );
}
