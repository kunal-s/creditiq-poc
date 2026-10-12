import { AlertTriangle } from "lucide-react";
import type { CrossVerificationView } from "@/api/types";
import { t } from "@/config/terminology";
import { itemById, openBlocking } from "@/domain/crossVerification";

/** While a blocking discrepancy is open: how many, and the one of greatest credit impact on the
 * board (the engine's first_blocking), with the way straight to its card. */
export function BlockingBanner({
  view,
  onAdjudicate,
}: {
  view: CrossVerificationView;
  onAdjudicate: (findingId: string) => void;
}) {
  if (!view.blocked) return null;
  const first = itemById(view, view.first_blocking)?.finding;
  const n = view.counts.blocking_open;
  // "Serious" when every open blocking discrepancy is serious; otherwise "blocking".
  const kind = openBlocking(view).every((i) => i.finding.severity === "serious")
    ? "serious"
    : "blocking";
  return (
    <div
      className="flex flex-wrap items-start gap-3 rounded border border-destructive/30 bg-destructive/10 px-4 py-3"
      data-testid="xv-banner"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
      <div className="min-w-0 flex-1 basis-64">
        <p className="text-[13px] font-semibold text-destructive">
          {n === 1
            ? t(`crossVerification.banner.${kind}One`)
            : t(`crossVerification.banner.${kind}Many`, { n })}
        </p>
        {first && (
          <p className="mt-0.5 break-words text-[12.5px] leading-relaxed text-foreground/80">
            <span className="break-all font-mono text-[11.5px] font-medium text-foreground">
              {first.ref ?? first.rule_id}
            </span>
            {" · "}
            {first.explanation}
            {first.policy_ref && (
              <span className="text-muted-foreground">
                {" · "}
                {first.policy_ref}
              </span>
            )}
          </p>
        )}
      </div>
      {first && (
        <button
          type="button"
          onClick={() => onAdjudicate(first.id)}
          className="h-8 shrink-0 rounded bg-destructive px-3 text-[12.5px] font-medium text-destructive-foreground hover:opacity-90"
          data-testid="xv-adjudicate-now"
          data-target={first.id}
        >
          {t("crossVerification.banner.adjudicateNow")}
        </button>
      )}
    </div>
  );
}
