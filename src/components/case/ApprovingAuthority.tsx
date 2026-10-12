import { Fragment, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import type { ApprovingAuthority, AuthorityStep } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { Details } from "@/components/common/Details";
import { t } from "@/config/terminology";
import { formatInr, useLabels } from "@/domain/cases";
import { authorityRises, normElementId, openNorm } from "@/domain/policy";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";

// The approving authority the case needs (FRD F-21): the matrix's amount band
// for each product requested, raised by the categories of the policy
// deviations, with the rule that decided it. RBL's recorded approval is never
// shown here; the analyst stays blind to it (it appears only on Comparison).

const NORM_SLOT = "\u0000";

/** The band an amount fell in, in words. */
export function bandText(step: AuthorityStep): string {
  const from = step.band_from_inr ?? null;
  const to = step.band_to_inr ?? null;
  if (from === null && to !== null) return t("approvingAuthority.band.upTo", { to: formatInr(to) });
  if (from !== null && to !== null)
    return t("approvingAuthority.band.between", { from: formatInr(from), to: formatInr(to) });
  return t("approvingAuthority.band.above", { from: formatInr(from ?? 0) });
}

/** How a deviation rule raised the authority, in words. */
export function effectText(step: AuthorityStep): string {
  const n = step.levels_above ?? 0;
  const effect = step.at_least
    ? n > 0
      ? t("approvingAuthority.effect.levelsAtLeast", { n, authority: step.at_least.label })
      : t("approvingAuthority.effect.atLeast", { authority: step.at_least.label })
    : t("approvingAuthority.effect.levels", { n });
  return step.capped ? `${effect}, ${t("approvingAuthority.capped")}` : effect;
}

/** A step as one sentence, norm ids in plain text (the Comparison tab). */
export function stepSentence(step: AuthorityStep, amount: number): string {
  if (step.kind === "amount") {
    return t("approvingAuthority.step.amount", {
      product: step.product_label ?? step.product ?? "",
      amount: formatInr(amount),
      band: bandText(step),
      authority: step.authority.label,
    });
  }
  return t("approvingAuthority.step.deviation", {
    category: step.category_label ?? step.category ?? "",
    norms: (step.norms ?? []).join(", "),
    effect: effectText(step),
    authority: step.authority.label,
  });
}

function NormLinks({ ids }: { ids: string[] }) {
  return (
    <>
      {ids.map((id, i) => (
        <Fragment key={id}>
          {i > 0 && ", "}
          <button
            type="button"
            onClick={() => openNorm(id)}
            aria-controls={normElementId(id)}
            className="font-medium text-primary underline decoration-dotted underline-offset-2"
            data-testid="authority-norm"
          >
            {id}
          </button>
        </Fragment>
      ))}
    </>
  );
}

function StepText({ step, amount }: { step: AuthorityStep; amount: number }): ReactNode {
  if (step.kind === "amount") return stepSentence(step, amount);
  const [before, after] = t("approvingAuthority.step.deviation", {
    category: step.category_label ?? step.category ?? "",
    norms: NORM_SLOT,
    effect: effectText(step),
    authority: step.authority.label,
  }).split(NORM_SLOT);
  return (
    <>
      {before}
      <NormLinks ids={step.norms ?? []} />
      {after}
    </>
  );
}

/** The authority the case needs, the amount it rests on, what the norms not yet assessed could
 * do, and every step of the matrix that applied, the one that decides marked. Its norm ids lead
 * to their rows. */
export function AuthorityView({
  caseId,
  authority,
}: {
  caseId: string;
  authority: ApprovingAuthority;
}) {
  const labels = useLabels();
  const canCompare = useCan("comparison.adjudicate");
  const required = authority.required;
  const unevaluated = authority.unevaluated ?? [];
  const rises = authorityRises(authority);
  return (
    <div
      className="min-w-0 space-y-2 rounded border border-border bg-surface px-4 py-3"
      data-testid="approving-authority"
    >
      {authority.outcome === "cannot_determine" || !required ? (
        <p className="text-[13px] text-flag-foreground" data-testid="authority-cannot-determine">
          {t("approvingAuthority.cannotDetermine.no_product", {
            facilities: labels.facilities(authority.unmapped_facilities ?? []),
          })}
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p
              className="flex min-w-0 flex-wrap items-center gap-2"
              data-testid="authority-required"
            >
              <span className="min-w-0 break-words text-[14px] font-semibold text-foreground">
                {t("approvingAuthority.required", { authority: required.label })}
              </span>
              <Chip tone="info">{t("approvingAuthority.level", { n: required.level })}</Chip>
            </p>
            {authority.provisional && (
              <Chip tone="muted">
                <span data-testid="authority-provisional">
                  {t("approvingAuthority.provisional")}
                </span>
              </Chip>
            )}
          </div>
          <p className="break-words text-[12px] text-muted-foreground">
            {t("approvingAuthority.basis", {
              amount: formatInr(authority.amount_inr),
              products: authority.product_labels.join(", "),
            })}
          </p>
          {unevaluated.length > 0 && authority.could_rise_to && (
            <p
              className="break-words rounded border border-flag/35 bg-flag-soft px-3 py-2 text-[12px] text-flag-foreground"
              data-testid="authority-lower-bound"
              data-rises={rises ? "true" : "false"}
            >
              {rises
                ? t("approvingAuthority.lowerBound", {
                    n: unevaluated.length,
                    norms: (authority.unevaluated_labels ?? unevaluated).join(", "),
                    authority: authority.could_rise_to.label,
                  })
                : t("approvingAuthority.lowerBoundSame", {
                    n: unevaluated.length,
                    norms: (authority.unevaluated_labels ?? unevaluated).join(", "),
                  })}
            </p>
          )}
          <Details title={t("approvingAuthority.how")} testId="authority-how" open>
            <ol className="list-decimal space-y-1.5 break-words pl-5 text-[12.5px]">
              {authority.steps.map((step) => (
                <li
                  key={step.rule}
                  data-testid="authority-step"
                  data-rule={step.rule}
                  data-kind={step.kind}
                  data-governs={step.governs ? "true" : "false"}
                  className={cn(step.governs && "font-medium text-foreground")}
                >
                  <StepText step={step} amount={authority.amount_inr} />{" "}
                  {step.governs && <Chip tone="primary">{t("approvingAuthority.governs")}</Chip>}
                </li>
              ))}
            </ol>
          </Details>
        </>
      )}
      {authority.provisional && (
        <p className="text-[11.5px] text-muted-foreground">
          {t("approvingAuthority.awaitingMatrix")}
        </p>
      )}
      {canCompare && (
        <Link
          to="/appraisals/$caseId/comparison"
          params={{ caseId }}
          className="inline-block text-[12px] font-medium text-primary hover:underline"
          data-testid="authority-compare"
        >
          {t("approvingAuthority.compare")}
        </Link>
      )}
    </div>
  );
}
