import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { api } from "@/api/client";
import { Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t, tOr } from "@/config/terminology";
import { formatDate } from "@/domain/cases";
import { useDocumentTypes } from "@/domain/documents";

export const Route = createFileRoute("/admin/document-types")({ component: DocumentTypes });

function DocumentTypes() {
  const types = useDocumentTypes();
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <QueryView query={types}>
        {(d) => {
          const groups = [...new Set(d.types.map((x) => x.group))];
          return groups.map((group) => (
            <Panel
              key={group}
              title={tOr(`admin.documentGroup.${group}`, group)}
              subtitle={t("admin.documents.count", {
                n: d.types.filter((x) => x.group === group).length,
              })}
              testId="admin-document-group"
            >
              <ul className="divide-y divide-border">
                {d.types
                  .filter((x) => x.group === group)
                  .map((x) => (
                    <li key={x.id} className="px-4 py-2.5" data-testid="admin-document-type">
                      <p className="text-[13px] font-medium">{x.name}</p>
                      <p className="text-[12px] text-muted-foreground">{x.description}</p>
                    </li>
                  ))}
              </ul>
            </Panel>
          ));
        }}
      </QueryView>
      <Proposals />
    </div>
  );
}

/** Types people made on appraisals when no published type fitted (F-09.10), most used first:
 * candidates for the closed list. Counts only, as the Administrator does not open appraisals. */
function Proposals() {
  const proposals = useQuery({
    queryKey: ["admin", "case-document-types"],
    queryFn: api.caseDocumentTypeProposals,
  });
  return (
    <Panel
      title={t("caseType.admin.title")}
      subtitle={t("caseType.admin.subtitle")}
      testId="admin-case-type-proposals"
    >
      <QueryView query={proposals}>
        {(list) =>
          list.length === 0 ? (
            <p className="px-4 py-3 text-[12.5px] text-muted-foreground">
              {t("caseType.admin.empty")}
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {list.map((p) => (
                <li key={p.name} className="px-4 py-2.5" data-testid="admin-case-type">
                  <p className="text-[13px] font-medium">{p.name}</p>
                  {p.description && (
                    <p className="text-[12px] text-muted-foreground">{p.description}</p>
                  )}
                  <p className="text-[12px] text-muted-foreground">
                    {(p.fields ?? []).length > 0
                      ? t("caseType.admin.fields", {
                          list: (p.fields ?? []).map((f) => f.name.replace(/_/g, " ")).join(", "),
                        })
                      : t("caseType.admin.fieldsNone")}
                  </p>
                  <p className="tabular text-[11.5px] text-muted-foreground">
                    {t("caseType.admin.usage", { cases: p.cases, documents: p.documents })} ·{" "}
                    {t("caseType.admin.lastMade", { date: formatDate(p.last_made) })}
                  </p>
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>
    </Panel>
  );
}
