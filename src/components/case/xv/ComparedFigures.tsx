import type { FindingOutcome, FindingSide, XvItem } from "@/api/types";
import { Chip, type Tone } from "@/components/common/Panel";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { cardElementId, checkElementId, comparesText } from "@/domain/crossVerification";
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

/** The checks of an area that compared figures, whether or not they differ. */
function comparedItems(items: XvItem[]): XvItem[] {
  return items.filter(
    (i) =>
      LOOK[i.finding.outcome] !== undefined &&
      i.finding.sides.filter((s) => s.value !== null && s.value !== undefined && s.value !== "")
        .length >= 2,
  );
}

/** Every pair of figures an area's checks compared, side by side, discrepancy or not (F-19):
 * each figure opens its page, and the row is coloured by the outcome the engine reached. The
 * screen measures nothing: the outcome, the tolerance and the note are the engine's. */
export function ComparedFigures({ caseId, items }: { caseId: string; items: XvItem[] }) {
  const rows = comparedItems(items);
  if (rows.length === 0) return null;
  return (
    <section
      className="rounded border border-border bg-surface"
      aria-label={t("crossVerification.figures.title")}
      data-testid="xv-figures"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 px-4 py-2.5">
        <h3 className={subsectionTitle}>{t("crossVerification.figures.title")}</h3>
        <p className="text-[11.5px] text-muted-foreground">{t("crossVerification.figures.note")}</p>
      </header>
      <ul className="divide-y divide-border border-t border-border">
        {rows.map((item) => (
          <FigureRow key={item.finding.id} caseId={caseId} item={item} />
        ))}
      </ul>
    </section>
  );
}

function FigureRow({ caseId, item }: { caseId: string; item: XvItem }) {
  const f = item.finding;
  const look = LOOK[f.outcome]!;
  const sides = f.sides.filter((s) => s.value !== null && s.value !== undefined && s.value !== "");
  // A discrepancy opens its card; any other check, its row further down the section.
  const target = f.outcome === "fail" ? cardElementId(f.id) : checkElementId(f.id);
  return (
    <li
      className={cn("border-l-[3px] px-4 py-2.5", look.bar)}
      data-testid="xv-figure-row"
      data-rule={f.rule_id}
      data-outcome={f.outcome}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <a
          href={`#${target}`}
          className="min-w-0 break-words text-[12.5px] text-foreground hover:underline"
        >
          <span className="font-mono text-[11.5px] text-muted-foreground">{f.rule_id}</span>
          {" · "}
          <span className="font-medium">{comparesText(f)}</span>
          {f.scope && <span className="text-muted-foreground"> · {f.scope}</span>}
        </a>
        <span className="flex shrink-0 items-center gap-1.5">
          {f.tolerance && (
            <span className="tabular text-[11px] text-muted-foreground">
              {t("crossVerification.figures.tolerance", { tolerance: f.tolerance })}
            </span>
          )}
          {/* A rule with no tolerance compares exactly, so it agrees or differs. */}
          <Chip tone={look.tone}>
            {t(f.tolerance || f.outcome === "incomplete" ? look.label : look.exact)}
          </Chip>
        </span>
      </div>
      <div className="mt-1.5 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
        {sides.map((side, i) => (
          <Side key={`${side.label}-${i}`} caseId={caseId} side={side} valueClass={look.value} />
        ))}
      </div>
      {f.outcome === "incomplete" && f.explanation && (
        <p className="mt-1.5 break-words text-[11.5px] leading-snug text-muted-foreground">
          {f.explanation}
        </p>
      )}
    </li>
  );
}

function Side({
  caseId,
  side,
  valueClass,
}: {
  caseId: string;
  side: FindingSide;
  valueClass: string;
}) {
  const viewer = useDocViewer();
  const e = side.evidence?.[0];
  const value = (
    <span
      className={cn("tabular text-[15px] font-semibold leading-tight", valueClass)}
      data-testid="xv-figure-value"
    >
      {figure(side.value)}
    </span>
  );
  return (
    <div className="min-w-0" data-testid="xv-figure-side">
      <p className="break-words text-[11px] leading-snug text-muted-foreground">{side.label}</p>
      {e ? (
        <button
          type="button"
          onClick={() =>
            viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null })
          }
          title={t("crossVerification.figures.openEvidence", { label: side.label, page: e.page })}
          className="rounded-sm underline decoration-dotted underline-offset-4 hover:decoration-solid focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {value}
        </button>
      ) : (
        value
      )}
    </div>
  );
}
