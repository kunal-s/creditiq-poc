import { useRouterState } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Sparkles, X, ArrowUp, FileSearch } from "lucide-react";
import { useSession } from "@/domain/session";
import { t } from "@/config/terminology";

type Ctx = { scope: string; actions: string[] };

function contextFor(pathname: string): Ctx {
  if (pathname.startsWith("/docready"))
    return {
      scope: t("nav.readinessConsole"),
      actions: ["What is still blocking this file", "Summarise this checklist"],
    };
  if (pathname.startsWith("/appraisals/") && pathname.includes("/spread"))
    return {
      scope: t("page.spread.title"),
      actions: ["Explain this ratio", "Summarise the trend"],
    };
  if (pathname.startsWith("/appraisals/") && pathname.includes("/cross-verification"))
    return { scope: t("page.crossVerification.title"), actions: ["Summarise open findings"] };
  if (pathname.startsWith("/appraisals/"))
    return { scope: t("term.appraisal.title"), actions: ["Summarise this step"] };
  if (pathname.startsWith("/memos"))
    return { scope: t("nav.memoLibrary"), actions: ["Find memos by rating"] };
  if (pathname.startsWith("/audit"))
    return { scope: t("nav.auditLedger"), actions: ["Reconstruct a decision"] };
  if (pathname.startsWith("/admin"))
    return { scope: t("nav.group.admin"), actions: ["What changed in configuration"] };
  return { scope: t("nav.group.workbench"), actions: ["Summarise what needs my attention"] };
}

type Message = { from: "user" | "copilot"; text: string };

export function CopilotRail({ onClose }: { onClose: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const session = useSession();
  const ctx = useMemo(() => contextFor(pathname), [pathname]);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);

  function ask(question: string) {
    if (!question.trim()) return;
    setMessages((prev) => [
      ...prev,
      { from: "user", text: question },
      {
        from: "copilot",
        text: "Not grounded yet in this build — I'll answer from this case's evidence once a case is loaded and the pipeline has run.",
      },
    ]);
    setDraft("");
  }

  return (
    <aside className="hidden w-80 shrink-0 flex-col border-l border-border bg-surface xl:flex">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Sparkles className="h-4 w-4 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold leading-tight">
            {t("tenant.product.name")} Copilot
          </p>
          <p className="truncate text-[11px] text-muted-foreground">Context: {ctx.scope}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close copilot"
          className="grid h-6 w-6 place-items-center rounded text-muted-foreground hover:bg-muted"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        <div className="rounded border border-border bg-surface-muted p-3">
          <p className="text-[12.5px] leading-relaxed text-foreground">
            {session ? `Good morning, ${session.user.name.split(" ")[0]}.` : "Good morning."} Ask
            about this screen, or pick a starting action below.
          </p>
        </div>

        <p className="field-label">Starting actions</p>
        <div className="space-y-1.5">
          {ctx.actions.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => ask(a)}
              className="flex w-full items-center gap-2 rounded border border-border bg-surface px-2.5 py-2 text-left text-[12.5px] text-foreground transition-colors hover:border-primary/40 hover:bg-accent"
            >
              <FileSearch className="h-3.5 w-3.5 shrink-0 text-primary" />
              {a}
            </button>
          ))}
        </div>

        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.from === "user"
                ? "rounded border border-border bg-surface p-3"
                : "rounded border border-info/25 bg-info-soft p-3"
            }
          >
            <p className="text-[12.5px] leading-relaxed text-foreground/90">{m.text}</p>
          </div>
        ))}

        <div className="rounded border border-info/25 bg-info-soft p-3">
          <p className="field-label">Grounding</p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-foreground/80">
            Answers will cite the filing, statement or page they came from. The copilot never
            changes a figure or a rating; you do.
          </p>
        </div>
      </div>

      <div className="border-t border-border p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(draft);
          }}
          className="flex items-end gap-2 rounded border border-border bg-surface p-2 focus-within:ring-1 focus-within:ring-ring"
        >
          <textarea
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask about this screen…"
            className="max-h-28 min-h-[2.5rem] w-full resize-none bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground"
          />
          <button
            type="submit"
            aria-label="Send"
            className="grid h-7 w-7 shrink-0 place-items-center rounded bg-primary text-primary-foreground disabled:opacity-40"
            disabled={!draft.trim()}
          >
            <ArrowUp className="h-3.5 w-3.5" />
          </button>
        </form>
      </div>
    </aside>
  );
}
