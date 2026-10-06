import { createFileRoute } from "@tanstack/react-router";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { formatWhen, sectionLabel, useConfigVersions } from "@/domain/admin";

export const Route = createFileRoute("/admin/")({ component: Configuration });

function Configuration() {
  const versions = useConfigVersions();
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <QueryView query={versions}>
        {(list) => {
          const current = list.find((v) => v.current);
          return (
            <>
              {current && (
                <Panel title={t("admin.config.current")} testId="config-current">
                  <dl className="grid gap-x-8 gap-y-2 px-4 py-3 text-[12.5px] sm:grid-cols-3">
                    <div>
                      <dt className="text-muted-foreground">{t("admin.config.publishedOn")}</dt>
                      <dd className="font-medium">{formatWhen(current.published_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">{t("admin.config.publishedBy")}</dt>
                      <dd className="font-medium">{current.author}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">{t("admin.config.versionNumber")}</dt>
                      <dd className="font-medium tabular">{list.length - list.indexOf(current)}</dd>
                    </div>
                  </dl>
                  <p className="border-t border-border px-4 py-2.5 text-[12px] text-muted-foreground">
                    {t("admin.config.readOnly")}
                  </p>
                </Panel>
              )}
              <Panel
                title={t("admin.config.history")}
                subtitle={t("admin.config.historyHelp")}
                testId="config-history"
              >
                <ul className="divide-y divide-border">
                  {list.map((v, i) => (
                    <li
                      key={v.version}
                      className="space-y-1 px-4 py-3"
                      data-testid="config-version"
                    >
                      <p className="flex flex-wrap items-center gap-2 text-[13px] font-medium">
                        {t("admin.config.versionN", { n: list.length - i })}
                        {v.current && <Chip tone="positive">{t("admin.config.inForce")}</Chip>}
                        <span className="text-[12px] font-normal text-muted-foreground">
                          {formatWhen(v.published_at)} · {v.author}
                        </span>
                      </p>
                      {v.note && <p className="text-[12.5px] text-foreground">{v.note}</p>}
                      <p className="text-[12px] text-muted-foreground">
                        {v.prior_version
                          ? t("admin.config.changed", {
                              n: v.sections_changed.length,
                              sections: v.sections_changed.map(sectionLabel).join(", ") || "—",
                            })
                          : t("admin.config.first")}
                      </p>
                    </li>
                  ))}
                </ul>
              </Panel>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
