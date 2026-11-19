import { ChevronRight } from "lucide-react";
import { useState } from "react";
import type { Recalculation, RecalculationChange } from "@/api/types";
import { Chip, Panel, type Tone } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { formatDate } from "@/domain/cases";
import { useRecalculations } from "@/domain/extraction";
import { money } from "@/domain/units";
import { cn } from "@/lib/utils";

// The Extractions tab's record of each approved change and what it moved when the appraisal was
// recalculated: the value, its document, what it was and is now, who changed and approved it, and
// every figure, policy norm, cross-check, readiness and authority that reads differently since.
//
// Test ids:
//   recalc-panel      the panel (hidden while there is no recalculation)
//   recalc-entry      one recalculation (data-field: the value changed); recalc-change each result
//                     that moved (data-area, data-key); recalc-nothing when none did
//   recalc-more       show every recalculation, not only the latest

const AREAS: RecalculationChange["area"][] = ["figure", "norm", "check", "readiness", "authority"];

/** The tone an outcome reads in once it has changed: a small signal, beside its word. */
const OUTCOME_TONE: Record<string, Tone> = {
  pass: "positive",
  deviation: "critical",
  fail: "critical",
  cannot_evaluate: "flag",
  incomplete: "flag",
  not_applicable: "muted",
};

/** One side of a change, as the change's kind writes it. */
function sideText(change: RecalculationChange, side: "before" | "after"): string {
  const value = change[side];
  const detail = side === "before" ? change.detail_before : change.detail_after;
  if (value === null || value === undefined) return t("recalculation.none");
  if (change.kind === "amount" && typeof value === "number") return money(value);
  if (change.kind === "percent") return `${value}%`;
  if (change.kind === "outcome") {
    const word =
      change.area === "norm"
        ? t(`policy.outcome.${value}`)
        : t(`recalculation.check.${value as string}`);
    return detail ? `${word} (${detail})` : word;
  }
  return String(value);
}

export function RecalculationPanel({ caseId }: { caseId: string }) {
  const recalculations = useRecalculations(caseId);
  const [all, setAll] = useState(false);
  const list = recalculations.data ?? [];
  if (list.length === 0) return null;
  const shown = all ? list : list.slice(0, 1);
  return (
    <Panel
      title={t("recalculation.title")}
      subtitle={t("recalculation.subtitle")}
      testId="recalc-panel"
    >
      <ul className="divide-y divide-border">
        {shown.map((r) => (
          <Entry key={r.id} r={r} />
        ))}
      </ul>
      {list.length > 1 && (
        <button
          type="button"
          aria-expanded={all}
          onClick={() => setAll((v) => !v)}
          className="flex w-full items-center gap-1.5 border-t border-border px-4 py-2 text-left text-[12px] font-medium text-primary hover:bg-surface-muted"
          data-testid="recalc-more"
        >
          <ChevronRight
            className={cn("size-3 transition-transform", all && "rotate-90")}
            aria-hidden
          />
          {all ? t("recalculation.showLatest") : t("recalculation.showAll", { n: list.length })}
        </button>
      )}
    </Panel>
  );
}

function Entry({ r }: { r: Recalculation }) {
  const w = r.trigger;
  const moved = r.changes ?? [];
  return (
    <li className="space-y-2 px-4 py-3" data-testid="recalc-entry" data-field={w.field_value_id}>
      <div className="space-y-0.5">
        <p className="text-[12.5px] font-medium text-foreground">
          {t("recalculation.changedValue", { label: w.label })}
        </p>
        <p className="break-words text-[11.5px] text-muted-foreground">
          {w.file_name
            ? t("recalculation.inDocument", { document: w.document, file: w.file_name })
            : w.document}
        </p>
        <p className="tabular text-[12.5px] text-foreground" data-testid="recalc-from-to">
          {t("recalculation.fromTo", {
            from: w.from_value ?? t("recalculation.none"),
            to: w.to_value ?? t("recalculation.none"),
          })}
        </p>
        <p className="text-[11px] text-muted-foreground">
          {w.changed_by
            ? t("recalculation.by", {
                maker: w.changed_by,
                checker: r.approved_by,
                at: formatDate(r.at),
              })
            : t("recalculation.approvedBy", { checker: r.approved_by, at: formatDate(r.at) })}
        </p>
        {w.reason && (
          <p className="text-[11.5px] text-muted-foreground">
            {t("recalculation.reason", { reason: w.reason })}
          </p>
        )}
      </div>
      <div className="space-y-1.5">
        <p className="field-label">{t("recalculation.moved")}</p>
        {moved.length === 0 ? (
          <p className="text-[12px] text-muted-foreground" data-testid="recalc-nothing">
            {t("recalculation.nothing")}
          </p>
        ) : (
          AREAS.map((area) => {
            const changes = moved.filter((c) => c.area === area);
            if (changes.length === 0) return null;
            return (
              <div key={area} className="space-y-0.5">
                <p className="text-[11px] font-medium text-muted-foreground">
                  {t(`recalculation.area.${area}`)}
                </p>
                <ul className="space-y-1">
                  {changes.map((c) => (
                    <li
                      key={c.key}
                      className="text-[12px] leading-snug"
                      data-testid="recalc-change"
                      data-area={c.area}
                      data-key={c.key}
                    >
                      <span className="block text-foreground">{c.label}</span>
                      <span className="tabular flex flex-wrap items-center gap-x-1.5 text-muted-foreground">
                        <span>{sideText(c, "before")}</span>
                        <span aria-hidden>→</span>
                        {c.kind === "outcome" && typeof c.after === "string" ? (
                          <Chip tone={OUTCOME_TONE[c.after] ?? "muted"}>
                            {sideText(c, "after")}
                          </Chip>
                        ) : (
                          <span className="font-medium text-foreground">
                            {sideText(c, "after")}
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })
        )}
      </div>
    </li>
  );
}
