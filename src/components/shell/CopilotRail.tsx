import { useRouterState } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Sparkles, X, ArrowUp, FileSearch } from "lucide-react";
import { CURRENT_USER } from "@/data/seed";

type Ctx = { scope: string; note: string; actions: string[] };

function contextFor(pathname: string): Ctx {
  if (pathname === "/")
    return {
      scope: "Credit Workbench",
      note: "I can see your four in-flight appraisals and the two open Northwind discrepancies.",
      actions: [
        "Start an appraisal",
        "Summarise what needs my attention",
        "What changed since Friday",
        "Draft the Northwind discrepancy note",
      ],
    };
  if (pathname.includes("/cross-verification"))
    return {
      scope: "Cross-Verification",
      note: "Triangulating declared financials, GST filings, bank credits and bureau conduct.",
      actions: [
        "Explain the turnover gap",
        "Trace the undisclosed lender payment",
        "Rank discrepancies by credit impact",
      ],
    };
  if (pathname.startsWith("/appraisals"))
    return {
      scope: "Appraisal workspace",
      note: "I have this borrower's evidence set, spread and citation trail loaded.",
      actions: ["Summarise this step", "List unresolved items", "Show the evidence behind a figure"],
    };
  if (pathname.startsWith("/memos"))
    return {
      scope: "Memo Library",
      note: "23 memos issued this month across the West Region book.",
      actions: ["Find memos rated CCB-5 or worse", "Compare two memos", "Export a committee pack"],
    };
  if (pathname.startsWith("/audit"))
    return {
      scope: "Audit trail",
      note: "Every figure, override and reason is reconstructable for examiner walk-through.",
      actions: ["Reconstruct a decision", "Show all analyst overrides", "Prepare an examiner pack"],
    };
  return {
    scope: "Administration",
    note: "Control-plane settings shape how every memo in this bank is produced.",
    actions: ["Explain a policy threshold", "What changed in configuration", "Review role permissions"],
  };
}

export function CopilotRail({ onClose }: { onClose: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const ctx = useMemo(() => contextFor(pathname), [pathname]);
  const [draft, setDraft] = useState("");

  return (
    <aside className="hidden w-80 shrink-0 flex-col border-l border-border bg-surface xl:flex">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Sparkles className="h-4 w-4 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold leading-tight">CreditIQ Copilot</p>
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
            Good morning, {CURRENT_USER.name.split(" ")[0]}. {ctx.note}
          </p>
        </div>

        <p className="field-label">Starting actions</p>
        <div className="space-y-1.5">
          {ctx.actions.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => setDraft(a)}
              className="flex w-full items-center gap-2 rounded border border-border bg-surface px-2.5 py-2 text-left text-[12.5px] text-foreground transition-colors hover:border-primary/40 hover:bg-accent"
            >
              <FileSearch className="h-3.5 w-3.5 shrink-0 text-primary" />
              {a}
            </button>
          ))}
        </div>

        <div className="rounded border border-info/25 bg-info-soft p-3">
          <p className="field-label">Grounding</p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-foreground/80">
            Answers cite the filing, statement or page they came from. The copilot never changes a
            figure or a rating; you do.
          </p>
        </div>
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2 rounded border border-border bg-surface p-2 focus-within:ring-1 focus-within:ring-ring">
          <textarea
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask about this screen…"
            className="max-h-28 min-h-[2.5rem] w-full resize-none bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground"
          />
          <button
            type="button"
            aria-label="Send"
            className="grid h-7 w-7 shrink-0 place-items-center rounded bg-primary text-primary-foreground disabled:opacity-40"
            disabled={!draft.trim()}
          >
            <ArrowUp className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}