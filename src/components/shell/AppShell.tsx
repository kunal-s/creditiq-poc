import { Link, useRouterState } from "@tanstack/react-router";
import { useMemo, type ReactNode } from "react";
import { LogOut } from "lucide-react";
import { buildNav } from "./nav";
import { useSession, signOut } from "@/domain/session";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";

function TopBar() {
  const session = useSession();

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-sidebar-border bg-sidebar px-4 text-sidebar-foreground">
      <Link to="/" className="flex items-center gap-2.5">
        <span className="grid h-7 w-7 place-items-center rounded bg-sidebar-primary text-[13px] font-bold text-sidebar-primary-foreground">
          {t("tenant.brand.mark")}
        </span>
        <span className="text-[15px] font-semibold tracking-tight text-sidebar-accent-foreground">
          {t("tenant.product.name")}
        </span>
      </Link>
      <div className="hidden h-6 w-px bg-sidebar-border md:block" />
      <div className="hidden min-w-0 flex-col leading-tight md:flex">
        <span className="truncate text-[13px] font-medium text-sidebar-accent-foreground">
          {t("tenant.bank.name")}
        </span>
        <span className="truncate text-[11px] text-sidebar-foreground/70">
          {t("tenant.bank.unit")}
        </span>
      </div>
      {session && (
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden flex-col items-end leading-tight sm:flex">
            <span className="text-[12.5px] font-medium text-sidebar-accent-foreground">
              {session.user.name}
            </span>
            <span className="text-[11px] text-sidebar-foreground/70">{session.user.roleLabel}</span>
          </div>
          <span className="grid h-8 w-8 place-items-center rounded-full bg-sidebar-accent text-[12px] font-semibold text-sidebar-accent-foreground">
            {session.user.initials}
          </span>
          <button
            type="button"
            aria-label="Sign out"
            onClick={() => void signOut()}
            className="grid h-8 w-8 place-items-center rounded text-sidebar-foreground/80 hover:bg-sidebar-accent"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </header>
  );
}

function SideNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const session = useSession();
  const nav = useMemo(buildNav, []);
  const visibleNav = nav.filter((group) => session?.user.navGroups.includes(group.id));

  return (
    <nav className="hidden w-60 shrink-0 flex-col overflow-y-auto border-r border-sidebar-border bg-sidebar py-3 text-sidebar-foreground md:flex">
      {visibleNav.map((group) => (
        <div key={group.id} className="mb-4 px-2.5">
          <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.09em] text-sidebar-foreground/45">
            {group.group}
          </p>
          <ul className="space-y-px">
            {group.items.map((item) => {
              const active =
                item.to === "/"
                  ? pathname === "/"
                  : pathname === item.to || pathname.startsWith(item.to + "/");
              return (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className={cn(
                      "flex items-center gap-2 rounded px-2 py-1.5 text-[13px] transition-colors",
                      active
                        ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                    )}
                  >
                    <span className="truncate">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <SideNav />
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
