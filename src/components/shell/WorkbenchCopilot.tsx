import { Link, useRouterState } from "@tanstack/react-router";
import { useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { FileText, Sparkles, X } from "lucide-react";
import { buildNav } from "./nav";
import { useAssistantDock } from "./AssistantDock";
import { t } from "@/config/terminology";
import { useCases } from "@/domain/cases";
import { useReviewQueue } from "@/domain/review";
import { useCan, useSession } from "@/domain/session";

// The copilot beside the screens outside an appraisal, as the original design: a greeting with
// where the desk stands, starting actions that open the screens that answer them, and the
// grounding note. Questions are asked inside an appraisal, where the assistant reads its
// documents and rules; here the message box says so rather than pretending to answer.

function dayPart(): "morning" | "afternoon" | "evening" {
  const hour = new Date().getHours();
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
}

export function WorkbenchCopilot() {
  const dock = useAssistantDock();
  const canRead = useCan("case.read");
  const setAvailable = dock?.setAvailable;
  useEffect(() => {
    if (!canRead || !setAvailable) return;
    setAvailable(true);
    return () => setAvailable(false);
  }, [canRead, setAvailable]);
  if (!dock || !canRead || !dock.open || !dock.node) return null;
  return createPortal(<Panel onClose={() => dock.setOpen(false)} />, dock.node);
}

function Panel({ onClose }: { onClose: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const session = useSession();
  const canCreate = useCan("case.create");
  const canReview = useCan("review.read");
  const cases = useCases();
  const review = useReviewQueue();
  const screen = useMemo(() => {
    const items = buildNav().flatMap((g) => g.items);
    const hit = items
      .filter((i) => (i.to === "/" ? pathname === "/" : pathname.startsWith(i.to)))
      .sort((a, b) => b.to.length - a.to.length)[0];
    return hit?.label ?? t("tenant.product.name");
  }, [pathname]);
  const open = (cases.data ?? []).filter((c) => c.stage !== "Completed");
  const items = (review.data ?? []).filter((i) => i.status === "open").length;
  const pressing = [...open].sort(
    (a, b) =>
      (b.files_altered ?? 0) * 1000 +
      (b.files_attention ?? 0) * 10 +
      b.open_review_items -
      ((a.files_altered ?? 0) * 1000 + (a.files_attention ?? 0) * 10 + a.open_review_items),
  )[0];
  const name = session?.user.name.split(" ")[0] ?? "";

  const actions: { to: string; params?: { caseId: string }; label: string }[] = [
    ...(canCreate ? [{ to: "/appraisals/new", label: t("copilot.workbench.start") }] : []),
    ...(canReview ? [{ to: "/review", label: t("copilot.workbench.attention") }] : []),
    ...(pressing
      ? [
          {
            to: "/appraisals/$caseId",
            params: { caseId: pressing.id },
            label: t("copilot.workbench.pressing", { borrower: pressing.borrower }),
          },
        ]
      : []),
    { to: "/docready", label: t("copilot.workbench.readiness") },
  ];

  return (
    <section
      className="flex h-full min-h-0 flex-col bg-surface text-foreground"
      data-testid="workbench-copilot"
    >
      <header className="flex shrink-0 items-start gap-2 border-b border-border px-3 py-3">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[13.5px] font-semibold leading-tight tracking-tight">
            {t("assistant.title")}
          </h2>
          <p className="truncate text-[11px] leading-tight text-muted-foreground">
            {t("copilot.workbench.context", { screen })}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("assistant.close")}
          className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </header>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <p className="rounded border border-border bg-muted/60 px-3 py-3 text-[13px] leading-relaxed">
          {t(`assistant.greeting.${dayPart()}`, { name })}{" "}
          {t("copilot.workbench.state", { n: open.length, items })}
        </p>
        <div>
          <p className="mb-2 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
            {t("assistant.startingActions")}
          </p>
          <ul className="flex flex-col gap-2">
            {actions.map((a) => (
              <li key={a.label}>
                <Link
                  to={a.to}
                  {...(a.params ? { params: a.params } : {})}
                  className="flex w-full items-center gap-2.5 rounded border border-border bg-surface px-3 py-2.5 text-left text-[13px] text-foreground transition-colors hover:border-primary/40 hover:bg-accent/50"
                >
                  <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                  {a.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded border border-primary/20 bg-accent px-3 py-3">
          <p className="text-[10.5px] font-semibold uppercase tracking-wide text-accent-foreground">
            {t("assistant.groundingTitle")}
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
            {t("assistant.grounding")}
          </p>
        </div>
      </div>
      <div className="shrink-0 border-t border-border p-3">
        <textarea
          disabled
          rows={2}
          placeholder={t("copilot.workbench.ask")}
          aria-label={t("copilot.workbench.ask")}
          className="w-full resize-none rounded border border-border bg-muted/40 px-3 py-2 text-[12.5px] placeholder:text-muted-foreground"
        />
      </div>
    </section>
  );
}
