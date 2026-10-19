import type {
  CaseFacts,
  CrossVerificationView,
  Finding,
  NormResult,
  PolicyAssessment,
  Spread,
  SpreadRow,
  TurnoverFigure,
  TurnoverYear,
} from "@/api/types";

// The Spread tab (F-22): the statements year by year, turnover from every source side by side,
// and the ratios against the policy. Every figure, outcome and band is the engine's; what is
// worked out here is only arrangement, and the year-on-year changes the trend notes describe.

export type TurnoverSource = TurnoverFigure["source"];

/** The turnover sources in the order the table lists them. */
export const TURNOVER_SOURCES: TurnoverSource[] = ["financials", "gst", "bank", "itr", "declared"];

/** The documents a turnover source is read from, as a cross-check names its sides' sources. */
const SOURCE_DOCUMENTS: Record<TurnoverSource, string[]> = {
  financials: ["audited_financial_statements"],
  gst: ["gstr_3b"],
  bank: ["bank_statement"],
  itr: ["income_tax_return"],
  declared: ["application_message"],
};

/** The financial years with any turnover figure, oldest first. */
export function turnoverYears(facts: CaseFacts): TurnoverYear[] {
  return [...facts.turnover].sort((a, b) => a.fy_end.localeCompare(b.fy_end));
}

/** The sources with a figure in any year, in table order, each with the engine's label. */
export function turnoverSources(
  years: TurnoverYear[],
): { source: TurnoverSource; label: string }[] {
  return TURNOVER_SOURCES.flatMap((source) => {
    const figure = years.flatMap((y) => y.figures).find((f) => f.source === source);
    return figure ? [{ source, label: figure.label }] : [];
  });
}

export function figureFor(year: TurnoverYear, source: TurnoverSource): TurnoverFigure | undefined {
  return year.figures.find((f) => f.source === source);
}

export type FigureVerdict = "agrees" | "differs" | "not_compared" | null;

/** What the turnover cross-checks of a year concluded about one source's figure: it differs where
 * a check failed on its side, agrees where a check passed with it, was not compared where the only
 * checks of it could not run, and nothing where no check of that year read it. */
export function figureVerdict(
  board: CrossVerificationView | undefined,
  fy: string,
  source: TurnoverSource,
): { verdict: FigureVerdict; checks: Finding[] } {
  const docs = SOURCE_DOCUMENTS[source];
  const reads = (f: Finding) =>
    f.sides.find((s) => (s.sources ?? []).some((x) => docs.includes(x)) && s.value !== null);
  const checks = (board?.items ?? [])
    .map((i) => i.finding)
    .filter((f) => f.area === "turnover" && f.scope === fy && reads(f));
  if (checks.some((f) => f.outcome === "fail" && reads(f)?.differs))
    return { verdict: "differs", checks };
  if (checks.some((f) => f.outcome === "pass")) return { verdict: "agrees", checks };
  if (checks.some((f) => f.outcome === "incomplete")) return { verdict: "not_compared", checks };
  return { verdict: null, checks };
}

/** The turnover discrepancies still open on the board, for the banner at the head of the tab. */
export function openTurnoverDiscrepancies(board: CrossVerificationView | undefined) {
  return (board?.items ?? []).filter(
    (i) => i.finding.area === "turnover" && i.finding.outcome === "fail" && !i.adjudicated,
  );
}

export function rowsOf(spread: Spread, section: SpreadRow["section"]): SpreadRow[] {
  return spread.rows.filter((r) => r.section === section);
}

export function rowByKey(spread: Spread, key: string): SpreadRow | undefined {
  return spread.rows.find((r) => r.key === key);
}

/** An amount in crore, as the statement tables write it under their "INR crore" heading. */
export function crore(value: number): string {
  return (value / 1e7).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** A spread figure as its unit reads in a table: amounts in crore, ratios to two places. */
export function cellText(value: number | null | undefined, unit: SpreadRow["unit"]): string {
  if (value === null || value === undefined) return "—";
  if (unit === "inr") return crore(value);
  if (unit === "x") return `${value.toFixed(2)}x`;
  if (unit === "%") return `${value.toFixed(1)}%`;
  return `${Math.round(value)} days`;
}

/** A ratio tile: a norm of the ratios family, or a spread ratio no norm tests. */
export type RatioTile = {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  norm: NormResult | null;
};

/** The ratios the policy assessed, in its order, then the spread's other ratios and margins with
 * their value for the year the policy assessed (the latest column). */
export function ratioTiles(spread: Spread, policy: PolicyAssessment): RatioTile[] {
  const norms = policy.norms.filter((n) => n.family === "ratios");
  const assessed = new Set(norms.map((n) => n.label.toLowerCase()));
  const last = spread.columns.length - 1;
  const extra = spread.rows
    .filter((r) => (r.kind === "ratio" || r.unit === "%") && !assessed.has(r.label.toLowerCase()))
    .map((r) => ({
      key: r.key,
      label: r.label,
      value: r.cells[last]?.value ?? null,
      unit: r.unit,
      norm: null,
    }));
  return [
    ...norms.map((n) => ({
      key: n.id,
      label: n.label,
      value: n.actual ?? null,
      unit: n.unit ?? "",
      norm: n,
    })),
    ...extra,
  ];
}

/** The change from the year before to the latest year, where both are on file. */
export function lastChange(row: SpreadRow | undefined, columns: Spread["columns"]) {
  if (!row || row.cells.length < 2 || columns.length < 2) return null;
  const n = row.cells.length;
  const before = row.cells[n - 2]?.value;
  const after = row.cells[n - 1]?.value;
  if (before === null || before === undefined || after === null || after === undefined) return null;
  return {
    before,
    after,
    delta: after - before,
    pct: before !== 0 ? ((after - before) / Math.abs(before)) * 100 : null,
    from: columns[n - 2]!.fy,
    to: columns[n - 1]!.fy,
  };
}
