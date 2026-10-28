import { Eye, Info } from "lucide-react";
import { useState } from "react";
import type { CellWorking, NormComponent, NormInput, NormResult } from "@/api/types";
import { FigureWorking } from "@/components/case/spread/FigureWorking";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/config/terminology";
import { actualText, comparison, inputLabel, inputValue, substituted } from "@/domain/policy";
import { useDisplayUnit } from "@/domain/units";
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

/** The explicit way to look at where a figure came from: opens the viewer at its page, with
 * the region marked. Shown wherever there is a page to open, so the reader does not have to
 * discover that the number itself is a link. */
function EvidenceEye({
  caseId,
  label,
  evidence,
}: {
  caseId: string;
  label: string;
  evidence?: NormInput["evidence"];
}) {
  const viewer = useDocViewer();
  const e = evidence?.[0];
  if (!e) return <span className="inline-block w-4" aria-hidden />;
  return (
    <button
      type="button"
      onClick={() =>
        viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null })
      }
      title={t("policy.working.viewEvidence", { label })}
      aria-label={t("policy.working.viewEvidence", { label })}
      data-testid="norm-figure-eye"
      className="text-muted-foreground transition-colors hover:text-primary"
    >
      <Eye className="h-3.5 w-3.5" aria-hidden />
    </button>
  );
}

/** How a statement figure was read, and the way to edit it: opens the figure's working in a dialog,
 * so a ratio can be followed down to the printed figure and corrected there. */
function WorkingDetail({
  caseId,
  label,
  working,
}: {
  caseId: string;
  label: string;
  working: CellWorking | null | undefined;
}) {
  const [open, setOpen] = useState(false);
  if (!working) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title={t("spreadPage.working.detail")}
        aria-label={`${t("spreadPage.working.detail")}: ${label}`}
        data-testid="norm-figure-working"
        className="text-muted-foreground transition-colors hover:text-primary"
      >
        <Info className="h-3.5 w-3.5" aria-hidden />
      </button>
      {open && (
        <Dialog open onOpenChange={(o) => !o && setOpen(false)}>
          <DialogContent className="max-w-md" data-testid="norm-working-dialog">
            <DialogHeader>
              <DialogTitle>{label}</DialogTitle>
              <DialogDescription>{t("spreadPage.working.title")}</DialogDescription>
            </DialogHeader>
            <FigureWorking caseId={caseId} label={label} fy="" working={working} />
          </DialogContent>
        </Dialog>
      )}
    </>
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
  eye,
  strong = false,
}: {
  indent?: boolean;
  sign?: string;
  label: React.ReactNode;
  value: React.ReactNode;
  origin?: string;
  eye?: React.ReactNode;
  strong?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_auto_3.75rem_1rem] items-baseline gap-x-2.5 py-[3px]",
        indent && "pl-4",
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
      <span className="justify-self-end self-center leading-none">{eye}</span>
    </div>
  );
}

/** One input of the figures table: the figure itself, then the lines it was summed from where
 * it is derived. Several inputs share one box, divided rather than boxed separately. */
function FigureBlock({
  caseId,
  input,
  first,
}: {
  caseId: string;
  input: NormInput;
  first: boolean;
}) {
  const components = (input.components ?? []) as NormComponent[];
  return (
    <div className={cn(!first && "mt-1 border-t border-border/70 pt-1")}>
      <Row
        label={input.label}
        value={
          <Figure
            caseId={caseId}
            label={input.label}
            value={inputValue(input, input.value)}
            evidence={input.evidence}
          />
        }
        origin={originText(input)}
        eye={
          <span className="inline-flex items-center gap-1.5">
            <WorkingDetail caseId={caseId} label={input.label} working={input.working} />
            <EvidenceEye caseId={caseId} label={input.label} evidence={input.evidence} />
          </span>
        }
        strong
      />
      {components.map((c, i) => (
        <Row
          key={`${c.label}-${i}`}
          indent
          sign={i === 0 ? "" : c.sign < 0 ? "\u2212" : "+"}
          label={c.label}
          value={
            <Figure
              caseId={caseId}
              label={c.label}
              value={inputValue(input, c.value)}
              evidence={c.evidence}
            />
          }
          origin={c.evidence?.[0] ? t("policy.working.fromPage", { page: c.evidence[0].page }) : ""}
          eye={
            <span className="inline-flex items-center gap-1.5">
              <WorkingDetail caseId={caseId} label={c.label} working={c.working} />
              <EvidenceEye caseId={caseId} label={c.label} evidence={c.evidence} />
            </span>
          }
        />
      ))}
    </div>
  );
}

/** How a norm reached its number (F-20.2).

 * Three blocks at most, and only the ones that say something new:
 *   1. the calculation — the expression, then the same expression with the figures read and the
 *      test against the norm on the same line, so the whole result is one glance;
 *   2. the figures — only where there is more than one, or one is derived and opens into the
 *      lines it was summed from; a single printed figure is already on the calculation line;
 *   3. what is missing, for a norm that could not be evaluated.
 *
 * Every figure links to its page and carries an eye to open it. Nothing here changes an
 * outcome; the norm decided it, and this only shows how. */
export function NormWorking({ caseId, norm }: { caseId: string; norm: NormResult }) {
  useDisplayUnit();
  const inputs = norm.inputs ?? [];
  const missing = norm.missing ?? [];
  const evaluated = norm.outcome === "pass" || norm.outcome === "deviation";
  const Icon = OUTCOME_ICON[norm.outcome];
  const derived = inputs.some((i) => (i.components ?? []).length > 0);
  // One printed figure needs no table under the line that already shows it.
  const showFigures = inputs.length > 1 || derived;
  const single = inputs.length === 1 && !derived;

  return (
    <div className="max-w-3xl space-y-2.5" data-testid="norm-working">
      {inputs.length > 0 && (
        <div data-testid="norm-substituted">
          <p className="text-[11.5px] text-muted-foreground">{norm.formula}</p>
          <p className="mt-1 flex flex-wrap items-baseline gap-x-1.5 gap-y-1 text-[13px]">
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
                  value={inputValue(piece, piece.value)}
                  evidence={piece.evidence}
                  className="font-medium"
                />
              ),
            )}
            {evaluated && (
              <>
                <span className="text-muted-foreground">=</span>
                <span
                  className={cn("tabular text-[15px] font-semibold", OUTCOME_TEXT[norm.outcome])}
                >
                  {actualText(norm)}
                </span>
                <span
                  className="ml-1 inline-flex items-baseline gap-1 text-[11.5px]"
                  data-testid="norm-test"
                >
                  <Icon
                    className={cn("h-3 w-3 self-center", OUTCOME_TEXT[norm.outcome])}
                    aria-hidden
                  />
                  <span className="tabular text-muted-foreground">{comparison(norm)}</span>
                  <span className={cn("font-medium", OUTCOME_TEXT[norm.outcome])}>
                    {t(
                      norm.outcome === "pass"
                        ? "policy.working.satisfied"
                        : "policy.working.notSatisfied",
                    )}
                  </span>
                </span>
              </>
            )}
          </p>
          {single && inputs[0] && (
            <p className="mt-0.5 inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              {t("policy.working.readFrom")} {originText(inputs[0])}
              <EvidenceEye caseId={caseId} label={inputs[0].label} evidence={inputs[0].evidence} />
            </p>
          )}
        </div>
      )}

      {showFigures && (
        <div className="rounded border border-border/70 bg-surface-muted/40 px-2.5 py-1.5">
          {inputs.map((input, i) => (
            <FigureBlock key={input.name} caseId={caseId} input={input} first={i === 0} />
          ))}
        </div>
      )}

      {missing.length > 0 && (
        <div data-testid="norm-working-missing">
          <Caption>{t("policy.working.missingTitle")}</Caption>
          <ul className="mt-0.5 space-y-0.5 text-[12px] text-muted-foreground">
            {missing.map((name) => (
              <li key={name}>
                {inputLabel(norm, name)} — {t("policy.working.notOnFile")}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(norm.definition && norm.definition !== norm.formula) || norm.note ? (
        <div className="space-y-0.5 text-[11px] text-muted-foreground">
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
