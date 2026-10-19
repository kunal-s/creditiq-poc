import type { XvArea, XvItem } from "@/api/types";
import { AreaFactsSection } from "@/components/case/CrossVerification";
import { t } from "@/config/terminology";
import {
  areaHeadingId,
  areaSectionId,
  comparedItems,
  withOutcome,
} from "@/domain/crossVerification";
import { cn } from "@/lib/utils";
import { ComparedFigures } from "./ComparedFigures";
import { CheckPanel, DiscrepancyCard } from "./DiscrepancyCard";
import { IncompleteList } from "./IncompleteList";
import { PassedList } from "./PassedList";
import { AREA_STATUS } from "./styles";

/** The areas whose section opens with every compared pair of figures (ComparedFigures), the
 * selected one's card or check beside them. */
export const FIGURE_AREAS: XvArea["area"][] = ["turnover"];

/** The comparison a figure area shows beside its list when none has been picked: its first
 * discrepancy, else its first comparison. */
export function defaultPick(items: XvItem[]): string | null {
  const compared = comparedItems(items);
  return (compared.find((i) => i.finding.outcome === "fail") ?? compared[0])?.finding.id ?? null;
}

/** "8 rules · 2 discrepancies · 1 could not be checked · 4 passed", as the engine counted them;
 * the parts with nothing in them are left out. */
function countsLine(area: XvArea): string {
  const parts = [
    area.rules === 1
      ? t("crossVerification.count.ruleOne")
      : t("crossVerification.count.ruleMany", { n: area.rules }),
  ];
  if (area.discrepancies > 0)
    parts.push(
      area.discrepancies === 1
        ? t("crossVerification.count.discrepancyOne")
        : t("crossVerification.count.discrepancyMany", { n: area.discrepancies }),
    );
  if (area.incomplete > 0)
    parts.push(t("crossVerification.count.incomplete", { n: area.incomplete }));
  if (area.passed > 0) parts.push(t("crossVerification.count.passed", { n: area.passed }));
  if (area.not_applicable > 0)
    parts.push(t("crossVerification.count.notApplicable", { n: area.not_applicable }));
  return parts.join(" · ");
}

/** One area of the board: its discrepancies ranked by credit impact within the area, the checks
 * that could not run, those that passed or did not apply, and the facts the checks compared. */
export function AreaSection({
  caseId,
  area,
  items,
  expanded,
  onToggle,
  picked,
  onPick,
}: {
  caseId: string;
  area: XvArea;
  /** The area's items, in the engine's order. */
  items: XvItem[];
  expanded: ReadonlySet<string>;
  onToggle: (findingId: string) => void;
  /** In a figure area, the comparison shown beside the list (the default pick when none). */
  picked?: string | null | undefined;
  onPick?: ((findingId: string) => void) | undefined;
}) {
  const status = AREA_STATUS[area.status];
  const Icon = status.icon;
  const figures = FIGURE_AREAS.includes(area.area);
  const compared = figures ? comparedItems(items) : [];
  const chosen =
    compared.find((i) => i.finding.id === picked) ??
    compared.find((i) => i.finding.id === defaultPick(items));
  // In a figure area the compared discrepancies sit beside the list; any other is listed below.
  const beside = new Set(compared.map((i) => i.finding.id));
  const discrepancies = withOutcome(items, "fail");
  const listed = discrepancies.filter((i) => !beside.has(i.finding.id));
  const panelId = `${areaSectionId(area.area)}-panel`;
  return (
    <section
      id={areaSectionId(area.area)}
      aria-labelledby={areaHeadingId(area.area)}
      className="min-w-0 scroll-mt-4 space-y-3"
      data-testid={areaSectionId(area.area)}
      data-status={area.status}
    >
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-1 border-b border-border pb-2">
        <div className="min-w-0">
          {/* Focused when the area's card on the overview is clicked. */}
          <h2
            id={areaHeadingId(area.area)}
            tabIndex={-1}
            className="flex items-center gap-2 rounded-sm text-[16px] font-semibold tracking-tight text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon className={cn("h-4 w-4 shrink-0", status.text)} aria-hidden />
            <span className="min-w-0 break-words">
              {t(`crossVerification.area.${area.area}.title`)}
            </span>
          </h2>
          <p className="mt-0.5 break-words text-[12px] text-muted-foreground">
            {t(`crossVerification.area.${area.area}.purpose`)}
          </p>
        </div>
        <p
          className="tabular break-words text-[11.5px] text-muted-foreground"
          data-testid="xv-area-counts"
        >
          {countsLine(area)}
        </p>
      </header>

      {/* Turnover is read as figures: every pair the checks compared, agreeing or not, in a
          compact list on the left, and the one selected beside it: a discrepancy's card, with its
          sources, gap, evidence and decision, or any other check's sources and gap. */}
      {figures && chosen && (
        <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
          <ComparedFigures
            items={items}
            selected={chosen.finding.id}
            panelId={panelId}
            onSelect={(id) => {
              onPick?.(id);
              const item = compared.find((i) => i.finding.id === id);
              if (item?.finding.outcome === "fail" && !expanded.has(id)) onToggle(id);
            }}
          />
          <div id={panelId} className="min-w-0 lg:sticky lg:top-4" data-testid="xv-figure-panel">
            {chosen.finding.outcome === "fail" ? (
              <DiscrepancyCard
                caseId={caseId}
                item={chosen}
                expanded={expanded.has(chosen.finding.id)}
                onToggle={() => onToggle(chosen.finding.id)}
              />
            ) : (
              <CheckPanel key={chosen.finding.id} caseId={caseId} item={chosen} />
            )}
          </div>
        </div>
      )}

      {discrepancies.length === 0 ? (
        <p
          className="rounded border border-border bg-surface px-4 py-2.5 text-[12.5px] text-muted-foreground"
          data-testid="xv-area-none"
        >
          {t("crossVerification.section.none")}
        </p>
      ) : (
        listed.length > 0 && (
          <div className="space-y-3" data-testid="xv-discrepancies">
            {listed.map((item) => (
              <DiscrepancyCard
                key={item.finding.id}
                caseId={caseId}
                item={item}
                expanded={expanded.has(item.finding.id)}
                onToggle={() => onToggle(item.finding.id)}
              />
            ))}
          </div>
        )
      )}
      <IncompleteList
        caseId={caseId}
        items={withOutcome(items, "incomplete")}
        count={area.incomplete}
      />
      <PassedList
        passed={withOutcome(items, "pass")}
        notApplicable={withOutcome(items, "not_applicable")}
        counts={{ passed: area.passed, notApplicable: area.not_applicable }}
      />
      <AreaFactsSection caseId={caseId} area={area.area} />
    </section>
  );
}
