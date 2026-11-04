import { createFileRoute } from "@tanstack/react-router";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { formatDate } from "@/domain/cases";
import { useCamTemplates } from "@/domain/findings";

// The memo templates, as the original's template designer: each template's sections in order,
// what each is for and what it is drafted from. The configured template is the default; an
// analyst makes another from a memo, so this screen reads them.

export const Route = createFileRoute("/admin/templates")({ component: Templates });

function Templates() {
  const templates = useCamTemplates();
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <QueryView
        query={templates}
        isEmpty={(data) => data.templates.length === 0}
        empty={{ title: t("admin.templates.none"), description: t("admin.templates.noneHelp") }}
      >
        {(data) => (
          <>
            {data.templates.map((tpl) => (
              <Panel
                key={tpl.id}
                title={tpl.name}
                subtitle={
                  tpl.default
                    ? t("admin.templates.default", { n: tpl.sections.length })
                    : t("admin.templates.made", {
                        n: tpl.sections.length,
                        by: tpl.created_by_name ?? tpl.created_by ?? "",
                        at: tpl.created_at ? formatDate(tpl.created_at) : "",
                      })
                }
                action={
                  tpl.default ? <Chip tone="primary">{t("admin.templates.inUse")}</Chip> : undefined
                }
                testId="admin-template"
              >
                {tpl.description && (
                  <p className="border-b border-border px-4 py-2.5 text-[12.5px] text-muted-foreground">
                    {tpl.description}
                  </p>
                )}
                <ol className="divide-y divide-border">
                  {tpl.sections.map((s, i) => (
                    <li
                      key={s.id || i}
                      className="flex gap-3 px-4 py-2.5"
                      data-testid="admin-template-section"
                    >
                      <span className="tabular w-5 shrink-0 pt-px text-[12px] text-muted-foreground">
                        {i + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-medium text-foreground">{s.title}</p>
                        {s.purpose && (
                          <p className="mt-0.5 text-[12px] text-muted-foreground">{s.purpose}</p>
                        )}
                      </div>
                      <span className="max-w-[45%] shrink-0 text-right text-[11.5px] text-muted-foreground">
                        {(s.parts ?? []).length > 0
                          ? t("admin.templates.parts", {
                              parts: (s.parts ?? [])
                                .map((id) => data.parts.find((p) => p.id === id)?.title ?? id)
                                .join(", "),
                            })
                          : t("admin.templates.analystWrites")}
                      </span>
                    </li>
                  ))}
                </ol>
              </Panel>
            ))}
          </>
        )}
      </QueryView>
    </div>
  );
}
