import type { FindingOutcome, FindingSide, XvItem } from "@/api/types";
import { Chip, type Tone } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { comparedItems, comparesText } from "@/domain/crossVerification";
import { cn } from "@/lib/utils";
import { subsectionTitle } from "./styles";

/** How a compared pair reads, by the engine's outcome: green where the figures agree within the
 * rule's tolerance, red where they do not, amber where the check could not compare them. */
const LOOK: Partial<
  Record<FindingOutcome, { tone: Tone; value: string; bar: string; label: string; exact: string }>
> = {
  pass: {
    tone: "positive",
    value: "text-positive",
    bar: "border-l-positive",
    label: "crossVerification.figures.matches",
    exact: "crossVerification.figures.agrees",
  },
  fail: {
    tone: "critical",
    value: "text-destructive",
    bar: "border-l-destructive",
    label: "crossVerification.figures.differs",
    exact: "crossVerification.figures.exactDiffers",
  },
  incomplete: {
    tone: "flag",
    value: "text-muted-foreground",
    bar: "border-l-flag",
    label: "crossVerification.figures.incomplete",
    exact: "crossVerification.figures.incomplete",
  },
};

function figure(v: FindingSide["value"]): string {
  if (v === null || v === undefined || v === "") return "—";
  return typeof v === "number" ? formatInr(v) : String(v);
}

/** Every pair of figures an area's checks compared, discrepancy or not (F-19), as a compact list
 * beside the selected check's detail: each row coloured by the outcome the engine reached, and
 * selecting it shows that check on the right. The screen measures nothing: the outcome and the
 * tolerance are the engine's. */
export function ComparedFigures({
  items,
  selected,
  onSelect,
  panelId,
}: {
  items: XvItem[];
  selected: string | null;
  onSelect: (findingId: string) => void;
  /** The panel the selection shows in, for assistive technology. */
  panelId: string;
}) {
  const rows = comparedItems(items);
  if (rows.length === 0) return null;
  return (
    <section
      className="min-w-0 rounded border border-border bg-surface"
      aria-label={t("crossVerification.figures.title")}
      data-testid="xv-figures"
    >
      <header className="px-3 py-2">
        <h3 className={subsectionTitle}>{t("crossVerification.figures.title")}</h3>
        <p className="text-[11.5px] text-muted-foreground">
          {t("crossVerification.figures.select")}
        </p>
      </header>
      <ul className="divide-y divide-border border-t border-border">
        {rows.map((item) => (
          <FigureRow
            key={item.finding.id}
            item={item}
            selected={item.finding.id === selected}
            onSelect={() => onSelect(item.finding.id)}
            panelId={panelId}
          />
        ))}
      </ul>
    </section>
  );
}

function FigureRow({
  item,
  selected,
  onSelect,
  panelId,
}: {
  item: XvItem;
  selected: boolean;
  onSelect: () => void;
  panelId: string;
}) {
  const f = item.finding;
  const look = LOOK[f.outcome]!;
  const sides = f.sides.filter((s) => s.value !== null && s.value !== undefined && s.value !== "");
  return (
    <li
      className={cn("border-l-[3px]", look.bar, selected && "bg-info-soft")}
      data-testid="xv-figure-row"
      data-rule={f.rule_id}
      data-outcome={f.outcome}
      data-finding={f.id}
      data-selected={selected ? "true" : "false"}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        aria-controls={panelId}
        className="block w-full px-3 py-2 text-left transition-colors hover:bg-foreground/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        data-testid="xv-figure-select"
      >
        <span className="flex flex-wrap items-start justify-between gap-x-2 gap-y-0.5">
          <span className="min-w-0 break-words text-[12px] text-foreground">
            <span className="font-medium">{comparesText(f)}</span>
            {f.scope && <span className="text-muted-foreground"> · {f.scope}</span>}
          </span>
          {/* A rule with no tolerance compares exactly, so it agrees or differs. */}
          <Chip tone={look.tone}>
            {t(f.tolerance || f.outcome === "incomplete" ? look.label : look.exact)}
          </Chip>
        </span>
        <span className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5">
          {sides.map((side, i) => (
            <span key={`${side.label}-${i}`} className="min-w-0" data-testid="xv-figure-side">
              <span
                className={cn("tabular text-[13px] font-semibold", look.value)}
                data-testid="xv-figure-value"
              >
                {figure(side.value)}
              </span>{" "}
              <span className="text-[11px] text-muted-foreground">{side.label}</span>
            </span>
          ))}
        </span>
        {f.tolerance && (
          <span className="mt-0.5 block text-[11px] text-muted-foreground">
            {t("crossVerification.figures.tolerance", { tolerance: f.tolerance })}
          </span>
        )}
      </button>
    </li>
  );
}
