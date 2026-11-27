// Test ids: identifier-fields, identifier-<id>, start-choice-<key>, format-hint, format-check.
import type { IntakeField, IntakeProduct, Meta } from "@/api/types";
import { t } from "@/config/terminology";
import { productOf, startChoiceKeys, startIdentifiers } from "@/domain/intake";
import { FieldEditor } from "./FieldEditor";
import { fieldLabel, identifierLabel } from "./labels";

/** Box 3 of the start screen: one optional field per identifier the product offers, each with a
 * short format hint under it, two to a row when the box is wide enough. Boxes that apply only to
 * some customers or case types (a business's GSTIN, the account of a loan being transferred) show
 * once that choice is made under Provenance and hints. */
export function IdentifierFields({
  product,
  form,
  values,
  choices,
  onValue,
}: {
  product: string;
  form: IntakeProduct;
  values: Record<string, string>;
  choices: Record<string, string>;
  onValue: (id: string, value: string) => void;
}) {
  const boxes = startIdentifiers(form, choices);
  return (
    <div data-testid="identifier-fields">
      <div className="grid gap-x-3 gap-y-2 @min-[17rem]/box:grid-cols-2">
        {boxes.map((box) => {
          const label = identifierLabel(product, box.id);
          const lifted = (box.unless?.["customer_type"] ?? []).includes(
            choices["customer_type"] ?? "",
          );
          return (
            <div key={box.id} className="min-w-0" data-testid={`identifier-${box.id}`}>
              <span className="field-label">{label}</span>
              <FieldEditor
                field={{ id: box.id, type: box.type, required: false, holder: box.holder ?? null }}
                value={values[box.id] ?? ""}
                label={label}
                holderLifted={lifted}
                showHint
                onChange={(v) => onValue(box.id, v)}
              />
            </div>
          );
        })}
      </div>
      {boxes.length < form.start.identifiers.length && (
        <p className="mt-2 text-[11px] text-muted-foreground">{t("intake.start.moreBoxes")}</p>
      )}
    </div>
  );
}

/** The start choices a product's identifier boxes depend on (customer type, case type), as
 * lists under Provenance and hints. */
export function StartChoices({
  meta,
  product,
  form,
  choices,
  onChoice,
}: {
  meta: Meta;
  product: string;
  form: IntakeProduct;
  choices: Record<string, string>;
  onChoice: (key: string, value: string) => void;
}) {
  const p = productOf(meta, product);
  const keys = startChoiceKeys(form);
  if (keys.length === 0) return null;
  const field = (key: string): IntakeField => ({
    id: key,
    type: "choice",
    required: false,
    options: key === "customer_type" ? (p?.customer_types ?? []) : (p?.case_types ?? []),
  });
  return (
    <>
      {keys.map((key) => (
        <label key={key} className="block min-w-0">
          <span className="field-label">{fieldLabel(key)}</span>
          <FieldEditor
            field={field(key)}
            value={choices[key] ?? ""}
            onChange={(v) => onChoice(key, v)}
            testId={`start-choice-${key}`}
          />
        </label>
      ))}
    </>
  );
}
