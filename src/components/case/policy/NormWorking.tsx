import type { NormComponent, NormInput, NormResult } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { actualText, comparison, inputLabel, inputValue, substituted } from "@/domain/policy";
import { cn } from "@/lib/utils";
import { OUTCOME_ICON, OUTCOME_TEXT } from "./styles";

/** A figure, as a link to the page it was read from where there is one. */
function Figure({
  caseId,
  label,
  value,
  evidence,
  className,
}: {
  caseId: string;
  label: string;
  value: string;
  evidence?: NormInput["evidence"];
  className?: string;
}) {
  const viewer = useDocViewer();
  const e = evidence?.[0];
  if (!e) return <span className={cn("tabular", className)}>{value}</span>;
  return (
    <button
      type="button"
      onClick={() =>
        viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null })
      }
      title={`${label} · ${t("policy.working.fromPage", { page: e.page })}`}
      className={cn(
        "tabular text-primary underline decoration-dotted underline-offset-2",
        className,
      )}
    >
      {value}
    </button>
  );
}

/** Where a figure came from, in a few words. */
function originText(input: NormInput): string {
  const basis = input.basis ?? "document";
  if (basis === "case") return t("policy.working.fromCase");
  if (basis === "checklist") return t("policy.working.fromChecklist");
  const page = input.evidence?.[0]?.page;
  return page ? t("policy.working.fromPage", { page }) : t(`policy.basis.${basis}`);
}

/** A small caption above a block of the working. */
function Caption({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </p>
  );
}

/** One row of the figures table: a label, its value right-aligned, and where it came from. */
function Row({
  indent = false,
  sign,
  label,
  value,
  origin,
  strong = false,
}: {
  indent?: boolean;
  sign?: string;
  label: React.ReactNode;
  value: React.ReactNode;
  origin?: string;
  strong?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-[1fr_auto_4.5rem] items-baseline gap-x-3 py-[3px]",
        indent && "pl-5",
      )}
    >
      <span
        className={cn(
          "min-w-0 truncate text-[12px]",
          strong ? "font-medium text-foreground" : "text-muted-foreground",
        )}
      >
        {sign && <span className="inline-block w-3 text-muted-foreground">{sign}</span>}
        {label}
      </span>
      <span className={cn("text-[12px] tabular", strong && "font-medium")}>{value}</span>
      <span className="text-[11px] text-muted-foreground">{origin}</span>
    </div>
  );
}

/** One input, with the lines it was summed from where it is derived. */
function FigureBlock({ caseId, input }: { caseId: string; input: NormInput }) {
  const components = (input.components ?? []) as NormComponent[];
  const value = (
    <Figure
      caseId={caseId}
      label={input.label}
      value={inputValue(input.name, input.value)}
      evidence={input.evidence}
    />
  );
  if (components.length === 0)
    return <Row label={input.label} value={value} origin={originText(input)} strong />;
  return (
    <div className="rounded border border-border/70 bg-surface-muted/40 px-2.5 py-1.5">
      <Row label={input.label} value={value} origin={originText(input)} strong />
      <div className="mt-0.5 border-t border-border/70 pt-0.5">
        {components.map((c, i) => (
          <Row
            key={`${c.label}-${i}`}
            indent
            sign={i === 0 ? "" : c.sign < 0 ? "−" : "+"}
            label={c.label}
            value={
              <Figure
                caseId={caseId}
                label={c.label}
                value={inputValue(input.name, c.value)}
                evidence={c.evidence}
              />
            }
            origin={
              c.evidence?.[0] ? t("policy.working.fromPage", { page: c.evidence[0].page }) : ""
            }
          />
        ))}
      </div>
    </div>
  );
}

/** How a norm reached its number (F-20.2), laid out as the working: the expression, the same
 * expression with the figures that were read, each figure with where it came from — a derived
 * figure opening into the lines it was summed from — and the test against the norm.
 *
 * Every figure links to the page it was read from. Nothing here changes an outcome; the norm
 * decided it, and this only shows how. */
export function NormWorking({ caseId, norm }: { caseId: string; norm: NormResult }) {
  const inputs = norm.inputs ?? [];
  const missing = norm.missing ?? [];
  const evaluated = norm.outcome === "pass" || norm.outcome === "deviation";
  const Icon = OUTCOME_ICON[norm.outcome];

  return (
    <div className="space-y-3" data-testid="norm-working">
      <div className="space-y-1">
        <Caption>{t("policy.working.expression")}</Caption>
        <p className="text-[12.5px] text-foreground">{norm.formula}</p>
      </div>

      {evaluated && inputs.length > 0 && (
        <div className="space-y-1" data-testid="norm-substituted">
          <Caption>{t("policy.working.calculation")}</Caption>
          {/* The formula with each name replaced by the figure that was read, so the line reads
              as the sum that was done: (1.63 cr + 48.32 lakh) ÷ (15.00 lakh + 30.00 cr) = 0.07x */}
          <p className="flex flex-wrap items-baseline gap-x-1 gap-y-1 text-[13px] leading-relaxed">
            {substituted(norm).map((piece, i) =>
              typeof piece === "string" ? (
                <span key={`t${i}`} className="whitespace-pre text-muted-foreground">
                  {piece}
                </span>
              ) : (
                <Figure
                  key={`${piece.name}-${i}`}
                  caseId={caseId}
                  label={piece.label}
                  value={inputValue(piece.name, piece.value)}
                  evidence={piece.evidence}
                  className="font-medium"
                />
              ),
            )}
            <span className="px-1 text-muted-foreground">=</span>
            <span className={cn("tabular text-[15px] font-semibold", OUTCOME_TEXT[norm.outcome])}>
              {actualText(norm)}
            </span>
          </p>
        </div>
      )}

      {inputs.length > 0 && (
        <div className="space-y-1">
          <Caption>{t("policy.working.figures")}</Caption>
          <div className="space-y-1.5">
            {inputs.map((input) => (
              <FigureBlock key={input.name} caseId={caseId} input={input} />
            ))}
          </div>
        </div>
      )}

      {missing.length > 0 && (
        <div className="space-y-1" data-testid="norm-working-missing">
          <Caption>{t("policy.working.missingTitle")}</Caption>
          <ul className="space-y-0.5 text-[12px] text-muted-foreground">
            {missing.map((name) => (
              <li key={name}>
                {inputLabel(norm, name)} — {t("policy.working.notOnFile")}
              </li>
            ))}
          </ul>
        </div>
      )}

      {evaluated && (
        <div
          className={cn(
            "flex items-center gap-2 rounded border-l-2 bg-surface-muted/50 px-2.5 py-1.5 text-[12.5px]",
            norm.outcome === "pass" ? "border-l-positive" : "border-l-destructive",
          )}
          data-testid="norm-test"
        >
          <Icon className={cn("h-3.5 w-3.5 shrink-0", OUTCOME_TEXT[norm.outcome])} aria-hidden />
          <span className="tabular text-[13px] font-medium text-foreground">
            {comparison(norm) ?? actualText(norm)}
          </span>
          <span className={cn("text-[12.5px] font-medium", OUTCOME_TEXT[norm.outcome])}>
            {t(
              norm.outcome === "pass" ? "policy.working.satisfied" : "policy.working.notSatisfied",
            )}
          </span>
        </div>
      )}

      {(norm.definition && norm.definition !== norm.formula) || norm.note ? (
        <div className="space-y-0.5 text-[11.5px] text-muted-foreground">
          {norm.definition && norm.definition !== norm.formula && (
            <p data-testid="norm-definition">
              <span className="font-medium text-foreground">{t("policy.definition")}: </span>
              {norm.definition}
            </p>
          )}
          {norm.note && (
            <p data-testid="norm-note">
              <span className="font-medium text-foreground">{t("policy.note")}: </span>
              {norm.note}
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
