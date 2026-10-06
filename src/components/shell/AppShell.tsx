import { Link, useRouterState } from "@tanstack/react-router";
import { useMemo, useState, type ReactNode } from "react";
import { LogOut, Menu } from "lucide-react";
import { buildNav, type NavGroup, type NavItem } from "./nav";
import { CaseNav } from "./CaseNav";
import { useSession, signOut } from "@/domain/session";
import { DocViewerProvider } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

// The prototype's shell (top bar and grouped side navigation), fed by the
// engine API. A case's header and tabs live in its layout route. On phones
// the side navigation becomes a menu sheet (docs/functional-requirements.md
// F-06.2).

function TopBar({ menu }: { menu: ReactNode }) {
  const session = useSession();

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-sidebar-border bg-sidebar px-4 text-sidebar-foreground">
      {menu}
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
            aria-label={t("action.signOut")}
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

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const session = useSession();
  const nav = useMemo(buildNav, []);
  const allowed = (item: NavItem) =>
    !item.permission || (session?.user.permissions.includes(item.permission) ?? false);
  const visible: NavGroup[] = nav
    .filter((group) => session?.user.navGroups.includes(group.id))
    .map((group) => ({ ...group, items: group.items.filter(allowed) }))
    .filter((group) => group.items.length > 0);
  // Cases stays active inside a case; New case only on its own screen.
  const isActive = (to: string) =>
    to === "/"
      ? pathname === "/" || (pathname.startsWith("/appraisals/") && pathname !== "/appraisals/new")
      : pathname === to || pathname.startsWith(to + "/");

  const openCase = /^\/appraisals\/([^/]+)/.exec(pathname)?.[1];
  const caseId = openCase && openCase !== "new" ? decodeURIComponent(openCase) : undefined;

  return (
    <>
      {caseId && <CaseNav caseId={caseId} pathname={pathname} onNavigate={onNavigate} />}
      {visible.map((group) => (
        <div key={group.id} className="mb-4 px-2.5">
          <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.09em] text-sidebar-foreground/45">
            {group.group}
          </p>
          <ul className="space-y-px">
            {group.items.map((item) => (
              <li key={`${group.id}-${item.to}`}>
                <Link
                  to={item.to}
                  onClick={onNavigate}
                  className={cn(
                    "flex items-center gap-2 rounded px-2 py-1.5 text-[13px] transition-colors",
                    isActive(item.to)
                      ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                  )}
                >
                  <span className="truncate">{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  );
}

function SideNav() {
  return (
    <nav className="hidden w-60 shrink-0 flex-col overflow-y-auto border-r border-sidebar-border bg-sidebar py-3 text-sidebar-foreground md:flex">
      <NavLinks />
    </nav>
  );
}

function MobileMenu() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          aria-label={t("action.openMenu")}
          className="grid h-8 w-8 place-items-center rounded text-sidebar-foreground/80 hover:bg-sidebar-accent md:hidden"
        >
          <Menu className="h-4 w-4" />
        </button>
      </SheetTrigger>
      <SheetContent
        side="left"
        className="w-64 border-sidebar-border bg-sidebar p-0 py-3 text-sidebar-foreground"
      >
        <SheetTitle className="sr-only">{t("action.menu")}</SheetTitle>
        <NavLinks onNavigate={() => setOpen(false)} />
      </SheetContent>
    </Sheet>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <TopBar menu={<MobileMenu />} />
      <div className="flex min-h-0 flex-1">
        <SideNav />
        <div className="flex min-w-0 flex-1 flex-col">
          <DocViewerProvider>
            <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
          </DocViewerProvider>
        </div>
      </div>
    </div>
  );
}
