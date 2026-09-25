import { Link, useRouterState } from "@tanstack/react-router";
import { useMemo, useState, type ReactNode } from "react";
import {
  Search,
  Sparkles,
  ChevronRight,
  ShieldCheck,
  Bell,
  PanelRightClose,
  LogOut,
} from "lucide-react";
import { buildNav } from "./nav";
import { STAGE_ROUTE } from "@/api/types";
import { useCases, findCase } from "@/domain/cases";
import { useSession, signOut } from "@/domain/session";
import { t } from "@/config/terminology";
import { CopilotRail } from "@/components/shell/CopilotRail";
import { cn } from "@/lib/utils";

function useActiveAppraisal() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { data: cases } = useCases();
  const match = pathname.match(/^\/appraisals\/([\w-]+)/);
  const appraisal = match ? findCase(cases, match[1]) : undefined;
  return { pathname, appraisal };
}

function TopBar({
  copilotOpen,
  onToggleCopilot,
}: {
  copilotOpen: boolean;
  onToggleCopilot: () => void;
}) {
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
      <div className="relative mx-auto hidden w-full max-w-md lg:block">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-sidebar-foreground/60" />
        <input
          aria-label="Search borrowers, memos and identifiers"
          placeholder={t("search.placeholder")}
          className="h-8 w-full rounded border border-sidebar-border bg-sidebar-accent/60 pl-8 pr-14 text-[13px] text-sidebar-accent-foreground placeholder:text-sidebar-foreground/55 focus:outline-none focus:ring-1 focus:ring-sidebar-ring"
        />
        <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-sidebar-border px-1.5 py-0.5 text-[10px] text-sidebar-foreground/60">
          ⌘K
        </kbd>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          aria-label="Notifications"
          className="relative grid h-8 w-8 place-items-center rounded text-sidebar-foreground/80 hover:bg-sidebar-accent"
        >
          <Bell className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onToggleCopilot}
          className={cn(
            "flex h-8 items-center gap-1.5 rounded border px-2.5 text-[12px] font-medium transition-colors",
            copilotOpen
              ? "border-sidebar-primary/60 bg-sidebar-primary/15 text-sidebar-primary"
              : "border-sidebar-border text-sidebar-foreground/85 hover:bg-sidebar-accent",
          )}
        >
          {copilotOpen ? (
            <PanelRightClose className="h-3.5 w-3.5" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          {t("action.toggleCopilot")}
        </button>
        {session && (
          <div className="ml-1 flex items-center gap-2 border-l border-sidebar-border pl-3">
            <div className="hidden flex-col items-end leading-tight sm:flex">
              <span className="text-[12.5px] font-medium text-sidebar-accent-foreground">
                {session.user.name}
              </span>
              <span className="text-[11px] text-sidebar-foreground/70">
                {session.user.roleLabel}
              </span>
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
      </div>
    </header>
  );
}

function SideNav() {
  const { pathname, appraisal } = useActiveAppraisal();
  const session = useSession();
  const nav = useMemo(buildNav, []);
  const visibleNav = nav.filter((group) => session?.user.navGroups.includes(group.id));
  const stepBaseId = appraisal?.id;

  return (
    <nav className="hidden w-60 shrink-0 flex-col overflow-y-auto border-r border-sidebar-border bg-sidebar py-3 text-sidebar-foreground md:flex">
      {visibleNav.map((group) => (
        <div key={group.id} className="mb-4 px-2.5">
          <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.09em] text-sidebar-foreground/45">
            {group.group}
          </p>
          <ul className="space-y-px">
            {group.items.map((item) => {
              if (item.step && !stepBaseId) return null;
              const to = item.step ? `/appraisals/${stepBaseId}/${item.to}` : item.to;
              const active =
                item.to === "/"
                  ? pathname === "/"
                  : pathname === to || pathname.startsWith(to + "/");
              const isCurrentStep =
                item.step && appraisal && STAGE_ROUTE[appraisal.stage] === item.to;
              return (
                <li key={item.label}>
                  <Link
                    to={to}
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
                          isCurrentStep ? "bg-sidebar-primary" : "bg-sidebar-border",
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
      <div className="mt-auto px-4 pt-3 text-[11px] leading-snug text-sidebar-foreground/45">
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="h-3 w-3" /> {t("tenant.footer.dataPlaneNote")}
        </span>
        <span className="mt-1 block">{t("tenant.footer.buildNote")}</span>
      </div>
    </nav>
  );
}

const PIPELINE_STAGES = [
  "identity",
  "data",
  "spread",
  "crossVerification",
  "draft",
  "submission",
] as const;

function ContextStrip() {
  const { appraisal } = useActiveAppraisal();
  if (!appraisal) return null;
  const stageOrder: (typeof appraisal.stage)[] = [
    "Identity",
    "Data",
    "Spread",
    "Cross-Verification",
    "Draft",
    "Submission",
  ];
  const currentIndex = stageOrder.indexOf(appraisal.stage);

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-border bg-surface px-5 py-2.5">
      <div className="flex min-w-0 items-center gap-3">
        <div className="min-w-0">
          <Link
            to="/appraisals/$id/identity"
            params={{ id: appraisal.id }}
            className="truncate text-[14px] font-semibold text-foreground hover:text-primary"
          >
            {appraisal.borrower}
          </Link>
          <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground tabular">
            <span>PAN {appraisal.pan}</span>
            <span className="text-border">|</span>
            <span>GSTIN {appraisal.gstin}</span>
            <span className="text-border">|</span>
            <span>{appraisal.id}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1">
        {stageOrder.map((stage, i) => {
          const done = appraisal.stage === "Completed" || i < currentIndex;
          const current = i === currentIndex;
          return (
            <Link
              key={stage}
              to={"/appraisals/$id/" + STAGE_ROUTE[stage]}
              params={{ id: appraisal.id }}
              className={cn(
                "rounded px-2 py-1 text-[11px] font-medium transition-colors",
                current
                  ? "bg-primary text-primary-foreground"
                  : done
                    ? "bg-positive-soft text-positive hover:bg-positive-soft/70"
                    : "text-muted-foreground hover:bg-muted",
              )}
            >
              {t(`stage.${PIPELINE_STAGES[i]}`)}
            </Link>
          );
        })}
      </div>

      <div className="ml-auto flex items-center gap-5 text-[11px]">
        <div>
          <span className="field-label block">Analyst</span>
          <span className="text-[12px] text-foreground">{appraisal.analyst}</span>
        </div>
        <div>
          <span className="field-label block">Relationship manager</span>
          <span className="text-[12px] text-foreground">{appraisal.rm}</span>
        </div>
        {appraisal.discrepancies > 0 && (
          <Link
            to="/appraisals/$id/cross-verification"
            params={{ id: appraisal.id }}
            className="rounded border border-flag/40 bg-flag-soft px-2 py-1 text-[11px] font-medium text-flag-foreground"
          >
            {appraisal.discrepancies} open discrepanc{appraisal.discrepancies === 1 ? "y" : "ies"}
            <ChevronRight className="ml-0.5 inline h-3 w-3" />
          </Link>
        )}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [copilotOpen, setCopilotOpen] = useState(true);

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <TopBar copilotOpen={copilotOpen} onToggleCopilot={() => setCopilotOpen((v) => !v)} />
      <div className="flex min-h-0 flex-1">
        <SideNav />
        <div className="flex min-w-0 flex-1 flex-col">
          <ContextStrip />
          <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
        </div>
        {copilotOpen && <CopilotRail onClose={() => setCopilotOpen(false)} />}
      </div>
    </div>
  );
}
