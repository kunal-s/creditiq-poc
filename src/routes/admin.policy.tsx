import { createFileRoute } from "@tanstack/react-router";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { requirementText, usePolicyConfig } from "@/domain/admin";

export const Route = createFileRoute("/admin/policy")({ component: PolicyNorms });

const FAMILIES = ["eligibility", "ratios", "security_cover", "documentation"] as const;

function PolicyNorms() {
  const policy = usePolicyConfig();
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <QueryView query={policy}>
        {(p) => {
          const ratio = (key: string | null | undefined) => p.ratios.find((r) => r.key === key);
          const category = (key: string) =>
            (p.deviation_categories ?? []).find((c) => c.key === key)?.label ?? key;
          return FAMILIES.map((family) => {
            const norms = (p.norms ?? []).filter((n) => n.family === family);
            if (norms.length === 0) return null;
            return (
              <Panel
                key={family}
                title={t(`policy.family.${family}`)}
                subtitle={t("admin.policy.count", { n: norms.length })}
                testId={`admin-norms-${family}`}
              >
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[520px] text-[12.5px]">
                    <thead>
                      <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
                        <th className="px-4 py-2 font-medium">{t("admin.policy.norm")}</th>
                        <th className="px-3 py-2 font-medium">{t("admin.policy.requirement")}</th>
                        <th className="px-4 py-2 font-medium">{t("admin.policy.deviation")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {norms.map((n) => {
                        const r = ratio(n.ratio);
                        return (
                          <tr key={n.id} className="align-top" data-testid="admin-norm">
                            <td className="px-4 py-2">
                              {n.label ?? r?.label ?? n.id}
                              {n.status === "provisional" && (
                                <Chip tone="muted" className="ml-2">
                                  {t("policy.provisional")}
                                </Chip>
                              )}
                            </td>
                            <td className="px-3 py-2 tabular">
                              {requirementText(
                                n.kind ?? r?.kind,
                                n.threshold ?? r?.acceptable,
                                n.unit ?? r?.unit,
                              )}
                            </td>
                            <td className="px-4 py-2 text-muted-foreground">
                              {category(n.category)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Panel>
            );
          });
        }}
      </QueryView>
    </div>
  );
}
