import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { t, tOr } from "@/config/terminology";
import { confidencePct } from "@/domain/extraction";
import { Chip, type Tone } from "./Panel";

/** Confidence with its composition on hover (F-17.1, F-17.3). The tone
 * follows the engine's routing (below threshold means in review); the
 * screen applies no threshold of its own. */
export function ConfidenceChip({
  confidence,
  components,
  flagged,
}: {
  confidence: number | null | undefined;
  components?: Record<string, number> | undefined;
  flagged?: boolean;
}) {
  if (typeof confidence !== "number") return <span className="text-muted-foreground">—</span>;
  const tone: Tone = flagged ? "flag" : "positive";
  const parts = Object.entries(components ?? {});
  const chip = (
    <Chip tone={tone}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      <span className="tabular" data-testid="confidence">
        {confidencePct(confidence)}
      </span>
    </Chip>
  );
  if (parts.length === 0) return chip;
  const composition = parts
    .map(([k, v]) => `${tOr(`confidenceComponent.${k}`, k)} ${confidencePct(v)}`)
    .join(" · ");
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            tabIndex={0}
            aria-label={`${t("data.composition")}: ${composition}`}
            title={composition}
          >
            {chip}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <p className="font-medium">{t("data.composition")}</p>
          <ul className="mt-1 space-y-0.5">
            {parts.map(([k, v]) => (
              <li key={k} className="flex justify-between gap-4">
                <span>{tOr(`confidenceComponent.${k}`, k)}</span>
                <span className="tabular">{confidencePct(v)}</span>
              </li>
            ))}
          </ul>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
