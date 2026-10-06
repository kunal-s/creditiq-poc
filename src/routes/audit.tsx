import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { Details } from "@/components/common/Details";
import { PageHeader } from "@/components/shell/PageHeader";
import { t } from "@/config/terminology";
import { actionLabel, formatWhen, useAudit } from "@/domain/admin";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [{ title: `${t("page.audit.title")} — ${t("tenant.product.name")}` }],
  }),
  component: Audit,
});

const select =
  "h-8 rounded border border-border bg-surface px-2 text-[12.5px] text-foreground outline-none focus:border-primary/60";

function Audit() {
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [caseId, setCaseId] = useState("");
  const audit = useAudit({
    ...(actor ? { actor } : {}),
    ...(action ? { action } : {}),
    ...(caseId.trim() ? { caseId: caseId.trim() } : {}),
  });
  return (
    <div>
      <PageHeader
        eyebrow={t("page.audit.eyebrow")}
        title={t("page.audit.title")}
        purpose={t("page.audit.purpose")}
      />
      <div className="space-y-4 px-4 py-5 sm:px-6">
        <QueryView query={audit}>
          {(page) => (
            <Panel
              title={t("audit.entries")}
              testId="audit"
              action={
                <div className="flex flex-wrap gap-2">
                  <select
                    className={select}
                    value={action}
                    onChange={(e) => setAction(e.target.value)}
                    aria-label={t("audit.filterAction")}
                  >
                    <option value="">{t("audit.allActions")}</option>
                    {page.actions.map((a) => (
                      <option key={a} value={a}>
                        {actionLabel(a)}
                      </option>
                    ))}
                  </select>
                  <select
                    className={select}
                    value={actor}
                    onChange={(e) => setActor(e.target.value)}
                    aria-label={t("audit.filterPerson")}
                  >
                    <option value="">{t("audit.allPeople")}</option>
                    {page.actors.map((a) => (
                      <option key={a} value={a}>
                        {page.entries.find((e) => e.actor === a)?.actor_name ?? a}
                      </option>
                    ))}
                  </select>
                  <input
                    className={`${select} w-40`}
                    value={caseId}
                    onChange={(e) => setCaseId(e.target.value)}
                    placeholder={t("audit.caseId")}
                    aria-label={t("audit.caseId")}
                  />
                </div>
              }
            >
              {page.entries.length === 0 ? (
                <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
                  {t("audit.none")}
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {page.entries.map((e) => (
                    <li key={e.seq} className="space-y-1 px-4 py-2.5" data-testid="audit-entry">
                      <p className="flex flex-wrap items-baseline gap-x-2 text-[13px]">
                        <span className="font-medium">{actionLabel(e.action)}</span>
                        <span className="text-muted-foreground">
                          {e.actor_name} · {formatWhen(e.at)}
                        </span>
                        {e.case_id && (
                          <Link
                            to="/appraisals/$caseId"
                            params={{ caseId: e.case_id }}
                            className="text-[12px] text-primary hover:underline"
                          >
                            {e.case_id}
                          </Link>
                        )}
                      </p>
                      {Object.keys(e.detail).length > 0 && (
                        <Details>
                          <dl className="space-y-0.5 text-[12px]">
                            {Object.entries(e.detail).map(([k, v]) => (
                              <div key={k} className="flex gap-2">
                                <dt className="w-32 shrink-0 text-muted-foreground">
                                  {k.replace(/_/g, " ")}
                                </dt>
                                <dd className="min-w-0 break-words">
                                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </Details>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
        </QueryView>
      </div>
    </div>
  );
}
