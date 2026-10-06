import { createFileRoute } from "@tanstack/react-router";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { useLabels } from "@/domain/cases";
import { useTaxonomy } from "@/domain/checklist";

export const Route = createFileRoute("/admin/checklist")({ component: Checklist });

function Checklist() {
  const taxonomy = useTaxonomy();
  const labels = useLabels();
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
                          {t("admin.checklist.appliesTo", {
                            constitutions: i.constitutions
                              .map((k) => labels.constitution(k))
                              .join(", "),
                          })}
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
