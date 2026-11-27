import { createFileRoute } from "@tanstack/react-router";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { useLabels, useMeta } from "@/domain/cases";
import { useTaxonomy } from "@/domain/checklist";
import type { ChecklistItemDef } from "@/api/types";

export const Route = createFileRoute("/admin/checklist")({ component: Checklist });

/** Who an item applies to. A business banking item names its constitutions; an item of another
 * product (a loan against property) names that product, its customer types (or every one) and its
 * case types, and says when the form or the case type alone calls for it. */
function appliesTo(
  i: ChecklistItemDef,
  productDefault: string | null | undefined,
  labels: ReturnType<typeof useLabels>,
): string {
  const products = i.products ?? [];
  if (products.length === 0 || products.includes(productDefault ?? "")) {
    return t("admin.checklist.appliesTo", {
      constitutions: i.constitutions.map((k) => labels.constitution(k)).join(", "),
    });
  }
  const customers = i.customer_types?.length
    ? i.customer_types.map((k) => labels.customerType(k)).join(", ")
    : t("admin.checklist.everyCustomerType");
  const parts = [products.map((p) => labels.product(p)).join(", "), customers];
  if (i.case_types?.length) parts.push(i.case_types.map((k) => labels.caseType(k)).join(", "));
  const scope = parts.join(" · ");
  return i.when_any
    ? t("admin.checklist.appliesToWhen", { scope })
    : t("admin.checklist.appliesToScope", { scope });
}

function Checklist() {
  const taxonomy = useTaxonomy();
  const labels = useLabels();
  const productDefault = useMeta().data?.product_default;
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <QueryView query={taxonomy}>
        {(c) => (
          <>
            <p className="max-w-3xl text-[12.5px] text-muted-foreground" data-testid="admin-gates">
              {t("admin.checklist.gates", {
                review: c.review_gate_threshold,
                disbursement: c.disbursement_gate_threshold,
              })}
            </p>
            {c.sections.map((section) => {
              const items = c.items.filter((i) => i.category === section);
              if (items.length === 0) return null;
              return (
                <Panel
                  key={section}
                  title={section}
                  subtitle={t("checklist.weight", { n: c.section_weight[section] ?? 0 })}
                  testId="admin-checklist-section"
                >
                  <ul className="divide-y divide-border">
                    {items.map((i) => (
                      <li key={i.id} className="space-y-0.5 px-4 py-2.5" data-testid="admin-item">
                        <p className="flex flex-wrap items-center gap-2 text-[13px] font-medium">
                          {i.name}
                          {i.blocking && (
                            <Chip tone="critical" upper>
                              {t("checklist.blocking")}
                            </Chip>
                          )}
                        </p>
                        <p className="text-[12px] text-muted-foreground">{i.why}</p>
                        <p className="text-[11.5px] text-muted-foreground">
                          {appliesTo(i, productDefault, labels)}
                        </p>
                      </li>
                    ))}
                  </ul>
                </Panel>
              );
            })}
          </>
        )}
      </QueryView>
    </div>
  );
}
