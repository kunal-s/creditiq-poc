import { Undo2 } from "lucide-react";
import type { ReactNode } from "react";
import { Switch } from "@/components/ui/switch";
import { t } from "@/config/terminology";
import type { Editor, FieldState } from "@/domain/settings";
import { cn } from "@/lib/utils";

// The controls of the Settings screen (F-00.6). A changed field is marked, with the value in force
// and a way back to it; without config.publish each shows the value in force as text.

const control =
  "h-7 rounded border border-border bg-surface text-[12.5px] outline-none focus:border-primary/60 focus:ring-1 focus:ring-ring";
const changedControl = "border-flag bg-flag-soft";
const invalidControl = "border-destructive bg-destructive/5";

function ReadOnly({ field, children }: { field: string; children: ReactNode }) {
  return (
    <span className="tabular text-[12.5px]" data-testid={`setting-${field}`}>
      {children}
    </span>
  );
}

/** A field's control, and once changed, the value in force and a way back to it. */
function Field({
  edit,
  field,
  label,
  was,
  state,
  invalid = t("admin.settings.invalid.number"),
  children,
}: {
  edit: Editor;
  field: string;
  label: string;
  was: string;
  state: FieldState;
  /** What to enter instead of a value that cannot be taken. */
  invalid?: string;
  children: ReactNode;
}) {
  return (
    <div
      className="flex min-w-0 flex-col items-start gap-0.5"
      data-testid={`setting-${field}`}
      data-changed={state.changed ? "true" : "false"}
    >
      {children}
      {state.invalid && <span className="text-[11px] text-destructive">{invalid}</span>}
      {state.changed && (
        <span className="inline-flex items-center gap-1 text-[11px] text-flag-foreground">
          <span data-testid="setting-was">{t("admin.settings.was", { value: was })}</span>
          <button
            type="button"
            onClick={() => edit.undo(field)}
            aria-label={t("admin.settings.undo", { label })}
            title={t("admin.settings.undo", { label })}
            className="rounded p-0.5 hover:bg-flag-soft"
            data-testid="setting-undo"
          >
            <Undo2 className="h-3 w-3" />
          </button>
        </span>
      )}
    </div>
  );
}

/** An amount, typed as text and checked only for being a number; the engine checks the rest. */
export function NumberSetting({
  edit,
  field,
  label,
  was,
  unit,
  prefix,
  kind = "number",
}: {
  edit: Editor;
  field: string;
  label: string;
  /** The value in force, with its unit. */
  was: string;
  unit?: string;
  prefix?: string;
  /** A count is a whole number, 0 or more; an amount is above 0. */
  kind?: "number" | "count" | "amount";
}) {
  if (edit.readOnly) {
    return (
      <ReadOnly field={field}>
        {prefix ? `${prefix} ` : ""}
        {was}
      </ReadOnly>
    );
  }
  const state = edit.state(field);
  return (
    <Field
      edit={edit}
      field={field}
      label={label}
      was={was}
      state={state}
      invalid={t(`admin.settings.invalid.${kind}`)}
    >
      <span className="inline-flex items-center gap-1.5">
        {prefix && <span className="text-[11.5px] text-muted-foreground">{prefix}</span>}
        <input
          type="text"
          inputMode={kind === "count" ? "numeric" : "decimal"}
          aria-label={label}
          aria-invalid={state.invalid || undefined}
          value={String(state.value)}
          onChange={(e) => edit.set(field, e.target.value)}
          className={cn(
            control,
            "w-20 px-2 text-right tabular",
            state.changed && changedControl,
            state.invalid && invalidControl,
          )}
        />
        {unit && <span className="text-[11.5px] text-muted-foreground">{unit}</span>}
      </span>
    </Field>
  );
}

/** One of a list of values (a severity, an authority). */
export function ChoiceSetting({
  edit,
  field,
  label,
  was,
  options,
}: {
  edit: Editor;
  field: string;
  label: string;
  was: string;
  options: { value: string; label: string }[];
}) {
  if (edit.readOnly) return <ReadOnly field={field}>{was}</ReadOnly>;
  const state = edit.state(field);
  return (
    <Field edit={edit} field={field} label={label} was={was} state={state}>
      <select
        aria-label={label}
        value={String(state.value)}
        onChange={(e) => edit.set(field, e.target.value)}
        className={cn(control, "max-w-full px-1.5", state.changed && changedControl)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

/** On or off, as a switch with its state in words beside it. */
export function SwitchSetting({
  edit,
  field,
  label,
  was,
  on,
  off,
}: {
  edit: Editor;
  field: string;
  label: string;
  was: string;
  on: string;
  off: string;
}) {
  if (edit.readOnly) return <ReadOnly field={field}>{was}</ReadOnly>;
  const state = edit.state(field);
  return (
    <Field edit={edit} field={field} label={label} was={was} state={state}>
      <span className="inline-flex items-center gap-1.5">
        <Switch
          checked={state.value === true}
          onCheckedChange={(checked) => edit.set(field, checked)}
          aria-label={label}
          className={cn(state.changed && "ring-2 ring-flag ring-offset-1")}
        />
        <span className="text-[12px]">{state.value === true ? on : off}</span>
      </span>
    </Field>
  );
}

/** Yes or no, as a checkbox under a column that names it. */
export function CheckboxSetting({
  edit,
  field,
  label,
  was,
}: {
  edit: Editor;
  field: string;
  label: string;
  was: string;
}) {
  if (edit.readOnly) return <ReadOnly field={field}>{was}</ReadOnly>;
  const state = edit.state(field);
  return (
    <Field edit={edit} field={field} label={label} was={was} state={state}>
      <label
        className={cn(
          "inline-flex cursor-pointer items-center gap-1.5 rounded border border-transparent px-1 py-0.5 text-[12px]",
          state.changed && changedControl,
        )}
      >
        <input
          type="checkbox"
          checked={state.value === true}
          onChange={(e) => edit.set(field, e.target.checked)}
          className="h-3.5 w-3.5 accent-primary"
        />
        <span className="sr-only">{label}</span>
      </label>
    </Field>
  );
}
