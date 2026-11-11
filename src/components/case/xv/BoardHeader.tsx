import { Link } from "@tanstack/react-router";
import type { CrossVerificationView } from "@/api/types";
import { t } from "@/config/terminology";
import { formatStamp } from "@/domain/crossVerification";
import { useCan } from "@/domain/session";
import { headerButton } from "./styles";

/** One line on where the board stands, from the view's counts. */
function summaryLine(view: CrossVerificationView): string {
  if (view.items.length === 0) return t("crossVerification.summary.notRun");
  const { total, adjudicated } = view.counts;
  const notRun = view.items.filter((i) => i.finding.outcome === "incomplete").length;
  if (total === 0)
    return notRun > 0
      ? t("crossVerification.summary.noneNotRun", { n: notRun })
      : t("crossVerification.summary.none");
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
  const canQueue = useCan("review.read");
  const meta = view ? metaLine(view) : "";
  return (
    <div className="border-b border-border bg-surface px-4 py-4 sm:px-6" data-testid="xv-header">
      {/* As every step's header: what it is, then its actions under it. */}
      <div className="min-w-0">
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
            title={view?.run ? t("crossVerification.meta.runId", { id: view.run.id }) : undefined}
          >
            {meta}
          </p>
        )}
      </div>
      {/* The way on is the bar at the foot of the step; the queue is here while there is
          something in it to decide. */}
      {view && canQueue && view.counts.total > view.counts.adjudicated && (
        <div className="mt-3 flex max-w-full flex-wrap items-center gap-2">
          <Link to="/review" className={headerButton} data-testid="xv-exception-queue">
            {t("crossVerification.header.queue")}
          </Link>
        </div>
      )}
    </div>
  );
}
