import { useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import type { IntakeField } from "@/api/types";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { cleanInput, formatHintKey, FULL_LENGTH, looksValid } from "@/domain/intake";
import { cn } from "@/lib/utils";
import { fieldLabel, inputClass, onRadioKeys, radioTabIndex } from "./labels";

/** Lists an application cannot be created without offer no empty choice. */
const ALWAYS_CHOSEN = new Set(["bank_stage", "channel"]);

const CODES = new Set(["pan", "gstin", "udyam", "cin_or_llpin"]);
const FIGURES = new Set(["amount", "months", "number", "digits", "pincode"]);

type Props = {
  field: IntakeField;
  value: string;
  onChange: (value: string) => void;
  onFocus?: () => void;
  /** The accessible name (a row's field is named with its row: "Co-applicant 1 – PAN"). */
  label?: string;
  /** The id a visible <label htmlFor> points at. */
  id?: string;
  /** For a `parties` field: the names it chooses from. */
  parties?: string[];
  /** The individual-PAN rule does not apply (a non-individual customer). */
  holderLifted?: boolean;
  showHint?: boolean;
  testId?: string;
};

/** The input for one field of the form, by its type (config/intake.yaml): a choice is a list, a
 * yes/no two radio buttons, a date a date, a `parties` field the names of another section's rows;
 * codes are typed in capitals, figures take digits only and rupees show ₹ with Indian grouping.
 * A code's format is judged once it is complete or the field is left, on a line kept for it so
 * nothing moves (the engine stays the judge). */
export function FieldEditor(props: Props) {
  const { field } = props;
  if (field.type === "choice") return <ChoiceInput {...props} />;
  if (field.type === "yes_no") return <YesNoInput {...props} />;
  if (field.type === "parties") return <PartiesInput {...props} />;
  if (field.type === "amount") return <AmountInput {...props} />;
  return <TextInput {...props} />;
}

const stop = (e: { stopPropagation: () => void }) => e.stopPropagation();

function ChoiceInput({ field, value, onChange, onFocus, label, id, testId }: Props) {
  const options = (field.options ?? []).filter((o) => o.id !== "unknown");
  return (
    <select
      id={id}
      aria-label={label ?? fieldLabel(field.id)}
      aria-required={field.required || undefined}
      className={inputClass}
      value={value}
      onFocus={onFocus}
      onClick={stop}
      onChange={(e) => onChange(e.target.value)}
      data-testid={testId}
    >
      {!ALWAYS_CHOSEN.has(field.id) || value === "" ? (
        <option value="">{t("term.notConfirmed")}</option>
      ) : null}
      {options.map((o) => (
        <option key={o.id} value={o.id}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function YesNoInput({ field, value, onChange, onFocus, label, testId }: Props) {
  const answers = ["yes", "no"] as const;
  return (
    <div
      className="mt-1 flex gap-1.5"
      role="radiogroup"
      aria-label={label ?? fieldLabel(field.id)}
      aria-required={field.required || undefined}
      onKeyDown={onRadioKeys}
      data-testid={testId}
    >
      {answers.map((answer, i) => (
        <button
          key={answer}
          type="button"
          role="radio"
          aria-checked={value === answer}
          tabIndex={radioTabIndex(value === answer, i, value !== "")}
          onClick={(e) => {
            stop(e);
            onFocus?.();
            onChange(value === answer ? "" : answer);
          }}
          className={cn(
            "h-8 min-w-14 rounded border px-2.5 text-[12px] font-medium",
            value === answer
              ? "border-primary bg-accent text-primary"
              : "border-border bg-surface text-muted-foreground hover:bg-muted",
          )}
        >
          {t(`intake.answer.${answer}`)}
        </button>
      ))}
    </div>
  );
}

function PartiesInput({ field, value, onChange, label, parties = [], testId }: Props) {
  const chosen = value
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
  if (parties.length === 0)
    return <p className="mt-1 text-[11.5px] text-muted-foreground">{t("intake.ownersNone")}</p>;
  return (
    <div
      className="mt-1 flex flex-wrap gap-1.5"
      role="group"
      aria-label={label ?? fieldLabel(field.id)}
      data-testid={testId}
    >
      {parties.map((name) => {
        const on = chosen.includes(name);
        return (
          <button
            key={name}
            type="button"
            aria-pressed={on}
            onClick={(e) => {
              stop(e);
              onChange((on ? chosen.filter((n) => n !== name) : [...chosen, name]).join("; "));
            }}
            className={cn(
              "rounded border px-2 py-0.5 text-[11.5px]",
              on
                ? "border-primary/50 bg-primary/10 font-medium text-primary"
                : "border-border text-muted-foreground hover:bg-muted",
            )}
          >
            {name}
          </button>
        );
      })}
    </div>
  );
}

function TextInput({
  field,
  value,
  onChange,
  onFocus,
  label,
  id,
  holderLifted = false,
  showHint = false,
  testId,
}: Props) {
  const noteId = useId();
  const [left, setLeft] = useState(false);
  // Aadhaar is kept as its last four digits only (never the full number).
  const hintKey =
    field.id === "aadhaar_last4"
      ? "intake.hint.aadhaar"
      : formatHintKey(field.type, holderLifted ? null : field.holder);
  const full = FULL_LENGTH[field.type] ?? (field.type === "digits" ? field.length : null);
  const judged = left || (full != null && value.trim().length >= full);
  const valid =
    !judged ||
    looksValid(field.type, value, {
      length: field.length,
      holder: field.holder,
      lifted: holderLifted,
    });
  const code = CODES.has(field.type);
  const figure = FIGURES.has(field.type);
  const hint = hintKey ? t(hintKey, { n: field.length ?? "" }) : null;
  // A line is kept under any field that can show a hint or a format check.
  const note = Boolean(hintKey) || field.type === "months";
  return (
    <>
      <input
        id={id}
        aria-label={label ?? fieldLabel(field.id)}
        aria-required={field.required || undefined}
        aria-invalid={!valid || undefined}
        aria-describedby={note ? noteId : undefined}
        type={field.type === "date" ? "date" : "text"}
        className={cn(
          inputClass,
          (code || figure) && "tabular",
          code && "uppercase placeholder:normal-case",
        )}
        value={value}
        inputMode={figure ? (field.type === "number" ? "decimal" : "numeric") : undefined}
        maxLength={field.type === "digits" ? (field.length ?? undefined) : undefined}
        placeholder={hint && !showHint ? hint : undefined}
        onFocus={onFocus}
        onBlur={() => setLeft(true)}
        onClick={stop}
        onChange={(e) => onChange(cleanInput(field.type, e.target.value, field.length))}
        data-testid={testId}
      />
      {note && (
        <p
          id={noteId}
          className={cn(
            "mt-0.5 min-h-4 text-[11px] leading-4",
            valid ? "text-muted-foreground" : "text-flag-foreground",
          )}
          data-testid={valid ? (showHint ? "format-hint" : undefined) : "format-check"}
        >
          {!valid ? t("intake.hint.check") : showHint ? hint : null}
        </p>
      )}
    </>
  );
}

/** Rupees, right-aligned with ₹ before them and Indian grouping (12,00,000) as they are typed;
 * the caret stays after the same digit, and Backspace or Delete over a comma removes the digit
 * beside it. The figure in words below (INR 12.00 lakh). Only digits are kept. */
function AmountInput({ field, value, onChange, onFocus, label, id, testId }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const caret = useRef<number | null>(null);
  const n = Number(value);
  const shown = value && n > 0 ? n.toLocaleString("en-IN") : value;

  // Put the caret back after the same number of digits once the grouping is redrawn.
  useLayoutEffect(() => {
    const el = input.current;
    const digits = caret.current;
    if (!el || digits === null || document.activeElement !== el) return;
    let at = 0;
    for (let seen = 0; at < shown.length && seen < digits; at++) if (/\d/.test(shown[at]!)) seen++;
    el.setSelectionRange(at, at);
    caret.current = null;
  }, [shown]);

  const skipComma = (e: KeyboardEvent<HTMLInputElement>) => {
    const el = e.currentTarget;
    const at = el.selectionStart ?? 0;
    if (at !== el.selectionEnd) return;
    if (e.key === "Backspace" && el.value[at - 1] === ",") el.setSelectionRange(at - 1, at - 1);
    if (e.key === "Delete" && el.value[at] === ",") el.setSelectionRange(at + 1, at + 1);
  };

  return (
    <>
      <div className="relative mt-1">
        <span
          className="pointer-events-none absolute inset-y-0 left-2.5 grid place-items-center text-[12.5px] text-muted-foreground"
          aria-hidden
        >
          {t("intake.rupee")}
        </span>
        <input
          ref={input}
          id={id}
          aria-label={label ?? fieldLabel(field.id)}
          aria-required={field.required || undefined}
          inputMode="numeric"
          className={cn(inputClass, "mt-0 pl-6 text-right tabular")}
          value={shown}
          onFocus={onFocus}
          onClick={stop}
          onKeyDown={skipComma}
          onChange={(e) => {
            const pos = e.target.selectionStart ?? e.target.value.length;
            caret.current = e.target.value.slice(0, pos).replace(/\D/g, "").length;
            onChange(cleanInput("amount", e.target.value));
          }}
          data-testid={testId}
        />
      </div>
      <p className="mt-0.5 min-h-4 text-right text-[11px] leading-4 text-muted-foreground tabular">
        {n > 0 ? formatInr(n) : null}
      </p>
    </>
  );
}
