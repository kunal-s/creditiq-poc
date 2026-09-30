import { AlertTriangle, ShieldCheck } from "lucide-react";
import type { Readiness } from "@/api/types";
import { ScoreBar } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { countItems, readyForCredit, useTaxonomy } from "@/domain/checklist";
import { cn } from "@/lib/utils";

/** Readiness against the gates, in one summary (F-13.4, F-13.5): the verdict,
 * the weighted score, the counts by status and each gate. */
export function ReadinessSummary({ r }: { r: Readiness }) {
  const taxonomy = useTaxonomy();
  const counts = countItems(r.items);
  const ready = readyForCredit(r);
  const score = Math.round(r.score_pct);
  const gates = [
    { label: t("readiness.reviewGate"), threshold: r.gate_pct, met: r.gate_met },
    ...(taxonomy.data
      ? [
          {
            label: t("readiness.disbursementGate"),
            threshold: taxonomy.data.disbursement_gate_threshold,
            met: r.score_pct >= taxonomy.data.disbursement_gate_threshold && r.blocking_open === 0,
          },
        ]
      : []),
  ];
  const statuses = [
    { key: "satisfied", n: counts.satisfied, tone: "text-positive" },
    { key: "insufficient", n: counts.insufficient, tone: "text-flag-foreground" },
    { key: "missing", n: counts.missing, tone: "text-destructive" },
    { key: "in_review", n: counts.in_review, tone: "text-info" },
    { key: "waived", n: counts.waived, tone: "text-muted-foreground" },
  ] as const;

  return (
    <div
      className={cn(
        "rounded border px-4 py-3",
        ready ? "border-positive/40 bg-positive-soft/60" : "border-border bg-surface",
      )}
      data-testid="checklist-summary"
    >
      <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
        <div
          className="flex min-w-0 flex-1 items-start gap-2.5"
          data-testid="gate-banner"
          data-ready={ready}
        >
          {ready ? (
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          )}
          <div className="min-w-0">
            <p
              className={cn(
                "text-[13px] font-semibold",
                ready ? "text-positive" : "text-destructive",
              )}
            >
              {ready
                ? t("readinessGates.readyForCredit")
                : t("readiness.notReady", { score, gate: Math.round(r.gate_pct) })}
            </p>
            <p
              className="mt-0.5 max-w-2xl text-[12px] text-muted-foreground"
              data-testid="blocking-gaps"
            >
              {r.blocking_open > 0
                ? t("readiness.blockingOpen", { n: r.blocking_open })
                : t("readiness.noBlocking")}
            </p>
          </div>
        </div>

        <div className="w-full min-w-[14rem] sm:w-72">
          <div className="flex items-baseline justify-between">
            <span className="field-label">{t("readiness.score")}</span>
            <span
              className="tabular text-[22px] font-semibold leading-none"
              data-testid="readiness-score"
            >
              {score}%
            </span>
          </div>
          <ScoreBar
            className="mt-1.5 h-2"
            score={r.score_pct}
            gate={r.gate_pct}
            blocking={r.blocking_open}
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border pt-3">
        <dl className="flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
          {statuses.map((s) => (
            <div key={s.key} className="flex gap-1">
              <dt className="text-muted-foreground">{t(`docStatus.${s.key}`)}</dt>
              <dd
                className={cn("tabular font-semibold", s.n > 0 ? s.tone : "text-muted-foreground")}
              >
                {s.n}
              </dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          {gates.map((g) => (
            <span
              key={g.label}
              className={cn(
                "rounded border px-2 py-0.5 text-[11.5px]",
                g.met
                  ? "border-positive/40 bg-positive-soft text-positive"
                  : "border-border bg-surface-muted/50 text-muted-foreground",
              )}
              data-testid="gate"
              title={t("readiness.threshold", { threshold: Math.round(g.threshold), score })}
            >
              {g.label} {Math.round(g.threshold)}% ·{" "}
              {g.met ? t("readiness.met") : t("readiness.notMet")}
            </span>
          ))}
        </div>
      </div>
      {r.provisional && (
        <p className="mt-2 text-[12px] text-flag-foreground" data-testid="provisional">
          {t("checklist.provisionalHelp")}
        </p>
      )}
    </div>
  );
}
