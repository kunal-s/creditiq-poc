import { Link } from "@tanstack/react-router";
import { ArrowLeft, ArrowRight, Lock } from "lucide-react";
import type { CrossVerificationView } from "@/api/types";
import { t } from "@/config/terminology";
import { formatStamp } from "@/domain/crossVerification";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { headerButton } from "./styles";

/** One line on where the board stands, from the view's counts. */
function summaryLine(view: CrossVerificationView): string {
  if (view.items.length === 0) return t("crossVerification.summary.notRun");
  const { total, adjudicated } = view.counts;
  if (total === 0) return t("crossVerification.summary.none");
  if (adjudicated >= total) {
    return total === 1
      ? t("crossVerification.summary.decidedOne")
      : t("crossVerification.summary.decidedMany", { n: total });
  }
  return total === 1
    ? t("crossVerification.summary.one")
    : t("crossVerification.summary.many", { n: total });
}

/** "1 of 7 adjudicated · XR-000021-003 · 18 rules across 9 sources · 09 Oct 2026, 14:00": the
 * decisions made, when there is anything to decide, and the run the board shows, if any. */
function metaLine(view: CrossVerificationView): string {
  const { counts, run } = view;
  const parts: string[] = [];
  if (counts.total > 0) {
    parts.push(
      t("crossVerification.meta.adjudicated", {
        adjudicated: counts.adjudicated,
        total: counts.total,
      }),
    );
  }
  if (run) {
    parts.push(
      t("crossVerification.meta.run", {
        id: run.id,
        rules: run.rules,
        sources: run.sources,
        at: formatStamp(run.at),
      }),
    );
  }
  return parts.join(" · ");
}

/** The tab's header: what the board found, and the way on to the draft, closed while a
 * blocking discrepancy is open. */
export function BoardHeader({
  caseId,
  view,
}: {
  caseId: string;
  view: CrossVerificationView | undefined;
}) {
  const canOutputs = useCan("output.read");
  const canQueue = useCan("review.read");
  const meta = view ? metaLine(view) : "";
  return (
    <div
      className="flex flex-wrap items-end justify-between gap-3 border-b border-border bg-surface px-4 py-4 sm:px-6"
      data-testid="xv-header"
    >
      <div className="min-w-0 flex-1 basis-[26rem]">
        <p className="field-label break-words">{t("crossVerification.kicker", { id: caseId })}</p>
        <h2 className="text-[19px] font-semibold tracking-tight text-foreground">
          {t("page.crossVerification.title")}
        </h2>
        {view && (
          <p
            className="mt-1 max-w-3xl text-[13px] text-muted-foreground"
            data-testid="xv-summary-line"
          >
            {summaryLine(view)}
          </p>
        )}
        {meta && (
          <p
            className="tabular mt-1 break-words text-[11.5px] text-muted-foreground"
            data-testid="xv-meta-line"
          >
            {meta}
          </p>
        )}
      </div>
      {view && (
        <div className="flex max-w-full flex-wrap items-center gap-2">
          {canOutputs && (
            <Link
              to="/appraisals/$caseId/policy"
              params={{ caseId }}
              hash="financials"
              className={headerButton}
              data-testid="xv-back-spread"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden />{" "}
              {t("crossVerification.header.spread")}
            </Link>
          )}
          {canQueue && (
            <Link to="/review" className={headerButton} data-testid="xv-exception-queue">
              {t("crossVerification.header.queue")}
            </Link>
          )}
          {canOutputs && (
            <Link
              to="/appraisals/$caseId/outputs"
              params={{ caseId }}
              search={{ view: "cam" }}
              disabled={view.blocked}
              tabIndex={view.blocked ? 0 : undefined}
              title={view.blocked ? t("crossVerification.header.continueBlocked") : undefined}
              className={cn(
                "inline-flex h-9 items-center gap-1.5 rounded px-3 text-[12.5px] font-medium",
                view.blocked
                  ? "cursor-not-allowed border border-border bg-muted text-muted-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90",
              )}
              data-testid="xv-continue"
            >
              {view.blocked && <Lock className="h-3.5 w-3.5" aria-hidden />}
              {t("crossVerification.header.continue")}
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
