import type { AssessmentGate } from "@/api/types";
import { t } from "@/config/terminology";

/** One condition of the F-13 gate, worded for the screen. The engine sends the blockers as
 * keys; the wording lives in the terminology, so the three conditions read the same wherever
 * they are shown. */
export type GateCondition = { key: string; met: boolean; label: string };

export function gateConditions(gate: AssessmentGate): GateCondition[] {
  const blocked = (key: string) => (gate.blockers ?? []).includes(key);
  const score = Math.round(gate.score_pct ?? 0);
  const required = Math.round(gate.gate_pct ?? 0);
  return [
    {
      key: "review_gate",
      met: !blocked("review_gate"),
      label: t(
        blocked("review_gate")
          ? "assessment.condition.reviewGateUnmet"
          : "assessment.condition.reviewGate",
        { score, gate: required },
      ),
    },
    {
      key: "blocking_items",
      met: !blocked("blocking_items"),
      label: blocked("blocking_items")
        ? t("assessment.condition.blockingItems", { n: gate.blocking_open ?? 0 })
        : t("assessment.condition.blockingItemsClear"),
    },
    {
      key: "open_exceptions",
      met: !blocked("open_exceptions"),
      label: blocked("open_exceptions")
        ? t("assessment.condition.openExceptions", { n: gate.open_exceptions ?? 0 })
        : t("assessment.condition.openExceptionsClear"),
    },
  ];
}
