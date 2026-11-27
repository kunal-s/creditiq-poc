// Test ids: group-<section>, field-<id>, prefilled, typed, proposed-status, candidate,
// confirm-<id>.
import { Check } from "lucide-react";
import { useId } from "react";
import type { CaseProposal, IntakeField, Meta } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { ProposedStatusChip } from "@/components/documents/chips";
import { t, tOr } from "@/config/terminology";
import {
  isPrefilled,
  normaliseFor,
  setValue,
  settle,
  unsettled,
  type Draft,
} from "@/domain/intake";
import { cn } from "@/lib/utils";
import { FieldEditor } from "./FieldEditor";
import { fieldLabel } from "./labels";

/** A section of single values on the application form (case details, borrower, business …):
 * each field with where its value came from — read from the message (found, unclear, not found,
 * invalid, with the candidates to choose from), pre-filled (a default, the RM's branch, an
 * identifier typed at the start) or typed. Selecting a field shows its span in the message. */
export function ValuesSection({
  sectionId,
  fields,
  draft,
  proposal,
  meta,
  selected,
  onSelect,
  onChange,
}: {
  sectionId: string;
  fields: IntakeField[];
  draft: Draft;
  proposal: CaseProposal | null;
  meta: Meta;
  selected: string | null;
  onSelect: (key: string) => void;
  onChange: (draft: Draft) => void;
}) {
  const pending = unsettled(meta, proposal, draft);
  const help = tOr(`intake.sectionHelp.${sectionId}`, "");
  return (
    <Panel
      title={tOr(`intake.section.${sectionId}`, sectionId)}
      subtitle={help || undefined}
      testId={`group-${sectionId}`}
    >
      <div className="@container/fields">
        <ul className="grid gap-x-4 gap-y-1 px-2 py-2 @min-[34rem]/fields:grid-cols-2 @min-[56rem]/fields:grid-cols-3">
          {fields.map((field) => (
            <FieldCell
              key={field.id}
              field={field}
              draft={draft}
              proposal={proposal}
              needs={pending.includes(field.id)}
              selected={selected === field.id}
              onSelect={() => onSelect(field.id)}
              onChange={onChange}
            />
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function FieldCell({
  field,
  draft,
  proposal,
  needs,
  selected,
  onSelect,
  onChange,
}: {
  field: IntakeField;
  draft: Draft;
  proposal: CaseProposal | null;
  needs: boolean;
  selected: boolean;
  onSelect: () => void;
  onChange: (draft: Draft) => void;
}) {
  const key = field.id;
  const inputId = useId();
  const read = proposal?.fields[key];
  // A value typed at the start comes back in the proposal too; it is shown as an identifier.
  const f = read && !read.source ? read : null;
  const value = draft.values[key] ?? "";
  const prefilled = isPrefilled(draft, key);
  const lifted = (field.unless?.["customer_type"] ?? []).includes(
    draft.values["customer_type"] ?? "",
  );
  return (
    <li
      data-field={key}
      data-testid={`field-${key}`}
      onClick={onSelect}
      className={cn(
        "min-w-0 cursor-pointer rounded border px-2 py-1.5",
        needs
          ? "border-flag/40 bg-flag-soft/40"
          : selected
            ? "border-primary/30 bg-primary/5"
            : "border-transparent hover:bg-surface-muted/60",
      )}
    >
      <div className="flex min-h-5 flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
        <label htmlFor={inputId} className="field-label">
          {fieldLabel(key)}
          {field.required && (
            <span className="text-critical-text" aria-hidden>
              {" "}
              *
            </span>
          )}
        </label>
        <span className="flex items-center gap-1.5">
          {f && draft.settled[key] && (f.status === "unclear" || f.status === "invalid") && (
            <Chip tone="positive">
              <Check className="h-3 w-3" aria-hidden /> {t("newApplication.confirmedByYou")}
            </Chip>
          )}
          {prefilled ? (
            <Chip tone="muted">
              <span data-testid="prefilled">
                {t(`newApplication.prefilled.${draft.prefilled[key]!.source}`)}
              </span>
            </Chip>
          ) : f ? (
            <ProposedStatusChip status={f.status} />
          ) : value.trim() ? (
            <Chip tone="muted">
              <span data-testid="typed">{t("intake.typed")}</span>
            </Chip>
          ) : null}
        </span>
      </div>
      <FieldEditor
        field={field}
        value={value}
        id={inputId}
        label={fieldLabel(key)}
        holderLifted={lifted}
        onFocus={onSelect}
        onChange={(v) => onChange(setValue(draft, key, v))}
      />
      {f?.note && <p className="mt-1 text-[11.5px] text-flag-foreground">{f.note}</p>}
      {f &&
        (f.status === "unclear" || f.status === "invalid") &&
        (f.candidates ?? []).length > 0 && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-muted-foreground">
              {t("newApplication.candidates")}
            </span>
            {(f.candidates ?? []).map((c) => (
              <button
                key={`${c.span.start}-${c.value}`}
                type="button"
                data-testid="candidate"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect();
                  onChange(setValue(draft, key, normaliseFor(field, c.value), c.span));
                }}
                className="rounded border border-flag/40 bg-surface px-1.5 py-0.5 text-[11.5px] font-medium text-foreground hover:bg-flag-soft"
              >
                {candidateLabel(field, c.value)}
              </button>
            ))}
          </div>
        )}
      {needs && (
        <button
          type="button"
          data-testid={`confirm-${key}`}
          onClick={(e) => {
            e.stopPropagation();
            onChange(settle(draft, key));
          }}
          className="mt-1.5 inline-flex items-center gap-1 rounded border border-border bg-surface px-2 py-0.5 text-[11.5px] font-medium text-foreground hover:bg-muted"
        >
          <Check className="h-3 w-3" aria-hidden /> {t("newApplication.confirmValue")}
        </button>
      )}
    </li>
  );
}

/** A candidate as the RM reads it: a configured id shows its label. */
function candidateLabel(field: IntakeField, value: string): string {
  const id = normaliseFor(field, value);
  return (field.options ?? []).find((o) => o.id === id)?.label ?? value.replace(/_/g, " ");
}
