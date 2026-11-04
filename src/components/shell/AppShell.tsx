import { Link, useRouterState } from "@tanstack/react-router";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, LogOut, Menu, PanelRight, ShieldCheck } from "lucide-react";
import { api } from "@/api/client";
import { formatDate } from "@/domain/cases";
import { buildNav, type NavGroup, type NavItem } from "./nav";
import { CaseNav } from "./CaseNav";
import { useSession, signOut } from "@/domain/session";
import {
  AssistantDockProvider,
  AssistantDockSlot,
  useAssistantDock,
} from "@/components/shell/AssistantDock";
import { GlobalSearch } from "./GlobalSearch";
import { WorkbenchCopilot } from "./WorkbenchCopilot";
import { useReviewQueue } from "@/domain/review";
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
      {session?.user.permissions.includes("case.read") ? (
        <div className="hidden min-w-0 flex-1 justify-center px-4 md:flex">
          <GlobalSearch />
        </div>
      ) : (
        <div className="flex-1" />
      )}
      {session && (
        <div className="ml-auto flex items-center gap-2">
          <ReviewBell />
          <CopilotToggle />
          <div className="mx-1 hidden h-6 w-px bg-sidebar-border sm:block" />
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

/** The open review items, as a bell: a dot while any wait, and a click opens the queue. */
function ReviewBell() {
  const canReview = useSession()?.user.permissions.includes("review.read") ?? false;
  const queue = useReviewQueue();
  if (!canReview) return null;
  const n = (queue.data ?? []).filter((i) => i.status === "open").length;
  const label = n > 0 ? t("notifications.open", { n }) : t("notifications.none");
  return (
    <Link
      to="/review"
      aria-label={label}
      title={label}
      className="relative grid h-8 w-8 place-items-center rounded text-sidebar-foreground/80 hover:bg-sidebar-accent"
      data-testid="review-bell"
    >
      <Bell className="h-4 w-4" />
      {n > 0 && (
        <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-flag ring-2 ring-sidebar" />
      )}
    </Link>
  );
}

/** The assistant, offered in the top bar where the open screen has one (an appraisal). */
function CopilotToggle() {
  const dock = useAssistantDock();
  if (!dock?.available) return null;
  return (
    <button
      type="button"
      onClick={() => dock.setOpen(!dock.open)}
      aria-pressed={dock.open}
      aria-label={t("assistant.launcher")}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded border px-2 text-[12.5px] font-medium sm:px-3",
        dock.open
          ? "border-sidebar-primary bg-sidebar-primary/20 text-sidebar-accent-foreground"
          : "border-sidebar-primary/60 text-sidebar-primary hover:bg-sidebar-accent",
      )}
      data-testid="assistant-launcher"
    >
      <PanelRight className="h-3.5 w-3.5" />
      <span className="max-sm:sr-only">{t("assistant.topBar")}</span>
    </button>
  );
}

const LAST_CASE_KEY = "creditiq.lastCase";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const session = useSession();
  const nav = useMemo(buildNav, []);
  const allowed = (item: NavItem) =>
    !item.permission || (session?.user.permissions.includes(item.permission) ?? false);
  const visible: NavGroup[] = nav
    .filter((group) => session?.user.navGroups.includes(group.gate ?? group.id))
    .map((group) => ({ ...group, items: group.items.filter(allowed) }))
    // The Appraisal group stays for the open appraisal's steps even where New appraisal is not allowed.
    .filter((group) => group.items.length > 0 || group.id === "appraisal");
  // My appraisals stays active inside an appraisal; New appraisal only on its own screen. Of the
  // items a path falls under, the most specific is active (Settings, not Configuration, at
  // /admin/settings).
  const matches = (to: string) =>
    to === "/" ? pathname === "/" : pathname === to || pathname.startsWith(to + "/");
  const active = visible
    .flatMap((group) => group.items.map((item) => item.to))
    .filter(matches)
    .sort((a, b) => b.length - a.length)[0];
  const isActive = (to: string) => to === active;

  const openCase = /^\/appraisals\/([^/]+)/.exec(pathname)?.[1];
  const inCase = openCase && openCase !== "new" ? decodeURIComponent(openCase) : undefined;
  // Outside an appraisal, the last one opened keeps its steps under New appraisal, as the
  // original design shows them; only while it is still on the list.
  const canRead = session?.user.permissions.includes("case.read") ?? false;
  const cases = useQuery({ queryKey: ["cases"], queryFn: api.listCases, enabled: canRead });
  const [last, setLast] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(LAST_CASE_KEY);
    } catch {
      return null;
    }
  });
  useEffect(() => {
    if (!inCase || inCase === last) return;
    setLast(inCase);
    try {
      sessionStorage.setItem(LAST_CASE_KEY, inCase);
    } catch {
      /* nothing to do */
    }
  }, [inCase, last]);
  const caseId = inCase ?? (last && cases.data?.some((c) => c.id === last) ? last : undefined);

  return (
    <>
      {visible
        .filter((group) => group.items.length > 0 || caseId)
        .map((group) => (
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
            {/* The open appraisal's steps, under New appraisal, as the original design. */}
            {group.id === "appraisal" && caseId && (
              <CaseNav caseId={caseId} pathname={pathname} onNavigate={onNavigate} />
            )}
          </div>
        ))}
    </>
  );
}

/** The foot of the side menu: the configuration every check runs under, and since when. */
function NavFooter() {
  const inForce = useQuery({ queryKey: ["config", "in-force"], queryFn: api.configInForce });
  if (!inForce.data) return null;
  return (
    <p
      className="mt-auto flex items-start gap-1.5 px-4 pb-1 pt-4 text-[10.5px] leading-snug text-sidebar-foreground/45"
      data-testid="nav-footer"
    >
      <ShieldCheck className="mt-px h-3 w-3 shrink-0" aria-hidden />
      {t("nav.footer", { date: formatDate(inForce.data.published_at) })}
    </p>
  );
}

function SideNav() {
  return (
    <nav className="hidden w-60 shrink-0 flex-col overflow-y-auto border-r border-sidebar-border bg-sidebar py-3 text-sidebar-foreground md:flex">
      <NavLinks />
      <NavFooter />
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

/** Outside an appraisal the dock holds the workbench copilot; inside, the appraisal's own. */
function WorkbenchAssistant() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const inCase = /^\/appraisals\/(?!new$)[^/]+/.test(pathname);
  return inCase ? null : <WorkbenchCopilot />;
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <AssistantDockProvider>
      <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
        <TopBar menu={<MobileMenu />} />
        <div className="flex min-h-0 flex-1">
          <SideNav />
          <div className="flex min-w-0 flex-1 flex-col">
            <DocViewerProvider>
              {/* A container: a page lays itself out by the room it has, which the assistant's column
                takes from. */}
              <main className="@container/main min-h-0 flex-1 overflow-y-auto">{children}</main>
            </DocViewerProvider>
          </div>
          <AssistantDockSlot />
          <WorkbenchAssistant />
        </div>
      </div>
    </AssistantDockProvider>
  );
}
