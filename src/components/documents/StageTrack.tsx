import { t } from "@/config/terminology";
import { DOC_STEPS, docTrack } from "@/domain/documents";
import type { LogicalDocument } from "@/api/types";
import { cn } from "@/lib/utils";

const TONE = {
  running: "bg-info animate-pulse",
  attention: "bg-flag",
  done: "bg-positive",
  off: "bg-border",
} as const;

/** A document's progress through received, quality, split, classified and
 * extracted, as five segments and the name of the step it is on. */
export function StageTrack({ doc }: { doc: LogicalDocument | undefined }) {
  const { done, state } = docTrack(doc);
  const current = Math.min(done, DOC_STEPS.length - 1);
  const label =
    state === "off"
      ? t(`documentStatus.${doc!.status}`)
      : state === "done"
        ? t("documentTrack.complete")
        : state === "running"
          ? t(`documentTrack.running.${DOC_STEPS[current]}`)
          : t("documentTrack.attention", { step: t(`documentTrack.step.${DOC_STEPS[current]}`) });
  return (
    <span
      className="inline-flex items-center gap-1.5"
      data-testid="stage-track"
      data-step={state === "done" ? "complete" : DOC_STEPS[current]}
      data-state={state}
      title={DOC_STEPS.map((s) => t(`documentTrack.step.${s}`)).join(" → ")}
    >
      <span className="flex gap-0.5" aria-hidden>
        {DOC_STEPS.map((step, i) => (
          <span
            key={step}
            className={cn(
              "h-1.5 w-3 rounded-full",
              state === "off"
                ? TONE.off
                : i < done
                  ? TONE.done
                  : i === current
                    ? TONE[state]
                    : "bg-border",
            )}
          />
        ))}
      </span>
      <span
        className={cn(
          "text-[11px]",
          state === "attention" ? "font-medium text-flag-foreground" : "text-muted-foreground",
        )}
      >
        {label}
      </span>
    </span>
  );
}
