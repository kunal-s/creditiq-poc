import { createFileRoute } from "@tanstack/react-router";
import { Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t, tOr } from "@/config/terminology";
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
    </div>
  );
}
