/** /api/meta for the New appraisal, filled in for an engine that predates products and forms. */
import type { IntakeProduct, Meta, IntakeField, IntakeFieldType, ProductMeta } from "@/api/types";

/** A business banking form for an engine that does not serve one yet (no `products` lists or
 * `intake` in /api/meta): the identifiers, case details, borrower and facility lines it always
 * had, so the screen keeps working as it did. */
function fallbackForm(meta: Meta): IntakeProduct {
  const f = (id: string, type: IntakeFieldType, extra: Partial<IntakeField> = {}): IntakeField => ({
    id,
    type,
    required: false,
    ...extra,
  });
  return {
    start: {
      message_required: false,
      documents: { required: true, min_files: 1, suggested: [] },
      identifiers: [
        { id: "pan", type: "pan", holder: "entity" },
        { id: "gstin", type: "gstin" },
        { id: "cin", type: "cin_or_llpin" },
        { id: "udyam", type: "udyam" },
        { id: "application_id", type: "text" },
      ],
    },
    sections: [
      {
        id: "case",
        fields: [
          f("case_type", "choice", { options: meta.case_types }),
          f("application_id", "text"),
          f("customer_id", "text"),
          f("branch", "choice", { options: meta.branches }),
          f("bank_stage", "choice", { options: meta.bank_stages }),
          f("channel", "choice", { options: meta.channels }),
        ],
      },
      {
        id: "borrower",
        fields: [
          f("borrower", "text", { required: true }),
          f("constitution", "choice", { options: meta.constitutions }),
          f("pan", "pan", { holder: "entity" }),
          f("gstin", "gstin"),
          f("cin", "cin_or_llpin"),
          f("udyam", "udyam"),
        ],
      },
      {
        id: "facilities",
        repeat: { min: 1, max: 10 },
        fields: [
          f("facility", "choice", { options: meta.facilities, required: true }),
          f("amount_inr", "amount", { required: true }),
        ],
      },
      {
        id: "declared",
        fields: [f("declared_turnover_inr", "amount"), f("proposed_emi_inr", "amount")],
      },
    ],
  };
}

/** /api/meta with every product's lists and form, filled in for an engine that predates them
 * (one business banking product, as the screen always had). */
export function withIntakeDefaults(meta: Meta): Meta {
  const raw = (meta.products ?? []) as Partial<ProductMeta>[];
  const products: ProductMeta[] = (raw.length ? raw : [{ id: meta.product_default ?? "bbg" }]).map(
    (p) => ({
      id: p.id ?? "bbg",
      label: p.label ?? p.id ?? "",
      prefix: p.prefix ?? (p.id ?? "bbg").toUpperCase(),
      case_types: p.case_types ?? meta.case_types,
      stages: p.stages ?? meta.bank_stages,
      customer_types: p.customer_types ?? meta.constitutions.filter((c) => c.id !== "unknown"),
      programs: p.programs ?? [],
      minimum: p.minimum ?? meta.case_create_minimum.filter((k) => k !== "product"),
    }),
  );
  const intake = { ...meta.intake };
  for (const p of products) intake[p.id] ??= fallbackForm(meta);
  return { ...meta, products, intake };
}
