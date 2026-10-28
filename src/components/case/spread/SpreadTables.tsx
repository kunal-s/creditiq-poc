import type {
  CellWorking,
  CrossVerificationView,
  Evidence,
  Spread,
  SpreadRow,
  TurnoverYear,
} from "@/api/types";
import { t } from "@/config/terminology";
import {
  cellText,
  figureFor,
  figureVerdict,
  rowsOf,
  turnoverSources,
  type FigureVerdict,
} from "@/domain/spread";
import { inUnit, unitHeading, useDisplayUnit } from "@/domain/units";
import { cn } from "@/lib/utils";

/** A figure picked for the source panel: what it is, for which year, and where it was read. */
export type Picked = {
  id: string;
  label: string;
  fy: string;
  text: string;
  unit: string;
  evidence: Evidence[];
  manual: boolean;
  /** How the figure was arrived at, where the engine gives it (a statement line or a derived line). */
  working?: CellWorking | null;
};

/** The picked figure as the spread now has it: an edit recalculates the spread, and the panel beside the
 * table follows rather than showing the figure as it was. Figures that are not statement lines stay as picked. */
export function pickedNow(spread: Spread, picked: Picked | null): Picked | null {
  if (!picked) return picked;
  for (const row of spread.rows) {
    const i = spread.columns.findIndex((c) => `${row.key}:${c.fy}` === picked.id);
    const cell = i >= 0 ? row.cells[i] : undefined;
    if (cell)
      return {
        ...picked,
        text: cellText(cell.value, row.unit),
        evidence: cell.evidence ?? [],
        manual: cell.relies_on_manual,
        working: cell.working ?? null,
      };
  }
  return picked;
}

/** A figure in a table: the marker says where it came from (grey: a page; amber: a person's
 * entry), the colour what the checks made of it, and a click puts it in the source panel. */
export function FigureCell({
  picked,
  selected,
  tone,
  strong,
  onPick,
}: {
  picked: Picked;
  selected: boolean;
  tone?: string | undefined;
  strong?: boolean;
  onPick: (p: Picked) => void;
}) {
  if (picked.text === "—") return <span className="text-muted-foreground">—</span>;
  return (
    <button
      type="button"
      onClick={() => onPick(picked)}
      aria-pressed={selected}
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 tabular transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected
          ? "border-primary/50 bg-surface shadow-sm"
          : "border-transparent hover:border-border hover:bg-surface",
        strong && "font-semibold",
        tone ?? "text-foreground",
      )}
      data-testid="spread-figure"
      data-selected={selected ? "true" : "false"}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 shrink-0 rounded-full",
          picked.manual
            ? "bg-flag"
            : picked.evidence.length > 0
              ? "bg-muted-foreground/50"
              : "bg-transparent",
        )}
        aria-hidden
      />
      {picked.text}
    </button>
  );
}

function Card({
  title,
  subtitle,
  children,
  testId,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  testId: string;
}) {
  return (
    <section className="min-w-0 rounded border border-border bg-surface" data-testid={testId}>
      {/* The tab above names the table; the heading stays for a screen reader. */}
      <header className="px-4 pb-2.5 pt-3">
        <h3 className="sr-only">{title}</h3>
        <p className="text-[12px] text-muted-foreground">{subtitle}</p>
      </header>
      {children}
    </section>
  );
}

/** Year columns' header cells, the selected year shaded down the table. */
function YearHeads({ years, selected }: { years: string[]; selected: string }) {
  return (
    <>
      {years.map((fy) => (
        <th
          key={fy}
          scope="col"
          className={cn(
            "px-4 py-2 text-right font-medium",
            fy === selected && "bg-info-soft text-foreground",
          )}
        >
          {fy}
        </th>
      ))}
    </>
  );
}

const TH = "border-y border-border text-[11px] uppercase tracking-wide text-muted-foreground";

const VERDICT_TONE: Record<Exclude<FigureVerdict, null>, string> = {
  agrees: "text-positive",
  differs: "text-destructive",
  not_compared: "text-flag-foreground",
};

/** Turnover year by year from every source on file (F-18.1), each figure coloured by what the
 * turnover cross-checks of its year concluded: green where it agrees within tolerance, red where
 * it differs, amber where it could not be compared. */
export function TurnoverByYear({
  years,
  board,
  selected,
  picked,
  onPick,
}: {
  years: TurnoverYear[];
  board: CrossVerificationView | undefined;
  selected: string;
  picked: string | null;
  onPick: (p: Picked) => void;
}) {
  const unit = useDisplayUnit();
  const sources = turnoverSources(years);
  if (sources.length === 0) return null;
  return (
    <Card
      title={t("spreadPage.turnover.title")}
      subtitle={t("spreadPage.turnover.subtitle", { unit: unitHeading(unit) })}
      testId="spread-turnover"
    >
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[480px] text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-4 py-2 text-left font-medium">
                {t("spreadPage.turnover.source")}
              </th>
              <YearHeads years={years.map((y) => y.fy)} selected={selected} />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sources.map(({ source, label }) => (
              <tr key={source} data-testid="spread-turnover-row" data-source={source}>
                <th scope="row" className="px-4 py-2.5 text-left font-medium text-foreground">
                  {label}
                </th>
                {years.map((y) => {
                  const f = figureFor(y, source);
                  const { verdict, checks } = figureVerdict(board, y.fy, source);
                  const id = `turnover:${source}:${y.fy}`;
                  const partial =
                    f?.months_covered !== null &&
                    f?.months_covered !== undefined &&
                    f.months_covered < 12;
                  return (
                    <td
                      key={y.fy}
                      className={cn(
                        "px-4 py-2 text-right align-top",
                        y.fy === selected && "bg-info-soft/40",
                      )}
                      data-testid="spread-turnover-cell"
                      data-fy={y.fy}
                      data-verdict={verdict ?? "none"}
                      title={checks
                        .map((c) => `${c.rule_id} · ${c.compares ?? c.title}`)
                        .join("\n")}
                    >
                      {f && f.value !== null ? (
                        <>
                          <FigureCell
                            picked={{
                              id,
                              label,
                              fy: y.fy,
                              text: inUnit(f.value, unit),
                              unit: unitHeading(unit),
                              evidence: f.evidence ?? [],
                              manual: f.relies_on_manual,
                            }}
                            selected={picked === id}
                            tone={verdict ? VERDICT_TONE[verdict] : undefined}
                            strong={source === "financials"}
                            onPick={onPick}
                          />
                          {verdict && (
                            <span className="sr-only">{t(`spreadPage.verdict.${verdict}`)}</span>
                          )}
                          {partial && (
                            <span className="block text-[11px] text-muted-foreground">
                              {t("spreadPage.turnover.months", { n: f.months_covered ?? 0 })}
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul
        className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border px-4 py-2.5 text-[11.5px] text-muted-foreground"
        data-testid="spread-turnover-legend"
      >
        {(["agrees", "differs", "not_compared"] as const).map((v) => (
          <li key={v} className="flex items-center gap-1.5">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                v === "agrees" ? "bg-positive" : v === "differs" ? "bg-destructive" : "bg-flag",
              )}
              aria-hidden
            />
            {t(`spreadPage.verdict.${v}`)}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** One statement of the spread, line by line and year by year (F-22.1). A figure that relies on
 * a person's entry is marked, and named under the table so it is confirmed before it is used. */
export function StatementTable({
  spread,
  section,
  selected,
  picked,
  onPick,
}: {
  spread: Spread;
  section: "profit_and_loss" | "balance_sheet";
  selected: string;
  picked: string | null;
  onPick: (p: Picked) => void;
}) {
  const unit = useDisplayUnit();
  const rows = rowsOf(spread, section);
  if (rows.length === 0) return null;
  const years = spread.columns.map((c) => c.fy);
  const manual = rows.flatMap((r) =>
    r.cells.flatMap((c, i) => (c.relies_on_manual ? [{ row: r, cell: c, fy: years[i]! }] : [])),
  );
  return (
    <Card
      title={t(`spreadPage.statement.${section}.title`)}
      subtitle={t(`spreadPage.statement.${section}.subtitle`, { unit: unitHeading(unit) })}
      testId={`spread-${section}`}
    >
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[520px] text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-4 py-2 text-left font-medium">
                {t("spreadPage.statement.lineItem")}
              </th>
              <YearHeads years={years} selected={selected} />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row) => (
              <StatementRow
                key={row.key}
                row={row}
                years={years}
                selected={selected}
                picked={picked}
                onPick={onPick}
              />
            ))}
          </tbody>
        </table>
      </div>
      {manual.length > 0 && (
        <ul className="border-t border-border bg-critical-soft px-4 py-2.5 text-[12px] text-destructive">
          {manual.map(({ row, cell, fy }) => (
            <li key={`${row.key}-${fy}`} data-testid="spread-manual-note">
              {cell.evidence?.[0]
                ? t("spreadPage.statement.manualPage", {
                    label: row.label,
                    fy,
                    page: cell.evidence[0].page,
                  })
                : t("spreadPage.statement.manual", { label: row.label, fy })}
            </li>
          ))}
        </ul>
      )}
      <p className="border-t border-border px-4 py-2.5 text-[11.5px] text-muted-foreground">
        {t("spreadPage.statement.footnote")}
      </p>
    </Card>
  );
}

function StatementRow({
  row,
  years,
  selected,
  picked,
  onPick,
}: {
  row: SpreadRow;
  years: string[];
  selected: string;
  picked: string | null;
  onPick: (p: Picked) => void;
}) {
  const unit = useDisplayUnit();
  const strong = row.kind === "derived";
  return (
    <tr data-testid="spread-row" data-row={row.key}>
      <th
        scope="row"
        className={cn(
          "px-4 py-2 text-left text-foreground",
          strong ? "font-semibold" : "font-normal",
        )}
        title={row.formula ?? undefined}
      >
        {row.label}
      </th>
      {row.cells.map((cell, i) => {
        const fy = years[i]!;
        const id = `${row.key}:${fy}`;
        return (
          <td
            key={fy}
            className={cn("px-4 py-1.5 text-right", fy === selected && "bg-info-soft/40")}
          >
            <FigureCell
              picked={{
                id,
                label: row.label,
                fy,
                text: cellText(cell.value, row.unit),
                unit: row.unit === "inr" ? unitHeading(unit) : "",
                evidence: cell.evidence ?? [],
                manual: cell.relies_on_manual,
                working: cell.working ?? null,
              }}
              selected={picked === id}
              tone={cell.relies_on_manual ? "text-destructive" : undefined}
              strong={strong}
              onPick={onPick}
            />
          </td>
        );
      })}
    </tr>
  );
}
