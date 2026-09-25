import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AlertTriangle, ArrowUpRight, ShieldAlert, Sparkles, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import {
  ROLES,
  addUser,
  setUserRole,
  setUserStatus,
  sodConflicts,
  useAdminState,
  type RoleId,
} from "@/data/admin";
import { useSession } from "@/domain/session";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/users")({
  head: () => ({
    meta: [
      { title: `${t("page.adminUsers.title")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content: `Who at ${t("tenant.bank.name")} can author, adjudicate, approve and configure — with segregation-of-duties checks that block one person from both writing and approving a memo.`,
      },
    ],
  }),
  component: UsersAndRoles,
});

const STATUS_TONE = {
  active: "border-positive/30 bg-positive-soft text-positive",
  invited: "border-info/25 bg-info-soft text-info",
  suspended: "border-critical/30 bg-critical-soft text-critical",
} as const;

function UsersAndRoles() {
  const session = useSession();
  const actor = session?.user.name ?? "Unknown";
  const s = useAdminState();
  const [selected, setSelected] = useState<string>(s.users[0]?.slug ?? "");
  const [inviting, setInviting] = useState(false);
  const [form, setForm] = useState({
    name: "",
    email: "",
    role: "analyst" as RoleId,
    branch: t("tenant.bank.hub"),
  });

  const conflicts = useMemo(() => sodConflicts(s.users), [s.users]);
  const user = s.users.find((u) => u.slug === selected) ?? s.users[0]!;
  const role = ROLES.find((r) => r.id === user.role)!;
  const userConflicts = conflicts.filter((c) => c.slug === user.slug);

  return (
    <div>
      <PageHeader
        eyebrow={t("page.adminUsers.eyebrow")}
        title={t("page.adminUsers.title")}
        purpose="Six roles, one rule: nobody authors and approves the same memo. Role changes take effect on the next sign-in and are written to the audit ledger with who made them."
        actions={
          <button
            onClick={() => setInviting((v) => !v)}
            className="flex h-9 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
          >
            <UserPlus className="h-3.5 w-3.5" /> Invite a user
          </button>
        }
      />

      <div className="space-y-4 px-6 py-5">
        {conflicts.filter((c) => c.severity === "blocked").length > 0 && (
          <div className="flex items-start gap-2.5 rounded border border-critical/30 bg-critical-soft px-4 py-3">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-critical" />
            <div className="text-[12.5px] text-critical">
              <p className="font-medium">
                Segregation of duties is breached and submissions from this tenant are blocked.
              </p>
              {conflicts
                .filter((c) => c.severity === "blocked")
                .map((c) => (
                  <p key={c.slug + c.detail} className="mt-0.5">
                    {c.detail}
                  </p>
                ))}
            </div>
          </div>
        )}

        {inviting && (
          <Panel
            title="Invite a user"
            subtitle="An invitation is issued through the identity directory; the role applies at first sign-in."
          >
            <div className="grid gap-3 px-4 py-3 md:grid-cols-4">
              <label className="text-[12px]">
                <span className="field-label">Full name</span>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Full name"
                  className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                />
              </label>
              <label className="text-[12px]">
                <span className="field-label">Bank email</span>
                <input
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder={`name@${t("tenant.bank.emailDomain")}`}
                  className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                />
              </label>
              <label className="text-[12px]">
                <span className="field-label">Role</span>
                <select
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value as RoleId })}
                  className="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
                >
                  {ROLES.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex items-end gap-2">
                <button
                  onClick={() => {
                    if (!form.name.trim() || !form.email.includes("@")) {
                      toast.error("A full name and a bank email are needed");
                      return;
                    }
                    const slug = form.name.toLowerCase().replace(/[^a-z]+/g, "-");
                    addUser(
                      {
                        slug,
                        name: form.name.trim(),
                        email: form.email.trim(),
                        role: form.role,
                        branch: form.branch,
                        status: "invited",
                        lastActive: "Not yet signed in",
                        authored: 0,
                        approved: 0,
                        delegation: ROLES.find((r) => r.id === form.role)!.approver
                          ? "To be set by the Chief Credit Officer"
                          : "None",
                      },
                      actor,
                    );
                    setSelected(slug);
                    setInviting(false);
                    setForm({ ...form, name: "", email: "" });
                    toast.success(`${form.name.trim()} invited`, {
                      description: "Invitation sent through the identity directory.",
                    });
                  }}
                  className="h-8 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Send invitation
                </button>
                <button
                  onClick={() => setInviting(false)}
                  className="h-8 rounded border border-border px-3 text-[12.5px] hover:bg-muted"
                >
                  Cancel
                </button>
              </div>
            </div>
          </Panel>
        )}

        <div className="grid gap-4 [@media(min-width:1700px)]:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
          <Panel
            title="People"
            subtitle={`${s.users.length} users in the ${t("tenant.bank.name")} tenant`}
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-[12.5px]">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-2 py-2 font-medium">Role</th>
                    <th className="px-2 py-2 font-medium">Branch</th>
                    <th className="px-2 py-2 font-medium text-right">Authored</th>
                    <th className="px-2 py-2 font-medium text-right">Approved</th>
                    <th className="px-2 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {s.users.map((u) => {
                    const flagged = conflicts.some((c) => c.slug === u.slug);
                    return (
                      <tr
                        key={u.slug}
                        onClick={() => setSelected(u.slug)}
                        className={cn(
                          "cursor-pointer align-top hover:bg-muted/60",
                          selected === u.slug && "bg-muted",
                        )}
                      >
                        <td className="px-4 py-2">
                          <p className="flex items-center gap-1.5 font-medium text-foreground">
                            {u.name}
                            {flagged && (
                              <AlertTriangle className="h-3.5 w-3.5 text-flag-foreground" />
                            )}
                          </p>
                          <p className="text-[11.5px] text-muted-foreground">{u.email}</p>
                        </td>
                        <td className="px-2 py-2">
                          <select
                            value={u.role}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => {
                              const next = e.target.value as RoleId;
                              setUserRole(u.slug, next, actor);
                              const after = sodConflicts(
                                s.users.map((x) => (x.slug === u.slug ? { ...x, role: next } : x)),
                              ).filter((c) => c.slug === u.slug);
                              if (after.length)
                                toast.warning(`Segregation of duties: ${u.name}`, {
                                  description: after[0]!.detail,
                                });
                              else
                                toast.success(
                                  `${u.name} is now ${ROLES.find((r) => r.id === next)!.label}`,
                                );
                            }}
                            className="h-8 w-44 rounded border border-border bg-surface px-1.5 text-[12px] text-foreground"
                          >
                            {ROLES.map((r) => (
                              <option key={r.id} value={r.id}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-2 py-2 text-muted-foreground">{u.branch}</td>
                        <td className="px-2 py-2 text-right tabular-nums text-foreground">
                          {u.authored}
                        </td>
                        <td className="px-2 py-2 text-right tabular-nums text-foreground">
                          {u.approved}
                        </td>
                        <td className="px-2 py-2">
                          <span
                            className={cn(
                              "rounded border px-1.5 py-0.5 text-[10.5px] capitalize",
                              STATUS_TONE[u.status],
                            )}
                          >
                            {u.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          <div className="space-y-4">
            <Panel title={user.name} subtitle={`${role.label} · ${user.branch}`}>
              <div className="space-y-3 px-4 py-3">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]">
                  {[
                    ["Email", user.email],
                    ["Last active", user.lastActive],
                    ["Delegated authority", user.delegation],
                    ["Memos authored", String(user.authored)],
                    ["Memos approved", String(user.approved)],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt className="field-label">{k}</dt>
                      <dd className="mt-0.5 text-foreground">{v}</dd>
                    </div>
                  ))}
                </dl>
                <div>
                  <p className="field-label">What this role can do</p>
                  <ul className="mt-1 space-y-1">
                    {role.permissions.map((p) => (
                      <li key={p} className="flex gap-1.5 text-[12px] text-muted-foreground">
                        <span>—</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1.5 text-[11.5px] text-muted-foreground">{role.summary}</p>
                </div>
                {userConflicts.length > 0 && (
                  <div className="rounded border border-flag/35 bg-flag-soft px-2.5 py-2">
                    {userConflicts.map((c) => (
                      <p key={c.detail} className="text-[12px] text-flag-foreground">
                        {c.severity === "blocked" ? "Blocked: " : "Watch: "}
                        {c.detail}
                      </p>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {(["active", "suspended"] as const).map((st) => (
                    <button
                      key={st}
                      onClick={() => {
                        setUserStatus(user.slug, st);
                        toast(`${user.name} ${st === "active" ? "reinstated" : "suspended"}`);
                      }}
                      className={cn(
                        "h-8 rounded border px-2.5 text-[12px]",
                        user.status === st
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border bg-surface hover:bg-muted",
                      )}
                    >
                      {st === "active" ? "Active" : "Suspend access"}
                    </button>
                  ))}
                  <Link
                    to="/audit"
                    className="flex h-8 items-center gap-1 rounded border border-border bg-surface px-2.5 text-[12px] hover:bg-muted"
                  >
                    See their decisions in the ledger <ArrowUpRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            </Panel>

            <Panel
              title="Segregation of duties"
              subtitle="The author of a memo may never approve it."
            >
              <ul className="divide-y divide-border">
                {conflicts.map((c) => (
                  <li key={c.slug + c.detail} className="flex items-start gap-2 px-4 py-2.5">
                    <span
                      className={cn(
                        "mt-0.5 shrink-0 rounded border px-1.5 py-0.5 text-[10.5px]",
                        c.severity === "blocked"
                          ? "border-critical/30 bg-critical-soft text-critical"
                          : "border-flag/35 bg-flag-soft text-flag-foreground",
                      )}
                    >
                      {c.severity === "blocked" ? "Blocked" : "Watch"}
                    </span>
                    <p className="text-[12px] text-muted-foreground">{c.detail}</p>
                  </li>
                ))}
                {conflicts.length === 0 && (
                  <li className="px-4 py-4 text-[12.5px] text-muted-foreground">
                    No conflicts. Every approver on this tenant holds no authoring history, and no
                    one holds both an authoring and an approving role.
                  </li>
                )}
              </ul>
            </Panel>

            <div className="rounded border border-border bg-surface p-4">
              <p className="flex items-center gap-1.5 text-[12.5px] font-semibold">
                <Sparkles className="h-3.5 w-3.5 text-primary" /> Ask the copilot
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                "Who can approve a memo above INR 25 crore?" — the copilot reads the role matrix and
                delegated authority and answers with names, limits and the memos each has approved.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
