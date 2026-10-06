import { createFileRoute } from "@tanstack/react-router";
import { Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { permissionLabel, useUsers } from "@/domain/admin";

export const Route = createFileRoute("/admin/users")({ component: Users });

function Users() {
  const users = useUsers();
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <QueryView query={users}>
        {(list) => {
          const roles = [...new Map(list.map((u) => [u.role, u])).values()];
          return (
            <>
              <Panel title={t("admin.users.people")} testId="admin-users">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px] text-[12.5px]">
                    <thead>
                      <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
                        <th className="px-4 py-2 font-medium">{t("admin.users.name")}</th>
                        <th className="px-3 py-2 font-medium">{t("admin.users.role")}</th>
                        <th className="px-3 py-2 font-medium">{t("admin.users.email")}</th>
                        <th className="px-4 py-2 font-medium">{t("admin.users.branch")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {list.map((u) => (
                        <tr key={u.id} data-testid="admin-user">
                          <td className="px-4 py-2 font-medium">{u.name}</td>
                          <td className="px-3 py-2">{u.roleLabel}</td>
                          <td className="px-3 py-2 text-muted-foreground">{u.email}</td>
                          <td className="px-4 py-2 text-muted-foreground">{u.branch}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
              <Panel title={t("admin.users.roles")} subtitle={t("admin.users.rolesHelp")}>
                <ul className="divide-y divide-border">
                  {roles.map((r) => (
                    <li key={r.role} className="px-4 py-3" data-testid="admin-role">
                      <p className="text-[13px] font-medium">{r.roleLabel}</p>
                      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[12px] text-muted-foreground">
                        {r.permissions.map((p) => (
                          <li key={p}>{permissionLabel(p)}</li>
                        ))}
                      </ul>
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
