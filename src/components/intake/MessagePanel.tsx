import { Pencil } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import type { CaseProposal } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { type Draft } from "@/domain/intake";
import { messageSpans } from "@/domain/intakeCreate";
import { markRuns, type Mark } from "@/domain/proposal";
import { cn } from "@/lib/utils";

/** The pasted message as it was read: every value taken from it marked, the selected field's span
 * and its candidates stronger, and the parts set aside before reading (headers, quoted text,
 * signatures) greyed. Selecting a field brings its span into view inside the message box only. */
export function MessagePanel({
  text,
  proposal,
  draft,
  selected,
  onEdit,
}: {
  text: string;
  proposal: CaseProposal;
  draft: Draft;
  selected: string | null;
  onEdit: () => void;
}) {
  const box = useRef<HTMLPreElement | null>(null);
  const marks = useMemo(() => {
    const out: Mark[] = (proposal.stripped ?? []).map((s) => ({ ...s.span, level: "stripped" }));
    for (const { key, span } of messageSpans(draft))
      out.push({ ...span, level: key === selected ? "selected" : "found" });
    if (selected) {
      for (const c of proposal.fields[selected]?.candidates ?? []) {
        out.push({ ...c.span, level: "candidate" });
      }
    }
    return out;
  }, [draft, proposal.fields, proposal.stripped, selected]);
  const runs = markRuns(text, marks);

  // Scroll the message box, never the page, to the selected span.
  useEffect(() => {
    const el = box.current;
    const mark = el?.querySelector<HTMLElement>('mark[data-mark="selected"]');
    if (!el || !mark) return;
    const top = mark.offsetTop; // the box is the mark's offset parent
    if (top < el.scrollTop || top + mark.offsetHeight > el.scrollTop + el.clientHeight) {
      el.scrollTo({ top: Math.max(0, top - el.clientHeight / 3), behavior: "smooth" });
    }
  }, [selected]);

  return (
    <Panel
      title={t("newApplication.message")}
      subtitle={t("newApplication.messageClickHelp")}
      action={
        <button
          type="button"
          onClick={onEdit}
          className="flex h-7 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] font-medium text-foreground hover:bg-muted"
        >
          <Pencil className="h-3 w-3" aria-hidden /> {t("newApplication.editMessage")}
        </button>
      }
    >
      <pre
        ref={box}
        className="relative max-h-80 overflow-auto whitespace-pre-wrap break-words px-4 py-3 font-sans text-[12.5px] leading-relaxed text-foreground"
        data-testid="message-view"
      >
        {runs.map((run) =>
          run.level ? (
            <mark
              key={run.start}
              data-mark={run.level}
              title={run.level === "stripped" ? t("newApplication.strippedHelp") : undefined}
              className={cn(
                "rounded-[2px] text-foreground",
                run.level === "selected" && "bg-primary/25 ring-1 ring-primary",
                run.level === "candidate" && "bg-flag/35 ring-1 ring-flag",
                run.level === "found" && "bg-accent",
                run.level === "stripped" && "bg-transparent text-muted-foreground/60",
              )}
            >
              {run.text}
            </mark>
          ) : (
            <span key={run.start}>{run.text}</span>
          ),
        )}
      </pre>
    </Panel>
  );
}
