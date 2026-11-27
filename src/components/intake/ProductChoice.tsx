// Test ids: product-choice, product-<id> (role radio, aria-checked), product-switch,
// product-switch-confirm, intake-steps, step-<id> (data-state done | current | to-do).
import { Check } from "lucide-react";
import type { ProductMeta } from "@/api/types";
import { t, tOr } from "@/config/terminology";
import { cn } from "@/lib/utils";
import { onRadioKeys, productName, radioTabIndex } from "./labels";

/** Step 1: the product, as two slim options side by side (stacked when the content area is
 * narrow). The form, the documents suggested, the minimum and the case number follow it. Once
 * the form is open, choosing the other product asks first (`pending`): the message, identifiers
 * and documents are kept. */
export function ProductChoice({
  products,
  value,
  pending,
  step,
  onChoose,
  onConfirm,
  onCancel,
  disabled = false,
}: {
  products: ProductMeta[];
  value: string;
  pending: string | null;
  step: IntakeStep;
  onChoose: (id: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  /** While the message is read again for a new product. */
  disabled?: boolean;
}) {
  const current = products.find((p) => p.id === value);
  const next = products.find((p) => p.id === pending);
  return (
    <section
      className="rounded border border-border bg-surface px-4 py-3"
      data-testid="product-choice"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 className="field-label">{t("intake.product.title")}</h2>
        <IntakeSteps current={step} />
      </div>
      <div
        className="mt-2 grid gap-2 @min-[45rem]/main:grid-cols-2"
        role="radiogroup"
        aria-label={t("intake.product.title")}
        onKeyDown={onRadioKeys}
      >
        {products.map((p, i) => {
          const on = p.id === value;
          return (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={on}
              aria-label={productName(p)}
              tabIndex={radioTabIndex(
                on,
                i,
                products.some((x) => x.id === value),
              )}
              disabled={disabled}
              data-testid={`product-${p.id}`}
              onClick={() => onChoose(p.id)}
              className={cn(
                "flex min-w-0 items-start gap-2.5 rounded border px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-60",
                on ? "border-primary bg-accent/60" : "border-border hover:bg-surface-muted",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border",
                  on ? "border-primary bg-primary text-primary-foreground" : "border-border",
                )}
                aria-hidden
              >
                {on && <Check className="size-3" strokeWidth={3} />}
              </span>
              <span className="min-w-0">
                <span
                  className={cn(
                    "block text-[13px] font-semibold",
                    on ? "text-primary" : "text-foreground",
                  )}
                >
                  {productName(p)}
                </span>
                <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">
                  {tOr(`intake.product.about.${p.id}`, "")}
                </span>
              </span>
            </button>
          );
        })}
      </div>
      {next && current && (
        <div
          className="mt-2 flex flex-wrap items-center gap-2 rounded border border-flag/40 bg-flag-soft px-3 py-2 text-[12px] text-flag-foreground"
          data-testid="product-switch"
          role="group"
          aria-label={t("intake.product.switchTitle", { product: productName(next) })}
        >
          <p className="min-w-0 flex-1 basis-64">
            <span className="font-semibold">
              {t("intake.product.switchTitle", { product: productName(next) })}
            </span>{" "}
            {t("intake.product.switchHelp")}
          </p>
          <button
            type="button"
            onClick={onCancel}
            className="h-8 rounded border border-border bg-surface px-2.5 font-medium text-foreground hover:bg-muted"
          >
            {t("intake.product.keep", { product: current.prefix })}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            data-testid="product-switch-confirm"
            className="h-8 rounded bg-primary px-2.5 font-medium text-primary-foreground hover:bg-primary/90"
          >
            {t("intake.product.switch")}
          </button>
        </div>
      )}
    </section>
  );
}

export type IntakeStep = "product" | "start" | "details" | "review";
const STEPS: IntakeStep[] = ["product", "start", "details", "review"];

/** The steps of a new application as small chips in one wrapping row: done, the current one and
 * those to come. They are sections of one page, so the chips show progress; they do not navigate. */
export function IntakeSteps({ current }: { current: IntakeStep }) {
  const at = STEPS.indexOf(current);
  return (
    <ol
      className="flex flex-wrap items-center gap-1"
      aria-label={t("intake.steps.label")}
      data-testid="intake-steps"
    >
      {STEPS.map((step, i) => {
        const state = i < at ? "done" : i === at ? "current" : "to-do";
        return (
          <li
            key={step}
            data-testid={`step-${step}`}
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
            className={cn(
              "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-px text-[11px] font-medium",
              state === "current"
                ? "border-primary/40 bg-accent text-primary"
                : "border-border bg-surface",
              state === "done" && "text-foreground",
              state === "to-do" && "text-muted-foreground",
            )}
          >
            {state === "done" ? (
              <Check className="size-3 text-positive" aria-hidden />
            ) : (
              <span className="tabular" aria-hidden>
                {i + 1}
              </span>
            )}
            {t(`intake.steps.${step}`)}
          </li>
        );
      })}
    </ol>
  );
}
