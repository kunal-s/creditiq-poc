// Words and styles the New appraisal's components share: labels from the terminology by id.
import type { KeyboardEvent } from "react";
import type { IntakeField, ProductMeta } from "@/api/types";
import { t, tOr } from "@/config/terminology";

export const inputClass =
  "mt-1 h-9 w-full min-w-0 rounded border border-border bg-surface px-2.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/70 focus:border-primary/60 focus:ring-1 focus:ring-ring";

/** A field's label: the form's wording for its id (intake.field.*), else the id in words. */
export function fieldLabel(id: string): string {
  return tOr(`intake.field.${id}`, tOr(`proposalField.${id}`, id));
}

/** An identifier box's label: the product's own wording first ("Applicant PAN"), else the box's. */
export function identifierLabel(product: string, id: string): string {
  return tOr(`intake.identifier.${product}.${id}`, tOr(`intake.identifier.${id}`, id));
}

/** "Loan against property (LAP)": a product as the options and chips name it. */
export function productName(p: Pick<ProductMeta, "label" | "prefix">): string {
  return t("intake.product.name", { label: p.label, prefix: p.prefix });
}

/** "Property 2": a row's name in its section (intake.row.<section>, else "Row 2"). */
export function rowLabel(section: string, n: number): string {
  return tOr(`intake.row.${section}`, t("intake.row.other")).replace("{n}", String(n));
}

/** The fields kept aside from the message (the form has no field for them), shown as text. */
export function extraFields(keys: string[]): IntakeField[] {
  return keys.map((id) => ({ id, type: "text", required: false }));
}

/** Arrow keys move the choice within a radio group (the WAI-ARIA radio pattern). */
export function onRadioKeys(e: KeyboardEvent<HTMLElement>): void {
  const step = (
    { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 } as Record<string, number>
  )[e.key];
  if (!step) return;
  const radios = Array.from(
    e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]:not(:disabled)'),
  );
  const at = radios.indexOf(document.activeElement as HTMLButtonElement);
  if (at < 0) return;
  e.preventDefault();
  const next = radios[(at + step + radios.length) % radios.length]!;
  next.focus();
  next.click();
}

/** One tab stop per radio group: the chosen option, else the first. */
export function radioTabIndex(checked: boolean, index: number, anyChecked: boolean): 0 | -1 {
  return checked || (!anyChecked && index === 0) ? 0 : -1;
}
