import { Link } from "@tanstack/react-router";
import type { NormInput, NormResult } from "@/api/types";
import { checkRow } from "@/components/case/xv/styles";
import { Chip } from "@/components/common/Panel";
import { Details } from "@/components/common/Details";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { actualText, inputLabel, inputValue, normElementId } from "@/domain/policy";
import { cn } from "@/lib/utils";
import { NormWorking } from "./NormWorking";
import { OUTCOME_ICON, OUTCOME_TEXT } from "./styles";

/** A ratio's band against its configured values (the engine's): green within the norm, amber past
 * it but within the marginal value, red past that. */
const BAND_TONE = { within: "positive", marginal: "flag", outside: "critical" } as const;
const BAND_TEXT = {
  within: "text-positive",
  marginal: "text-flag-foreground",
  outside: "text-destructive",
} as const;

/** The required and actual columns: one width for every row and for the list's column heads, so
 * the values line up down a family. */
export const VALUES = "grid-cols-2 gap-x-4 sm:w-72";

/** Where a figure with no document page comes from. */
function InputBasis({ caseId, input }: { caseId: string; input: NormInput }) {
  const basis = input.basis ?? "document";
  if (basis === "document") return null;
  if (basis === "checklist")
    return (
      <Link
        to="/appraisals/$caseId/completeness"
        params={{ caseId }}
        className="text-primary hover:underline"
        data-testid="norm-input-checklist"
        title={(input.refs ?? []).join(", ")}
      >
        {t("policy.basis.checklist")}
      </Link>
    );
  return (
    <span className="text-muted-foreground" data-testid="norm-input-basis" data-basis={basis}>
      ({t(`policy.basis.${basis}`)})
    </span>
  );
}

/** One norm: the required and the actual value, the figures it used with the pages they were
 * read from, why it could not be evaluated, and how it is calculated. A key figure on the
 * overview, or a norm id in an authority step, scrolls to it and focuses it; the row stays marked
 * (data-target) until the focus leaves. */
export function NormRow({ caseId, norm }: { caseId: string; norm: NormResult }) {
  const viewer = useDocViewer();
  const Icon = OUTCOME_ICON[norm.outcome];
  return (
    <li
      id={normElementId(norm.id)}
      tabIndex={-1}
      className={cn("space-y-1 px-4 py-2", checkRow)}
      data-testid="norm"
      data-norm={norm.id}
      data-outcome={norm.outcome}
    >
      <div className="flex flex-wrap items-start gap-x-2 gap-y-1">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", OUTCOME_TEXT[norm.outcome])} aria-hidden />
        <span className="sr-only">{t(`policy.outcome.${norm.outcome}`)}</span>
        <div className="min-w-0 flex-1 basis-48">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] font-medium text-foreground">
            <span className="min-w-0 break-words">{norm.label}</span>
            {norm.outcome === "deviation" && <Chip tone="critical">{norm.category_label}</Chip>}
            {norm.band && (
              <span data-testid="norm-band" data-band={norm.band}>
                <Chip tone={BAND_TONE[norm.band]}>{t(`policy.band.${norm.band}`)}</Chip>
              </span>
            )}
            {norm.provisional && <Chip tone="muted">{t("policy.provisional")}</Chip>}
          </p>
        </div>
        {/* Beside the label at a fixed width, so required and actual line up under the list's
            column heads however wide the window is; under the label, each with its own label,
            where the row is narrow. */}
        <div
          className={cn(
            "ml-6 grid w-full shrink-0 text-left text-[12px] sm:ml-auto sm:text-right",
            VALUES,
          )}
        >
          <span className="tabular">
            <span className="text-muted-foreground sm:sr-only">{t("policy.required")} </span>
            {norm.required}
            {norm.marginal_text && (
              <span className="block text-[11px] text-muted-foreground" data-testid="norm-marginal">
                {t("policy.marginalAt", { value: norm.marginal_text })}
              </span>
            )}
          </span>
          <span className="tabular">
            <span className="text-muted-foreground sm:sr-only">{t("policy.actual")} </span>
            <span
              className={cn(
                "font-semibold",
                norm.band ? BAND_TEXT[norm.band] : OUTCOME_TEXT[norm.outcome],
              )}
              data-testid="norm-actual"
            >
              {actualText(norm)}
            </span>
          </span>
        </div>
      </div>
      {norm.reason && (
        <p
          className={cn(
            "ml-6 text-[12px]",
            norm.outcome === "deviation" ? "text-destructive" : "text-flag-foreground",
          )}
          data-testid="norm-reason"
          data-reason={norm.reason}
        >
          {t(`policy.reason.${norm.reason}`, {
            inputs: (norm.reason_inputs ?? []).map((name) => inputLabel(norm, name)).join(", "),
          })}
        </p>
      )}
      {(norm.missing ?? []).length > 0 && (
        <p className="ml-6 text-[12px] text-flag-foreground" data-testid="norm-missing">
          {t("policy.missing", {
            inputs: (norm.missing ?? []).map((name) => inputLabel(norm, name)).join(", "),
          })}
        </p>
      )}
      {/* The figures it used and, at the end of the same line, how it was decided. */}
      <div className="ml-6 flex flex-wrap items-center gap-x-4 gap-y-1">
        {norm.outcome !== "not_applicable" && (norm.inputs ?? []).length > 0 && (
          <ul className="contents text-[11.5px]">
            {(norm.inputs ?? []).map((input) => {
              const e = input.evidence?.[0];
              return (
                <li
                  key={input.name}
                  className="inline-flex min-w-0 flex-wrap items-center gap-1"
                  data-testid="norm-input"
                >
                  <span className="text-muted-foreground">{input.label}</span>
                  {e ? (
                    <button
                      type="button"
                      onClick={() =>
                        viewer.open({
                          caseId,
                          documentId: e.document_id,
                          page: e.page,
                          bbox: e.bbox ?? null,
                        })
                      }
                      className="tabular font-medium text-primary underline decoration-dotted underline-offset-2"
                    >
                      {inputValue(input.name, input.value)}
                    </button>
                  ) : (
                    <span className="tabular font-medium">
                      {inputValue(input.name, input.value)}
                    </span>
                  )}
                  <InputBasis caseId={caseId} input={input} />
                  {input.relies_on_manual && <Chip tone="flag">{t("crossCheck.manual")}</Chip>}
                  {input.awaiting_review && (
                    <Chip tone="flag">
                      <span data-testid="norm-input-awaiting">{t("policy.awaitingReview")}</span>
                    </Chip>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <Details testId="norm-details" variant="inline">
          <NormWorking caseId={caseId} norm={norm} />
        </Details>
      </div>
    </li>
  );
}
