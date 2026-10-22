import { Pencil, Undo2 } from "lucide-react";
import { useState } from "react";
import type { CellInput, CellWorking } from "@/api/types";
import { Chip, type Tone } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { formatDate } from "@/domain/cases";
import { useCan } from "@/domain/session";
import { inRupees, printedAmount } from "@/domain/statementEdits";
import { cn } from "@/lib/utils";
import { EditFigureDialog, RevertFigureDialog } from "./EditFigureDialog";

const STATE_TONE: Record<CellWorking["state"], Tone> = {
  printed: "positive",
  nil: "muted",
  not_printed: "muted",
  edited: "flag",
  derived: "info",
  ratio: "info",
  missing: "critical",
};

type Editing = {
  label: string;
  target: NonNullable<CellWorking["target"]>;
  source: CellWorking["source"];
  current: number | null;
};

/** How one statement figure was arrived at: where it was read and in what unit, whether the
 * statement printed it, left it as nil or a person entered it, and for a sum or a ratio the
 * figures it is worked from, each of which can be opened and edited in turn. */
export function FigureWorking({
  caseId,
  label,
  fy,
  working,
}: {
  caseId: string;
  label: string;
  fy: string;
  working: CellWorking;
}) {
  const canEdit = useCan("review.decide");
  const [editing, setEditing] = useState<Editing | null>(null);
  const [reverting, setReverting] = useState<string | null>(null);
  const src = working.source;
  const unit = src?.unit_label ?? null;
  const edit = working.edit;
  const own: Editing | null = working.target
    ? {
        label,
        target: working.target,
        source: src,
        current: edit?.value ?? src?.printed_value ?? null,
      }
    : null;
  return (
    <div className="space-y-2.5" data-testid="figure-working">
      <Chip tone={STATE_TONE[working.state]}>{t(`spreadPage.working.state.${working.state}`)}</Chip>
      {src?.row_label && (
        <p className="text-[12px] text-muted-foreground">
          {t("spreadPage.working.row", { label: src.row_label })}
        </p>
      )}
      {src?.printed != null && src.printed !== "" && (
        <p className="text-[12px] text-muted-foreground">
          {t("spreadPage.working.printed", { value: src.printed })}
        </p>
      )}
      {unit && src?.printed_value != null && (
        <p className="text-[12px] text-muted-foreground">
          {t("spreadPage.working.unit", {
            unit,
            printed: printedAmount(src.printed_value),
            rupees: inRupees(src.printed_value * src.scale),
          })}
        </p>
      )}
      {edit && (
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
          {canEdit && (
            <button
              type="button"
              onClick={() => setReverting(edit.id)}
              className="mt-1 inline-flex items-center gap-1 font-medium text-primary hover:underline"
              data-testid="figure-revert"
            >
              <Undo2 className="h-3.5 w-3.5" aria-hidden />
              {t("spreadPage.working.revert")}
            </button>
          )}
        </div>
      )}
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
              <InputRow
                key={input.key}
                input={input}
                canEdit={canEdit}
                onEdit={setEditing}
                onRevert={setReverting}
              />
            ))}
          </ul>
        </div>
      )}
      {canEdit && own && (
        <button
          type="button"
          onClick={() => setEditing(own)}
          className="inline-flex items-center gap-1 text-[12.5px] font-medium text-primary hover:underline"
          data-testid="figure-edit"
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden />
          {t("spreadPage.working.edit")}
        </button>
      )}
      {editing && (
        <EditFigureDialog
          caseId={caseId}
          label={editing.label}
          fy={fy}
          target={editing.target}
          source={editing.source}
          current={editing.current}
          onClose={() => setEditing(null)}
        />
      )}
      {reverting && (
        <RevertFigureDialog caseId={caseId} editId={reverting} onClose={() => setReverting(null)} />
      )}
    </div>
  );
}

/** One figure a sum or a ratio is worked from, and the figures that sum is worked from in turn. */
function InputRow({
  input,
  canEdit,
  onEdit,
  onRevert,
  depth = 0,
}: {
  input: CellInput;
  canEdit: boolean;
  onEdit: (e: Editing) => void;
  onRevert: (editId: string) => void;
  depth?: number;
}) {
  return (
    <li data-testid="figure-input" data-state={input.state}>
      <div
        className="flex items-baseline gap-2 px-2.5 py-1.5 text-[12px]"
        style={{ paddingLeft: `${0.625 + depth * 0.9}rem` }}
      >
        <span className="min-w-0 flex-1 truncate text-foreground">
          {input.sign < 0 ? "− " : ""}
          {input.label}
        </span>
        <span className="tabular text-foreground">
          {input.value === null || input.value === undefined ? "—" : inRupees(input.value)}
        </span>
        <span
          className={cn(
            "text-[10.5px]",
            input.state === "edited"
              ? "font-semibold text-flag-foreground"
              : "text-muted-foreground",
          )}
        >
          {input.state === "printed" ? "" : t(`spreadPage.working.state.${input.state}`)}
        </span>
        {canEdit && input.target && (
          <button
            type="button"
            onClick={() =>
              onEdit({
                label: input.label,
                target: input.target!,
                source: input.source,
                current: input.edit?.value ?? input.source?.printed_value ?? null,
              })
            }
            aria-label={`${t("spreadPage.working.editInput")} ${input.label}`}
            className="text-muted-foreground hover:text-primary"
            data-testid="figure-input-edit"
          >
            <Pencil className="h-3 w-3" aria-hidden />
          </button>
        )}
      </div>
      {input.edit && (
        <p
          className="space-x-1.5 px-2.5 pb-1.5 text-[11px] text-flag-foreground"
          style={{ paddingLeft: `${0.625 + depth * 0.9}rem` }}
          data-testid="figure-input-edit-record"
        >
          <span>
            {t("spreadPage.working.editedBy", {
              name: input.edit.edited_by,
              date: formatDate(input.edit.edited_at),
            })}
            {". "}
            {t("spreadPage.working.reason", { reason: input.edit.reason })}
          </span>
          {canEdit && (
            <button
              type="button"
              onClick={() => onRevert(input.edit!.id)}
              className="font-medium text-primary hover:underline"
            >
              {t("spreadPage.working.revert")}
            </button>
          )}
        </p>
      )}
      {(input.parts ?? []).length > 0 && (
        <ul>
          {(input.parts ?? []).map((p) => (
            <InputRow
              key={p.key}
              input={p}
              canEdit={canEdit}
              onEdit={onEdit}
              onRevert={onRevert}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
