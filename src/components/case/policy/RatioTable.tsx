import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { useState } from "react";
import type { CellWorking, NormResult, Spread, SpreadRow } from "@/api/types";
import { EditFigureDialog } from "@/components/case/spread/EditFigureDialog";
import { t } from "@/config/terminology";
import { actualText, inputLabel, normElementId } from "@/domain/policy";
import { useSpread } from "@/domain/findings";
import { cellText } from "@/domain/spread";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { NormDetail, BAND_TEXT, split, statusOf } from "./NormTile";
import { OUTCOME_TEXT } from "./styles";

type Band = "within" | "marginal" | "outside";

/** The band a value falls in against the norm's own limits (the engine's numbers), for the years the
 * engine did not assess itself: the same test it applies to the latest. */
function bandOf(norm: NormResult, value: number): Band | null {
  const { threshold, marginal } = norm;
  if (threshold === null || threshold === undefined || marginal === null || marginal === undefined)
    return null;
  if (norm.comparator === "max") {
    return value <= threshold ? "within" : value <= marginal ? "marginal" : "outside";
  }
  return value >= threshold ? "within" : value >= marginal ? "marginal" : "outside";
}

const ZONE = {
  within: "bg-positive/40",
  marginal: "bg-flag/50",
  outside: "bg-destructive/35",
} as const;

/** The three zones laid out on one scale, the latest value a dot among them: the limits are the engine's
 * numbers, and the scale only has to hold them and the value. */
function RangeBar({
  norm,
  value,
  band,
}: {
  norm: NormResult;
  value: number | null;
  band: Band | null;
}) {
  const { threshold, marginal } = norm;
  const caption = (
    <p className="mt-0.5 text-[10.5px] leading-tight text-muted-foreground">
      {t("policy.ratios.limits", { required: norm.required, marginal: norm.marginal_text ?? "" })}
    </p>
  );
  // The limits as numbers place the scale; without them only the requirement is written.
  if (threshold === null || threshold === undefined || marginal === null || marginal === undefined)
    return <div className="min-w-[8rem]">{caption}</div>;
  const max = norm.comparator === "max";
  const hi = Math.max(threshold, marginal, value ?? 0) * (max ? 1.25 : 1.3);
  const pos = (v: number) => `${Math.min(100, Math.max(0, (v / hi) * 100))}%`;
  // Zones from the low end of the scale to the high end.
  const zones: { from: number; to: number; band: Band }[] = max
    ? [
        { from: 0, to: threshold, band: "within" },
        { from: threshold, to: marginal, band: "marginal" },
        { from: marginal, to: hi, band: "outside" },
      ]
    : [
        { from: 0, to: marginal, band: "outside" },
        { from: marginal, to: threshold, band: "marginal" },
        { from: threshold, to: hi, band: "within" },
      ];
  return (
    <div
      className="min-w-[8rem]"
      role="img"
      aria-label={
        value === null
          ? t("policy.ratios.limits", {
              acceptable: norm.threshold_text ?? "",
              marginal: norm.marginal_text ?? "",
            })
          : t("policy.ratios.scaleLabel", { value: actualText(norm) })
      }
      data-testid="ratio-scale"
    >
      <div className="relative h-2 overflow-hidden rounded-full">
        {zones.map((z) => (
          <span
            key={z.band}
            className={cn("absolute inset-y-0", ZONE[z.band])}
            style={{ left: pos(z.from), width: `calc(${pos(z.to)} - ${pos(z.from)})` }}
          />
        ))}
      </div>
      {value !== null && (
        <div className="relative h-2.5">
          <span
            className={cn(
              "absolute -top-[13px] h-3 w-3 -translate-x-1/2 rounded-full border-2 border-surface shadow-sm",
              band === "within"
                ? "bg-positive"
                : band === "marginal"
                  ? "bg-flag"
                  : "bg-destructive",
            )}
            style={{ left: pos(value) }}
          />
        </div>
      )}
      {caption}
    </div>
  );
}

/** How the latest year moved on the year before, in the direction that is better for this ratio. */
function Trend({
  norm,
  row,
  spread,
}: {
  norm: NormResult;
  row: SpreadRow | undefined;
  spread: Spread;
}) {
  if (!row) return null;
  const n = row.cells.length;
  const after = row.cells[n - 1]?.value;
  const before = row.cells[n - 2]?.value;
  if (n < 2 || after === null || after === undefined || before === null || before === undefined)
    return null;
  const delta = after - before;
  const fy = spread.columns[n - 2]?.fy ?? "";
  const flat = Math.abs(delta) < (row.unit === "days" ? 0.5 : 0.005);
  const better = norm.comparator === "max" ? delta < 0 : delta > 0;
  const Icon = flat ? Minus : delta > 0 ? ArrowUpRight : ArrowDownRight;
  const size = cellText(Math.abs(delta), row.unit).replace(/^—$/, "");
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-[11px] font-medium",
        flat ? "text-muted-foreground" : better ? "text-positive" : "text-destructive",
      )}
      title={t(
        flat
          ? "policy.ratios.trendFlat"
          : delta > 0
            ? "policy.ratios.trendUp"
            : "policy.ratios.trendDown",
        {
          delta: size,
          fy,
        },
      )}
      data-testid="ratio-trend"
      data-direction={flat ? "flat" : better ? "better" : "worse"}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {flat ? t("policy.ratios.flat") : t(better ? "policy.ratios.better" : "policy.ratios.worse")}
      {!flat && <span className="font-normal opacity-80">{`${delta > 0 ? "+" : "−"}${size}`}</span>}
    </span>
  );
}

type Entering = { label: string; fy: string; working: CellWorking };

/** An input the statements do not give, where it can be entered from the page: the spread's own row for it. */
function entryFor(norm: NormResult, spread: Spread | undefined): Entering[] {
  if (!spread) return [];
  const last = spread.columns.length - 1;
  // The norm names what is missing by its label, which is the spread row's own label.
  return (norm.missing ?? []).flatMap((name) => {
    const row = spread.rows.find((r) => r.label === name || r.key === name);
    const working = row?.cells[last]?.working;
    return row && working?.target
      ? [{ label: row.label, fy: spread.columns[last]!.fy, working }]
      : [];
  });
}

/** The financial ratios as one table: what each ratio tells in plain words, every year side by side with
 * the direction of travel, the latest set against the limits on a scale, and its working opening under
 * its own row. A ratio that cannot be evaluated says what is missing and, where the page has it, lets the
 * figure be entered there. */
export function RatioTable({
  caseId,
  norms,
  selected,
  onSelect,
  detailId,
}: {
  caseId: string;
  norms: NormResult[];
  selected: string | null;
  onSelect: (id: string, force?: boolean) => void;
  detailId: string;
}) {
  const spread = useSpread(caseId).data;
  const canEdit = useCan("review.decide");
  const [entering, setEntering] = useState<Entering | null>(null);
  const years = spread?.columns ?? [];
  const rowFor = (norm: NormResult) =>
    norm.ratio
      ? spread?.rows.find((r) => r.section === "ratios" && r.key === norm.ratio)
      : undefined;
  return (
    <div
      className="overflow-hidden rounded border border-border bg-surface"
      data-testid="ratio-table"
    >
      <div
        className="hidden items-end gap-x-4 border-b border-border bg-surface-muted/60 px-4 py-2 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground lg:grid"
        style={{ gridTemplateColumns: gridColumns(years.length) }}
        aria-hidden
      >
        <span>{t("policy.ratios.ratio")}</span>
        {years.map((y, i) => (
          <span
            key={y.key}
            className={cn("text-right", i === years.length - 1 && "text-foreground")}
          >
            {y.fy.replace("FY ", "FY")}
          </span>
        ))}
        <span>{t("policy.ratios.policy")}</span>
        <span className="text-right">{t("policy.ratios.latest")}</span>
      </div>
      <ul data-testid="policy-norms" className="divide-y divide-border">
        {norms.map((norm) => {
          const row = rowFor(norm);
          const status = statusOf(norm);
          const evaluated = norm.outcome === "pass" || norm.outcome === "deviation";
          const [figure, unit] = evaluated ? split(actualText(norm)) : ["—", ""];
          const tone = !evaluated
            ? "text-muted-foreground"
            : norm.band
              ? BAND_TEXT[norm.band]
              : OUTCOME_TEXT[norm.outcome];
          const open = selected === norm.id;
          const reason = norm.reason
            ? t(`policy.reason.${norm.reason}`, {
                inputs: (norm.reason_inputs ?? []).map((n) => inputLabel(norm, n)).join(", "),
              })
            : null;
          const missing =
            (norm.missing ?? []).length > 0
              ? t("policy.missing", {
                  inputs: (norm.missing ?? []).map((n) => inputLabel(norm, n)).join(", "),
                })
              : null;
          const enter = entryFor(norm, spread);
          const meaning = norm.ratio ? `policy.ratios.meaning.${norm.ratio}` : null;
          return (
            <li
              key={norm.id}
              id={normElementId(norm.id)}
              tabIndex={-1}
              onFocus={(e) => {
                if (e.target === e.currentTarget) onSelect(norm.id, true);
              }}
              className={cn("min-w-0", open ? "bg-info-soft/60" : "bg-surface")}
              data-testid="norm"
              data-norm={norm.id}
              data-outcome={norm.outcome}
              data-selected={open ? "true" : "false"}
            >
              <button
                type="button"
                onClick={() => onSelect(norm.id)}
                aria-expanded={open}
                aria-controls={detailId}
                className="block w-full px-4 py-3 text-left transition-colors hover:bg-foreground/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                data-testid="norm-select"
              >
                <span
                  className="grid items-center gap-x-4 gap-y-2 lg:[grid-template-columns:var(--cols)]"
                  style={{ ["--cols" as string]: gridColumns(years.length) }}
                >
                  <span className="min-w-0">
                    <span className="block text-[13.5px] font-semibold text-foreground">
                      {norm.label}
                      {norm.provisional && (
                        <span className="ml-2 text-[10.5px] font-normal text-muted-foreground/80">
                          {t("policy.provisional")}
                        </span>
                      )}
                    </span>
                    {meaning && (
                      <span className="mt-0.5 block text-[12px] leading-snug text-muted-foreground">
                        {t(meaning)}
                      </span>
                    )}
                  </span>
                  {/* Each year, in the band it falls in; the latest set apart. */}
                  {years.map((y, i) => {
                    const v = row?.cells[i]?.value ?? null;
                    const band = v !== null ? bandOf(norm, v) : null;
                    const latest = i === years.length - 1;
                    return (
                      <span
                        key={y.key}
                        className={cn(
                          "tabular text-[13px] lg:text-right",
                          latest ? "font-semibold" : "font-normal",
                          v === null
                            ? "text-muted-foreground"
                            : band
                              ? BAND_TEXT[band]
                              : "text-foreground",
                        )}
                        data-testid="ratio-year"
                        data-fy={y.fy}
                      >
                        <span className="text-[10.5px] text-muted-foreground lg:hidden">
                          {y.fy}{" "}
                        </span>
                        {row ? cellText(v, row.unit) : "—"}
                      </span>
                    );
                  })}
                  <span className="min-w-0">
                    <RangeBar
                      norm={norm}
                      value={
                        evaluated && norm.actual !== null && norm.actual !== undefined
                          ? norm.actual
                          : null
                      }
                      band={norm.band ?? null}
                    />
                  </span>
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-1 lg:flex-col lg:items-end lg:gap-y-1">
                    <span
                      className={cn("tabular font-semibold leading-none", tone)}
                      data-testid="norm-actual"
                    >
                      <span className="text-[22px]">{figure}</span>
                      <span className="text-[12px]">{unit}</span>
                    </span>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11.5px] font-medium",
                        status.tone,
                      )}
                      data-testid={norm.band ? "norm-band" : "norm-status"}
                      data-band={norm.band ?? undefined}
                      data-status={status.key}
                    >
                      <span className={cn("h-1.5 w-1.5 rounded-full", status.dot)} aria-hidden />
                      {status.label}
                    </span>
                    <Trend norm={norm} row={row} spread={spread!} />
                  </span>
                </span>
                <span className="sr-only">{t(`policy.outcome.${norm.outcome}`)}</span>
                {norm.marginal_text && (
                  <span className="sr-only" data-testid="norm-marginal">
                    {t("policy.marginalAt", { value: norm.marginal_text })}
                  </span>
                )}
                {(reason || missing) && (
                  <span
                    className={cn(
                      "mt-2 block text-[12px] leading-snug",
                      norm.outcome === "deviation" ? "text-destructive" : "text-flag-foreground",
                    )}
                    data-testid={reason ? "norm-reason" : "norm-missing"}
                    data-reason={norm.reason ?? undefined}
                  >
                    {reason ?? missing}
                  </span>
                )}
              </button>
              {!evaluated && (missing || reason) && (
                <div
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 pb-3 pt-0 text-[12px]"
                  data-testid="ratio-actions"
                >
                  {canEdit &&
                    enter.map((e) => (
                      <button
                        key={e.label}
                        type="button"
                        onClick={() => setEntering(e)}
                        title={t("policy.ratios.enterHint")}
                        className="rounded border border-primary/40 px-2 py-1 font-medium text-primary hover:bg-primary/5"
                        data-testid="ratio-enter"
                      >
                        {t("policy.ratios.enter", { label: e.label })}
                      </button>
                    ))}
                  {enter.length === 0 && (
                    <span className="text-muted-foreground">{t("policy.ratios.needsData")}</span>
                  )}
                </div>
              )}
              {open && (
                <NormDetail
                  caseId={caseId}
                  norm={norm}
                  id={detailId}
                  onClose={() => onSelect(norm.id)}
                />
              )}
            </li>
          );
        })}
      </ul>
      {entering?.working.target && (
        <EditFigureDialog
          caseId={caseId}
          label={entering.label}
          fy={entering.fy}
          target={entering.working.target}
          source={entering.working.source}
          current={null}
          onClose={() => setEntering(null)}
        />
      )}
    </div>
  );
}

/** Name, a column per year, the scale, the latest: the same widths in the head and in every row. */
function gridColumns(years: number): string {
  return `minmax(0,1.7fr) repeat(${Math.max(years, 1)}, minmax(4.25rem,0.55fr)) minmax(9.5rem,1.1fr) minmax(7.5rem,0.8fr)`;
}
