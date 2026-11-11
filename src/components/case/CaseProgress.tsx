import { Link } from "@tanstack/react-router";
import { ArrowRight, CheckCircle2, CircleDashed, Circle } from "lucide-react";
import type { CaseDetail } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { CASE_TABS, caseTabPath } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { readinessBreakdown, readyForCredit, useChecklist } from "@/domain/checklist";
import { useCrossVerification } from "@/domain/crossVerification";
import { useCam } from "@/domain/findings";
import { usePolicy } from "@/domain/policy";
import { useCan } from "@/domain/session";
import { memoSections, submissionState } from "@/domain/submission";
import { cn } from "@/lib/utils";

// Where a created case stands, one line per stage after the documents, each from the engine's own
// record (the same reads the steps make, so the two never disagree), then the one thing to do next.
// A stage the role cannot read is left out.
//
// Test ids: case-progress, case-progress-row (data-row, data-state), case-progress-next (data-to).

type State = "done" | "open" | "waiting";
type Row = { key: string; state: State; text: string; hash?: string };

const MARK: Record<State, { icon: typeof Circle; tone: string }> = {
  done: { icon: CheckCircle2, tone: "text-positive" },
  open: { icon: CircleDashed, tone: "text-flag-foreground" },
  waiting: { icon: Circle, tone: "text-muted-foreground" },
};

/** The path of a step, by its tab key. */
const pathOf = (caseId: string, key: string) =>
  caseTabPath(
    caseId,
    CASE_TABS.find((tab) => tab.key === key)!,
  );

export function CaseProgressCard({ c }: { c: CaseDetail }) {
  const canChecks = useCan("finding.read");
  const canOutputs = useCan("output.read");
  const checklist = useChecklist(c.id).data;
  const board = useCrossVerification(c.id).data;
  const policy = usePolicy(c.id).data;
  const cam = useCam(c.id).data;

  const rows: Row[] = [];
  if (checklist) {
    const b = readinessBreakdown(checklist.items);
    rows.push({
      key: "completeness",
      state: readyForCredit(checklist) ? "done" : "open",
      text: t("caseProgress.documents", { n: b.satisfied, total: b.total }),
    });
  }
  if (canChecks && board) {
    const open = board.counts.total - board.counts.adjudicated;
    const notRun = board.items.filter((i) => i.finding.outcome === "incomplete").length;
    rows.push({
      key: "crossVerification",
      state: open > 0 ? "open" : notRun > 0 ? "open" : "done",
      text:
        open > 0
          ? t("caseProgress.xvOpen", { n: open })
          : notRun > 0
            ? t("caseProgress.xvNotRun", { n: notRun })
            : t("caseProgress.xvClear"),
    });
  }
  if (canChecks && policy?.counts) {
    const d = policy.counts.deviations;
    rows.push({
      key: "policy",
      state: d > 0 ? "open" : "done",
      text: d > 0 ? t("caseProgress.deviations", { n: d }) : t("caseProgress.noDeviation"),
    });
  }
  if (canOutputs && cam) {
    const m = memoSections(cam);
    rows.push({
      key: "outputs",
      state: m.edited > 0 ? "done" : "open",
      text: t("caseProgress.memo", { n: m.edited, total: m.total }),
    });
    if (board && checklist) {
      const s = submissionState(board, checklist, cam);
      rows.push({
        key: "rating",
        state: s.recommendation ? "done" : "open",
        text: s.recommendation
          ? t("caseProgress.recommendationDone")
          : t("caseProgress.recommendationOpen"),
        ...(s.recommendation ? {} : { hash: "recommendation" }),
      });
      rows.push({
        key: "submission",
        state: s.unmet.length === 0 ? "done" : "waiting",
        text:
          s.unmet.length === 0
            ? t("caseProgress.submissionOpen")
            : t("caseProgress.submissionClosed", { n: s.unmet.length }),
      });
    }
  }
  const next = rows.find((r) => r.state === "open");

  return (
    <Panel title={t("caseProgress.title")} testId="case-progress">
      <ol className="divide-y divide-border">
        {rows.map((r) => {
          const { icon: Icon, tone } = MARK[r.state];
          return (
            <li key={r.key} data-testid="case-progress-row" data-row={r.key} data-state={r.state}>
              <Link
                to={pathOf(c.id, r.key)}
                {...(r.hash ? { hash: r.hash } : {})}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-muted"
              >
                <Icon className={cn("size-4 shrink-0", tone)} aria-hidden />
                <span className="w-44 shrink-0 text-[12.5px] font-medium text-foreground max-sm:w-32">
                  {t(`caseTab.${r.key}`)}
                </span>
                <span className="min-w-0 flex-1 text-[12.5px] text-muted-foreground">{r.text}</span>
                <span className="sr-only">({t(`caseProgress.state.${r.state}`)})</span>
              </Link>
            </li>
          );
        })}
      </ol>
      {next && (
        <div className="flex justify-end border-t border-border px-4 py-3">
          <Link
            to={pathOf(c.id, next.key)}
            {...(next.hash ? { hash: next.hash } : {})}
            className="inline-flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
            data-testid="case-progress-next"
            data-to={next.key}
          >
            {t(`caseProgress.next.${next.key}`)} <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      )}
    </Panel>
  );
}
