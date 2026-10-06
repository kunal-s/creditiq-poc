import { createFileRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PageHeader";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

// Administration (FRD §6): what the published configuration says and who may
// do what. Read-only: an administrator publishes a new version outside the app.

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [{ title: `${t("page.admin.title")} — ${t("tenant.product.name")}` }],
  }),
  component: AdminLayout,
});

const SECTIONS = [
  { to: "/admin", key: "configuration" },
  { to: "/admin/policy", key: "policy" },
  { to: "/admin/checklist", key: "checklist" },
  { to: "/admin/document-types", key: "documentTypes" },
  { to: "/admin/users", key: "users" },
] as const;

function AdminLayout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <div>
      <PageHeader
        eyebrow={t("page.admin.eyebrow")}
        title={t("page.admin.title")}
        purpose={t("page.admin.purpose")}
      />
      <nav
        className="flex gap-1 overflow-x-auto border-b border-border px-4 py-2 sm:px-6"
        aria-label={t("page.admin.sections")}
      >
        {SECTIONS.map((s) => (
          <Link
            key={s.to}
            to={s.to}
            data-testid={`admin-${s.key}`}
            className={cn(
              "shrink-0 rounded-full px-3 py-1 text-[12px] font-medium transition-colors",
              pathname.replace(/\/$/, "") === s.to
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
            )}
          >
            {t(`nav.admin.${s.key}`)}
          </Link>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
