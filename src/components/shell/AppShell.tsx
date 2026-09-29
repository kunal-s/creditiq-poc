import { Link, useRouterState } from "@tanstack/react-router";
import { useMemo, useState, type ReactNode } from "react";
import { ChevronRight, LogOut, Menu } from "lucide-react";
import { APPRAISAL_STEPS, buildNav, type NavGroup } from "./nav";
import { useCan, useSession, signOut } from "@/domain/session";
import { formatInr, stageLabel, useCase, useLabels } from "@/domain/cases";
import { DocViewerProvider } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

// The prototype's shell (top bar, grouped side navigation with case steps,
// and the case context strip), fed by the engine API. On phones the side
// navigation becomes a menu sheet (docs/functional-requirements.md F-06.2).

/** The case the current route belongs to, if any. */
function useActiveCaseId(): { pathname: string; caseId?: string } {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const appraisal = pathname.match(/^\/appraisals\/([^/]+)/)?.[1];
  if (appraisal && appraisal !== "new") return { pathname, caseId: decodeURIComponent(appraisal) };
  const docready = pathname.match(/^\/docready\/([^/]+)/)?.[1];
  if (docready) return { pathname, caseId: decodeURIComponent(docready) };
  return { pathname };
}

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
  const { pathname, caseId } = useActiveCaseId();
  const session = useSession();
  const nav = useMemo(buildNav, []);
  const visible: NavGroup[] = nav.filter((group) => session?.user.navGroups.includes(group.id));

  return (
    <>
      {visible.map((group) => (
        <div key={group.id} className="mb-4 px-2.5">
          <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.09em] text-sidebar-foreground/45">
            {group.group}
          </p>
          <ul className="space-y-px">
            {group.items.map((item) => {
              if (item.step && !caseId) return null;
              const to =
                item.step === "appraisal"
                  ? `/appraisals/${encodeURIComponent(caseId!)}/${item.to}`
                  : item.step === "docready"
                    ? `/docready/${encodeURIComponent(caseId!)}/${item.to}`
                    : item.to;
              const active =
                item.to === "/"
                  ? pathname === "/"
                  : pathname === to ||
                    (!item.step &&
                      pathname.startsWith(to + "/") &&
                      to !== "/appraisals" &&
                      to !== "/docready");
              return (
                <li key={`${group.id}-${item.to}`}>
                  <Link
                    to={to}
                    onClick={onNavigate}
                    className={cn(
                      "flex items-center gap-2 rounded px-2 py-1.5 text-[13px] transition-colors",
                      item.step && "pl-4 text-[12.5px]",
                      active
                        ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                    )}
                  >
                    {item.step && (
                      <span
                        className={cn(
                          "h-1.5 w-1.5 shrink-0 rounded-full",
                          active ? "bg-sidebar-primary" : "bg-sidebar-border",
                        )}
                      />
                    )}
                    <span className="truncate">{item.label}</span>
                  </Link>
                </li>
              );
            })}
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

function ContextStrip() {
  const { pathname, caseId } = useActiveCaseId();
  const { data: c } = useCase(caseId);
  const labels = useLabels();
  const canReview = useCan("review.read");
  // The DocReady workspace carries its own case header (its layout route).
  const onAppraisal = pathname.startsWith("/appraisals/");
  if (!caseId || !c || !onAppraisal) return null;

  return (
    <div
      className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-border bg-surface px-4 py-2.5 sm:px-5"
      data-testid="context-strip"
    >
      <div className="min-w-0">
        <span className="truncate text-[14px] font-semibold text-foreground">{c.borrower}</span>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-muted-foreground tabular">
          <span>{c.id}</span>
          <span className="text-border">|</span>
          <span>{labels.constitution(c.constitution)}</span>
          <span className="text-border">|</span>
          <span>{labels.facilities(c.facilities)}</span>
          {c.pan && (
            <>
              <span className="text-border">|</span>
              <span>
                {t("identifier.pan")} {c.pan}
              </span>
            </>
          )}
          {c.gstin && (
            <>
              <span className="text-border">|</span>
              <span>
                {t("identifier.gstin")} {c.gstin}
              </span>
            </>
          )}
          <span className="text-border">|</span>
          <span>{formatInr(c.amount_inr)}</span>
        </div>
      </div>

      <div className="hidden flex-wrap items-center gap-1 md:flex">
        {APPRAISAL_STEPS.map((step) => {
          const to = `/appraisals/${encodeURIComponent(c.id)}/${step.to}`;
          return (
            <Link
              key={step.to}
              to={to}
              className={cn(
                "rounded px-2 py-1 text-[11px] font-medium transition-colors",
                pathname === to
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {t(`step.${step.key}`)}
            </Link>
          );
        })}
      </div>

      <div className="flex items-center gap-5 text-[11px] md:ml-auto">
        <div>
          <span className="field-label block">{t("term.stage")}</span>
          <span className="text-[12px] text-foreground">{stageLabel(c.stage)}</span>
        </div>
        <div>
          <span className="field-label block">{t("term.rm")}</span>
          <span className="text-[12px] text-foreground">{c.rm}</span>
        </div>
        {c.open_review_items > 0 && canReview && (
          <Link
            to="/exceptions"
            className="rounded border border-flag/40 bg-flag-soft px-2 py-1 text-[11px] font-medium text-flag-foreground"
          >
            {c.open_review_items} {t("term.reviewItemsOpen")}
            <ChevronRight className="ml-0.5 inline h-3 w-3" />
          </Link>
        )}
      </div>
    </div>
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
            <ContextStrip />
            <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
          </DocViewerProvider>
        </div>
      </div>
    </div>
  );
}
